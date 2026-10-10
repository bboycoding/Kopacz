"""Ustawienia kopacza zapisywane do config.json obok programu.

Sekrety (webhook, hasła) są w osobnym, szyfrowanym pliku — patrz secrets_store.py.
"""
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field, fields

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

BACKENDS = ("postmessage", "foreground")
ON_MISSED = ("defer", "skip")


@dataclass
class ChatCommand:
    text: str = ""
    every_min: float = 30.0         # co ile minut
    jitter_s: float = 60.0          # losowy rozrzut ±s
    on_missed: str = "defer"        # "defer" = wyślij raz po powrocie, "skip" = czekaj na następny termin


@dataclass
class ServerProfile:
    id: str = "default"
    name: str = "Mój serwer"
    address: str = ""
    login_command: str = "/login {password}"
    lobby_commands: list[str] = field(default_factory=list)   # np. ["/server skyblock"]
    # Wzorce (regex) szukane w liniach latest.log. Puste = zdarzenie nie jest wykrywane.
    pat_login_prompt: str = ""
    pat_logged_in: str = ""
    pat_lobby: str = ""
    pat_in_game: str = ""
    pat_moved_to_lobby: str = ""
    pat_ban: str = ""
    pat_player_chat: str = r" » "   # linie czatu graczy — ignorowane przy wykrywaniu zdarzeń


@dataclass
class AccountCfg:
    id: str = ""
    name: str = ""
    nick: str = ""
    instance_id: str = ""           # ID instancji launchera (nazwa folderu)
    log_path: str = ""              # ręczna ścieżka do latest.log (puste = z instancji)
    server_id: str = "default"
    home_command: str = ""          # np. "/home kopanie"
    after_join_commands: list[str] = field(default_factory=list)
    schedule: list[ChatCommand] = field(default_factory=list)
    enabled: bool = True


@dataclass
class LauncherCfg:
    exe: str = ""
    instances_dir: str = ""
    args_template: str = "-l {instance} -s {server} -a {nick}"


@dataclass
class DiscordCfg:
    enabled: bool = False
    batch_seconds: float = 5.0
    max_chars: int = 1800
    group_window_s: float = 20.0
    status_every_min: float = 30.0
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class RejoinCfg:
    enabled: bool = False
    chat_key: str = "T"
    menu_keys: list[str] = field(default_factory=lambda: ["TAB", "ENTER", "wait:2", "ENTER"])
    pause_before_s: float = 5.0
    join_timeout_s: float = 20.0
    backoff_s: list[float] = field(default_factory=lambda: [10, 20, 40, 80, 160, 300])
    max_attempts_l0: int = 6
    max_attempts_l1: int = 5
    max_attempts_l2: int = 2
    connect_timeout_s: float = 20.0     # po nawigacji po menu: tyle czasu na „Connecting to”
    login_timeout_s: float = 45.0       # od połączenia do wejścia do lobby / trybu gry
    slow_retry: bool = True
    slow_retry_min: float = 30.0
    gate_spacing_s: float = 10.0
    stabilize_s: float = 60.0


_NESTED = {
    "servers": ServerProfile,
    "accounts": AccountCfg,
}


