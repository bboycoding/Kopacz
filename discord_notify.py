"""Wysyłka na Discorda przez webhook: jeden wspólny wątek, kolejka, paczkowanie i alerty zbiorcze.

Limit Discorda to ok. 30 wiadomości na minutę na webhook. Linie logu z wielu kont trafiają do jednej
paczki (co `batch_seconds` albo po przekroczeniu `max_chars`), a alerty o tym samym problemie na kilku
kontach naraz łączą się w jedną wiadomość. Awaria Discorda nigdy nie zatrzymuje reszty programu.
"""
import json
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

USER_AGENT = "MojKopacz/2.0 (+https://github.com/bboycoding/Kopacz)"
WEBHOOK_RE = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+/?$")
MIN_SEND_GAP = 2.0          # s; 30 wiadomości na minutę = 1 na 2 s
FINAL_FLUSH_S = 3.0         # tyle czasu na wysłanie reszty przy zamykaniu programu
MAX_RETRIES = 4


def valid_webhook(url: str) -> bool:
    return bool(WEBHOOK_RE.match(url.strip()))


@dataclass
class Stats:
    sent: int = 0
    errors: int = 0
    dropped: int = 0
    last_error: str = ""


@dataclass
class _PendingAlert:
    summary: str
    ping: bool
    first_at: float
    accounts: dict[str, str] = field(default_factory=dict)   # etykieta konta -> tekst


