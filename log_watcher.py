"""Czytanie latest.log i rozpoznawanie zdarzeń (rozłączenie, lobby, wejście do gry, ban…).

Zdarzenia ogólne dla Minecrafta (Connecting to, Client disconnected, Stopping!) są wpisane w kod.
Zdarzenia zależne od serwera (logowanie, lobby, wejście do gry, ban) pochodzą z wzorców profilu serwera.
"""
import gzip
import os
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache

# Rodzaje zdarzeń.
CONNECTING = "connecting"
DISCONNECTED = "disconnected"
STOPPING = "stopping"
LOGIN_PROMPT = "login_prompt"
LOGGED_IN = "logged_in"
LOBBY = "lobby"
IN_GAME = "in_game"
MOVED_TO_LOBBY = "moved_to_lobby"
BAN = "ban"
CHAT = "chat"                 # zwykła linia czatu serwera
CHAT_PLAYER = "chat_player"   # czat graczy — nigdy nie wywołuje zdarzeń (ochrona przed podszywaniem się)
LOG = "log"                   # pozostałe linie logu

EVENT_KINDS = (CONNECTING, DISCONNECTED, STOPPING, LOGIN_PROMPT, LOGGED_IN, LOBBY, IN_GAME,
               MOVED_TO_LOBBY, BAN)

LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] \[([^\]/]+)(?:/([A-Z]+))?\]: (.*)$")
CHAT_RE = re.compile(r"\[CHAT\] ?(.*)$")
DISCONNECT_RE = re.compile(r"^Client disconnected with reason: ?(.*)$")

# Kolejność ma znaczenie: ban i przeniesienie do lobby sprawdzane przed zwykłymi komunikatami.
_PROFILE_PATTERNS = (
    (BAN, "pat_ban"),
    (MOVED_TO_LOBBY, "pat_moved_to_lobby"),
    (LOGIN_PROMPT, "pat_login_prompt"),
    (LOGGED_IN, "pat_logged_in"),
    (IN_GAME, "pat_in_game"),
    (LOBBY, "pat_lobby"),
)


@dataclass(frozen=True)
class LogEvent:
    kind: str
    text: str        # treść bez znacznika czasu i nazwy wątku
    raw: str         # cała linia
    ts: str = ""     # "HH:MM:SS" z logu


@lru_cache(maxsize=256)
def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def classify(raw: str, profile=None) -> LogEvent | None:
    """Zwraca zdarzenie dla linii logu albo None dla linii niebędących wpisem (np. ciąg stack trace)."""
    m = LINE_RE.match(raw)
    if not m:
        return None
    ts, _thread, _level, msg = m.groups()

    chat = CHAT_RE.search(msg)
    if chat:
        text = chat.group(1)
        if profile is not None:
            if profile.pat_player_chat and _rx(profile.pat_player_chat).search(text):
                return LogEvent(CHAT_PLAYER, text, raw, ts)
            for kind, attr in _PROFILE_PATTERNS:
                pattern = getattr(profile, attr)
                if pattern and _rx(pattern).search(text):
                    return LogEvent(kind, text, raw, ts)
        return LogEvent(CHAT, text, raw, ts)

    if msg.startswith("Connecting to "):
        return LogEvent(CONNECTING, msg, raw, ts)
    d = DISCONNECT_RE.match(msg)
    if d:
        reason = d.group(1).strip() or "brak powodu"
        # Ban zwykle przychodzi jako powód rozłączenia („You are banned…”), nie jako linia czatu.
        if profile is not None and profile.pat_ban and _rx(profile.pat_ban).search(reason):
            return LogEvent(BAN, reason, raw, ts)
        return LogEvent(DISCONNECTED, reason, raw, ts)
    if msg == "Stopping!":
        return LogEvent(STOPPING, msg, raw, ts)
    return LogEvent(LOG, msg, raw, ts)


def read_log_lines(path: str) -> Iterator[str]:
    """Linie z pliku .log albo .log.gz (do testów wzorców na starych logach)."""
    opener = gzip.open if path.lower().endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield line.rstrip("\r\n")


def summarize(path: str, profile=None, samples: int = 3) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Przepuszcza log przez wzorce: liczba zdarzeń wg rodzaju i kilka przykładowych linii."""
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for line in read_log_lines(path):
        ev = classify(line, profile)
        if ev is None or ev.kind not in EVENT_KINDS:
            continue
        counts[ev.kind] = counts.get(ev.kind, 0) + 1
        if len(examples.setdefault(ev.kind, [])) < samples:
            examples[ev.kind].append(line[:200])
    return counts, examples


class LogTail(threading.Thread):
    """Doczytuje nowe linie pliku co `poll` sekund.

    Plik jest otwierany tylko na czas odczytu. Trzymanie uchwytu blokowałoby grze rotację
    latest.log przy kolejnym starcie (Windows nie pozwala przenieść otwartego pliku).
    Rotację (nowy plik pod tą samą nazwą) wykrywa po zmianie czasu utworzenia lub spadku rozmiaru.
    """

    MAX_CHUNK = 1 << 20

    def __init__(self, path: str, callback: Callable[[str], None], poll: float = 0.5,
                 from_start: bool = False, name: str = "LogTail"):
        super().__init__(daemon=True, name=name)
        self.path = path
        self.callback = callback
        self.poll = poll
        self.from_start = from_start
        self.errors = 0
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        pos = 0
        created = None
        buf = b""
        first = True
        while not self._stop_event.wait(self.poll):
            try:
                st = os.stat(self.path)
            except OSError:
                created = None          # pliku nie ma (np. trwa rotacja) — po pojawieniu czytamy od zera
                first = False
                continue
            key = st.st_ctime_ns
            if created is None:
                created = key
                pos = st.st_size if (first and not self.from_start) else 0
                buf = b""
            elif key != created or st.st_size < pos:
                created, pos, buf = key, 0, b""
            first = False
            if st.st_size <= pos:
                continue
            try:
                with open(self.path, "rb") as f:
                    f.seek(pos)
                    chunk = f.read(min(st.st_size - pos, self.MAX_CHUNK))
            except OSError:
                continue
            pos += len(chunk)
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for line in lines:
                try:
                    self.callback(line.decode("utf-8", "replace").rstrip("\r"))
                except Exception:  # noqa: BLE001 — błąd odbiorcy nie może zatrzymać czytania
                    self.errors += 1
