"""Narzędzia diagnostyczne z konsoli (bez GUI).

  python devtools.py instances    — launcher, instancje, okna gry i konta
"""
import sys

import launcher as L
from config import load_config
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


COMMANDS = {"instances": cmd_instances}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[argv[1]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
