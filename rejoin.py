"""Odzyskiwanie połączenia z serwerem (poziom 0: powrót z lobby do trybu gry).

Rejoiner działa w wątku nadzorcy konta (Account). Gdy log zgłosi przeniesienie do lobby albo
rozłączenie, kopacz jest natychmiast wstrzymywany (żeby nie klikał w menu), a następnie:
  lobby       → pauza → komendy lobby→gra z profilu serwera → czekanie na wzorzec „wejście do gry”
                → ponawianie z rosnącym odstępem → po wyczerpaniu prób stan BŁĄD, alert z pingiem
                i (opcjonalnie) wolne ponawianie co N minut
  rozłączenie → kopacz zostaje wstrzymany; wznawia się sam, gdy konto wróci na serwer
                (poziom 1, czyli samodzielna nawigacja po menu, dojdzie w kolejnym kroku)
  ban         → tylko alert (wysyła go Monitor), bez ponawiania
Wszystkie czekania są przerywane stopem (F8, zamknięcie programu).
"""
import queue
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import contextmanager

import log_watcher as W
from chat import ChatAborted, ChatError, ChatSender
from config import AccountCfg, RejoinCfg, ServerProfile
from windows import is_connected

TICK = 0.2
COMMAND_GAP = 1.2           # przerwa między komendami wysyłanymi jedna po drugiej
SETTLE_S = 3.0              # chwila po wejściu do gry, zanim kopacz ruszy
DEBOUNCE_S = 3.0            # tyle sekund brak „Multiplayer” w tytule = rozłączenie
HOLD_ALERT_S = 600.0        # po tylu sekundach rozłączenia bez powrotu: alert z pingiem
LOG_TAIL_LINES = 30
LOG_TAIL_CHARS = 1500

OK, RECOVERING, ERROR, BANNED = "ok", "recovering", "error", "banned"


class RejoinGate:
    """Wspólna dla wszystkich kont: tylko jedno konto naraz wysyła komendy powrotu, z odstępem
    między kolejnymi (po restarcie serwera wszystkie konta wracają jednocześnie)."""

    def __init__(self, spacing_s: float = 10.0, clock: Callable[[], float] = time.monotonic):
        self.spacing = spacing_s
        self._clock = clock
        self._lock = threading.Lock()
        self._last = -1e9

    @contextmanager
    def turn(self, stop_event: threading.Event):
        while not self._lock.acquire(timeout=0.2):
            if stop_event.is_set():
                raise ChatAborted()
        try:
            wait = self.spacing - (self._clock() - self._last)
            if wait > 0 and stop_event.wait(wait):
                raise ChatAborted()
            yield
        finally:
            self._last = self._clock()
            self._lock.release()


