"""Pętla kopania — jeden wątek na jedno okno Minecrafta."""
import random
import threading
import time

from config import Config
from win_input import key_to_vk, make_sender
from windows import McWindow, is_alive

HOLD_TICK = 0.25  # co ile sekund podtrzymywać trzymany klawisz


def _hold(sender, vk: int, duration: float, stop_event: threading.Event) -> bool:
    """Trzyma klawisz przez duration. Zwraca False, jeśli przerwano stopem."""
    with sender.session():
        sender.key_down(vk)
        try:
            end = time.monotonic() + duration
            while True:
                left = end - time.monotonic()
                if left <= 0:
                    return True
                if stop_event.wait(min(HOLD_TICK, left)):
                    return False
                sender.hold_tick()
        finally:
            sender.key_up(vk)


class Miner(threading.Thread):
    def __init__(self, window: McWindow, cfg: Config):
        super().__init__(daemon=True)
        self.window = window
        self.cfg = cfg
        self.sender = make_sender(cfg.backend, window.hwnd)
        self._stop_event = threading.Event()
        self.cycles = 0
        self.started_at: float | None = None
        self.status = "Startuje…"

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def runtime(self) -> float:
        return time.time() - self.started_at if self.started_at else 0.0

    def _segment_time(self) -> float:
        c = self.cfg
        t = c.blocks * c.sec_per_block * (1 + c.wall_push_pct / 100)
        if c.jitter_pct:
            t *= 1 + random.uniform(-c.jitter_pct, c.jitter_pct) / 100
        return t

    def run(self) -> None:
        c = self.cfg
        hwnd = self.window.hwnd
        self.started_at = time.time()
        try:
            right, left = key_to_vk(c.key_right), key_to_vk(c.key_left)
            self.status = "Kopie"
            self.sender.lmb_down()
            while not self._stop_event.is_set():
                for vk in (right, left):
                    if not is_alive(hwnd):
                        self.status = "Okno MC zamknięte"
                        return
                    if not _hold(self.sender, vk, self._segment_time(), self._stop_event):
                        return
                    if self._stop_event.wait(c.turn_pause):
                        return
                self.cycles += 1
                if c.lmb_refresh_cycles and self.cycles % c.lmb_refresh_cycles == 0:
                    self.sender.lmb_up()
                    time.sleep(0.05)
                    self.sender.lmb_down()
        except Exception as e:  # noqa: BLE001 — błąd pokazywany w GUI
            self.status = f"Błąd: {e}"
        finally:
            self.sender.release_all()
            if self.status == "Kopie":
                self.status = "Zatrzymany"


def run_action(window: McWindow, backend: str, vk: int, duration: float,
               mine: bool, stop_event: threading.Event) -> None:
    """Jednorazowa akcja (test okna / kalibracja): idzie klawiszem vk, opcjonalnie kopiąc."""
    sender = make_sender(backend, window.hwnd)
    try:
        if mine:
            sender.lmb_down()
        _hold(sender, vk, duration, stop_event)
    finally:
        sender.release_all()
