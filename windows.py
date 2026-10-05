"""Wyszukiwanie okien Minecrafta."""
import re
from dataclasses import dataclass

import win32gui
import win32process

# Klasy okien gry: GLFW (1.13+) i LWJGL2 (1.8–1.12).
GAME_CLASSES = {"GLFW30", "LWJGL"}
TITLE_RE = re.compile(r"^Minecraft", re.IGNORECASE)


@dataclass(frozen=True)
class McWindow:
    hwnd: int
    title: str
    pid: int

    @property
    def label(self) -> str:
        return f"{self.title}  [PID {self.pid}, hwnd {self.hwnd}]"


def _is_game_window(hwnd: int) -> bool:
    if not win32gui.IsWindowVisible(hwnd):
        return False
    cls = win32gui.GetClassName(hwnd)
    if cls in GAME_CLASSES:
        return True
    title = win32gui.GetWindowText(hwnd)
    # Fallback po tytule, z pominięciem okien launcherów.
    return bool(TITLE_RE.match(title)) and "launcher" not in title.lower()


def find_minecraft_windows() -> list[McWindow]:
    found: list[McWindow] = []

    def callback(hwnd, _):
        if _is_game_window(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            found.append(McWindow(hwnd, win32gui.GetWindowText(hwnd), pid))
        return True

    win32gui.EnumWindows(callback, None)
    return found


def is_alive(hwnd: int) -> bool:
    return bool(win32gui.IsWindow(hwnd))


def flash_window(hwnd: int) -> None:
    """Mignięcie okna na pasku zadań — żeby rozpoznać, które to okno."""
    try:
        win32gui.FlashWindow(hwnd, True)
    except win32gui.error:
        pass