class Rejoiner:
    def __init__(self, acc: AccountCfg, profile: ServerProfile | None, rcfg: RejoinCfg, miner, hwnd: int,
                 chat_key: str, stop_event: threading.Event, gate: RejoinGate,
                 emit: Callable[[str], None], alert: Callable[[str, str, str, bool], None],
                 sender_factory=ChatSender, connected: Callable[[int], bool] = is_connected,
                 rng: random.Random | None = None, clock: Callable[[], float] = time.monotonic):
        self.acc = acc
        self.profile = profile
        self.rcfg = rcfg
        self.miner = miner
        self.hwnd = hwnd
        self.chat_key = chat_key
        self.stop = stop_event
        self.gate = gate
        self._emit = emit
        self._alert = alert
        self.sender_factory = sender_factory
        self.connected = connected
        self.rng = rng or random.Random()
        self.clock = clock
        self.state = OK
        self._events: queue.Queue = queue.Queue()
        self._log: deque[str] = deque(maxlen=LOG_TAIL_LINES)
        self._lost_since: float | None = None
        self._error_alerted = False

    # ---------- wejście zdarzeń (z wątku LogTail) ----------

    def feed(self, ev: W.LogEvent) -> None:
        self._log.append(ev.raw)
        if ev.kind in (W.MOVED_TO_LOBBY, W.LOBBY, W.DISCONNECTED, W.BAN, W.IN_GAME):
            self._events.put(ev.kind)

    def _drain(self) -> set[str]:
        kinds = set()
        while True:
            try:
                kinds.add(self._events.get_nowait())
            except queue.Empty:
                return kinds

    # ---------- pomocnicze ----------

    def emit(self, text: str) -> None:
        try:
            self._emit(text)
        except Exception:  # noqa: BLE001 — Discord/GUI nie może przerwać odzyskiwania
            pass

    def alert(self, key: str, summary: str, text: str, ping: bool) -> None:
        try:
            self._alert(key, summary, text, ping)
        except Exception:  # noqa: BLE001
            pass

    def _note(self, text: str | None) -> None:
        self.miner.note = text

    def _jit(self, seconds: float, frac: float = 0.2) -> float:
        return seconds * self.rng.uniform(1 - frac, 1 + frac)

    def _window_lost(self) -> bool:
        if self.connected(self.hwnd):
            self._lost_since = None
            return False
        now = self.clock()
        if self._lost_since is None:
            self._lost_since = now
        return now - self._lost_since >= DEBOUNCE_S

    def _fail(self, text: str, ping: bool = True) -> None:
        self.state = ERROR
        self._note("Błąd: nie udało się wrócić na serwer")
        if self._error_alerted:
            return
        self._error_alerted = True
        self.emit(f"❌ {text}")
        self.alert("rejoin-error", "Nie udało się wrócić na serwer", text, ping)
        tail = "\n".join(self._log)[-LOG_TAIL_CHARS:]
        if tail:
            self.emit("Ostatnie linie logu:\n" + tail)

    # ---------- główna pętla (wołana z Account) ----------

    def poll(self) -> bool:
        """Sprawdza, czy trzeba odzyskiwać połączenie. Blokuje do końca odzyskiwania i zwraca True."""
        kinds = self._drain()
        if self.state == BANNED:
            return False
        trigger = None
        if W.BAN in kinds:
            trigger = "ban"
        elif W.DISCONNECTED in kinds:
            trigger = "disconnected"
        elif W.MOVED_TO_LOBBY in kinds or W.LOBBY in kinds:
            trigger = "lobby"
        elif self._window_lost():
            trigger = "disconnected"
        if trigger is None:
            return False
        self._recover(trigger)
        return True

    def _recover(self, trigger: str) -> None:
        started = self.clock()
        self.state = RECOVERING
        self._note("Odzyskiwanie")
        if not self.miner.pause():
            self.emit("⚠ kopacz nie zatrzymał się na czas")
        outcome = trigger
        while True:
            if outcome == "stop":
                return
            if outcome == "ban":
                self.state = BANNED
                self._note("Błąd: zbanowano")
                self.emit("⛔ ban — nie wracam na serwer")
                return
            if outcome == "in_game":
                return self._finish(started)
            if outcome == "error":
                return
            if outcome == "disconnected":
                outcome = self._await_manual_return()
            elif outcome == "lobby":
                outcome = self._level0()
            else:
                raise ValueError(outcome)

    # ---------- rozłączenie: czekamy na powrót ----------

    def _await_manual_return(self) -> str:
        self._note("Rozłączono, czekam na powrót")
        self.emit("⏸ rozłączono — kopanie wstrzymane, wznowię po powrocie na serwer")
        started = self.clock()
        alerted = False
        while True:
            if self.stop.is_set() or not self.miner.is_alive():
                return "stop"
            kinds = self._drain()
            if W.BAN in kinds:
                return "ban"
            if W.IN_GAME in kinds:
                return "in_game"
            if W.LOBBY in kinds or W.MOVED_TO_LOBBY in kinds:
                return "lobby"
            if not alerted and self.clock() - started >= HOLD_ALERT_S:
                alerted = True
                self._fail(f"Konto rozłączone od {HOLD_ALERT_S / 60:.0f} min i nie wróciło na serwer.")
            self.stop.wait(TICK)

    # ---------- poziom 0: lobby → tryb gry ----------

    def _level0(self) -> str:
        p, r = self.profile, self.rcfg
        if p is None or not p.lobby_commands:
            self._fail("Profil serwera nie ma komend lobby → gra, więc bot nie wie, jak wrócić do trybu gry.")
            return "error"
        self.emit("↻ przeniesiono do lobby — wracam do trybu gry")
        res = self._wait_for(self._jit(r.pause_before_s))
        if res != "timeout":
            return res
        attempts = max(1, r.max_attempts_l0)
        backoff = r.backoff_s or [10.0]
        first_round = True
        while True:
            for attempt in range(attempts):
                res = self._attempt(attempt, attempts)
                if res != "timeout":
                    return res
                if attempt + 1 < attempts:
                    res = self._wait_for(self._jit(backoff[min(attempt, len(backoff) - 1)]))
                    if res != "timeout":
                        return res
            if first_round:
                self._fail(f"Po {attempts} próbach nie ma potwierdzenia wejścia do trybu gry "
                           "(awaria serwera?). Kopanie wstrzymane.")
                first_round = False
            else:
                self._note("Błąd: nie udało się wrócić na serwer")
                self.emit("❌ kolejna seria prób nieudana")
            if r.slow_retry:
                self.emit(f"↻ wolne ponawianie: kolejna próba za {r.slow_retry_min:g} min")
                res = self._wait_for(r.slow_retry_min * 60)
            else:
                res = self._wait_for(None)
            if res != "timeout":
                return res
            self._note("Odzyskiwanie")

    def _attempt(self, attempt: int, attempts: int) -> str:
        """Jedna próba: komendy lobby → czekanie na wejście do gry. Zwraca wynik _wait_for."""
        p, r = self.profile, self.rcfg
        self.emit(f"↻ próba {attempt + 1}/{attempts}: " + " | ".join(p.lobby_commands))
        try:
            sender = self.sender_factory(self.hwnd, self.chat_key, self.stop)
            with self.gate.turn(self.stop):
                if not self.connected(self.hwnd):
                    return "disconnected"
                for i, command in enumerate(p.lobby_commands):
                    if i and self.stop.wait(COMMAND_GAP):
                        return "stop"
                    sender.send(command)
        except ChatAborted:
            return "stop"
        except ChatError as e:
            self.emit(f"⚠ nie wysłano komendy: {e}")
            return "timeout"
        return self._wait_for(r.join_timeout_s)

    def _wait_for(self, seconds: float | None) -> str:
        """Czeka na zdarzenie: in_game / ban / disconnected / stop albo timeout (None = bez limitu)."""
        deadline = None if seconds is None else self.clock() + seconds
        while True:
            if self.stop.is_set() or not self.miner.is_alive():
                return "stop"
            kinds = self._drain()
            if W.BAN in kinds:
                return "ban"
            if W.IN_GAME in kinds:
                return "in_game"
            if W.DISCONNECTED in kinds or self._window_lost():
                return "disconnected"
            if deadline is not None and self.clock() >= deadline:
                return "timeout"
            self.stop.wait(TICK)

    # ---------- koniec odzyskiwania ----------

    def _finish(self, started: float) -> None:
        if self.stop.wait(SETTLE_S):
            return
        commands = [c for c in [self.acc.home_command, *self.acc.after_join_commands] if c.strip()]
        if commands:
            try:
                sender = self.sender_factory(self.hwnd, self.chat_key, self.stop)
                for i, command in enumerate(commands):
                    if i and self.stop.wait(COMMAND_GAP):
                        return
                    sender.send(command)
            except ChatAborted:
                return
            except ChatError as e:
                self.emit(f"⚠ nie wysłano komendy po wejściu: {e}")
        self._lost_since = None
        self._error_alerted = False
        self.state = OK
        self._note(None)
        self.miner.resume()
        self.emit(f"✅ wrócono na serwer po {self.clock() - started:.0f} s, kopanie wznowione")
