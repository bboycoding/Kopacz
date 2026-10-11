"""Pętla kopania — jeden wątek na jedno okno Minecrafta."""
import random
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

import pywintypes

from config import Config
from win_input import key_to_vk, make_sender, tap
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


@dataclass(frozen=True)
class EatPlan:
    """Jedzenie co N cykli: klawisz slotu jedzenia, PPM przez `seconds`, powrót na slot kilofa."""
    food_vk: int
    pickaxe_vk: int
    every_cycles: int
    seconds: float

    @classmethod
    def from_account(cls, acc) -> "EatPlan | None":
        if not acc.eat_enabled:
            return None
        return cls(key_to_vk(str(acc.food_slot)), key_to_vk(str(acc.pickaxe_slot)),
                   max(1, acc.eat_every_cycles), acc.eat_seconds)


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
        self.note: str | None = None            # komunikat z zewnątrz (np. „Odzyskiwanie”); GUI pokazuje go zamiast statusu
        # Gdy True, zniknięcie okna gry (crash, restart instancji) nie kończy wątku: kopacz czeka na rebind().
        self.keep_alive_without_window = False
        self.eat: EatPlan | None = None         # ustawia App z konfiguracji konta, przed start()
        self.meals = 0

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

    def rebind(self, window: McWindow) -> None:
        """Przepina kopacza na nowe okno gry (po restarcie instancji). Wołać, gdy kopacz jest wstrzymany."""
        self.window = window
        self.sender = make_sender(self.cfg.backend, window.hwnd)

    def _survive_window_loss(self) -> bool:
        """Okno gry zniknęło. Czeka (bez wysyłania czegokolwiek), aż ktoś poprosi o pauzę i przepnie
        kopacza na nowe okno albo okno wróci. Zwraca False przy stopie."""
        self.sender.release_all()
        self.status = "Okno MC zamknięte"
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                return self._handle_pause()
            if is_alive(self.window.hwnd):
                self.sender.lmb_down()
                self.status = "Kopie"
                return True
            self._stop_event.wait(0.2)
        return False

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
        self._select_pickaxe()
        self.sender.lmb_down()
        self.status = "Kopie"
        return True

    # ---------- jedzenie ----------

    def _select_pickaxe(self) -> None:
        """Przełącza na slot z kilofem (gdy jedzenie jest ustawione — tylko wtedy znamy ten slot)."""
        if self.eat:
            with self.sender.session():
                tap(self.sender, self.eat.pickaxe_vk)

    def _eat(self) -> str:
        """Puść LPM → slot jedzenia → PPM przez czas jedzenia → puść → slot kilofa → LPM.
        Stop i pauza przerywają jedzenie; PPM jest zawsze puszczany. Zwraca DONE / STOPPED / PAUSED."""
        e = self.eat
        s = self.sender
        self.status = "Je"
        s.lmb_up()
        result = DONE
        with s.session():
            try:
                tap(s, e.food_vk)
                result = self._wait(0.2)            # gra potrzebuje chwili na zmianę przedmiotu w ręce
                if result == DONE:
                    s.rmb_down()
                    result = self._wait(e.seconds)
            finally:
                s.rmb_up()
                tap(s, e.pickaxe_vk)
        if result == DONE:
            self.meals += 1
            s.lmb_down()
            self.status = "Kopie"
        return result

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
        self.started_at = time.time()
        try:
            right, left = key_to_vk(c.key_right), key_to_vk(c.key_left)
            self.status = "Kopie"
            self._select_pickaxe()
            self.sender.lmb_down()
            while not self._stop_event.is_set():
                try:
                    if not self._run_cycle(c, right, left):
                        return
                except pywintypes.error:
                    # Okno zniknęło w trakcie wysyłania wiadomości. Bez rejoinu kończymy z błędem jak dotąd.
                    if not self.keep_alive_without_window:
                        raise
                    self._stop_event.wait(0.1)
        except Exception as e:  # noqa: BLE001 — błąd pokazywany w GUI
            self.status = f"Błąd: {e}"
        finally:
            self.sender.release_all()
            self._paused_ack.set()      # nikt nie czeka na pauzę kopacza, którego już nie ma
            self.note = None
            if self.status in ("Kopie", "Wstrzymany", "Je"):
                self.status = "Zatrzymany"

    def _run_cycle(self, c: Config, right: int, left: int) -> bool:
        """Jeden cykl prawo–lewo. False = koniec pracy kopacza (stop albo zamknięte okno)."""
        if not self._handle_pause():
            return False
        for vk in (right, left):
            if not is_alive(self.window.hwnd):
                if not self.keep_alive_without_window:
                    self.status = "Okno MC zamknięte"
                    return False
                if not self._survive_window_loss():
                    return False
                return True                 # nowy cykl na (być może) nowym oknie
            result = _hold(self.sender, vk, self._segment_time(), self._stop_event, self._pause_event)
            if result == DONE:
                result = self._wait(c.turn_pause)
            if result == STOPPED:
                return False
            if result == PAUSED:
                # Po wznowieniu zaczynamy cykl od nowa (od ruchu w prawo); niepełny cykl się nie liczy.
                return True
        self.cycles += 1
        if self.eat and self.cycles % self.eat.every_cycles == 0:
            # Postać stoi przy ścianie po zawrotce — dobry moment na jedzenie.
            return self._eat() != STOPPED
        if c.lmb_refresh_cycles and self.cycles % c.lmb_refresh_cycles == 0:
            self.sender.lmb_up()
            time.sleep(0.05)
            self.sender.lmb_down()
        return True


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
