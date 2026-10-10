"""Zakładka „Zaawansowane”: launcher (na razie), później rejoin i inne."""
import customtkinter as ctk

import theme as T
from config import LauncherCfg


class AdvancedTab:
    def __init__(self, app, parent):
        self.app = app
        f = app.fonts
        parent.grid_columnconfigure(0, weight=1)

        card = app._card(parent)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="LAUNCHER", font=f["label_md"], text_color=T.ACCENT).grid(
            row=0, column=0, sticky="w", padx=T.PAD, pady=(12, 0))
        ctk.CTkLabel(card, text="Prism, Fjord, PolyMC lub MultiMC. Potrzebny do powiązania okien z instancjami, "
                                "odczytu logów i (później) ponownego uruchamiania gry.",
                     font=f["body_sm"], text_color=T.TEXT_MUTED, wraplength=820, justify="left",
                     anchor="w").grid(row=1, column=0, sticky="w", padx=T.PAD, pady=(2, 4))

        cfg = app.cfg.launcher
        self.exe = self._row(card, 2, "Plik wykonywalny launchera", cfg.exe)
        self.instances_dir = self._row(card, 4, "Folder instancji (instances)", cfg.instances_dir)
        self.args = self._row(card, 6, "Szablon argumentów uruchomienia", cfg.args_template,
                              "Dostępne: {instance} {server} {nick}. Dla Fjorda sprawdzone przez --help: "
                              "-l <instancja> -s <serwer> -a <konto>. Inne launchery: sprawdź ich --help.")

        self.status = ctk.CTkLabel(card, text="", font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w")
        self.status.grid(row=9, column=0, sticky="w", padx=T.PAD, pady=(8, 0))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=10, column=0, sticky="w", padx=T.PAD, pady=(8, 14))
        app.secondary_button(buttons, "Wykryj", self.detect, width=90, height=34).pack(side="left")
        ctk.CTkButton(buttons, text="Zapisz", width=90, height=34, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.save).pack(side="left", padx=8)
        self.update_status()

        self._build_rejoin(parent)

        chat_card = app._card(parent)
        chat_card.grid(row=2, column=0, sticky="ew", pady=(T.GAP, 0))
        chat_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(chat_card, text="CZAT I KOMENDY", font=f["label_md"], text_color=T.ACCENT).grid(
            row=0, column=0, sticky="w", padx=T.PAD, pady=(12, 0))
        rejoin = app.cfg.rejoin
        self.chat_key = self._row(chat_card, 1, "Klawisz otwierający czat", rejoin.chat_key,
                                  "Domyślnie T (w options.txt: key_key.chat). Komendy z harmonogramu są wpisywane "
                                  "przez ten klawisz, w tle, bez przejmowania myszy.")
        self.stabilize = self._row(chat_card, 4, "Stabilizacja po powrocie [s]", f"{rejoin.stabilize_s:g}",
                                   "Tyle sekund konto musi nieprzerwanie kopać, zanim wyśle odłożoną komendę.")
        ctk.CTkButton(chat_card, text="Zapisz", width=90, height=34, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.save_chat).grid(row=7, column=0, sticky="w", padx=T.PAD, pady=(10, 14))

    def _build_rejoin(self, parent) -> None:
        app = self.app
        f = app.fonts
        r = app.cfg.rejoin
        card = app._card(parent)
        card.grid(row=1, column=0, sticky="ew", pady=(T.GAP, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="POWRÓT NA SERWER", font=f["label_md"], text_color=T.ACCENT).grid(
            row=0, column=0, sticky="w", padx=T.PAD, pady=(12, 0))
        self.rejoin_enabled = ctk.CTkCheckBox(
            card, text="Automatycznie wracaj na serwer (restart serwera, przeniesienie do lobby)",
            font=f["body"], text_color=T.TEXT, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            checkmark_color=T.ACCENT_TEXT)
        self.rejoin_enabled.grid(row=1, column=0, sticky="w", padx=T.PAD, pady=(8, 0))
        if r.enabled:
            self.rejoin_enabled.select()
        ctk.CTkLabel(card, text="Po przeniesieniu do lobby bot wstrzymuje kopanie, wpisuje komendy lobby → gra z profilu "
                                "serwera, czeka na potwierdzenie wejścia do gry i wznawia kopanie. Po rozłączeniu "
                                "wstrzymuje kopanie i wznawia je, gdy konto wróci na serwer.",
                     font=f["label_sm"], text_color=T.TEXT_MUTED, wraplength=820, justify="left",
                     anchor="w").grid(row=2, column=0, sticky="w", padx=T.PAD, pady=(2, 0))
        self.pause_before = self._row(card, 3, "Pauza przed pierwszą próbą [s]", f"{r.pause_before_s:g}")
        self.join_timeout = self._row(card, 6, "Czas oczekiwania na wejście do gry [s]", f"{r.join_timeout_s:g}")
        self.max_attempts = self._row(card, 9, "Liczba prób w serii", str(r.max_attempts_l0))
        self.backoff = self._row(card, 12, "Odstępy między próbami [s], po przecinku",
                                 ", ".join(f"{x:g}" for x in r.backoff_s),
                                 "Kolejne wartości dla kolejnych prób; ostatnia powtarza się, jeśli prób jest więcej.")
        self.gate_spacing = self._row(card, 15, "Odstęp między kontami [s]", f"{r.gate_spacing_s:g}",
                                      "Po restarcie serwera konta wracają po kolei, z tym minimalnym odstępem.")
        self.slow_retry = ctk.CTkCheckBox(card, text="Po wyczerpaniu prób ponawiaj powoli (np. gdy serwer leży)",
                                          font=f["body"], text_color=T.TEXT, fg_color=T.ACCENT,
                                          hover_color=T.ACCENT_HOVER, checkmark_color=T.ACCENT_TEXT)
        self.slow_retry.grid(row=18, column=0, sticky="w", padx=T.PAD, pady=(10, 0))
        if r.slow_retry:
            self.slow_retry.select()
        self.slow_min = self._row(card, 19, "Wolne ponawianie co [min]", f"{r.slow_retry_min:g}")
        ctk.CTkButton(card, text="Zapisz", width=90, height=34, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.save_rejoin).grid(row=22, column=0, sticky="w", padx=T.PAD, pady=(10, 14))

    def save_rejoin(self) -> None:
        from dataclasses import replace
        try:
            backoff = [float(x.strip().replace(",", ".")) for x in self.backoff.get().replace(";", ",").split(",")
                       if x.strip()]
        except ValueError:
            backoff = None
        try:
            fields = dict(
                enabled=bool(self.rejoin_enabled.get()),
                pause_before_s=float(self.pause_before.get().replace(",", ".")),
                join_timeout_s=float(self.join_timeout.get().replace(",", ".")),
                max_attempts_l0=int(self.max_attempts.get().strip()),
                backoff_s=backoff,
                gate_spacing_s=float(self.gate_spacing.get().replace(",", ".")),
                slow_retry=bool(self.slow_retry.get()),
                slow_retry_min=float(self.slow_min.get().replace(",", ".")))
        except ValueError:
            fields = None
        if fields is None or backoff is None:
            self.app.set_info("Niepoprawna liczba w ustawieniach powrotu na serwer.", error=True)
            return
        error = self.app.apply_rejoin_settings(replace(self.app.cfg.rejoin, **fields))
        if error:
            self.app.set_info(error, error=True)
        else:
            self.app.set_info("Zapisano ustawienia powrotu na serwer (obowiązują od następnego startu kopania).")

    def save_chat(self) -> None:
        try:
            stabilize = float(self.stabilize.get().strip().replace(",", "."))
        except ValueError:
            self.app.set_info("Niepoprawna liczba w polu stabilizacji.", error=True)
            return
        error = self.app.apply_chat_settings(self.chat_key.get().strip().upper(), stabilize)
        if error:
            self.app.set_info(error, error=True)
        else:
            self.app.set_info("Zapisano ustawienia czatu.")

    def _row(self, card, row: int, caption: str, value: str, hint: str = "") -> ctk.CTkEntry:
        f = self.app.fonts
        ctk.CTkLabel(card, text=caption, font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w").grid(
            row=row, column=0, sticky="w", padx=T.PAD, pady=(8, 2))
        e = self.app._entry(card, width=0)
        e.insert(0, value)
        e.grid(row=row + 1, column=0, sticky="ew", padx=T.PAD)
        if hint:
            ctk.CTkLabel(card, text=hint, font=f["label_sm"], text_color=T.TEXT_MUTED, wraplength=820,
                         justify="left", anchor="w").grid(row=row + 2, column=0, sticky="w", padx=T.PAD)
        return e

    def update_status(self) -> None:
        n = len(self.app.instances)
        self.status.configure(text=f"Wykryte instancje: {n}" if n else
                              "Nie znaleziono instancji. Kliknij „Wykryj” albo wskaż folder ręcznie.")

    def _set(self, entry: ctk.CTkEntry, text: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, text)

    def detect(self) -> None:
        exe, instances_dir = self.app.detect_launcher()
        if exe:
            self._set(self.exe, exe)
        if instances_dir:
            self._set(self.instances_dir, instances_dir)
        if not (exe or instances_dir):
            self.app.set_info("Nie znaleziono launchera. Uruchom go albo wskaż ścieżki ręcznie.", error=True)
            return
        self.app.apply_launcher(LauncherCfg(self.exe.get().strip(), self.instances_dir.get().strip(),
                                            self.args.get().strip()), save=False)
        self.update_status()
        self.app.set_info("Wykryto launcher. Kliknij „Zapisz”, żeby zachować ustawienia.")

    def save(self) -> None:
        error = self.app.apply_launcher(LauncherCfg(self.exe.get().strip(), self.instances_dir.get().strip(),
                                                    self.args.get().strip()), save=True)
        self.update_status()
        if error:
            self.app.set_info(error, error=True)
        else:
            self.app.set_info("Zapisano ustawienia launchera.")
