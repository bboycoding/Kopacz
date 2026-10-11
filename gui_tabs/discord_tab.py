"""Zakładka „Discord”: webhook, filtry, interwały, test."""
import threading

import customtkinter as ctk

import theme as T
from config import DiscordCfg
from discord_notify import DiscordNotifier, valid_webhook


class DiscordTab:
    def __init__(self, app, parent):
        self.app = app
        f = app.fonts
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        card = app._card(parent)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        form = ctk.CTkScrollableFrame(card, fg_color=T.CARD, corner_radius=0, scrollbar_button_color=T.BORDER,
                                      scrollbar_button_hover_color=T.TEXT_MUTED)
        form.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        form.grid_columnconfigure(0, weight=1)
        d = app.cfg.discord

        def caption(text: str, hint: str = "") -> None:
            ctk.CTkLabel(form, text=text, font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w").pack(
                fill="x", padx=8, pady=(10, 1))
            if hint:
                ctk.CTkLabel(form, text=hint, font=f["label_sm"], text_color=T.TEXT_MUTED, anchor="w",
                             justify="left", wraplength=780).pack(fill="x", padx=8)

        def entry(value: str, **kw) -> ctk.CTkEntry:
            e = app._entry(form, width=0, **kw)
            e.insert(0, value)
            e.pack(fill="x", padx=8)
            return e

        def textbox(lines: list[str]) -> ctk.CTkTextbox:
            t = ctk.CTkTextbox(form, height=90, corner_radius=T.RADIUS_CTRL, border_width=1,
                               border_color=T.BORDER, fg_color=T.INPUT_BG, text_color=T.TEXT, font=f["label"])
            t.insert("1.0", "\n".join(lines))
            t.pack(fill="x", padx=8)
            return t

        self.enabled = ctk.CTkCheckBox(form, text="Wysyłaj logi i alerty na Discorda", font=f["body"],
                                       text_color=T.TEXT, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                       checkmark_color=T.ACCENT_TEXT)
        self.enabled.pack(anchor="w", padx=8, pady=(8, 0))
        if d.enabled:
            self.enabled.select()

        caption("Adres webhooka", "Kanał → Edytuj → Integracje → Webhooki. Przechowywany szyfrowo, nie trafia do config.json.")
        self.webhook = entry(app.secrets.discord_webhook, show="•")
        caption("Twoje ID użytkownika Discorda (do pingów)",
                "Ping tylko przy stanie BŁĄD i banie. Same cyfry; puste = bez pingów.")
        self.ping_id = entry(app.secrets.discord_ping_id)

        caption("Wysyłaj także linie pasujące do wzorców (po jednym wyrażeniu w linii)",
                "Zawsze wysyłane: zdarzenia bota (rozłączenie, lobby, wejście do gry, ban) i linie z nickiem konta "
                "(np. Twoje klucze) — także gdy pasują do wzorców „Nigdy nie wysyłaj”.")
        self.include = textbox(d.include)
        caption("Nigdy nie wysyłaj linii pasujących do wzorców (szum)")
        self.exclude = textbox(d.exclude)

        caption("Paczkowanie wiadomości [s]", "Linie z wielu kont łączą się w jedną wiadomość co tyle sekund.")
        self.batch = entry(str(d.batch_seconds))
        caption("Okno łączenia alertów [s]", "Alert o tym samym problemie na kilku kontach naraz = jedna wiadomość.")
        self.group = entry(str(d.group_window_s))
        caption("Status kont co [min]", "0 = bez okresowego statusu.")
        self.status_every = entry(str(d.status_every_min))

        self.stats = ctk.CTkLabel(form, text="", font=f["body_sm"], text_color=T.TEXT_MUTED, anchor="w")
        self.stats.pack(fill="x", padx=8, pady=(14, 0))
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(8, 10))
        ctk.CTkButton(row, text="Zapisz", width=90, height=34, corner_radius=T.RADIUS_CTRL, font=f["label"],
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ACCENT_TEXT,
                      command=self.save).pack(side="left")
        app.secondary_button(row, "Wyślij test", self.send_test, width=110, height=34).pack(side="left", padx=8)

    def _lines(self, box: ctk.CTkTextbox) -> list[str]:
        return [ln.strip() for ln in box.get("1.0", "end").splitlines() if ln.strip()]

    def save(self) -> None:
        try:
            dcfg = DiscordCfg(
                enabled=bool(self.enabled.get()),
                batch_seconds=float(self.batch.get().replace(",", ".")),
                max_chars=self.app.cfg.discord.max_chars,
                group_window_s=float(self.group.get().replace(",", ".")),
                status_every_min=float(self.status_every.get().replace(",", ".")),
                include=self._lines(self.include),
                exclude=self._lines(self.exclude))
        except ValueError:
            self.app.set_info("Niepoprawna liczba w ustawieniach Discorda.", error=True)
            return
        error = self.app.save_discord(dcfg, self.webhook.get().strip(), self.ping_id.get().strip())
        if error:
            self.app.set_info(error, error=True)
        else:
            self.app.set_info("Zapisano ustawienia Discorda.")

    def send_test(self) -> None:
        url = self.webhook.get().strip()
        if not valid_webhook(url):
            self.app.set_info("Niepoprawny adres webhooka (powinien zaczynać się od https://discord.com/api/webhooks/).",
                              error=True)
            return
        self.app.set_info("Wysyłam wiadomość testową…")

        def worker():
            ok, err = DiscordNotifier(url).send_test()
            self.app.after(0, lambda: self.app.set_info(
                "Wysłano wiadomość testową. Sprawdź kanał na Discordzie." if ok
                else f"Test nieudany: {err}", error=not ok))

        threading.Thread(target=worker, daemon=True).start()

    def update_stats(self) -> None:
        n = self.app.monitor.notifier
        if n is None:
            text = "Wysyłka wyłączona (włącz, wpisz poprawny webhook i zapisz)."
        else:
            s = n.stats
            text = f"Wysłano: {s.sent} · błędy: {s.errors}" + (f" · ostatni błąd: {s.last_error}" if s.last_error else "")
        if self.stats.cget("text") != text:
            self.stats.configure(text=text)