@dataclass
class Config:
    blocks: int = 5                 # o ile bloków postać idzie w każdą stronę
    sec_per_block: float = 0.231    # czas przejścia 1 bloku (chód ≈ 4.317 b/s)
    turn_pause: float = 0.3         # pauza na zawrotkach [s]
    key_right: str = "D"
    key_left: str = "A"
    wall_push_pct: float = 0.0      # dodatkowy % czasu ruchu, żeby dociągnąć do ściany
    jitter_pct: float = 0.0         # losowy rozrzut czasu ruchu ±%
    lmb_refresh_cycles: int = 5     # co ile cykli ponownie wcisnąć LPM (0 = nigdy)
    backend: str = "postmessage"    # "postmessage" (w tle) lub "foreground"

    launcher: LauncherCfg = field(default_factory=LauncherCfg)
    discord: DiscordCfg = field(default_factory=DiscordCfg)
    rejoin: RejoinCfg = field(default_factory=RejoinCfg)
    servers: list[ServerProfile] = field(default_factory=list)
    accounts: list[AccountCfg] = field(default_factory=list)

    # Nieznane pola z pliku — przepisywane przy zapisie, żeby nic nie ginęło.
    extra: dict = field(default_factory=dict, repr=False)
    # Komunikat o problemie z wczytaniem pliku (pokazywany w GUI); nie zapisywany.
    load_error: str = field(default="", repr=False, compare=False)

    def validate(self) -> None:
        if not 1 <= self.blocks <= 256:
            raise ValueError("Ilość bloków musi być w zakresie 1–256.")
        if not 0.01 <= self.sec_per_block <= 5:
            raise ValueError("Sekundy na blok muszą być w zakresie 0.01–5.")
        if not 0 <= self.turn_pause <= 60:
            raise ValueError("Pauza na zawrotce musi być w zakresie 0–60 s.")
        if not 0 <= self.wall_push_pct <= 200:
            raise ValueError("Dociąg do ściany musi być w zakresie 0–200%.")
        if not 0 <= self.jitter_pct <= 50:
            raise ValueError("Rozrzut musi być w zakresie 0–50%.")
        if self.lmb_refresh_cycles < 0:
            raise ValueError("Odświeżanie LPM nie może być ujemne.")
        if self.backend not in BACKENDS:
            raise ValueError(f"Nieznana metoda inputu: {self.backend}")
        self._validate_servers()
        self._validate_accounts()
        self._validate_misc()

    def _validate_servers(self) -> None:
        ids = set()
        for s in self.servers:
            if not s.id or s.id in ids:
                raise ValueError(f"Profil serwera „{s.name}”: pusty lub powtórzony identyfikator.")
            ids.add(s.id)
            for f in fields(s):
                if f.name.startswith("pat_") and getattr(s, f.name):
                    _check_regex(getattr(s, f.name), f"serwer „{s.name}”, {f.name}")
            if "{password}" in "".join(s.lobby_commands):
                raise ValueError(f"Serwer „{s.name}”: {{password}} wolno użyć tylko w komendzie logowania.")

    def _validate_accounts(self) -> None:
        ids = set()
        server_ids = {s.id for s in self.servers}
        for a in self.accounts:
            if not a.id or a.id in ids:
                raise ValueError(f"Konto „{a.name}”: pusty lub powtórzony identyfikator.")
            ids.add(a.id)
            if self.servers and a.server_id not in server_ids:
                raise ValueError(f"Konto „{a.name}”: nieznany profil serwera „{a.server_id}”.")
            if "{password}" in "".join([a.home_command, *a.after_join_commands]):
                raise ValueError(f"Konto „{a.name}”: {{password}} wolno użyć tylko w komendzie logowania.")
            for c in a.schedule:
                if not c.text.strip():
                    raise ValueError(f"Konto „{a.name}”: pusta komenda w harmonogramie.")
                if not 0.1 <= c.every_min <= 24 * 60:
                    raise ValueError(f"Konto „{a.name}”: interwał komendy musi być w zakresie 0,1–1440 min.")
                if not 0 <= c.jitter_s <= 3600:
                    raise ValueError(f"Konto „{a.name}”: rozrzut komendy musi być w zakresie 0–3600 s.")
                if c.on_missed not in ON_MISSED:
                    raise ValueError(f"Konto „{a.name}”: nieznane zachowanie przy przegapieniu: {c.on_missed}")

    def _validate_misc(self) -> None:
        d, r = self.discord, self.rejoin
        for p in (*d.include, *d.exclude):
            _check_regex(p, "filtr Discorda")
        if not 1 <= d.batch_seconds <= 60:
            raise ValueError("Paczkowanie Discorda musi być w zakresie 1–60 s.")
        if not 200 <= d.max_chars <= 1900:
            raise ValueError("Rozmiar paczki Discorda musi być w zakresie 200–1900 znaków.")
        if r.max_attempts_l0 < 0 or r.max_attempts_l1 < 0 or r.max_attempts_l2 < 0:
            raise ValueError("Limity prób rejoinu nie mogą być ujemne.")
        if not r.backoff_s or any(x <= 0 for x in r.backoff_s):
            raise ValueError("Lista odstępów (backoff) musi zawierać liczby dodatnie.")
        from chat import parse_menu_keys
        from win_input import key_to_vk
        try:
            key_to_vk(r.chat_key)
        except ValueError as e:
            raise ValueError(f"Klawisz czatu: {e}") from e
        try:
            parse_menu_keys(r.menu_keys)
        except ValueError as e:
            raise ValueError(f"Sekwencja klawiszy w menu: {e}") from e
        if not 1 <= r.connect_timeout_s <= 600 or not 1 <= r.login_timeout_s <= 600:
            raise ValueError("Czasy oczekiwania na połączenie i logowanie muszą być w zakresie 1–600 s.")
        if not 0 <= r.pause_before_s <= 600:
            raise ValueError("Pauza przed powrotem musi być w zakresie 0–600 s.")
        if not 1 <= r.join_timeout_s <= 600:
            raise ValueError("Czas oczekiwania na wejście do gry musi być w zakresie 1–600 s.")
        if not 0 <= r.gate_spacing_s <= 600:
            raise ValueError("Odstęp między kontami musi być w zakresie 0–600 s.")
        if not 0 <= r.stabilize_s <= 3600:
            raise ValueError("Stabilizacja po powrocie musi być w zakresie 0–3600 s.")
        if r.slow_retry_min < 1:
            raise ValueError("Wolne ponawianie: minimum 1 minuta.")