class DiscordNotifier(threading.Thread):
    def __init__(self, webhook: str, ping_id: str = "", batch_seconds: float = 5.0, max_chars: int = 1800,
                 group_window_s: float = 20.0, status_every_min: float = 0.0, status_provider=None,
                 mask=None, total_accounts: int = 1):
        super().__init__(daemon=True, name="DiscordNotifier")
        self.webhook = webhook.strip()
        self.ping_id = ping_id.strip() if ping_id.strip().isdigit() else ""
        self.batch_seconds = batch_seconds
        self.max_chars = max_chars
        self.group_window_s = group_window_s
        self.status_every_min = status_every_min
        self.status_provider = status_provider
        self.mask = mask or (lambda t: t)           # np. zamiana haseł na ******
        self.total_accounts = max(1, total_accounts)
        self.stats = Stats()
        self._q: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._last_send = 0.0
        self._final = False

    # ---------- API dla reszty programu (wywoływane z dowolnego wątku) ----------

    def line(self, label: str, text: str) -> None:
        self._q.put(("line", label, text))

    def alert(self, key: str, summary: str, label: str, text: str, ping: bool = False) -> None:
        """Alert grupowany po `key`: kilka kont z tym samym problemem w oknie czasowym = jedna wiadomość."""
        self._q.put(("alert", key, summary, label, text, ping))

    def stop(self) -> None:
        self._stop_event.set()

    def send_test(self) -> tuple[bool, str]:
        """Synchroniczna wiadomość testowa (do przycisku w GUI; wołać z wątku roboczego)."""
        return self._post("✅ Mój Kopacz: test połączenia z webhookiem działa.", None, retries=1)

    # ---------- wątek ----------

    def run(self) -> None:
        lines: list[str] = []
        size = 0
        batch_started = 0.0
        alerts: dict[str, _PendingAlert] = {}
        next_status = (time.monotonic() + self.status_every_min * 60) if self.status_every_min > 0 else None

        def flush_lines() -> None:
            nonlocal lines, size
            if lines:
                self._send_lines(lines)
            lines, size = [], 0

        def flush_alerts(force: bool = False) -> None:
            now = time.monotonic()
            for key in list(alerts):
                pa = alerts[key]
                if force or now - pa.first_at >= self.group_window_s:
                    self._send_alert(pa)
                    del alerts[key]

        while True:
            stopping = self._stop_event.is_set()
            try:
                item = self._q.get(timeout=0.0 if stopping else 0.5)
            except queue.Empty:
                item = None
            now = time.monotonic()

            if item is not None:
                if item[0] == "line":
                    text = f"[{item[1]}] {item[2]}"[: self.max_chars - 10]
                    if size + len(text) + 1 > self.max_chars:
                        flush_lines()
                    if not lines:
                        batch_started = now
                    lines.append(text)
                    size += len(text) + 1
                else:
                    _, key, summary, label, text, ping = item
                    pa = alerts.setdefault(key, _PendingAlert(summary, ping, now))
                    pa.ping = pa.ping or ping
                    pa.accounts[label] = text
                continue

            if stopping:
                self._final = True      # reszta kolejki: jedna próba na wiadomość, bez czekania
                flush_lines()
                flush_alerts(force=True)
                return
            if lines and now - batch_started >= self.batch_seconds:
                flush_lines()
            flush_alerts()
            if next_status is not None and now >= next_status:
                next_status = now + self.status_every_min * 60
                self._send_status()

    # ---------- wysyłanie ----------

    @staticmethod
    def _fence(body: str) -> str:
        return "```\n" + body.replace("```", "'''") + "\n```"

    def _send_lines(self, lines: list[str]) -> None:
        self._post(self._fence(self.mask("\n".join(lines))), None)

    def _send_alert(self, pa: _PendingAlert) -> None:
        if len(pa.accounts) == 1:
            (label, text), = pa.accounts.items()
            body = f"⚠️ [{label}] {text}"
        else:
            labels = ", ".join(sorted(pa.accounts))
            body = f"⚠️ {pa.summary}: {len(pa.accounts)}/{self.total_accounts} kont ({labels})"
        ping = self.ping_id if pa.ping else ""
        if ping:
            body = f"<@{ping}> {body}"
        self._post(self.mask(body), ping or None)

    def _send_status(self) -> None:
        if not self.status_provider:
            return
        try:
            text = self.status_provider()
        except Exception as e:  # noqa: BLE001
            text = f"(nie udało się zebrać statusu: {e})"
        self._post("📊 Status\n" + self._fence(self.mask(text)), None)

    def _sleep(self, seconds: float) -> bool:
        """Czeka; zwraca False, jeśli program się zamyka i nie ma już czasu na ponawianie."""
        if self._final:
            return False
        return not self._stop_event.wait(seconds)

    def _post(self, content: str, ping_user: str | None, retries: int = MAX_RETRIES) -> tuple[bool, str]:
        if self._final:
            retries = 1
        payload = json.dumps({
            "content": content[:2000],
            "allowed_mentions": {"parse": [], **({"users": [ping_user]} if ping_user else {})},
        }).encode("utf-8")
        error = ""
        for attempt in range(retries):
            gap = MIN_SEND_GAP - (time.monotonic() - self._last_send)
            if gap > 0 and not self._final and not self._sleep(gap):
                break
            req = urllib.request.Request(
                self.webhook, data=payload, method="POST",
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
            self._last_send = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=10):
                    self.stats.sent += 1
                    return True, ""
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = _retry_after(e)
                    error = f"HTTP 429 (limit), czekam {wait:.0f} s"
                    if not self._sleep(min(wait, 60.0) + 0.5):
                        break
                    continue
                error = f"HTTP {e.code}"
                if e.code < 500:            # zły webhook / uprawnienia — ponawianie nic nie da
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                error = f"połączenie: {getattr(e, 'reason', e)}"
            if not self._sleep(2.0 ** attempt):
                break
        self.stats.errors += 1
        self.stats.dropped += 1
        self.stats.last_error = error or "nieznany błąd"
        return False, self.stats.last_error


def _retry_after(err: urllib.error.HTTPError) -> float:
    try:
        return float(json.loads(err.read().decode("utf-8")).get("retry_after"))
    except (ValueError, TypeError, OSError):
        pass
    try:
        return float(err.headers.get("Retry-After", "5"))
    except (TypeError, ValueError):
        return 5.0
