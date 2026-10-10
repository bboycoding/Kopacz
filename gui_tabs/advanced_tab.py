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
        self.status.grid(row=8, column=0, sticky="w", padx=T.PAD, pady=(8, 0))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=9, column=0, sticky="w", padx=T.PAD, pady=(8, 14))
        app.secondary_button(buttons, "Wykryj", self.detect, width=90, height=34).pack(side="left")
        ctk.CTkButton(buttons, text="Zapisz", width=90, height=34, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.save).pack(side="left", padx=8)
        self.update_status()

        chat_card = app._card(parent)
        chat_card.grid(row=1, column=0, sticky="ew", pady=(T.GAP, 0))
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
