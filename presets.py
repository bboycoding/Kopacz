"""Gotowe profile serwerów — punkt wyjścia do własnych ustawień w GUI."""
from dataclasses import replace

from config import BFSMC_IN_GAME_PATTERN, BFSMC_REWARD_PATTERN, ServerProfile

BFSMC = ServerProfile(
    id="bfsmc",
    name="bfsmc.pl (przykład)",
    address="bfsmc.pl",
    login_command="/login {password}",
    lobby_commands=["/server skyblock"],
    pat_login_prompt=r"Zaloguj się używając",
    pat_logged_in=r"Pomyślnie zalogowano",
    pat_lobby=r"WYBIERZ TRYB GRY",
    pat_in_game=BFSMC_IN_GAME_PATTERN,
    pat_moved_to_lobby=r"Rozłączono z \S+:",
    pat_ban=r"(?i)zbanowan|you are banned",
    pat_player_chat=r" » ",
    pat_reward=BFSMC_REWARD_PATTERN,
)

VANILLA = ServerProfile(
    id="vanilla",
    name="Pusty / vanilla",
    address="",
    login_command="",
    lobby_commands=[],
    # Zwykły serwer (np. Aternos): po wejściu serwer ogłasza „<nick> joined the game”; ban to powód rozłączenia.
    pat_in_game=r"joined the game",
    pat_ban=r"(?i)you are banned",
)

PRESETS = {"bfsmc": BFSMC, "vanilla": VANILLA}

# Domyślne filtry Discorda dla presetu bfsmc.pl (szum, który nie ma sensu na kanale).
BFSMC_DISCORD_EXCLUDE = [
    r"zdobył klucz",
    r"Czyszczenie przedmiotów",
    r"Klatka Dusz",
    r"^\s*[→←] ",
]


BFSMC_DISCORD_INCLUDE = [
    r"Restart serwera nastąpi",
]


def new_profile(preset_id: str, profile_id: str) -> ServerProfile:
    """Kopia presetu pod nowym identyfikatorem (żeby edycja nie zmieniała presetu)."""
    return replace(PRESETS[preset_id], id=profile_id,
                   lobby_commands=list(PRESETS[preset_id].lobby_commands))
