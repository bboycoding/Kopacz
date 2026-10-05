"""Okno aplikacji (customtkinter)."""
import threading
import time
import tkinter as tk
from dataclasses import replace

import customtkinter as ctk

import theme as T
from config import Config, load_config, save_config
from hotkey import GlobalHotkey
from miner import Miner, run_action
from win_input import VK_F8, key_to_vk
from windows import McWindow, find_minecraft_windows, flash_window

APP_VERSION = "1.2"
BACKEND_LABELS = {
    "postmessage": "W tle (PostMessage)",
    "foreground": "Pierwszy plan (po kolei)",
}
BACKEND_HINTS = {
    "postmessage": "Wysyłanie bezpośrednich komunikatów okna bez przejmowania kursora",
    "foreground": "Okno gry przejmuje fokus; przy wielu oknach ruch idzie po kolei",
}
CALIBRATION_BLOCKS = 10
TEST_SECONDS = 3.0
TICK_MS = 500
PULSE_MS = 100
TITLE_MAX = 48


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _dot(parent, color: str) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, width=8, height=8, corner_radius=4, fg_color=color)


class WindowRow:
    """Jeden wiersz listy okien MC (karta z checkboxem, statusem i przyciskami)."""

    def __init__(self, app: "App", parent, window: McWindow, row: int):
        self.app = app
        self.window = window
        self.selected = ctk.BooleanVar(value=True)
        self._state: tuple | None = None
        f = app.fonts

        self.frame = ctk.CTkFrame(parent, fg_color=T.SURFACE_ALT, corner_radius=T.RADIUS_CTRL)
        self.frame.grid(row=row, column=0, sticky="ew", pady=(0, T.GAP))
        self.frame.grid_columnconfigure(1, weight=1)

        self.check = ctk.CTkCheckBox(
            self.frame, text="", width=18, checkbox_width=18, checkbox_height=18, corner_radius=4,
            border_width=1, border_color=T.TEXT_MUTED, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            checkmark_color=T.ACCENT_TEXT, variable=self.selected, command=self._on_check)
        self.check.grid(row=0, column=0, padx=(12, 10), pady=10)

        names = ctk.CTkFrame(self.frame, fg_color="transparent")
        names.grid(row=0, column=1, sticky="ew")
        title = window.title if len(window.title) <= TITLE_MAX else window.title[:TITLE_MAX - 1] + "…"
        self.title = ctk.CTkLabel(names, text=title, font=f["headline_sm"], text_color=T.TEXT,
                                  anchor="w", height=20)
        self.title.pack(fill="x")
        self._sub_text = f"PID {window.pid} · hwnd {window.hwnd}"
        self.sub = ctk.CTkLabel(names, text=self._sub_text, font=f["body_sm"], text_color=T.TEXT_MUTED,
                                anchor="w", height=16)
        self.sub.pack(fill="x")

        # Plakietka statusu: kropka + tekst.
        self.chip = ctk.CTkFrame(self.frame, fg_color=T.BORDER, corner_radius=T.RADIUS_CHIP)
        self.chip.grid(row=0, column=2, padx=(T.GAP, 0))
        self.dot = _dot(self.chip, T.TEXT_MUTED)
        self.dot.pack(side="left", padx=(10, 6), pady=7)
        self.status = ctk.CTkLabel(self.chip, text="GOTOWY", font=f["label_sm"], text_color=T.TEXT_MUTED,
                                   height=14)
        self.status.pack(side="left", padx=(0, 10))

        # Ramka statystyk — widoczna tylko w trakcie kopania.
        self.stats = ctk.CTkFrame(self.frame, fg_color=T.INPUT_BG, corner_radius=T.RADIUS_CHIP)
        for text, color, font, padx, attr in (("Cykle:", T.TEXT_MUTED, f["body_sm"], (10, 0), None),
                                              ("0", T.TEXT, f["label"], (4, 0), "cycles"),
                                              ("│", T.BORDER, f["body_sm"], (8, 0), None),
                                              ("Czas:", T.TEXT_MUTED, f["body_sm"], (8, 0), None),
                                              ("00:00:00", T.ACCENT, f["label"], (4, 10), "runtime")):
            lbl = ctk.CTkLabel(self.stats, text=text, text_color=color, font=font, height=26)
            lbl.pack(side="left", padx=padx)
            if attr:
                setattr(self, attr, lbl)

        self.button = ctk.CTkButton(self.frame, width=84, height=30, corner_radius=T.RADIUS_CTRL,
                                    font=f["label"], command=lambda: app.toggle_window(window.hwnd))
        self.button.grid(row=0, column=4, padx=(T.GAP, 4))
        self.show = app.secondary_button(self.frame, f"{T.ICONS['show']}  Pokaż",
                                         lambda: flash_window(window.hwnd), width=84)
        self.show.grid(row=0, column=5, padx=(0, 12))
        self._style_button(running=False)

    def _on_check(self) -> None:
        self.title.configure(text_color=T.TEXT if self.selected.get() else T.TEXT_MUTED)

    def _style_button(self, running: bool) -> None:
        if running:
            self.button.configure(text=f"{T.ICONS['stop']}  Stop", fg_color=T.DANGER,
                                  hover_color=T.DANGER_HOVER, text_color=T.DANGER_TEXT)
        else:
            self.button.configure(text=f"{T.ICONS['start']}  Start", fg_color=T.ACCENT,
                                  hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT)

    def show_state(self, status: str, running: bool, cycles: int = 0, runtime: float = 0.0) -> None:
        """Wywoływane z _tick (główny wątek). Przerysowuje tylko to, co się zmieniło."""
        if running:
            self.cycles.configure(text=str(cycles))
            self.runtime.configure(text=_fmt_time(runtime))
        if self._state == (status, running):
            return
        self._state = (status, running)

        error = status.startswith("Błąd")
        color = T.status_color(status)
        mining = running and status == "Kopie"
        self.status.configure(text="BŁĄD" if error else status.upper(),
                              text_color=T.ACCENT if mining else (color if error else T.TEXT_MUTED))
        self.chip.configure(fg_color=T.CHIP_ACTIVE if mining else T.BORDER)
        self.dot.configure(fg_color=color)
        self.sub.configure(text=status if error else self._sub_text,
                           text_color=T.DANGER if error else T.TEXT_MUTED)
        if mining:
            self.app.pulse_add(self.dot, T.ACCENT, T.CHIP_ACTIVE)
        else:
            self.app.pulse_remove(self.dot)
        if running:
            self.stats.grid(row=0, column=3, padx=(T.GAP, 0))
        else:
            self.stats.grid_remove()
        self._style_button(running)

    def destroy(self) -> None:
        self.app.pulse_remove(self.dot)
        self.frame.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=T.APP_BG)
        self.title("Kopacz Julci")
        self.geometry("980x860")
        self.minsize(900, 700)

        self.cfg = load_config()
        self.miners: dict[int, Miner] = {}
        self.rows: dict[int, WindowRow] = {}
        self._action_stop = threading.Event()
        self._hotkey_pressed = threading.Event()

        self.fonts = T.fonts(self)
        self._icon_family = T.icon_font_family(self)
        self._pulsing: dict[ctk.CTkFrame, list[str]] = {}
        self._pulse_step = 0
        self._pulse_job = None
        self._info_color = T.ACCENT

        self._build()
        self.refresh_windows()

        self.hotkey = GlobalHotkey(VK_F8, self._on_hotkey)
        self.hotkey.start()
        if not self.hotkey.wait_ready():
            self.set_info("Nie udało się zarejestrować F8 (zajęty przez inny program).", error=True)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(TICK_MS, self._tick)
        self._pulse_job = self.after(PULSE_MS, self._pulse)

    # ---------- elementy wspólne ----------

    def secondary_button(self, parent, text: str, command, width: int = 0, height: int = 30) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, command=command, width=width, height=height,
                             corner_radius=T.RADIUS_CTRL, font=self.fonts["label"],
                             fg_color=T.SURFACE_ALT, hover_color=T.BORDER, text_color=T.TEXT,
                             border_width=1, border_color=T.BORDER)

    def _card(self, parent, **kw) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=T.CARD, corner_radius=T.RADIUS_CARD,
                            border_width=1, border_color=T.BORDER, **kw)

    def _entry(self, parent, width: int = 140, **kw) -> ctk.CTkEntry:
        e = ctk.CTkEntry(parent, width=width, height=30, corner_radius=T.RADIUS_CTRL, border_width=1,
                         border_color=T.BORDER, fg_color=T.INPUT_BG, text_color=T.TEXT,
                         font=self.fonts["label"], **kw)
        e.bind("<FocusIn>", lambda _: e.configure(border_color=T.ACCENT))
        e.bind("<FocusOut>", lambda _: e.configure(border_color=T.BORDER))
        return e

    def _section_icon(self, parent, name: str, color: str = T.ACCENT, size: int = 14):
        """Ikona z fontu systemowego Windows albo None, gdy fontu brak."""
        if not self._icon_family:
            return None
        return ctk.CTkLabel(parent, text=T.SECTION_ICONS[name], text_color=color,
                            font=ctk.CTkFont(family=self._icon_family, size=size))

    def _logo(self, parent) -> ctk.CTkFrame:
        box = ctk.CTkFrame(parent, width=40, height=40, fg_color=T.CARD, corner_radius=T.RADIUS_CTRL,
                           border_width=1, border_color=T.BORDER)
        box.grid_propagate(False)
        scale = ctk.ScalingTracker.get_window_scaling(self)
        px = max(2, round(3 * scale))
        size = px * len(T.PICKAXE)
        canvas = tk.Canvas(box, width=size, height=size, bg=T.CARD, highlightthickness=0, bd=0)
        colors = {"H": T.ACCENT, "W": T.PICK_HANDLE}
        for y, line in enumerate(T.PICKAXE):
            for x, ch in enumerate(line):
                if ch in colors:
                    canvas.create_rectangle(x * px, y * px, (x + 1) * px, (y + 1) * px,
                                            fill=colors[ch], width=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        return box

    # ---------- budowa GUI ----------

    def _build(self) -> None:
        f = self.fonts
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        outer = {"padx": T.PAD}

        # --- nagłówek aplikacji ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(12, 8), **outer)
        header.grid_columnconfigure(1, weight=1)
        self._logo(header).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title_row, text="Kopacz Julci", font=f["headline_lg"], text_color=T.TEXT,
                     height=28).pack(side="left")
        ctk.CTkLabel(title_row, text=f"V{APP_VERSION}", font=f["label_sm"], text_color=T.ACCENT,
                     fg_color=T.BORDER, corner_radius=4, height=18, width=34).pack(side="left", padx=8)
        ctk.CTkLabel(header, text="Bot AFK do kopania na stoniarkach", font=f["body_sm"],
                     text_color=T.TEXT_MUTED, height=16).grid(row=1, column=1, sticky="w")
        self.secondary_button(header, f"{T.ICONS['refresh']}  Odśwież", self.refresh_windows,
                              width=110, height=34).grid(row=0, column=2, rowspan=2)

        # --- karta: okna Minecrafta ---
        windows_card = self._card(self)
        windows_card.grid(row=1, column=0, sticky="nsew", pady=(0, T.GAP), **outer)
        windows_card.grid_columnconfigure(0, weight=1)
        windows_card.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(windows_card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=T.PAD, pady=(12, 8))
        icon = self._section_icon(bar, "windows", size=16)
        if icon:
            icon.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(bar, text="Okna Minecrafta", font=f["headline_sm"], text_color=T.TEXT).pack(side="left")
        self.count_badge = ctk.CTkLabel(bar, text="", font=f["label_md"], text_color=T.ACCENT,
                                        fg_color=T.BORDER, corner_radius=4, height=20)
        self.count_badge.pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(
            windows_card, height=110, fg_color=T.CARD, corner_radius=0,
            scrollbar_button_color=T.BORDER, scrollbar_button_hover_color=T.TEXT_MUTED)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=(T.PAD - 4, 4), pady=(0, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.empty_label = ctk.CTkLabel(self.list_frame, text="", font=f["body"], text_color=T.TEXT_MUTED)

        # --- karta: ustawienia ---
        settings = self._card(self)
        settings.grid(row=2, column=0, sticky="ew", pady=(0, T.GAP), **outer)
        settings.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        ctk.CTkLabel(settings, text="USTAWIENIA", font=f["label"], text_color=T.TEXT, height=18).grid(
            row=0, column=0, sticky="w", padx=T.PAD, pady=(10, 6))
        ctk.CTkLabel(settings, text="Konfiguracja czasowa i klawisze", font=f["label_sm"],
                     text_color=T.TEXT_MUTED, height=18).grid(row=0, column=2, sticky="e", padx=T.PAD)

        self.entries: dict[str, ctk.CTkEntry] = {}
        columns = [
            ("move", "Ruch", [("blocks", "Ilość bloków"),
                              ("sec_per_block", "Sekundy na blok"),
                              ("turn_pause", "Pauza na zawrotce [s]")]),
            ("keys", "Klawisze", [("key_right", "Klawisz w prawo"),
                                  ("key_left", "Klawisz w lewo")]),
            ("stability", "Stabilność", [("lmb_refresh_cycles", "Odśwież LPM co N cykli"),
                                         ("wall_push_pct", "Dociąg do ściany [%]"),
                                         ("jitter_pct", "Rozrzut czasu ±[%]")]),
        ]
        for col, (icon_name, heading, fields) in enumerate(columns):
            panel = ctk.CTkFrame(settings, fg_color=T.SURFACE_ALT, corner_radius=T.RADIUS_CTRL)
            panel.grid(row=1, column=col, sticky="nsew", pady=(0, 12),
                       padx=(T.PAD if col == 0 else T.GAP // 2, T.PAD if col == 2 else T.GAP // 2))
            head = ctk.CTkFrame(panel, fg_color="transparent")
            head.pack(fill="x", padx=12, pady=(8, 0))
            icon = self._section_icon(head, icon_name, size=12)
            if icon:
                icon.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(head, text=heading.upper(), font=f["label_md"], text_color=T.ACCENT,
                         height=16).pack(side="left")
            for key, label in fields:
                ctk.CTkLabel(panel, text=label, font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w",
                             height=16).pack(fill="x", padx=12, pady=(5, 2))
                is_key = key.startswith("key_")
                e = self._entry(panel, justify="center" if is_key else "left")
                e.insert(0, str(getattr(self.cfg, key)))
                e.pack(fill="x", padx=12)
                if is_key:
                    ctk.CTkLabel(e, text="KEY", font=f["label_sm"], text_color=T.TEXT_MUTED,
                                 fg_color=T.INPUT_BG, height=14, width=24).place(relx=1, x=-8, rely=0.5,
                                                                               anchor="e")
                if key == "wall_push_pct":
                    ctk.CTkLabel(panel, text="Eliminuje dryf postaci przy wielogodzinnej pracy",
                                 font=f["label_sm"], text_color=T.TEXT_MUTED, anchor="w", justify="left",
                                 wraplength=200, height=14).pack(fill="x", padx=12, pady=(3, 0))
                self.entries[key] = e
            if icon_name == "keys":
                # Metoda inputu wypełnia wolny dół kolumny klawiszy (oszczędza pełny rząd przy 900×700).
                ctk.CTkLabel(panel, text="Metoda inputu", font=f["body_sm"], text_color=T.TEXT_MUTED,
                             anchor="w", height=16).pack(fill="x", padx=12, pady=(5, 2))
                self.backend_var = ctk.StringVar(value=BACKEND_LABELS[self.cfg.backend])
                ctk.CTkOptionMenu(panel, variable=self.backend_var, values=list(BACKEND_LABELS.values()),
                                  height=30, corner_radius=T.RADIUS_CTRL, font=f["label"],
                                  fg_color=T.INPUT_BG, button_color=T.INPUT_BG, button_hover_color=T.BORDER,
                                  text_color=T.TEXT, dropdown_font=f["body"], dropdown_fg_color=T.SURFACE_ALT,
                                  dropdown_hover_color=T.BORDER, dropdown_text_color=T.TEXT,
                                  command=self._on_backend_change).pack(fill="x", padx=12)
                self.backend_hint = ctk.CTkLabel(panel, text=BACKEND_HINTS[self.cfg.backend],
                                                 font=f["label_sm"], text_color=T.TEXT_MUTED, anchor="w",
                                                 justify="left", wraplength=200, height=14)
                self.backend_hint.pack(fill="x", padx=12, pady=(3, 0))
            ctk.CTkFrame(panel, fg_color="transparent", height=10).pack()

        # --- pasek: test i kalibracja ---
        tools = self._card(self)
        tools.grid(row=3, column=0, sticky="ew", pady=(0, T.GAP), **outer)
        self.secondary_button(tools, f"{T.ICONS['test']}  Test okna ({TEST_SECONDS:.0f} s)",
                              self.test_window).pack(side="left", padx=(12, 4), pady=10)
        self.secondary_button(tools, f"{T.ICONS['calibrate']}  Kalibruj: idź {CALIBRATION_BLOCKS} bloków",
                              self.calibrate_walk).pack(side="left", padx=4)
        ctk.CTkButton(tools, text="Przelicz", width=84, height=30, corner_radius=T.RADIUS_CTRL,
                      font=f["label"], fg_color=T.ACCENT_TINT, hover_color=T.ACCENT_TINT_HOVER,
                      text_color=T.ACCENT, command=self.apply_calibration).pack(side="right", padx=(6, 12))
        self.calib_entry = self._entry(tools, width=64, justify="center")
        self.calib_entry.pack(side="right")
        ctk.CTkLabel(tools, text="Przeszło bloków:", font=f["body_sm"],
                     text_color=T.TEXT_MUTED).pack(side="right", padx=(12, 8))

        # --- pasek akcji ---
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", pady=(4, T.GAP + 2), **outer)
        ctk.CTkButton(actions, text=f"{T.ICONS['start']}  Start zaznaczone", height=40,
                      corner_radius=T.RADIUS_CTRL, font=f["headline_sm"], fg_color=T.ACCENT,
                      hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.start_selected).pack(side="left")
        ctk.CTkButton(actions, text=f"{T.ICONS['stop']}  Stop wszystkie (F8)", height=40,
                      corner_radius=T.RADIUS_CTRL, font=f["headline_sm"], fg_color=T.DANGER,
                      hover_color=T.DANGER_HOVER, text_color=T.DANGER_TEXT,
                      command=self.stop_all).pack(side="left", padx=10)
        self.secondary_button(actions, f"{T.ICONS['save']}  Zapisz ustawienia", self.save_settings,
                              height=40).pack(side="right")

        # --- pasek informacji ---
        info_bar = ctk.CTkFrame(self, fg_color=T.INPUT_BG, corner_radius=T.RADIUS_CTRL,
                                border_width=1, border_color=T.BORDER)
        info_bar.grid(row=5, column=0, sticky="ew", pady=(0, 12), **outer)
        self.info_dot = _dot(info_bar, T.ACCENT)
        self.info_dot.pack(side="left", padx=(12, 8), pady=9)
        self.info = ctk.CTkLabel(info_bar, text="", anchor="w", font=f["body_sm"], text_color=T.TEXT,
                                 height=16)
        self.info.pack(side="left", fill="x", expand=True, padx=(0, 12))

    def _on_backend_change(self, label: str) -> None:
        backend = next(k for k, v in BACKEND_LABELS.items() if v == label)
        self.backend_hint.configure(text=BACKEND_HINTS[backend])

    # ---------- animacja (główny wątek) ----------

    def pulse_add(self, dot: ctk.CTkFrame, color: str, background: str) -> None:
        self._pulsing[dot] = T.pulse_colors(color, background)

    def pulse_remove(self, dot: ctk.CTkFrame) -> None:
        self._pulsing.pop(dot, None)

    def _pulse(self) -> None:
        # Czyta wyłącznie stan GUI (słownik kropek ustawiany w _update_rows), nigdy wątków kopaczy.
        self._pulse_step += 1
        for dot, colors in self._pulsing.items():
            dot.configure(fg_color=colors[self._pulse_step % len(colors)])
        self._pulse_job = self.after(PULSE_MS, self._pulse)

    # ---------- ustawienia ----------

    def set_info(self, text: str, error: bool = False) -> None:
        self.info.configure(text=text, text_color=T.DANGER if error else T.TEXT)
        self._info_color = T.DANGER if error else T.ACCENT
        self.info_dot.configure(fg_color=self._info_color)
        if self.info_dot in self._pulsing:
            self.pulse_add(self.info_dot, self._info_color, T.INPUT_BG)

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
            self.empty_label.grid(row=0, column=0, pady=20)
        else:
            self.empty_label.grid_forget()
        self.count_badge.configure(text=f"  {len(windows)} wykryte  ")
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
        any_mining = False
        for hwnd, row in self.rows.items():
            m = self.miners.get(hwnd)
            if m and m.is_alive():
                status = m.status
                row.show_state(status, True, m.cycles, m.runtime)
                any_mining |= status == "Kopie"
            else:
                row.show_state(m.status if m else "Gotowy", False)
        # Kropka paska informacji pulsuje, gdy cokolwiek kopie.
        if any_mining and self.info_dot not in self._pulsing:
            self.pulse_add(self.info_dot, self._info_color, T.INPUT_BG)
        elif not any_mining and self.info_dot in self._pulsing:
            self.pulse_remove(self.info_dot)
            self.info_dot.configure(fg_color=self._info_color)

    def _tick(self) -> None:
        if self._hotkey_pressed.is_set():
            self._hotkey_pressed.clear()
            self.set_info(f"Zatrzymano wszystko klawiszem F8 ({time.strftime('%H:%M:%S')}).")
        self._update_rows()
        self.after(TICK_MS, self._tick)

    def on_close(self) -> None:
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
        self.stop_all()
        for m in self.miners.values():
            m.join(timeout=2)
        self.hotkey.stop()
        self.destroy()
