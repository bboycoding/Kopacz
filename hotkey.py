"""Globalny skrót klawiszowy (działa bez fokusu na GUI)."""
import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1


class GlobalHotkey(threading.Thread):
    def __init__(self, vk: int, callback):
        super().__init__(daemon=True)
        self.vk = vk
        self.callback = callback
        self.registered = False
        self._thread_id = None
        self._ready = threading.Event()

    def run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        self.registered = bool(user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, self.vk))
        self._ready.set()
        if not self.registered:
            return
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.callback()
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)

    def wait_ready(self, timeout: float = 2.0) -> bool:
        self._ready.wait(timeout)
        return self.registered

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
