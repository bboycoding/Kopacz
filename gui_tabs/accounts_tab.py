"""Zakładka „Konta”: lista kont i okno edycji konta."""
from tkinter import messagebox

import customtkinter as ctk

import theme as T
from config import AccountCfg, ChatCommand

NO_SERVER = "(brak profili serwera)"
MISSED_LABELS = {"defer": "Odłóż", "skip": "Pomiń"}


class AccountsTab:
    def __init__(self, app, parent):
        self.app = app
        f = app.fonts
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))
        ctk.CTkLabel(bar, text="Konta", font=f["headline_sm"], text_color=T.TEXT).pack(side="left")
        ctk.CTkButton(bar, text="+  Dodaj konto", height=32, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=lambda: AccountEditor(app, None)).pack(side="right")

        card = app._card(parent)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        self.list = ctk.CTkScrollableFrame(card, fg_color=T.CARD, corner_radius=0,
                                           scrollbar_button_color=T.BORDER,
                                           scrollbar_button_hover_color=T.TEXT_MUTED)
        self.list.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.list.grid_columnconfigure(0, weight=1)
        self.refresh()

    def refresh(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()
        app = self.app
        f = app.fonts
        if not app.cfg.accounts:
            ctk.CTkLabel(self.list, font=f["body"], text_color=T.TEXT_MUTED, justify="center",
                         text="Brak kont. Kliknij „Dodaj konto” i wskaż instancję launchera,\n"
                              "nick i (opcjonalnie) hasło oraz komendy.").grid(row=0, column=0, pady=30)
            return
        windows_by_instance = set(app.window_instance.values())
        for i, acc in enumerate(app.cfg.accounts):
            row = ctk.CTkFrame(self.list, fg_color=T.SURFACE_ALT, corner_radius=T.RADIUS_CTRL)
            row.grid(row=i, column=0, sticky="ew", pady=(0, T.GAP))
            row.grid_columnconfigure(0, weight=1)
            names = ctk.CTkFrame(row, fg_color="transparent")
            names.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
            title = acc.name or acc.nick or acc.instance_id
            ctk.CTkLabel(names, text=title + ("" if acc.enabled else "  (wyłączone)"), anchor="w",
                         font=f["headline_sm"], text_color=T.TEXT if acc.enabled else T.TEXT_MUTED,
                         height=20).pack(fill="x")
            window = "okno wykryte" if acc.instance_id in windows_by_instance else "brak okna"
            detail = f"nick {acc.nick or '—'} · instancja {acc.instance_id or '—'} · {window}"
            ctk.CTkLabel(names, text=detail, anchor="w", font=f["body_sm"], text_color=T.TEXT_MUTED,
                         height=16).pack(fill="x")
            app.secondary_button(row, "Edytuj", lambda a=acc: AccountEditor(app, a), width=72).grid(
                row=0, column=1, padx=(8, 4))
            app.secondary_button(row, "Usuń", lambda a=acc: self._delete(a), width=72).grid(
                row=0, column=2, padx=(0, 12))

    def _delete(self, acc: AccountCfg) -> None:
        if messagebox.askyesno("Usuń konto", f"Usunąć konto „{acc.name or acc.nick}”?\n"
                                             "Zapisane hasło też zostanie usunięte.", parent=self.app):
            self.app.delete_account(acc.id)


class AccountEditor(ctk.CTkToplevel):
    def __init__(self, app, account: AccountCfg | None):
        super().__init__(app, fg_color=T.APP_BG)
        self.app = app
        self.original = account
        self.title("Edycja konta" if account else "Nowe konto")
        self.geometry("680x820")
        self.minsize(620, 560)
        self.transient(app)
        f = app.fonts
        acc = account or AccountCfg()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        form = ctk.CTkScrollableFrame(self, fg_color=T.CARD, corner_radius=T.RADIUS_CARD,
                                      scrollbar_button_color=T.BORDER)
        form.grid(row=0, column=0, sticky="nsew", padx=T.PAD, pady=(T.PAD, T.GAP))
        form.grid_columnconfigure(0, weight=1)
        self.form = form

        def label(text: str, hint: str = "") -> None:
            ctk.CTkLabel(form, text=text, font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w").pack(
                fill="x", padx=12, pady=(10, 2))
            if hint:
                ctk.CTkLabel(form, text=hint, font=f["label_sm"], text_color=T.TEXT_MUTED, anchor="w",
                             justify="left", wraplength=600).pack(fill="x", padx=12, pady=(0, 2))

        def combo(values: list[str], value: str) -> ctk.CTkComboBox:
            c = ctk.CTkComboBox(form, values=values or [""], height=30, corner_radius=T.RADIUS_CTRL,
                                border_width=1, border_color=T.BORDER, fg_color=T.INPUT_BG,
                                button_color=T.BORDER, button_hover_color=T.TEXT_MUTED, text_color=T.TEXT,
                                font=f["label"], dropdown_font=f["body"], dropdown_fg_color=T.SURFACE_ALT,
                                dropdown_text_color=T.TEXT, dropdown_hover_color=T.BORDER)
            c.set(value)
            c.pack(fill="x", padx=12)
            return c

        label("Nazwa konta (do wyświetlania)")
        self.name = app._entry(form, width=0)
        self.name.insert(0, acc.name)
        self.name.pack(fill="x", padx=12)

        label("Instancja launchera", "Wybierz z listy wykrytych (Zaawansowane → Wykryj) albo wpisz ID "
                                     "(nazwa folderu instancji).")
        self.instance = combo([i.id for i in app.instances], acc.instance_id)

        label("Nick w grze", "Używany też przy ponownym uruchomieniu instancji (-a nick).")
        self.nick = combo(app.profile_names, acc.nick)

        label("Własna ścieżka do latest.log (opcjonalnie)", "Puste = ścieżka wyliczona z instancji.")
        self.log_path = app._entry(form, width=0)
        self.log_path.insert(0, acc.log_path)
        self.log_path.pack(fill="x", padx=12)

        label("Profil serwera")
        self._servers = {s.name: s.id for s in app.cfg.servers}
        current = next((s.name for s in app.cfg.servers if s.id == acc.server_id), None)
        self.server = ctk.CTkOptionMenu(form, values=list(self._servers) or [NO_SERVER], height=30,
                                        corner_radius=T.RADIUS_CTRL, font=f["label"], fg_color=T.INPUT_BG,
                                        button_color=T.INPUT_BG, button_hover_color=T.BORDER,
                                        text_color=T.TEXT, dropdown_fg_color=T.SURFACE_ALT,
                                        dropdown_hover_color=T.BORDER, dropdown_text_color=T.TEXT)
        self.server.set(current or (next(iter(self._servers)) if self._servers else NO_SERVER))
        self.server.pack(fill="x", padx=12)

        label("Hasło do logowania na serwerze",
              "Przechowywane szyfrowo (Windows DPAPI). Wstawiane tylko w miejsce {password} "
              "w komendzie logowania profilu serwera.")
        pw_row = ctk.CTkFrame(form, fg_color="transparent")
        pw_row.pack(fill="x", padx=12)
        pw_row.grid_columnconfigure(0, weight=1)
        self.password = app._entry(pw_row, width=0, show="•")
        self.password.insert(0, app.secrets.password_for(acc.id) if account else "")
        self.password.grid(row=0, column=0, sticky="ew")
        self.show_pw = ctk.CTkCheckBox(pw_row, text="Pokaż", width=60, checkbox_width=18, checkbox_height=18,
                                       font=f["body_sm"], text_color=T.TEXT_MUTED, fg_color=T.ACCENT,
                                       hover_color=T.ACCENT_HOVER, checkmark_color=T.ACCENT_TEXT,
                                       command=lambda: self.password.configure(
                                           show="" if self.show_pw.get() else "•"))
        self.show_pw.grid(row=0, column=1, padx=(10, 0))

        label("Komenda po powrocie na serwer (opcjonalnie)",
              "Zwykle puste: po wejściu do trybu postać jest od razu na miejscu. Wpisz np. /home 1 tylko wtedy, "
              "gdy trzeba gdzieś wrócić.")
        self.home = app._entry(form, width=0)
        self.home.insert(0, acc.home_command)
        self.home.pack(fill="x", padx=12)

        label("Dodatkowe komendy po wejściu (po jednej w linii)")
        self.after_join = ctk.CTkTextbox(form, height=70, corner_radius=T.RADIUS_CTRL, border_width=1,
                                         border_color=T.BORDER, fg_color=T.INPUT_BG, text_color=T.TEXT,
                                         font=f["label"])
        self.after_join.pack(fill="x", padx=12)
        self.after_join.insert("1.0", "\n".join(acc.after_join_commands))

        label("Harmonogram komend na czacie",
              "Komenda jest wpisywana na czacie co podany czas (z losowym rozrzutem ±s), tylko gdy konto kopie. "
              "Gdy termin minie w złym momencie: „Odłóż” = wyślij raz po powrocie, „Pomiń” = czekaj na następny termin.")
        self.schedule_frame = ctk.CTkFrame(form, fg_color="transparent")
        self.schedule_frame.pack(fill="x", padx=12)
        self.schedule_rows: list[dict] = []
        for cmd in acc.schedule:
            self._add_row(cmd)
        app.secondary_button(form, "+  Dodaj komendę", lambda: self._add_row(ChatCommand()), height=30,
                             width=160).pack(anchor="w", padx=12, pady=(6, 0))

        self.enabled = ctk.CTkCheckBox(form, text="Konto włączone", font=f["body"], text_color=T.TEXT,
                                       fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                       checkmark_color=T.ACCENT_TEXT)
        self.enabled.pack(anchor="w", padx=12, pady=(14, 12))
        if acc.enabled:
            self.enabled.select()

        self.error = ctk.CTkLabel(self, text="", font=f["body_sm"], text_color=T.DANGER, wraplength=480,
                                  justify="left", anchor="w")
        self.error.grid(row=1, column=0, sticky="ew", padx=T.PAD)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=T.PAD, pady=(T.GAP, T.PAD))
        ctk.CTkButton(buttons, text="Zapisz", height=36, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self._save).pack(side="left")
        app.secondary_button(buttons, "Anuluj", self.destroy, height=36, width=90).pack(side="left", padx=8)

        self.after(150, self._grab)

    def _add_row(self, cmd: ChatCommand) -> None:
        app = self.app
        f = app.fonts
        box = ctk.CTkFrame(self.schedule_frame, fg_color=T.SURFACE_ALT, corner_radius=T.RADIUS_CTRL)
        box.pack(fill="x", pady=(0, 6))
        box.grid_columnconfigure(0, weight=1)
        text = app._entry(box, width=0)
        text.insert(0, cmd.text)
        text.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=(8, 4))
        row = {"box": box, "text": text}
        app.secondary_button(box, "Teraz", lambda: self.app.send_chat_now(
            self.instance.get().strip(), text.get().strip()), width=60, height=30).grid(row=0, column=1, padx=2)
        app.secondary_button(box, "✕", lambda: self._remove_row(row), width=34, height=30).grid(
            row=0, column=2, padx=(2, 8))
        opts = ctk.CTkFrame(box, fg_color="transparent")
        opts.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))
        ctk.CTkLabel(opts, text="co [min]", font=f["body_sm"], text_color=T.TEXT_MUTED).pack(side="left")
        every = app._entry(opts, width=64, justify="center")
        every.insert(0, f"{cmd.every_min:g}")
        every.pack(side="left", padx=(6, 14))
        ctk.CTkLabel(opts, text="rozrzut ±[s]", font=f["body_sm"], text_color=T.TEXT_MUTED).pack(side="left")
        jitter = app._entry(opts, width=64, justify="center")
        jitter.insert(0, f"{cmd.jitter_s:g}")
        jitter.pack(side="left", padx=(6, 14))
        ctk.CTkLabel(opts, text="gdy przegapiona", font=f["body_sm"], text_color=T.TEXT_MUTED).pack(side="left")
        missed = ctk.CTkOptionMenu(opts, values=list(MISSED_LABELS.values()), width=90, height=30,
                                   corner_radius=T.RADIUS_CTRL, font=f["label"], fg_color=T.INPUT_BG,
                                   button_color=T.INPUT_BG, button_hover_color=T.BORDER, text_color=T.TEXT,
                                   dropdown_fg_color=T.SURFACE_ALT, dropdown_hover_color=T.BORDER,
                                   dropdown_text_color=T.TEXT)
        missed.set(MISSED_LABELS.get(cmd.on_missed, "Odłóż"))
        missed.pack(side="left", padx=(6, 0))
        row.update(every=every, jitter=jitter, missed=missed)
        self.schedule_rows.append(row)

    def _remove_row(self, row: dict) -> None:
        row["box"].destroy()
        self.schedule_rows.remove(row)

    def _read_schedule(self) -> list[ChatCommand]:
        by_label = {v: k for k, v in MISSED_LABELS.items()}
        commands = []
        for row in self.schedule_rows:
            text = row["text"].get().strip()
            if not text:
                continue
            try:
                commands.append(ChatCommand(
                    text=text,
                    every_min=float(row["every"].get().strip().replace(",", ".")),
                    jitter_s=float(row["jitter"].get().strip().replace(",", ".")),
                    on_missed=by_label[row["missed"].get()]))
            except ValueError:
                raise ValueError(f"Niepoprawna liczba w harmonogramie (komenda „{text}”).") from None
        return commands

    def _grab(self) -> None:
        try:
            self.lift()
            self.grab_set()
            self.focus()
        except Exception:  # noqa: BLE001 — okno mogło zostać już zamknięte
            pass

    def _save(self) -> None:
        nick = self.nick.get().strip()
        instance = self.instance.get().strip()
        if not nick and not instance:
            self.error.configure(text="Podaj nick albo instancję.")
            return
        try:
            schedule = self._read_schedule()
        except ValueError as e:
            self.error.configure(text=str(e))
            return
        server_id = self._servers.get(self.server.get(), self.original.server_id if self.original else "default")
        acc = AccountCfg(
            id=self.original.id if self.original else self.app.new_account_id(),
            name=self.name.get().strip() or nick or instance,
            nick=nick,
            instance_id=instance,
            log_path=self.log_path.get().strip(),
            server_id=server_id,
            home_command=self.home.get().strip(),
            after_join_commands=[ln.strip() for ln in self.after_join.get("1.0", "end").splitlines() if ln.strip()],
            schedule=schedule,
            enabled=bool(self.enabled.get()),
        )
        error = self.app.save_account(acc, self.password.get())
        if error:
            self.error.configure(text=error)
        else:
            self.destroy()
