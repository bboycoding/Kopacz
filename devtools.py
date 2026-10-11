"""Narzędzia diagnostyczne z konsoli (bez GUI).

  python devtools.py instances                 — launcher, instancje, okna gry i konta
  python devtools.py replay <plik> [preset]    — zdarzenia wykryte w starym logu (.log / .log.gz); preset: bfsmc, vanilla
  python devtools.py tail <id_instancji> [preset] — na żywo: zdarzenia z latest.log instancji (Ctrl+C kończy)
  python devtools.py discord-test              — wiadomość testowa na zapisany webhook
  python devtools.py chat <id_instancji> "<tekst>" — wpisuje tekst/komendę na czacie okna instancji (PRAWDZIWA wysyłka)
  python devtools.py keys <id_instancji> KLAWISZ... — naciska klawisze w oknie (np. TAB ENTER wait:2 ENTER)
  python devtools.py relaunch <id_instancji> [--yes] — restart JEDNEJ instancji. Bez --yes tylko pokazuje, co by zrobił
  python devtools.py eat-test <id_instancji>   — na PRAWDZIWYM oknie: kilof → jedzenie → kilof (wg ustawień konta)
  python devtools.py pause-test <id_instancji> [kopanie_s] [pauza_s]
                                               — na PRAWDZIWYM oknie: kopanie, pauza, wznowienie, stop
"""
import sys
import time

import launcher as L
import log_watcher as W
import presets
from config import load_config
from chat import ChatError, ChatSender
from miner import EatPlan, Miner
from win_input import PostMessageBackend, key_to_vk, tap
from discord_notify import DiscordNotifier, valid_webhook
from secrets_store import load_secrets
from windows import find_minecraft_windows


def cmd_instances() -> int:
    cfg = load_config()
    exe = cfg.launcher.exe
    instances_dir = cfg.launcher.instances_dir
    if not (exe and instances_dir):
        found_exe, found_dir = L.detect_launcher()
        exe, instances_dir = exe or found_exe, instances_dir or found_dir
        print("(launcher wykryty automatycznie — nie zapisany w config.json)")
    print(f"Launcher:        {exe or '— nie znaleziono —'}")
    print(f"Folder instancji: {instances_dir or '— nie znaleziono —'}")
    instances = L.list_instances(instances_dir)
    print(f"\nInstancje ({len(instances)}):")
    for i in instances:
        account = next((a for a in cfg.accounts if a.instance_id == i.id), None)
        print(f"  {i.id:<14} {i.name:<14} konto: {(account.nick or account.name) if account else '—':<18} {i.log_path}")
    windows = find_minecraft_windows()
    print(f"\nOkna gry ({len(windows)}):")
    for w in windows:
        print(f"  hwnd {w.hwnd:<9} PID {w.pid:<7} instancja: {L.instance_for_pid(w.pid) or '—'}")
    return 0


def _preset(name: str | None):
    if name is None:
        return presets.BFSMC
    if name not in presets.PRESETS:
        raise SystemExit(f"Nieznany preset „{name}” (dostępne: {', '.join(presets.PRESETS)}).")
    return presets.PRESETS[name]


def cmd_replay(path: str, preset: str | None = None) -> int:
    counts, examples = W.summarize(path, _preset(preset), samples=2)
    if not counts:
        print("Brak wykrytych zdarzeń.")
    for kind in W.EVENT_KINDS:
        if kind in counts:
            print(f"{kind:<16}{counts[kind]}")
            for ex in examples[kind]:
                print(f"    {ex}")
    return 0


def cmd_tail(instance_id: str, preset: str | None = None) -> int:
    cfg = load_config()
    instances_dir = cfg.launcher.instances_dir or L.detect_launcher()[1]
    path = L.log_path_for(instances_dir, instance_id)
    profile = _preset(preset)
    print(f"Czytam {path} (Ctrl+C kończy)")

    def show(line: str) -> None:
        ev = W.classify(line, profile)
        if ev is not None and ev.kind in W.EVENT_KINDS:
            print(f"{ev.ts}  {ev.kind:<15}{ev.text}")

    tail = W.LogTail(path, show)
    tail.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        tail.stop()
    return 0


def cmd_discord_test() -> int:
    secrets = load_secrets()
    if secrets.load_error:
        print(secrets.load_error)
        return 1
    if not valid_webhook(secrets.discord_webhook):
        print("Brak poprawnego webhooka — wpisz go w zakładce Discord i zapisz.")
        return 1
    ok, err = DiscordNotifier(secrets.discord_webhook).send_test()
    print("Wysłano. Sprawdź kanał." if ok else f"Błąd: {err}")
    return 0 if ok else 1


def _window_for(instance_id: str):
    windows = [w for w in find_minecraft_windows() if L.instance_for_pid(w.pid) == instance_id]
    if len(windows) != 1:
        print(f"Znaleziono {len(windows)} okien dla instancji „{instance_id}” (potrzebne dokładnie 1).")
        return None
    return windows[0]


def cmd_chat(instance_id: str, text: str) -> int:
    window = _window_for(instance_id)
    if window is None:
        return 1
    try:
        ChatSender(window.hwnd, load_config().rejoin.chat_key).send(text)
    except ChatError as e:
        print(f"Nie wysłano: {e}")
        return 1
    print(f"Wysłano: {text}")
    return 0


