"""Monitor logów: czyta latest.log kont, rozpoznaje zdarzenia i (opcjonalnie) przesyła je na Discorda."""
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass

import launcher as L
import log_watcher as W
from config import AccountCfg, Config, DiscordCfg, ServerProfile
from discord_notify import DiscordNotifier, FINAL_FLUSH_S, valid_webhook
from secrets_store import Secrets, mask

# Zdarzenia zgłaszane jako alert (grupowany); reszta zdarzeń idzie jako zwykła linia.
_ALERTS = {
    W.DISCONNECTED: ("disconnected", "Rozłączone", lambda ev: f"Rozłączono z serwerem: {ev.text}", False),
    W.MOVED_TO_LOBBY: ("lobby", "Przeniesione do lobby", lambda ev: f"Przeniesiono do lobby: {ev.text}", False),
    W.STOPPING: ("stopping", "Gra zamknięta", lambda ev: "Gra została zamknięta", False),
    W.BAN: ("ban", "Zbanowane", lambda ev: f"BAN: {ev.text}", True),
}
_EVENT_LABELS = {
    W.CONNECTING: "Łączenie z serwerem",
    W.LOGIN_PROMPT: "Serwer prosi o logowanie",
    W.LOGGED_IN: "Zalogowano",
    W.LOBBY: "Lobby",
    W.IN_GAME: "Wejście do gry",
}


def account_label(acc: AccountCfg) -> str:
    return acc.nick or acc.name or acc.instance_id


def account_log_path(acc: AccountCfg, instances_dir: str) -> str:
    if acc.log_path:
        return acc.log_path
    if acc.instance_id and instances_dir:
        return L.log_path_for(instances_dir, acc.instance_id)
    return ""


@dataclass
class _Filter:
    include: list[re.Pattern]
    exclude: list[re.Pattern]

    @classmethod
    def from_cfg(cls, d: DiscordCfg) -> "_Filter":
        return cls([re.compile(p) for p in d.include if p], [re.compile(p) for p in d.exclude if p])

    def forward(self, ev: W.LogEvent, nick: str) -> bool:
        """Czy zwykłą linię logu (nie zdarzenie) wysłać na Discorda."""
        if ev.kind not in (W.CHAT, W.CHAT_PLAYER):
            return False                # linie techniczne (render, authlib…) to szum
        if any(p.search(ev.text) for p in self.exclude):
            return False
        if nick and nick.lower() in ev.text.lower():
            return True
        return any(p.search(ev.text) for p in self.include)


class Monitor:
    """Zarządza wątkami LogTail kont i wspólnym DiscordNotifier. `apply` można wołać wielokrotnie."""

    def __init__(self, status_provider: Callable[[], str] | None = None):
        self.status_provider = status_provider
        self.notifier: DiscordNotifier | None = None
        self.tails: list[W.LogTail] = []
        self.listeners: list[Callable[[AccountCfg, W.LogEvent], None]] = []   # dla rejoinu (kolejne kroki)
        self._lock = threading.Lock()

    def apply(self, cfg: Config, secrets: Secrets, instances_dir: str) -> None:
        with self._lock:
            self._stop_locked()
            accounts = [a for a in cfg.accounts if a.enabled]
            notifier = None
            if cfg.discord.enabled and valid_webhook(secrets.discord_webhook):
                d = cfg.discord
                notifier = DiscordNotifier(
                    secrets.discord_webhook, secrets.discord_ping_id, d.batch_seconds, d.max_chars,
                    d.group_window_s, d.status_every_min, self.status_provider,
                    mask=lambda t: mask(t, secrets), total_accounts=len(accounts))
                notifier.start()
            self.notifier = notifier
            flt = _Filter.from_cfg(cfg.discord)
            profiles = {s.id: s for s in cfg.servers}
            for acc in accounts:
                path = account_log_path(acc, instances_dir)
                if not path:
                    continue
                handler = self._handler(acc, profiles.get(acc.server_id), flt, notifier)
                tail = W.LogTail(path, handler, name=f"LogTail-{acc.id}")
                tail.start()
                self.tails.append(tail)

    def _handler(self, acc: AccountCfg, profile: ServerProfile | None, flt: _Filter,
                 notifier: DiscordNotifier | None) -> Callable[[str], None]:
        label = account_label(acc)

        def handle(raw: str) -> None:
            ev = W.classify(raw, profile)
            if ev is None:
                return
            for listener in list(self.listeners):
                listener(acc, ev)
            if notifier is None:
                return
            if ev.kind in _ALERTS:
                key, summary, make_text, ping = _ALERTS[ev.kind]
                notifier.alert(key, summary, label, make_text(ev), ping)
            elif ev.kind in _EVENT_LABELS:
                notifier.line(label, f"● {_EVENT_LABELS[ev.kind]}")
            elif flt.forward(ev, acc.nick):
                notifier.line(label, f"{ev.ts} {ev.text}")

        return handle

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        for t in self.tails:
            t.stop()
        self.tails = []
        if self.notifier:
            self.notifier.stop()
            self.notifier.join(timeout=FINAL_FLUSH_S + 1)
            self.notifier = None
