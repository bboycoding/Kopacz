"""Zakładka „Serwer”: profile serwerów (komendy, wzorce logu) i sprawdzanie wzorców na prawdziwym logu."""
import os
import re
from tkinter import filedialog

import customtkinter as ctk

import launcher as L
import log_watcher as W
import presets
import theme as T
from config import ServerProfile

NONE = "(brak profili)"
PATTERN_FIELDS = (
    ("pat_login_prompt", "Prośba o logowanie", "Linia, w której serwer prosi o /login."),
    ("pat_logged_in", "Zalogowano", "Linia potwierdzająca udane logowanie."),
    ("pat_lobby", "Lobby (wybór trybu gry)", "Linia widoczna po wejściu do lobby."),
    ("pat_in_game", "Wejście do gry", "Linia widoczna po wejściu do właściwego trybu (np. powitanie SkyBlocka)."),
    ("pat_moved_to_lobby", "Przeniesienie do lobby", "Np. po restarcie trybu gry; klient zostaje połączony."),
    ("pat_ban", "Ban", "Po tej linii bot nie próbuje wracać na serwer, tylko wysyła alert."),
    ("pat_player_chat", "Czat graczy (ignorowany)", "Linie pasujące tutaj nigdy nie wywołują zdarzeń."),
    ("pat_reward", "Zdobycie nagrody (licznik kluczy)",
     "Komunikat, gdy TO konto zdobędzie nagrodę, np. Gracz {nick} zdobył klucz — {nick} zostanie zastąpiony "
     "nickiem konta. Na tej podstawie Discord dostaje podsumowanie kluczy."),
)
KIND_NAMES = {
    W.CONNECTING: "Łączenie", W.DISCONNECTED: "Rozłączenie", W.STOPPING: "Zamknięcie gry",
    W.LOGIN_PROMPT: "Prośba o logowanie", W.LOGGED_IN: "Zalogowano", W.LOBBY: "Lobby",
    W.IN_GAME: "Wejście do gry", W.MOVED_TO_LOBBY: "Przeniesienie do lobby", W.BAN: "Ban",
}


