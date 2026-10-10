"""Pętla kopania — jeden wątek na jedno okno Minecrafta."""
import random
import threading
import time
from contextlib import contextmanager

from config import Config
from win_input import key_to_vk, make_sender
from windows import McWindow, is_alive

HOLD_TICK = 0.25  # co ile sekund podtrzymywać trzymany klawisz (i sprawdzać stop/pauzę)

# Wynik czekania/trzymania klawisza.
DONE, STOPPED, PAUSED = "done", "stopped", "paused"


def _hold(sender, vk: int, duration: float, stop_event: threading.Event,
          pause_event: threading.Event | None = None) -> str:
    """Trzyma klawisz przez duration. Zwraca DONE, STOPPED (stop) albo PAUSED (prośba o pauzę)."""
    with sender.session():
        sender.key_down(vk)
        try:
            end = time.monotonic() + duration
            while True:
                left = end - time.monotonic()
                if left <= 0:
                    return DONE
                if stop_event.wait(min(HOLD_TICK, left)):
                    return STOPPED
                if pause_event is not None and pause_event.is_set():
                    return PAUSED
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
        self._pause_event = threading.Event()   # ktoś prosi o wstrzymanie
        self._paused_ack = threading.Event()    # kopacz potwierdza: klawisze i LPM puszczone
        self.cycles = 0
        self.started_at: float | None = None
        self.status = "Startuje…"

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def runtime(self) -> float:
        return time.time() - self.started_at if self.started_at else 0.0

    # ---------- pauza ----------

    @property
    def paused(self) -> bool:
        return self.is_alive() and self._paused_ack.is_set()

    def pause(self, timeout: float = 2.0) -> bool:
        """Wstrzymuje kopanie i czeka, aż klawisze i LPM zostaną puszczone.

        Zwraca True, gdy kopacz stoi (albo w ogóle nie działa), False przy przekroczeniu czasu."""
        if not self.is_alive():
            return True
        self._pause_event.set()
        return self._paused_ack.wait(timeout) or not self.is_alive()

    def resume(self) -> None:
        self._pause_event.clear()

    @contextmanager
    def paused_for(self, timeout: float = 2.0):
        """`with miner.paused_for() as ok:` — na czas bloku kopacz stoi; wznawia się po wyjściu."""
        ok = self.pause(timeout)
        try:
            yield ok
        finally:
            self.resume()

    def _handle_pause(self) -> bool:
        """Jeśli trwa prośba o pauzę: puszcza wszystko, potwierdza i czeka na wznowienie.
        Zwraca False, gdy w międzyczasie przyszedł stop."""
        if not self._pause_event.is_set():
            return True
        self.sender.release_all()
        self.status = "Wstrzymany"
        self._paused_ack.set()
        try:
            while self._pause_event.is_set():
                if self._stop_event.wait(0.1):
                    return False
        finally:
            self._paused_ack.clear()
        self.sender.lmb_down()
        self.status = "Kopie"
        return True

    def _wait(self, seconds: float) -> str:
        """Pauza na zawrotce, przerywana stopem lub prośbą o wstrzymanie."""
        end = time.monotonic() + seconds
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return DONE
            if self._stop_event.wait(min(HOLD_TICK, left)):
                return STOPPED
            if self._pause_event.is_set():
                return PAUSED

    # ---------- pętla ----------

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
                if not self._handle_pause():
                    return
                interrupted = False
                for vk in (right, left):
                    if not is_alive(hwnd):
                        self.status = "Okno MC zamknięte"
                        return
                    result = _hold(self.sender, vk, self._segment_time(), self._stop_event, self._pause_event)
                    if result == DONE:
                        result = self._wait(c.turn_pause)
                    if result == STOPPED:
                        return
                    if result == PAUSED:
                        # Po wznowieniu zaczynamy cykl od nowa (od ruchu w prawo); niepełny cykl się nie liczy.
                        interrupted = True
                        break
                if interrupted:
                    continue
                self.cycles += 1
                if c.lmb_refresh_cycles and self.cycles % c.lmb_refresh_cycles == 0:
                    self.sender.lmb_up()
                    time.sleep(0.05)
                    self.sender.lmb_down()
        except Exception as e:  # noqa: BLE001 — błąd pokazywany w GUI
            self.status = f"Błąd: {e}"
        finally:
            self.sender.release_all()
            self._paused_ack.set()      # nikt nie czeka na pauzę kopacza, którego już nie ma
            if self.status in ("Kopie", "Wstrzymany"):
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
