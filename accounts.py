"""Nadzorca konta: harmonogram komend na czacie, wysyłanych bez przerywania pracy innych kont.

Wszystko, co dotyka okna poza samym ruchem (czat, a w kolejnych krokach menu i rejoin), robi jeden wątek
na konto. Dzięki temu dwie rzeczy nigdy nie piszą naraz do tego samego okna, a ruch kopacza jest na czas
wysyłania wstrzymywany (Miner.paused_for).
"""
import queue
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from chat import ChatAborted, ChatError, ChatSender
from config import AccountCfg, ChatCommand
from windows import is_connected

TICK = 0.5              # co ile sekund nadzorca sprawdza terminy
COMMAND_GAP = 1.2       # przerwa między komendami wysyłanymi jedna po drugiej (antyspam serwera)
RETRY_AFTER_ERROR = 30.0
MIN_INTERVAL = 5.0


@dataclass
class _Scheduled:
    cmd: ChatCommand
    due: float
    pending: bool = False       # termin minął w złym momencie; czeka na stabilny powrót (on_missed="defer")


class Account(threading.Thread):
    def __init__(self, acc: AccountCfg, miner, hwnd: int, chat_key: str = "T", stabilize_s: float = 60.0,
                 emit: Callable[[str], None] | None = None, clock: Callable[[], float] = time.monotonic,
                 sender_factory=ChatSender, connected: Callable[[int], bool] = is_connected,
                 rng: random.Random | None = None):
        super().__init__(daemon=True, name=f"Account-{acc.id}")
        self.acc = acc
        self.miner = miner
        self.hwnd = hwnd
        self.chat_key = chat_key
        self.stabilize_s = stabilize_s
        self._emit = emit or (lambda text: None)
        self.clock = clock
        self.sender_factory = sender_factory
        self.connected = connected
        self.rng = rng or random.Random()
        self._stop_event = threading.Event()
        self._requests: queue.Queue = queue.Queue()     # „Wyślij teraz”: (tekst, callback)
        self._ok_since: float | None = None
        now = clock()
        self._items = [_Scheduled(c, now + self._interval(c)) for c in acc.schedule if c.text.strip()]

    def emit(self, text: str) -> None:
        try:
            self._emit(text)
        except Exception:  # noqa: BLE001 — np. Discord niedostępny; harmonogram działa dalej
            pass

    # ---------- API ----------

    def stop(self) -> None:
        self._stop_event.set()

    def send_now(self, text: str, callback: Callable[[bool, str], None] | None = None) -> None:
        """Wysyła komendę poza harmonogramem (z tego samego wątku, z pauzą kopacza)."""
        self._requests.put((text, callback))

    @property
    def next_due_in(self) -> float | None:
        """Za ile sekund najbliższa komenda (do podglądu w GUI)."""
        if not self._items:
            return None
        return max(0.0, min(i.due for i in self._items) - self.clock())

    # ---------- harmonogram ----------

    def _interval(self, cmd: ChatCommand) -> float:
        base = max(MIN_INTERVAL, cmd.every_min * 60)
        jitter = self.rng.uniform(-cmd.jitter_s, cmd.jitter_s) if cmd.jitter_s else 0.0
        return max(MIN_INTERVAL, base + jitter)

    def _can_send(self) -> bool:
        m = self.miner
        return m.is_alive() and m.status == "Kopie" and not m.paused and self.connected(self.hwnd)

    def _update_ok_since(self, now: float) -> None:
        if self._can_send():
            if self._ok_since is None:
                self._ok_since = now
        else:
            self._ok_since = None

    def _stable(self, now: float) -> bool:
        return self._ok_since is not None and now - self._ok_since >= self.stabilize_s

    def _skip_to_future(self, item: _Scheduled, now: float) -> None:
        step = max(MIN_INTERVAL, item.cmd.every_min * 60)
        while item.due <= now:
            item.due += step

    def run(self) -> None:
        try:
            while not self._stop_event.wait(TICK):
                if not self.miner.is_alive():
                    return
                now = self.clock()
                self._update_ok_since(now)
                self._serve_requests()
                due = self._collect_due(now)
                if due:
                    self._send_scheduled(due)
        except ChatAborted:
            return

    def _collect_due(self, now: float) -> list[_Scheduled]:
        ready = []
        for item in self._items:
            if now < item.due:
                continue
            if self._stable(now):
                ready.append(item)
            elif item.cmd.on_missed == "skip":
                self._skip_to_future(item, now)
                self.emit(f"⏭ pominięto komendę (konto nie kopało): {item.cmd.text}")
            elif not item.pending:
                item.pending = True
                self.emit(f"⏳ komenda odłożona do powrotu: {item.cmd.text}")
        return ready

    # ---------- wysyłanie ----------

    def _send_batch(self, texts: list[str]) -> tuple[bool, str]:
        """Pauza kopacza → wpisanie komend → wznowienie. Zwraca (ok, komunikat błędu)."""
        sender = self.sender_factory(self.hwnd, self.chat_key, self._stop_event)
        with self.miner.paused_for() as stopped:
            if not stopped:
                return False, "kopacz nie zatrzymał się na czas"
            for i, text in enumerate(texts):
                if i and self._stop_event.wait(COMMAND_GAP):
                    raise ChatAborted()
                try:
                    sender.send(text)
                except ChatError as e:
                    return False, str(e)
        return True, ""

    def _send_scheduled(self, due: list[_Scheduled]) -> None:
        texts = [i.cmd.text for i in due]
        ok, error = self._send_batch(texts)
        now = self.clock()
        for item in due:
            item.pending = False
            item.due = now + (self._interval(item.cmd) if ok else RETRY_AFTER_ERROR)
        if ok:
            self.emit("▶ wysłano: " + " | ".join(texts))
        else:
            self.emit(f"⚠ nie wysłano ({error}), kolejna próba za {RETRY_AFTER_ERROR:.0f} s: " + " | ".join(texts))

    def _serve_requests(self) -> None:
        while True:
            try:
                text, callback = self._requests.get_nowait()
            except queue.Empty:
                return
            if not self._can_send():
                ok, msg = False, "konto teraz nie kopie albo okno nie jest połączone z serwerem"
            else:
                ok, msg = self._send_batch([text])
            if ok:
                self.emit(f"▶ wysłano ręcznie: {text}")
            if callback:
                try:
                    callback(ok, msg)
                except Exception:  # noqa: BLE001 — błąd po stronie GUI nie może zabić harmonogramu
                    pass
