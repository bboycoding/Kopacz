"""Wpisywanie wiadomości i komend na czacie gry przez PostMessage (okno może być w tle)."""
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
        text = check_text(text)
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
            b.type_text(text)
            self._sleep(self.after_type_wait)
            tap(b, key_to_vk("ENTER"))
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
