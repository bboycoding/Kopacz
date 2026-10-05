"""Wygląd GUI w jednym miejscu: kolory, fonty, glify. Paleta wg projektu ze Stitcha."""
import tkinter.font as tkfont

import customtkinter as ctk

# ---------- kolory (warstwy od najciemniejszej) ----------
APP_BG = "#16181D"        # tło okna
CARD = "#1F2229"          # karty: lista, ustawienia, paski
SURFACE_ALT = "#262A33"   # wiersze okien, kolumny ustawień, przyciski drugorzędne
INPUT_BG = "#16181D"      # pola tekstowe, ramka statystyk, pasek informacji
BORDER = "#2E333D"        # ramki 1 px, separatory, tło plakietek

ACCENT = "#3DDC84"
ACCENT_HOVER = "#4AE390"
ACCENT_TEXT = "#16181D"   # tekst na akcentowym tle
DANGER = "#E5484D"
DANGER_HOVER = "#EC5D62"
DANGER_TEXT = "#FFFFFF"
WARNING = "#F5A623"
TEXT = "#F0F2F5"
TEXT_MUTED = "#8E95A5"
PICK_HANDLE = "#A0703C"   # trzonek kilofa w logo

# ---------- geometria ----------
RADIUS_CARD = 12
RADIUS_CTRL = 8
RADIUS_CHIP = 6
PAD = 16                  # wcięcie poziome kart
GAP = 8                   # odstęp między elementami

# ---------- statusy kopacza → kolor kropki ----------
STATUS_COLORS = {
    "Kopie": ACCENT,
    "Startuje…": WARNING,
    "Okno MC zamknięte": WARNING,
    "Zatrzymany": TEXT_MUTED,
    "Gotowy": TEXT_MUTED,
}


def status_color(status: str) -> str:
    if status.startswith("Błąd"):
        return DANGER
    return STATUS_COLORS.get(status, TEXT_MUTED)


# ---------- glify ----------
# Przyciski: zwykłe znaki Unicode (Tk sam dobierze font zastępczy).
ICONS = {
    "refresh": "↻",
    "start": "▶",
    "stop": "■",
    "show": "◉",
    "test": "⏱",
    "calibrate": "↔",
    "save": "✓",
}
# Ikony sekcji: font ikon systemu Windows (11 → Fluent, 10 → MDL2). Brak fontu = brak ikony.
ICON_FONTS = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
SECTION_ICONS = {
    "windows": "",   # Tiles
    "move": "",      # Walk
    "keys": "",      # KeyboardClassic
    "stability": "", # Equalizer
}

# Logo: kilof 8×8 w stylu Minecrafta (H = grot, W = trzonek).
PICKAXE = (
    "..HHHH..",
    ".....HH.",
    ".....WHH",
    "....W..H",
    "...W...H",
    "..W....H",
    ".W......",
    "W.......",
)

# ---------- fonty ----------
FONT_PREFERRED = "Inter"
FONT_FALLBACK = "Segoe UI"


def _families(root) -> set[str]:
    return set(tkfont.families(root))


def font_family(root) -> str:
    """Inter, jeśli jest zainstalowany, inaczej Segoe UI. Wymaga istniejącego okna Tk."""
    return FONT_PREFERRED if FONT_PREFERRED in _families(root) else FONT_FALLBACK


def icon_font_family(root) -> str | None:
    families = _families(root)
    return next((f for f in ICON_FONTS if f in families), None)


def fonts(root) -> dict[str, ctk.CTkFont]:
    family = font_family(root)

    def f(size: int, bold: bool = False) -> ctk.CTkFont:
        return ctk.CTkFont(family=family, size=size, weight="bold" if bold else "normal")

    return {
        "headline_lg": f(24, True),   # nazwa aplikacji
        "headline_sm": f(15, True),   # nagłówki kart, tytuły okien, główne przyciski
        "body": f(13),
        "body_sm": f(12),             # etykiety pól, podtytuły
        "label": f(13, True),         # przyciski, wartości w polach
        "label_md": f(11, True),      # nagłówki kolumn ustawień
        "label_sm": f(10, True),      # plakietki, dopiski
    }


# ---------- kolory pochodne ----------
def blend(c1: str, c2: str, t: float) -> str:
    """Kolor pomiędzy c1 (t=0) a c2 (t=1) — zamiennik przezroczystości, której Tk nie ma."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


ACCENT_TINT = blend(CARD, ACCENT, 0.12)        # tło przycisku „Przelicz”
ACCENT_TINT_HOVER = blend(CARD, ACCENT, 0.22)
CHIP_ACTIVE = blend(SURFACE_ALT, ACCENT, 0.12) # tło plakietki „KOPIE”


def pulse_colors(color: str, background: str, steps: int = 10) -> list[str]:
    """Jeden pełny cykl pulsowania (fala trójkątna) od color do 70% w stronę tła i z powrotem."""
    half = [blend(color, background, 0.7 * i / steps) for i in range(steps)]
    return half + half[:0:-1]
