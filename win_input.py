"""Wysyłanie klawiszy i LPM do okien Minecrafta.

Dwa tryby:
- PostMessageBackend — wiadomości do okna w tle, wiele okien naprawdę równolegle.
- ForegroundBackend — okno wyciągane na pierwszy plan + globalny input;
  przy wielu oknach obsługiwane po kolei (globalna blokada).

Interfejs obu: session() (kontekst jednego odcinka ruchu), key_down/key_up,
lmb_down/lmb_up, hold_tick (podtrzymanie w trakcie trzymania), release_all.
"""
import threading
import time
from contextlib import contextmanager

import pywintypes
import win32api
import win32con
import win32gui

VK_F8 = win32con.VK_F8

SPECIAL_KEYS = {
    "SPACE": win32con.VK_SPACE,
    "SHIFT": win32con.VK_LSHIFT,
    "CTRL": win32con.VK_LCONTROL,
    "LEFT": win32con.VK_LEFT,
    "RIGHT": win32con.VK_RIGHT,
    "UP": win32con.VK_UP,
    "DOWN": win32con.VK_DOWN,
}


def key_to_vk(name: str) -> int:
    name = name.strip().upper()
    if name in SPECIAL_KEYS:
        return SPECIAL_KEYS[name]
    if len(name) == 1 and name.isascii() and name.isalnum():
        return ord(name)
    raise ValueError(f"Nieznany klawisz: „{name}” (dozwolone: litera, cyfra, "
                     + ", ".join(SPECIAL_KEYS) + ")")


def _scan(vk: int) -> int:
    return win32api.MapVirtualKey(vk, 0)


def _key_lparam(vk: int, up: bool, repeat: bool = False) -> int:
    # Bity: 0–15 licznik powtórzeń, 16–23 scan code (GLFW mapuje klawisze po nim),
    # 30 poprzedni stan, 31 przejście (puszczenie).
    lp = 1 | (_scan(vk) << 16)
    if up:
        lp |= (1 << 30) | (1 << 31)
    elif repeat:
        lp |= 1 << 30
    return lp


class PostMessageBackend:
    name = "postmessage"

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._held: set[int] = set()
        self._lmb = False

    def _post(self, msg: int, wparam: int, lparam: int) -> None:
        win32api.PostMessage(self.hwnd, msg, wparam, lparam)

    def _center(self) -> int:
        _, _, w, h = win32gui.GetClientRect(self.hwnd)
        return win32api.MAKELONG(w // 2, h // 2)

    @contextmanager
    def session(self):
        yield

    def key_down(self, vk: int) -> None:
        self._post(win32con.WM_KEYDOWN, vk, _key_lparam(vk, up=False))
        self._held.add(vk)

    def key_up(self, vk: int) -> None:
        self._post(win32con.WM_KEYUP, vk, _key_lparam(vk, up=True))
        self._held.discard(vk)

    def lmb_down(self) -> None:
        self._post(win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, self._center())
        self._lmb = True

    def lmb_up(self) -> None:
        self._post(win32con.WM_LBUTTONUP, 0, self._center())
        self._lmb = False

    def hold_tick(self) -> None:
        # Jak autorepeat prawdziwej klawiatury.
        for vk in list(self._held):
            self._post(win32con.WM_KEYDOWN, vk, _key_lparam(vk, up=False, repeat=True))

    def release_all(self) -> None:
        for vk in list(self._held):
            try:
                self.key_up(vk)
            except pywintypes.error:
                self._held.discard(vk)
        if self._lmb:
            try:
                self.lmb_up()
            except pywintypes.error:
                self._lmb = False


# Tylko jedno okno naraz może być na pierwszym planie.
_FOREGROUND_LOCK = threading.Lock()


class ForegroundBackend:
    name = "foreground"

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._held: set[int] = set()
        self._lmb_wanted = False
        self._lmb_pressed = False
        self._in_session = False

    def _focus(self) -> None:
        if win32gui.GetForegroundWindow() == self.hwnd:
            return
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        # Wciśnięcie Alt pozwala obejść blokadę SetForegroundWindow z tła.
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        finally:
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)

    def _mouse(self, down: bool) -> None:
        flag = win32con.MOUSEEVENTF_LEFTDOWN if down else win32con.MOUSEEVENTF_LEFTUP
        win32api.mouse_event(flag, 0, 0, 0, 0)
        self._lmb_pressed = down

    @contextmanager
    def session(self):
        with _FOREGROUND_LOCK:
            self._in_session = True
            try:
                self._focus()
                if self._lmb_wanted:
                    self._mouse(True)
                yield
            finally:
                self._release_physical()
                self._in_session = False

    def key_down(self, vk: int) -> None:
        if self._in_session:
            win32api.keybd_event(vk, _scan(vk), 0, 0)
            self._held.add(vk)

    def key_up(self, vk: int) -> None:
        if vk in self._held:
            win32api.keybd_event(vk, _scan(vk), win32con.KEYEVENTF_KEYUP, 0)
            self._held.discard(vk)

    def lmb_down(self) -> None:
        self._lmb_wanted = True
        if self._in_session and not self._lmb_pressed:
            self._mouse(True)

    def lmb_up(self) -> None:
        self._lmb_wanted = False
        if self._lmb_pressed:
            self._mouse(False)

    def hold_tick(self) -> None:
        pass

    def _release_physical(self) -> None:
        for vk in list(self._held):
            self.key_up(vk)
        if self._lmb_pressed:
            self._mouse(False)

    def release_all(self) -> None:
        self._lmb_wanted = False
        self._release_physical()


def make_sender(backend: str, hwnd: int):
    if backend == "foreground":
        return ForegroundBackend(hwnd)
    return PostMessageBackend(hwnd)
