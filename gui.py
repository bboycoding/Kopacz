"""Okno aplikacji (customtkinter)."""
import threading
import time
from dataclasses import replace

import customtkinter as ctk

from config import Config, load_config, save_config
from hotkey import GlobalHotkey
from miner import Miner, run_action
from win_input import VK_F8, key_to_vk
from windows import McWindow, find_minecraft_windows, flash_window

BACKEND_LABELS = {
    "postmessage": "W tle (PostMessage)",
    "foreground": "Pierwszy plan (po kolei)",
}
CALIBRATION_BLOCKS = 10
TEST_SECONDS = 3.0
TICK_MS = 500


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class WindowRow:
    """Jeden wiersz listy okien MC."""

    def __init__(self, app: "App", parent, window: McWindow, row: int):
        self.window = window
        self.selected = ctk.BooleanVar(value=True)
        self.check = ctk.CTkCheckBox(parent, text=window.label, variable=self.selected)
        self.check.grid(row=row, column=0, sticky="w", padx=6, pady=4)
        self.status = ctk.CTkLabel(parent, text="Gotowy", width=210, anchor="w")
        self.status.grid(row=row, column=1, sticky="w", padx=6)
        self.button = ctk.CTkButton(parent, text="Start", width=70,
                                    command=lambda: app.toggle_window(window.hwnd))
        self.button.grid(row=row, column=2, padx=4)
        self.show = ctk.CTkButton(parent, text="Pokaż", width=60, fg_color="gray40",
                                  command=lambda: flash_window(window.hwnd))
        self.show.grid(row=row, column=3, padx=4)

    def destroy(self) -> None:
        for w in (self.check, self.status, self.button, self.show):
            w.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mój Kopacz")
        self.geometry("900x660")
        self.minsize(820, 600)

        self.cfg = load_config()
        self.miners: dict[int, Miner] = {}
        self.rows: dict[int, WindowRow] = {}
        self._action_stop = threading.Event()
        self._hotkey_pressed = threading.Event()

        self._build()
        self.refresh_windows()

        self.hotkey = GlobalHotkey(VK_F8, self._on_hotkey)
        self.hotkey.start()
        if not self.hotkey.wait_ready():
            self.set_info("Nie udało się zarejestrować F8 (zajęty przez inny program).", error=True)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(TICK_MS, self._tick)

    # ---------- budowa GUI ----------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkLabel(top, text="Okna Minecrafta", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)
        ctk.CTkButton(top, text="Odśwież", width=90, command=self.refresh_windows).pack(side="right", padx=6, pady=6)

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.empty_label = ctk.CTkLabel(self.list_frame, text="")

        settings = ctk.CTkFrame(self)
        settings.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        self.entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("blocks", "Ilość bloków", 0, 0),
            ("sec_per_block", "Sekundy na blok", 0, 2),
            ("turn_pause", "Pauza na zawrotce [s]", 0, 4),
            ("key_right", "Klawisz w prawo", 1, 0),
            ("key_left", "Klawisz w lewo", 1, 2),
            ("lmb_refresh_cycles", "Odśwież LPM co N cykli", 1, 4),
            ("wall_push_pct", "Dociąg do ściany [%]", 2, 0),
            ("jitter_pct", "Rozrzut czasu ±[%]", 2, 2),
        ]
        for key, label, r, c in fields:
            ctk.CTkLabel(settings, text=label).grid(row=r, column=c, sticky="e", padx=(10, 4), pady=4)
            e = ctk.CTkEntry(settings, width=80)
            e.insert(0, str(getattr(self.cfg, key)))
            e.grid(row=r, column=c + 1, sticky="w", pady=4)
            self.entries[key] = e

        ctk.CTkLabel(settings, text="Metoda inputu").grid(row=2, column=4, sticky="e", padx=(10, 4))
        self.backend_var = ctk.StringVar(value=BACKEND_LABELS[self.cfg.backend])
        ctk.CTkOptionMenu(settings, variable=self.backend_var, values=list(BACKEND_LABELS.values()),
                          width=200).grid(row=2, column=5, sticky="w")

        tools = ctk.CTkFrame(self)
        tools.grid(row=3, column=0, sticky="ew", padx=12, pady=6)
        ctk.CTkButton(tools, text=f"Test okna ({TEST_SECONDS:.0f} s)", command=self.test_window).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(tools, text=f"Kalibruj: idź {CALIBRATION_BLOCKS} bloków",
                      command=self.calibrate_walk).pack(side="left", padx=6)
        ctk.CTkLabel(tools, text="Przeszło bloków:").pack(side="left", padx=(12, 4))
        self.calib_entry = ctk.CTkEntry(tools, width=60)
        self.calib_entry.pack(side="left")
        ctk.CTkButton(tools, text="Przelicz", width=80, command=self.apply_calibration).pack(side="left", padx=6)

        actions = ctk.CTkFrame(self)
        actions.grid(row=4, column=0, sticky="ew", padx=12, pady=6)
        ctk.CTkButton(actions, text="▶ Start zaznaczone", fg_color="#2e7d32", hover_color="#1b5e20",
                      command=self.start_selected).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(actions, text="■ Stop wszystkie (F8)", fg_color="#c62828", hover_color="#8e0000",
                      command=self.stop_all).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Zapisz ustawienia", fg_color="gray40",
                      command=self.save_settings).pack(side="right", padx=6)

        self.info = ctk.CTkLabel(self, text="", anchor="w")
        self.info.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 10))

    # ---------- ustawienia ----------

    def set_info(self, text: str, error: bool = False) -> None:
        self.info.configure(text=text, text_color="#ef5350" if error else ("gray10", "gray90"))

    def read_settings(self) -> Config | None:
        try:
            def num(key, typ):
                return typ(self.entries[key].get().strip().replace(",", "."))

            backend = next(k for k, v in BACKEND_LABELS.items() if v == self.backend_var.get())
            cfg = Config(
                blocks=num("blocks", int),
                sec_per_block=num("sec_per_block", float),
                turn_pause=num("turn_pause", float),
                key_right=self.entries["key_right"].get().strip().upper(),
                key_left=self.entries["key_left"].get().strip().upper(),
                wall_push_pct=num("wall_push_pct", float),
                jitter_pct=num("jitter_pct", float),
                lmb_refresh_cycles=num("lmb_refresh_cycles", int),
                backend=backend,
            )
            cfg.validate()
            key_to_vk(cfg.key_right)
            key_to_vk(cfg.key_left)
        except ValueError as e:
            msg = str(e)
            if "invalid literal" in msg or "could not convert" in msg:
                msg = "Niepoprawna liczba w ustawieniach."
            self.set_info(msg, error=True)
            return None
        self.cfg = cfg
        return cfg

    def save_settings(self) -> None:
        cfg = self.read_settings()
        if cfg:
            save_config(cfg)
            self.set_info("Zapisano ustawienia.")

    # ---------- okna ----------

    def refresh_windows(self) -> None:
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        windows = find_minecraft_windows()
        # Okna z działającym kopaczem zostają na liście, nawet jeśli tytuł się zmienił.
        known = {w.hwnd for w in windows}
        windows += [m.window for h, m in self.miners.items() if h not in known and m.is_alive()]
        if not windows:
            self.empty_label.configure(text="Nie znaleziono okien Minecrafta. Uruchom grę i kliknij „Odśwież”.")
            self.empty_label.grid(row=0, column=0, columnspan=4, pady=20)
        else:
            self.empty_label.grid_forget()
        for i, w in enumerate(windows):
            self.rows[w.hwnd] = WindowRow(self, self.list_frame, w, i)
        self._update_rows()

    def _selected_windows(self) -> list[McWindow]:
        return [r.window for r in self.rows.values() if r.selected.get()]

    def _running(self, hwnd: int) -> bool:
        m = self.miners.get(hwnd)
        return bool(m and m.is_alive())

    # ---------- kopanie ----------

    def _start(self, window: McWindow, cfg: Config) -> None:
        if self._running(window.hwnd):
            return
        miner = Miner(window, replace(cfg))
        self.miners[window.hwnd] = miner
        miner.start()

    def toggle_window(self, hwnd: int) -> None:
        if self._running(hwnd):
            self.miners[hwnd].stop()
            return
        cfg = self.read_settings()
        if cfg:
            self._start(self.rows[hwnd].window, cfg)
            save_config(cfg)

    def start_selected(self) -> None:
        cfg = self.read_settings()
        if not cfg:
            return
        windows = self._selected_windows()
        if not windows:
            self.set_info("Zaznacz co najmniej jedno okno.", error=True)
            return
        save_config(cfg)
        for w in windows:
            self._start(w, cfg)
        self.set_info(f"Uruchomiono kopanie na {len(windows)} oknach. F8 = stop wszystkiego.")

    def stop_all(self) -> None:
        self._action_stop.set()
        for m in self.miners.values():
            m.stop()

    def _on_hotkey(self) -> None:
        # Wywoływane z wątku skrótu — tylko operacje bezpieczne wątkowo.
        self.stop_all()
        self._hotkey_pressed.set()

    # ---------- test i kalibracja ----------

    def _single_target(self) -> McWindow | None:
        windows = self._selected_windows()
        if len(windows) != 1:
            self.set_info("Do testu/kalibracji zaznacz dokładnie jedno okno.", error=True)
            return None
        if self._running(windows[0].hwnd):
            self.set_info("Najpierw zatrzymaj kopanie w tym oknie.", error=True)
            return None
        return windows[0]

    def _run_action(self, mine: bool, duration: float, done_msg: str) -> None:
        cfg = self.read_settings()
        window = self._single_target()
        if not cfg or not window:
            return
        self._action_stop = threading.Event()
        stop = self._action_stop
        vk = key_to_vk(cfg.key_right)

        def worker():
            run_action(window, cfg.backend, vk, duration, mine, stop)
            self.after(0, lambda: self.set_info(done_msg))

        self.set_info("Wykonuję… (przełącz się na okno MC, żeby obserwować; F8 przerywa)")
        threading.Thread(target=worker, daemon=True).start()

    def test_window(self) -> None:
        self._run_action(True, TEST_SECONDS,
                         "Test zakończony. Postać szła w prawo i kopała? Jeśli nie — zmień metodę inputu.")

    def calibrate_walk(self) -> None:
        cfg = self.read_settings()
        if not cfg:
            return
        self._run_action(False, CALIBRATION_BLOCKS * cfg.sec_per_block,
                         "Kalibracja zakończona. Wpisz, ile bloków faktycznie przeszła postać, i kliknij „Przelicz”.")

    def apply_calibration(self) -> None:
        cfg = self.read_settings()
        if not cfg:
            return
        try:
            walked = float(self.calib_entry.get().strip().replace(",", "."))
            if walked <= 0:
                raise ValueError
        except ValueError:
            self.set_info("Wpisz dodatnią liczbę przebytych bloków.", error=True)
            return
        new_spb = round(cfg.sec_per_block * CALIBRATION_BLOCKS / walked, 4)
        self.entries["sec_per_block"].delete(0, "end")
        self.entries["sec_per_block"].insert(0, str(new_spb))
        self.save_settings()
        self.set_info(f"Nowa wartość: {new_spb} s/blok (zapisano). Powtórz kalibrację, by sprawdzić.")

    # ---------- odświeżanie statusów ----------

    def _update_rows(self) -> None:
        for hwnd, row in self.rows.items():
            m = self.miners.get(hwnd)
            if m and m.is_alive():
                row.status.configure(text=f"{m.status} • cykle {m.cycles} • {_fmt_time(m.runtime)}")
                row.button.configure(text="Stop")
            else:
                row.status.configure(text=m.status if m else "Gotowy")
                row.button.configure(text="Start")

    def _tick(self) -> None:
        if self._hotkey_pressed.is_set():
            self._hotkey_pressed.clear()
            self.set_info(f"Zatrzymano wszystko klawiszem F8 ({time.strftime('%H:%M:%S')}).")
        self._update_rows()
        self.after(TICK_MS, self._tick)

    def on_close(self) -> None:
        self.stop_all()
        for m in self.miners.values():
            m.join(timeout=2)
        self.hotkey.stop()
        self.destroy()
