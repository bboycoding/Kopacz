"""Monitor logów: czyta latest.log kont, rozpoznaje zdarzenia i (opcjonalnie) przesyła je na Discorda."""
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import launcher as L
import log_watcher as W
from config import AccountCfg, Config, DiscordCfg, ServerProfile
from discord_notify import DiscordNotifier, FINAL_FLUSH_S, valid_webhook
from secrets_store import Secrets, mask

# Zdarzenia zgłaszane jako alert (grupowany); reszta zdarzeń idzie jako zwykła linia.
_ALERTS = {
    W.DISCONNECTED: ("disconnected", "Rozłączone", lambda ev: f"Rozłączono z serwerem: {ev.text}", False),
    W.MOVED_TO_LOBBY: ("lobby", "Przeniesione do lobby", lambda ev: f"Przeniesiono do lobby: {ev.text}", False),
    W.STOPPING: ("stopping", "Gra zamknięta", lambda ev: "Gra została zamknięta", False),
    W.BAN: ("ban", "Zbanowane", lambda ev: f"BAN: {ev.text}", True),
}
_EVENT_LABELS = {
    W.CONNECTING: "Łączenie z serwerem",
    W.LOGIN_PROMPT: "Serwer prosi o logowanie",
    W.LOGGED_IN: "Zalogowano",
    W.LOBBY: "Lobby",
    W.IN_GAME: "Wejście do gry",
}


SUMMARY_TICK = 5.0          # co ile sekund wątek podsumowań sprawdza, czy już pora
_now = datetime.now         # podmieniane w testach