def _check_regex(pattern: str, where: str) -> None:
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Niepoprawny wzorzec ({where}): {e}") from e


def _build(cls, data: dict):
    """Buduje dataclass z dict-a: ignoruje nieznane klucze, uzupełnia brakujące domyślnymi."""
    known = {f.name: f for f in fields(cls)}
    kwargs = {}
    for name, value in data.items():
        if name in known and name not in ("extra", "load_error"):
            kwargs[name] = value
    return cls(**kwargs)


def config_from_dict(data: dict) -> Config:
    top_known = {f.name for f in fields(Config)} - {"extra", "load_error"}
    flat = {k: v for k, v in data.items() if k in top_known
            and k not in ("launcher", "discord", "rejoin", "servers", "accounts")}
    cfg = Config(**flat)
    cfg.launcher = _build(LauncherCfg, data.get("launcher", {}))
    cfg.discord = _build(DiscordCfg, data.get("discord", {}))
    cfg.rejoin = _build(RejoinCfg, data.get("rejoin", {}))
    cfg.servers = [_build(ServerProfile, s) for s in data.get("servers", [])]
    cfg.accounts = []
    for a in data.get("accounts", []):
        acc = _build(AccountCfg, {k: v for k, v in a.items() if k != "schedule"})
        acc.schedule = [_build(ChatCommand, c) for c in a.get("schedule", [])]
        cfg.accounts.append(acc)
    cfg.extra = {k: v for k, v in data.items() if k not in top_known}
    return cfg


def config_to_dict(cfg: Config) -> dict:
    data = asdict(cfg)
    extra = data.pop("extra", {})
    data.pop("load_error", None)
    return {**extra, **data}


def load_config() -> Config:
    """Wczytuje config.json. Przy błędzie NIE gubi pliku po cichu: kopiuje go do config.json.bad
    i zwraca domyślne ustawienia z wypełnionym `load_error` (GUI pokazuje komunikat)."""
    if not os.path.exists(CONFIG_PATH):
        return Config()
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("główny element pliku musi być obiektem JSON")
        cfg = config_from_dict(data)
        cfg.validate()
        return cfg
    except (OSError, ValueError, TypeError) as e:
        try:
            shutil.copyfile(CONFIG_PATH, CONFIG_PATH + ".bad")
        except OSError:
            pass
        cfg = Config()
        cfg.load_error = (f"Błąd w config.json ({e}). Użyto ustawień domyślnych, "
                          "kopia uszkodzonego pliku: config.json.bad.")
        return cfg


def save_config(cfg: Config) -> None:
    """Zapis atomowy: plik tymczasowy, potem os.replace."""
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config_to_dict(cfg), f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CONFIG_PATH)