class ServerTab:
    def __init__(self, app, parent):
        self.app = app
        self.current_id: str | None = None
        f = app.fonts
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        ctk.CTkLabel(bar, text="Profil:", font=f["label"], text_color=T.TEXT).pack(side="left")
        self.picker = ctk.CTkOptionMenu(
            bar, values=[NONE], width=220, height=32, corner_radius=T.RADIUS_CTRL, font=f["label"],
            fg_color=T.INPUT_BG, button_color=T.INPUT_BG, button_hover_color=T.BORDER, text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE_ALT, dropdown_hover_color=T.BORDER, dropdown_text_color=T.TEXT,
            command=self._on_pick)
        self.picker.pack(side="left", padx=8)
        app.secondary_button(bar, "+ bfsmc.pl (przykład)", lambda: self.add_preset("bfsmc"), height=32).pack(
            side="left", padx=(8, 4))
        app.secondary_button(bar, "+ Pusty profil", lambda: self.add_preset("vanilla"), height=32).pack(side="left")
        app.secondary_button(bar, "Usuń profil", self.delete, height=32).pack(side="right")

        card = app._card(parent)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        form = ctk.CTkScrollableFrame(card, fg_color=T.CARD, corner_radius=0, scrollbar_button_color=T.BORDER,
                                      scrollbar_button_hover_color=T.TEXT_MUTED)
        form.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        form.grid_columnconfigure(0, weight=1)
        self.form = form

        def caption(text: str, hint: str = "") -> None:
            ctk.CTkLabel(form, text=text, font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w").pack(
                fill="x", padx=8, pady=(8, 1))
            if hint:
                ctk.CTkLabel(form, text=hint, font=f["label_sm"], text_color=T.TEXT_MUTED, anchor="w",
                             justify="left", wraplength=780).pack(fill="x", padx=8)

        def entry() -> ctk.CTkEntry:
            e = app._entry(form, width=0)
            e.pack(fill="x", padx=8)
            return e

        caption("Nazwa profilu")
        self.name = entry()
        caption("Adres serwera", "Używany przy ponownym uruchomieniu instancji (argument -s launchera).")
        self.address = entry()
        caption("Komenda logowania", "Znacznik {password} zostanie zastąpiony hasłem konta. Puste = serwer bez logowania.")
        self.login_command = entry()
        caption("Komendy z lobby do gry (po jednej w linii)", "Np. /server skyblock — wysyłane po przeniesieniu do lobby.")
        self.lobby_commands = ctk.CTkTextbox(form, height=60, corner_radius=T.RADIUS_CTRL, border_width=1,
                                             border_color=T.BORDER, fg_color=T.INPUT_BG, text_color=T.TEXT,
                                             font=f["label"])
        self.lobby_commands.pack(fill="x", padx=8)

        ctk.CTkLabel(form, text="WZORCE LOGU (wyrażenia regularne)", font=f["label_md"], text_color=T.ACCENT,
                     anchor="w").pack(fill="x", padx=8, pady=(16, 0))
        self.patterns: dict[str, ctk.CTkEntry] = {}
        for attr, title, hint in PATTERN_FIELDS:
            caption(title, hint)
            self.patterns[attr] = entry()

        ctk.CTkLabel(form, text="SPRAWDŹ WZORCE NA LOGU", font=f["label_md"], text_color=T.ACCENT,
                     anchor="w").pack(fill="x", padx=8, pady=(18, 0))
        caption("", "Wskaż latest.log albo spakowany log (.log.gz). Program pokaże, ile zdarzeń wykrył "
                    "wzorcami z formularza (także niezapisanymi).")
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(4, 0))
        app.secondary_button(row, "Wybierz log i sprawdź…", self.check_log, height=32).pack(side="left")
        self.result = ctk.CTkTextbox(form, height=190, corner_radius=T.RADIUS_CTRL, border_width=1,
                                     border_color=T.BORDER, fg_color=T.INPUT_BG, text_color=T.TEXT,
                                     font=ctk.CTkFont(family="Consolas", size=12), state="disabled")
        self.result.pack(fill="x", padx=8, pady=(8, 8))

        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(T.GAP, 0))
        ctk.CTkButton(footer, text="Zapisz profil", height=36, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.save).pack(side="left")
        self.refresh()

    # ---------- lista profili ----------

    def refresh(self, select: str | None = None) -> None:
        servers = self.app.cfg.servers
        names = [s.name for s in servers] or [NONE]
        self.picker.configure(values=names)
        target = next((s for s in servers if s.id == (select or self.current_id)), servers[0] if servers else None)
        if target:
            self.picker.set(target.name)
            self._load(target)
        else:
            self.picker.set(NONE)
            self._load(ServerProfile(id="", name=""))
            self.current_id = None

    def _on_pick(self, name: str) -> None:
        profile = next((s for s in self.app.cfg.servers if s.name == name), None)
        if profile:
            self._load(profile)

    def _set(self, entry: ctk.CTkEntry, text: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, text)

    def _load(self, p: ServerProfile) -> None:
        self.current_id = p.id or None
        self._set(self.name, p.name)
        self._set(self.address, p.address)
        self._set(self.login_command, p.login_command)
        self.lobby_commands.delete("1.0", "end")
        self.lobby_commands.insert("1.0", "\n".join(p.lobby_commands))
        for attr, entry in self.patterns.items():
            self._set(entry, getattr(p, attr))

    def _read(self) -> ServerProfile:
        base = next((s for s in self.app.cfg.servers if s.id == self.current_id), None)
        kwargs = {attr: e.get().strip() for attr, e in self.patterns.items()}
        return ServerProfile(
            id=self.current_id or self.app.new_server_id(self.name.get()),
            name=self.name.get().strip() or (base.name if base else "Serwer"),
            address=self.address.get().strip(),
            login_command=self.login_command.get().strip(),
            lobby_commands=[ln.strip() for ln in self.lobby_commands.get("1.0", "end").splitlines() if ln.strip()],
            **kwargs)

    # ---------- akcje ----------

    def add_preset(self, preset_id: str) -> None:
        profile = presets.new_profile(preset_id, self.app.new_server_id(presets.PRESETS[preset_id].name))
        error = self.app.save_server(profile, preset=preset_id)
        if error:
            self.app.set_info(error, error=True)
        else:
            self.refresh(select=profile.id)

    def save(self) -> None:
        profile = self._read()
        error = self.app.save_server(profile)
        if error:
            self.app.set_info(error, error=True)
        else:
            self.refresh(select=profile.id)

    def delete(self) -> None:
        if not self.current_id:
            return
        error = self.app.delete_server(self.current_id)
        if error:
            self.app.set_info(error, error=True)
        else:
            self.current_id = None
            self.refresh()

    def check_log(self) -> None:
        profile = self._read()
        for attr, _, _ in PATTERN_FIELDS:
            pattern = getattr(profile, attr)
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as e:
                    self.app.set_info(f"Niepoprawny wzorzec „{attr}”: {e}", error=True)
                    return
        initial = ""
        for inst in self.app.instances:
            folder = os.path.dirname(inst.log_path)
            if os.path.isdir(folder):
                initial = folder
                break
        path = filedialog.askopenfilename(
            parent=self.app, title="Wskaż log do sprawdzenia", initialdir=initial or None,
            filetypes=[("Logi Minecrafta", "*.log *.gz"), ("Wszystkie pliki", "*.*")])
        if not path:
            return
        try:
            counts, examples = W.summarize(path, profile)
        except OSError as e:
            self.app.set_info(f"Nie udało się odczytać logu: {e}", error=True)
            return
        lines = [f"Plik: {os.path.basename(path)}", ""]
        if not counts:
            lines.append("Nie wykryto żadnych zdarzeń. Sprawdź wzorce albo wybierz inny log.")
        for kind in W.EVENT_KINDS:
            if kind in counts:
                lines.append(f"{KIND_NAMES[kind]}: {counts[kind]}")
                lines.extend(f"    {ex}" for ex in examples[kind])
        missing = [KIND_NAMES[k] for k in (W.LOBBY, W.IN_GAME, W.LOGGED_IN) if k not in counts]
        if counts and missing:
            lines += ["", "Nie wykryto: " + ", ".join(missing) + " (może ich nie ma w tym logu albo wzorzec nie pasuje)."]
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("1.0", "\n".join(lines))
        self.result.configure(state="disabled")