def next_boundary(now: datetime, minutes: float) -> datetime:
    """Najbliższa „okrągła” pora: dla 60 min pełna godzina, dla 30 — :00 i :30 itd."""
    step = max(1, int(round(minutes)))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (now - midnight).total_seconds() / 60
    return midnight + timedelta(minutes=(int(elapsed // step) + 1) * step)


class RewardCounter:
    """Klucze (nagrody) zdobyte przez konta: w bieżącym okresie i od uruchomienia programu."""

    def __init__(self):
        self._lock = threading.Lock()
        self._window: dict[str, int] = {}
        self._total: dict[str, int] = {}
        self.labels: list[str] = []     # konta pokazywane w podsumowaniu (kolejność jak w konfiguracji)

    def set_labels(self, labels: list[str]) -> None:
        with self._lock:
            self.labels = list(dict.fromkeys(labels))

    def hit(self, label: str) -> None:
        with self._lock:
            self._window[label] = self._window.get(label, 0) + 1
            self._total[label] = self._total.get(label, 0) + 1

    def take_summary(self, start: datetime, end: datetime) -> str | None:
        """Tekst podsumowania okresu; zeruje licznik okresu. None, gdy nie ma kont."""
        with self._lock:
            if not self.labels:
                self._window.clear()
                return None
            rows = [f"{label}: {self._window.get(label, 0)}" for label in self.labels]
            window = sum(self._window.get(label, 0) for label in self.labels)
            total = sum(self._total.get(label, 0) for label in self.labels)
            self._window.clear()
        return (f"🔑 Klucze {start:%H:%M}–{end:%H:%M}\n" + "\n".join(rows)
                + f"\nRazem: {window} (od uruchomienia programu: {total})")


def reward_regex(profile: ServerProfile | None, nick: str) -> re.Pattern | None:
    """Wzorzec nagrody TEGO konta: {nick} zamieniony na nick (dosłownie). None, gdy brak wzorca lub nicku."""
    if profile is None or not profile.pat_reward or not nick:
        return None
    try:
        return re.compile(profile.pat_reward.replace("{nick}", re.escape(nick)), re.IGNORECASE)
    except re.error:
        return None


def account_label(acc: AccountCfg) -> str:
    return acc.nick or acc.name or acc.instance_id


def account_log_path(acc: AccountCfg, instances_dir: str) -> str:
    if acc.log_path:
        return acc.log_path
    if acc.instance_id and instances_dir:
        return L.log_path_for(instances_dir, acc.instance_id)
    return ""


@dataclass
class _Filter:
    include: list[re.Pattern]
    exclude: list[re.Pattern]

    @classmethod
    def from_cfg(cls, d: DiscordCfg) -> "_Filter":
        return cls([re.compile(p) for p in d.include if p], [re.compile(p) for p in d.exclude if p])

    def forward(self, ev: W.LogEvent, nick: str) -> bool:
        """Czy zwykłą linię logu (nie zdarzenie) wysłać na Discorda."""
        if ev.kind not in (W.CHAT, W.CHAT_PLAYER):
            return False                # linie techniczne (render, authlib…) to szum
        # Linie o własnym koncie (np. „Gracz <nick> zdobył klucz”) idą zawsze — także gdy pasują do
        # wykluczeń, które mają wycinać ten sam komunikat o INNYCH graczach.
        if nick and _mentions(ev.text, nick):
            return True
        if any(p.search(ev.text) for p in self.exclude):
            return False
        return any(p.search(ev.text) for p in self.include)


def _mentions(text: str, nick: str) -> bool:
    """Nick jako całe słowo: „julimat” nie pasuje do „julimat_afk” ani „xjulimat”."""
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(nick) + r"(?![A-Za-z0-9_])", text, re.IGNORECASE) is not None


class Monitor:
    """Zarządza wątkami LogTail kont i wspólnym DiscordNotifier. `apply` można wołać wielokrotnie."""

    def __init__(self, status_provider: Callable[[], str] | None = None):
        self.status_provider = status_provider
        self.notifier: DiscordNotifier | None = None
        self.tails: list[W.LogTail] = []
        self.listeners: list[Callable[[AccountCfg, W.LogEvent], None]] = []   # dla rejoinu (kolejne kroki)
        self._lock = threading.Lock()
        # Licznik kluczy i jego wątek żyją przez cały czas programu (nie zerują się przy zapisie ustawień).
        self.rewards = RewardCounter()
        self._summary_min = 0.0
        self._summary_stop = threading.Event()
        self._summary_thread: threading.Thread | None = None

    def apply(self, cfg: Config, secrets: Secrets, instances_dir: str) -> None:
        with self._lock:
            self._stop_locked()
            accounts = [a for a in cfg.accounts if a.enabled]
            notifier = None
            if cfg.discord.enabled and valid_webhook(secrets.discord_webhook):
                d = cfg.discord
                notifier = DiscordNotifier(
                    secrets.discord_webhook, secrets.discord_ping_id, d.batch_seconds, d.max_chars,
                    d.group_window_s, d.status_every_min, self.status_provider,
                    mask=lambda t: mask(t, secrets), total_accounts=len(accounts))
                notifier.start()
            self.notifier = notifier
            self.rewards.set_labels([account_label(a) for a in accounts])
            self._summary_min = cfg.discord.key_summary_min
            if self._summary_thread is None:
                self._summary_thread = threading.Thread(target=self._summary_loop, daemon=True,
                                                        name="KeySummary")
                self._summary_thread.start()
            flt = _Filter.from_cfg(cfg.discord)
            profiles = {s.id: s for s in cfg.servers}
            for acc in accounts:
                path = account_log_path(acc, instances_dir)
                if not path:
                    continue
                handler = self._handler(acc, profiles.get(acc.server_id), flt, notifier)
                tail = W.LogTail(path, handler, name=f"LogTail-{acc.id}")
                tail.start()
                self.tails.append(tail)

    def _handler(self, acc: AccountCfg, profile: ServerProfile | None, flt: _Filter,
                 notifier: DiscordNotifier | None) -> Callable[[str], None]:
        label = account_label(acc)
        reward = reward_regex(profile, acc.nick)

        def handle(raw: str) -> None:
            ev = W.classify(raw, profile)
            if ev is None:
                return
            # Liczymy tylko komunikaty serwera (CHAT), nie czat graczy — nikt nie „nabije” licznika.
            if reward is not None and ev.kind == W.CHAT and reward.search(ev.text):
                self.rewards.hit(label)
            for listener in list(self.listeners):
                listener(acc, ev)
            if notifier is None:
                return
            if ev.kind in _ALERTS:
                key, summary, make_text, ping = _ALERTS[ev.kind]
                notifier.alert(key, summary, label, make_text(ev), ping)
            elif ev.kind in _EVENT_LABELS:
                notifier.line(label, f"● {_EVENT_LABELS[ev.kind]}")
            elif flt.forward(ev, acc.nick):
                notifier.line(label, f"{ev.ts} {ev.text}")

        return handle

    def _summary_loop(self) -> None:
        """Co `key_summary_min` minut (o okrągłych porach) wysyła podsumowanie kluczy na Discorda."""
        window_start = _now()
        next_due: datetime | None = None
        minutes_seen = None
        while not self._summary_stop.wait(SUMMARY_TICK):
            minutes = self._summary_min
            if minutes <= 0:
                next_due = None
                continue
            now = _now()
            if next_due is None or minutes != minutes_seen:
                next_due, minutes_seen = next_boundary(now, minutes), minutes
                continue
            if now < next_due:
                continue
            text = self.rewards.take_summary(window_start, next_due)
            notifier = self.notifier
            if text and notifier is not None:
                try:
                    notifier.message(text)
                except Exception:  # noqa: BLE001 — Discord nie może zatrzymać licznika
                    pass
            window_start = next_due
            next_due = next_boundary(now, minutes)

    def stop(self) -> None:
        self._summary_stop.set()
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        for t in self.tails:
            t.stop()
        self.tails = []
        if self.notifier:
            self.notifier.stop()
            self.notifier.join(timeout=FINAL_FLUSH_S + 1)
            self.notifier = None
