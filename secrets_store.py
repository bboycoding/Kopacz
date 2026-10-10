"""Sekrety (webhook Discorda, hasła kont) w secrets.json, szyfrowane Windows DPAPI.

Odszyfrować może je tylko ten sam użytkownik Windows na tym samym komputerze.
Po przeniesieniu programu na inny komputer sekrety trzeba wpisać ponownie.
"""
import base64
import json
import os
from dataclasses import dataclass, field

import win32crypt

from config import BASE_DIR

SECRETS_PATH = os.path.join(BASE_DIR, "secrets.json")
_DESCRIPTION = "MojKopacz"
_VERSION = 1


@dataclass
class Secrets:
    discord_webhook: str = ""
    discord_ping_id: str = ""
    passwords: dict[str, str] = field(default_factory=dict)   # id konta → hasło
    load_error: str = field(default="", repr=False)

    def password_for(self, account_id: str) -> str:
        return self.passwords.get(account_id, "")


def mask(text: str, secrets: Secrets) -> str:
    """Podmienia hasła i webhook w tekście na ******; do statusów, logów i Discorda."""
    for secret in (secrets.discord_webhook, *secrets.passwords.values()):
        if secret:
            text = text.replace(secret, "******")
    return text


def _encrypt(raw: bytes) -> str:
    blob = win32crypt.CryptProtectData(raw, _DESCRIPTION, None, None, None, 0)
    return base64.b64encode(blob).decode("ascii")


def _decrypt(text: str) -> bytes:
    _, raw = win32crypt.CryptUnprotectData(base64.b64decode(text), None, None, None, 0)
    return raw


def load_secrets() -> Secrets:
    if not os.path.exists(SECRETS_PATH):
        return Secrets()
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            envelope = json.load(f)
        data = json.loads(_decrypt(envelope["data"]).decode("utf-8"))
        return Secrets(
            discord_webhook=str(data.get("discord_webhook", "")),
            discord_ping_id=str(data.get("discord_ping_id", "")),
            passwords={str(k): str(v) for k, v in data.get("passwords", {}).items()},
        )
    except Exception as e:  # noqa: BLE001 — uszkodzony plik albo inny użytkownik/komputer
        return Secrets(load_error=f"Nie udało się odczytać secrets.json ({e}). "
                                  "Wpisz webhook i hasła ponownie.")


def save_secrets(secrets: Secrets) -> None:
    payload = {
        "discord_webhook": secrets.discord_webhook,
        "discord_ping_id": secrets.discord_ping_id,
        "passwords": secrets.passwords,
    }
    envelope = {"version": _VERSION, "data": _encrypt(json.dumps(payload).encode("utf-8"))}
    tmp = SECRETS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(envelope, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SECRETS_PATH)