def cmd_keys(instance_id: str, *keys: str) -> int:
    window = _window_for(instance_id)
    if window is None or not keys:
        return 1
    backend = PostMessageBackend(window.hwnd)
    for key in keys:
        if key.lower().startswith("wait:"):
            time.sleep(float(key[5:]))
        else:
            tap(backend, key_to_vk(key))
            time.sleep(0.3)
        print(f"  {key}")
    return 0


def cmd_relaunch(instance_id: str, *flags: str) -> int:
    """Zamyka (łagodnie, potem siłą) TYLKO proces gry tej instancji i uruchamia ją ponownie przez launcher.
    Bez --yes: tryb „na sucho”, nic nie jest zamykane."""
    cfg = load_config()
    exe, instances_dir = cfg.launcher.exe, cfg.launcher.instances_dir
    if not (exe and instances_dir):
        found_exe, found_dir = L.detect_launcher()
        exe, instances_dir = exe or found_exe, instances_dir or found_dir
    account = next((a for a in cfg.accounts if a.instance_id == instance_id), None)
    nick = (account.nick or account.name) if account else ""
    profile = next((s for s in cfg.servers if account and s.id == account.server_id), None)
    server = profile.address if profile else ""
    if not nick:
        print("Brak konta dla tej instancji w config.json — nick będzie pusty (flaga -a pominięta).")
    argv = L.build_launch_argv(exe, cfg.launcher.args_template, instance=instance_id, server=server, nick=nick)
    procs = L.find_instance_processes(instances_dir, instance_id)
    print(f"Instancja:  {instance_id}")
    print(f"Do zamknięcia ({len(procs)}): " + (", ".join(f"PID {p.pid}" for p in procs) or "— żaden proces —"))
    print("Polecenie uruchomienia: " + " ".join(f'"{a}"' if " " in a else a for a in argv))
    if "--yes" not in flags:
        print("\nTRYB NA SUCHO — nic nie zostało zamknięte ani uruchomione. Dodaj --yes, żeby wykonać.")
        return 0
    pids = L.close_instance(instances_dir, instance_id, cfg.rejoin.close_timeout_s)
    print("Zamknięto PID: " + (", ".join(map(str, pids)) or "—"))
    L.launch_instance(exe, cfg.launcher.args_template, instance_id, server, nick)
    print("Uruchomiono launcher; czekam na okno gry…")
    window = L.wait_for_window(instance_id, cfg.rejoin.restart_timeout_s)
    print(f"Nowe okno: hwnd {window.hwnd}, PID {window.pid}" if window else "Okno gry nie pojawiło się w czasie.")
    return 0 if window else 1


def cmd_eat_test(instance_id: str) -> int:
    """Raz wykonuje krok jedzenia z ustawień konta (bez chodzenia i kopania)."""
    cfg = load_config()
    account = next((a for a in cfg.accounts if a.instance_id == instance_id), None)
    if account is None:
        print(f"Brak konta dla instancji „{instance_id}” w config.json.")
        return 1
    window = _window_for(instance_id)
    if window is None:
        return 1
    plan = EatPlan.from_account(account) or EatPlan.from_account(
        __import__("dataclasses").replace(account, eat_enabled=True))
    print(f"Slot kilofa {account.pickaxe_slot}, slot jedzenia {account.food_slot}, "
          f"PPM przez {account.eat_seconds:g} s")
    m = Miner(window, cfg)
    m.eat = plan
    m._select_pickaxe()
    print("Kilof w ręce; za 1 s jedzenie…")
    time.sleep(1)
    result = m._eat()
    m.sender.release_all()
    print("Gotowe: " + {"done": "zjedzono (albo pełny głód)", "stopped": "przerwano", "paused": "przerwano"}[result])
    return 0


def cmd_pause_test(instance_id: str, mine_s: str = "20", pause_s: str = "5") -> int:
    """Kopie `mine_s` s → pauza `pause_s` s → kopie 10 s → stop. Postać RUSZA SIĘ w grze — patrz na okno."""
    cfg = load_config()
    windows = [w for w in find_minecraft_windows() if L.instance_for_pid(w.pid) == instance_id]
    if len(windows) != 1:
        print(f"Znaleziono {len(windows)} okien dla instancji „{instance_id}” (potrzebne dokładnie 1).")
        return 1
    mine_s, pause_s = float(mine_s), float(pause_s)
    m = Miner(windows[0], cfg)
    start = time.monotonic()

    def log(msg: str) -> None:
        print(f"[{time.monotonic() - start:5.1f} s] {msg} | status: {m.status}, cykle: {m.cycles}")

    def released() -> str:
        held = getattr(m.sender, "_held", None)
        lmb = getattr(m.sender, "_lmb", getattr(m.sender, "_lmb_pressed", None))
        return f"wciśnięte klawisze: {sorted(held) if held else 'brak'}, LPM: {'WCIŚNIĘTY' if lmb else 'puszczony'}"

    m.start()
    time.sleep(mine_s)
    log("kopie")
    ok = m.pause()
    log(f"pauza (potwierdzona: {ok}); {released()}")
    time.sleep(pause_s)
    m.resume()
    time.sleep(1)
    log("wznowiono")
    time.sleep(10)
    m.stop()
    m.join(5)
    log(f"stop; {released()}")
    return 0 if ok else 1


COMMANDS = {"instances": cmd_instances, "replay": cmd_replay, "tail": cmd_tail, "discord-test": cmd_discord_test,
            "pause-test": cmd_pause_test, "chat": cmd_chat, "keys": cmd_keys,
            "relaunch": cmd_relaunch, "eat-test": cmd_eat_test}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    try:
        return COMMANDS[argv[1]](*argv[2:])
    except TypeError:
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
