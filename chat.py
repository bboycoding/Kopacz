"""Wpisywanie wiadomości i komend na czacie gry przez PostMessage (okno może być w tle)."""
import re
import threading

from windows import is_alive, is_connected
from win_input import PostMessageBackend, key_to_vk, tap

MAX_CHAT_LEN = 256   # limit długości wiadomości w Minecrafcie


class ChatError(Exception):
    """Nie udało się wysłać (okno zamknięte, brak połączenia, zły tekst)."""


class ChatAborted(Exception):
    """Przerwano z zewnątrz (stop programu)."""


def check_text(text: str) -> str:
    text = text.strip()
    if not text:
        raise ChatError("Pusta wiadomość.")
    if any(ord(c) < 32 for c in text):
        raise ChatError("Wiadomość zawiera znaki sterujące (np. nowa linia).")
    if len(text) > MAX_CHAT_LEN:
        raise ChatError(f"Wiadomość ma {len(text)} znaków (limit gry: {MAX_CHAT_LEN}).")
    return text


class ChatSender:
    """Otwiera czat, wpisuje tekst i zatwierdza Enterem.

    Kolejność: klawisz czatu → pauza → Backspace → tekst → Enter. Backspace usuwa ewentualną literę,
    którą Windows dorzuca do pola po otwarciu czatu klawiszem (TranslateMessage zamienia WM_KEYDOWN
    na WM_CHAR); przy pustym polu nie robi nic.
    """

    def __init__(self, hwnd: int, chat_key: str = "T", stop_event: threading.Event | None = None,
                 open_wait: float = 0.35, after_type_wait: float = 0.15, after_send_wait: float = 0.3,
                 require_connected: bool = True):
        self.hwnd = hwnd
        self.chat_vk = key_to_vk(chat_key)
        self.stop_event = stop_event or threading.Event()
        self.open_wait = open_wait
        self.after_type_wait = after_type_wait
        self.after_send_wait = after_send_wait
        self.require_connected = require_connected
        self.backend = PostMessageBackend(hwnd)

    def _sleep(self, seconds: float) -> None:
        if self.stop_event.wait(seconds):
            raise ChatAborted()

    def send(self, text: str) -> None:
        self._run(check_text(text))

    def regrab(self) -> None:
        """Łapie mysz w grze bez wysyłania niczego na czat: otwiera czat, oznacza okno jako aktywne
        i zamyka pusty czat Enterem — gra po zamknięciu ekranu przechwytuje mysz i kopanie znów działa.
        Potrzebne po powrocie na serwer (ekrany rozłączenia/ładowania puszczają mysz)."""
        self._run(None)

    def _run(self, text: str | None) -> None:
        if not is_alive(self.hwnd):
            raise ChatError("Okno gry jest zamknięte.")
        if self.require_connected and not is_connected(self.hwnd):
            raise ChatError("Okno gry nie jest połączone z serwerem (menu, ekran rozłączenia albo lobby w trakcie łączenia).")
        b = self.backend
        try:
            tap(b, self.chat_vk)
            self._sleep(self.open_wait)
            tap(b, key_to_vk("BACKSPACE"))
            self._sleep(0.05)
            # Czat jest otwarty, więc mysz na pewno jest puszczona — tylko teraz wolno „aktywować” okno.
            # Po Enterze gra zamknie czat i złapie mysz, inaczej w tle kopacz przestałby kopać.
            b.activate_hint()
            self._sleep(0.05)
            if text:
                b.type_text(text)
            self._sleep(self.after_type_wait)
            tap(b, key_to_vk("ENTER"))      # pusty czat: Enter tylko go zamyka
            self._sleep(self.after_send_wait)
        except ChatAborted:
            # Przerwane w środku: zamykamy czat, żeby nie został otwarty z niedopisanym tekstem.
            try:
                tap(b, key_to_vk("ESCAPE"))
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception as e:  # noqa: BLE001 — pywintypes.error przy zniknięciu okna
            raise ChatError(f"Błąd wysyłania: {e}") from e


def parse_menu_keys(tokens: list[str]) -> list[tuple[str, float | int]]:
    """Tokeny sekwencji menu: nazwa klawisza (TAB, ENTER, DOWN, …) albo `wait:<sekundy>`.
    Zwraca listę ("key", vk) / ("wait", sekundy); ValueError przy błędnym tokenie."""
    parsed: list[tuple[str, float | int]] = []
    for token in tokens:
        token = token.strip()
        if token.lower().startswith("wait:"):
            try:
                seconds = float(token[5:].replace(",", "."))
            except ValueError:
                raise ValueError(f"Niepoprawny czas w „{token}”.") from None
            if not 0 <= seconds <= 60:
                raise ValueError(f"Czas w „{token}” musi być w zakresie 0–60 s.")
            parsed.append(("wait", seconds))
        else:
            parsed.append(("key", key_to_vk(token)))
    return parsed


class MenuNavigator:
    """Naciska klawisze w menu gry (ekran rozłączenia → lista serwerów → dołączenie) przez PostMessage."""

    def __init__(self, hwnd: int, stop_event: threading.Event | None = None, key_gap: float = 0.3):
        self.hwnd = hwnd
        self.stop_event = stop_event or threading.Event()
        self.key_gap = key_gap
        self.backend = PostMessageBackend(hwnd)

    def run(self, tokens: list[str]) -> None:
        steps = parse_menu_keys(tokens)
        if not is_alive(self.hwnd):
            raise ChatError("Okno gry jest zamknięte.")
        try:
            for kind, value in steps:
                if kind == "wait":
                    if self.stop_event.wait(value):
                        raise ChatAborted()
                else:
                    tap(self.backend, value)
                    if self.stop_event.wait(self.key_gap):
                        raise ChatAborted()
        except ChatAborted:
            raise
        except Exception as e:  # noqa: BLE001 — pywintypes.error przy zniknięciu okna
            raise ChatError(f"Błąd wysyłania klawiszy: {e}") from e


def rules_to_text(rules: list[dict]) -> str:
    """Reguły klawiszy menu jako tekst do edycji: jedna w linii, „wzorzec => klawisze”."""
    return "\n".join(f"{r['pattern']} => {', '.join(r['keys'])}" for r in rules)


def parse_rules_text(text: str) -> list[dict]:
    """Odwrotność rules_to_text. ValueError z numerem linii przy błędzie."""
    rules = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if "=>" not in line:
            raise ValueError(f"Linia {n}: brak „=>” (format: wzorzec => klawisze).")
        pattern, keys_text = (part.strip() for part in line.rsplit("=>", 1))
        keys = [k.strip() for k in keys_text.replace(";", ",").split(",") if k.strip()]
        if not pattern or not keys:
            raise ValueError(f"Linia {n}: podaj wzorzec i klawisze.")
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Linia {n}: niepoprawny wzorzec ({e}).") from None
        try:
            parse_menu_keys(keys)
        except ValueError as e:
            raise ValueError(f"Linia {n}: {e}") from None
        rules.append({"pattern": pattern, "keys": keys})
    return rules
