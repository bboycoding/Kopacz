"""Ustawienia kopacza zapisywane do config.json obok programu."""
import json
import os
import sys
from dataclasses import asdict, dataclass, fields

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

BACKENDS = ("postmessage", "foreground")


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


def load_config() -> Config:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        known = {f.name for f in fields(Config)}
        cfg = Config(**{k: v for k, v in data.items() if k in known})
        cfg.validate()
        return cfg
    except (OSError, ValueError, TypeError):
        return Config()


def save_config(cfg: Config) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)
