"""Launcher Minecrafta (Prism / Fjord / PolyMC / MultiMC): wykrywanie, instancje, przypisanie okna do instancji."""
import json
import os
import re
from dataclasses import dataclass

import psutil

LAUNCHER_PROCESSES = ("fjordlauncher", "prismlauncher", "polymc", "multimc")
_NATIVES_RE = re.compile(r"^-Djava\.library\.path=(.+)$")


@dataclass(frozen=True)
class Instance:
    id: str          # nazwa folderu — to jest argument `-l` launchera
    name: str        # nazwa wyświetlana
    path: str
    log_path: str    # .../minecraft/logs/latest.log (może jeszcze nie istnieć)


def _proc_name(p: psutil.Process) -> str:
    return os.path.splitext(p.name().lower())[0]


def instance_dir_from_pid(pid: int) -> str | None:
    """Folder instancji procesu javaw: katalog nadrzędny `natives` z -Djava.library.path."""
    try:
        cmdline = psutil.Process(pid).cmdline()
    except (psutil.Error, OSError):
        return None
    for arg in cmdline:
        m = _NATIVES_RE.match(arg)
        if m:
            natives = os.path.normpath(m.group(1).strip('"'))
            if os.path.basename(natives).lower() == "natives":
                return os.path.dirname(natives)
    return None


def instance_for_pid(pid: int) -> str | None:
    """ID instancji (nazwa folderu) dla procesu gry albo None."""
    d = instance_dir_from_pid(pid)
    return os.path.basename(d) if d else None


def _minecraft_dir(instance_path: str) -> str:
    for name in ("minecraft", ".minecraft"):
        p = os.path.join(instance_path, name)
        if os.path.isdir(p):
            return p
    return os.path.join(instance_path, "minecraft")


def _cfg_name(instance_path: str, fallback: str) -> str:
    try:
        with open(os.path.join(instance_path, "instance.cfg"), encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("name="):
                    return line[5:].strip() or fallback
    except OSError:
        pass
    return fallback


def list_instances(instances_dir: str) -> list[Instance]:
    if not instances_dir or not os.path.isdir(instances_dir):
        return []
    result = []
    for entry in sorted(os.listdir(instances_dir), key=str.lower):
        path = os.path.join(instances_dir, entry)
        if os.path.isfile(os.path.join(path, "instance.cfg")):
            log = os.path.join(_minecraft_dir(path), "logs", "latest.log")
            result.append(Instance(entry, _cfg_name(path, entry), path, log))
    return result


def log_path_for(instances_dir: str, instance_id: str) -> str:
    return os.path.join(_minecraft_dir(os.path.join(instances_dir, instance_id)), "logs", "latest.log")


def list_profile_names(instances_dir: str) -> list[str]:
    """Nazwy profili z accounts.json launchera (tylko nazwy, tokeny nie są czytane)."""
    if not instances_dir:
        return []
    path = os.path.join(os.path.dirname(os.path.normpath(instances_dir)), "accounts.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [a["profile"]["name"] for a in data.get("accounts", []) if a.get("profile", {}).get("name")]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def detect_launcher() -> tuple[str, str]:
    """Zwraca (exe, instances_dir); puste napisy, gdy nie znaleziono."""
    exe = ""
    instances_dir = ""
    # 1) Działająca gra: javaw -> katalog instancji -> katalog instances; rodzic procesu = launcher.
    for p in psutil.process_iter(["name", "pid"]):
        try:
            if _proc_name(p) not in ("javaw", "java"):
                continue
            d = instance_dir_from_pid(p.info["pid"])
            if not d:
                continue
            instances_dir = os.path.dirname(d)
            parent = p.parent()
            if parent and _proc_name(parent) in LAUNCHER_PROCESSES:
                exe = parent.exe()
            break
        except (psutil.Error, OSError):
            continue
    # 2) Działający launcher bez gry.
    if not exe:
        for p in psutil.process_iter(["name"]):
            try:
                if _proc_name(p) in LAUNCHER_PROCESSES:
                    exe = p.exe()
                    break
            except (psutil.Error, OSError):
                continue
    # 3) Typowe miejsca instalacji.
    if not exe:
        exe = _search_common_paths()
    exe = _stable_path(exe)
    instances_dir = _stable_path(instances_dir)
    if exe and not instances_dir:
        instances_dir = _instances_dir_for_exe(exe)
    return exe, instances_dir


def _stable_path(path: str) -> str:
    """scoop trzyma wersję w folderze apps\\<nazwa>\\<wersja>; junction `current` przetrwa aktualizację."""
    if not path:
        return path
    parts = os.path.normpath(path).split(os.sep)
    for i, part in enumerate(parts):
        if part.lower() == "apps" and i + 2 < len(parts) and "scoop" in "".join(parts[:i]).lower():
            candidate = os.sep.join([*parts[:i + 2], "current", *parts[i + 3:]])
            if os.path.exists(candidate):
                return candidate
    return path


def _search_common_paths() -> str:
    env = os.environ
    roots = [os.path.join(env.get("USERPROFILE", ""), "scoop", "apps"),
             os.path.join(env.get("LOCALAPPDATA", ""), "Programs"),
             env.get("ProgramFiles", ""), env.get("ProgramFiles(x86)", "")]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if not any(k in name.lower() for k in LAUNCHER_PROCESSES):
                continue
            base = os.path.join(root, name)
            for sub in ("current", ""):
                for exe_name in os.listdir(os.path.join(base, sub)) if os.path.isdir(os.path.join(base, sub)) else []:
                    if exe_name.lower().endswith(".exe") and os.path.splitext(exe_name.lower())[0] in LAUNCHER_PROCESSES:
                        return os.path.join(base, sub, exe_name)
    return ""


def _instances_dir_for_exe(exe: str) -> str:
    exe_dir = os.path.dirname(exe)
    portable = os.path.join(exe_dir, "instances")
    if os.path.isdir(portable):
        return portable
    appdata = os.environ.get("APPDATA", "")
    for folder in ("FjordLauncher", "PrismLauncher", "PolyMC", "MultiMC"):
        cand = os.path.join(appdata, folder, "instances")
        if os.path.isdir(cand) and folder.lower() in os.path.basename(exe).lower():
            return cand
    return ""
