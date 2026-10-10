"""Launcher Minecrafta (Prism / Fjord / PolyMC / MultiMC): wykrywanie, instancje, przypisanie okna do instancji."""
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass

import psutil
import win32api
import win32con

from windows import find_minecraft_windows

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


# ---------- restart instancji (ostateczność) ----------

GAME_PROCESS_NAMES = ("javaw", "java")
_FLAG_RE = re.compile(r"^-{1,2}[A-Za-z]")


class RestartError(Exception):
    """Nie udało się zamknąć albo uruchomić instancji."""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def find_instance_processes(instances_dir: str, instance_id: str,
                            names: tuple[str, ...] = GAME_PROCESS_NAMES) -> list[psutil.Process]:
    """Procesy gry, które należą do tej JEDNEJ instancji (po -Djava.library.path=.../<id>/natives).
    Nigdy nie zwraca launchera ani procesów innych instancji."""
    if not instances_dir or not instance_id:
        return []
    target = _norm(os.path.join(instances_dir, instance_id))
    found = []
    for p in psutil.process_iter(["name", "pid"]):
        try:
            if _proc_name(p) not in names:
                continue
            d = instance_dir_from_pid(p.info["pid"])
            if d and _norm(d) == target:
                found.append(p)
        except (psutil.Error, OSError):
            continue
    return found


def close_instance(instances_dir: str, instance_id: str, timeout: float = 20.0,
                   stop_event: threading.Event | None = None,
                   names: tuple[str, ...] = GAME_PROCESS_NAMES) -> list[int]:
    """Zamyka grę tej instancji: najpierw łagodnie (WM_CLOSE do jej okien — kod wyjścia 0, launcher nie
    pokazuje komunikatu o awarii), po `timeout` s terminate, na końcu kill. Zwraca PID-y zamkniętych procesów."""
    procs = find_instance_processes(instances_dir, instance_id, names)
    pids = [p.pid for p in procs]
    if not procs:
        return []
    for w in find_minecraft_windows():
        if w.pid in pids:
            try:
                win32api.PostMessage(w.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:  # noqa: BLE001 — okno mogło zniknąć w międzyczasie
                pass
    stop = stop_event or threading.Event()
    deadline = time.monotonic() + timeout
    alive = procs
    while alive and time.monotonic() < deadline and not stop.is_set():
        _, alive = psutil.wait_procs(alive, timeout=0.5)
    if stop.is_set():
        return pids
    for p in alive:
        try:
            p.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(alive, timeout=5)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(alive, timeout=5)
    return pids


def build_launch_argv(exe: str, template: str, **values: str) -> list[str]:
    """Argumenty uruchomienia z szablonu, np. "-l {instance} -s {server} -a {nick}".
    Każdy token podstawiany osobno, więc wartości ze spacjami i nawiasami (np. „1.21.11(2)”) zostają
    jednym argumentem. Opcja z pustą wartością (np. brak adresu serwera) jest pomijana razem z flagą."""
    argv: list[str] = []
    for token in template.split():
        try:
            rendered = token.format(**values)
        except (KeyError, IndexError) as e:
            raise ValueError(f"Nieznane pole w szablonie argumentów: {e}") from e
        if "{" in token and not rendered.strip():
            if argv and _FLAG_RE.match(argv[-1]):
                argv.pop()
            continue
        argv.append(rendered)
    return [exe, *argv]


def launch_instance(exe: str, template: str, instance: str, server: str, nick: str) -> subprocess.Popen:
    if not exe or not os.path.isfile(exe):
        raise RestartError(f"Nie znaleziono launchera: {exe or '(nie ustawiony)'}")
    argv = build_launch_argv(exe, template, instance=instance, server=server, nick=nick)
    try:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, close_fds=True,
                                creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    except OSError as e:
        raise RestartError(f"Nie udało się uruchomić launchera: {e}") from e


def wait_for_window(instance_id: str, timeout: float, stop_event: threading.Event | None = None,
                    exclude: set[int] = frozenset()):
    """Czeka na okno gry tej instancji (poza `exclude`, np. starym hwnd). Zwraca McWindow albo None."""
    stop = stop_event or threading.Event()
    deadline = time.monotonic() + timeout
    while not stop.is_set():
        for w in find_minecraft_windows():
            if w.hwnd not in exclude and instance_for_pid(w.pid) == instance_id:
                return w
        if time.monotonic() >= deadline:
            return None
        stop.wait(1.0)
    return None


@dataclass
class GameRestarter:
    """Zamyka i uruchamia ponownie JEDNĄ instancję launchera."""
    exe: str
    args_template: str
    instances_dir: str
    instance_id: str
    nick: str
    server: str
    close_timeout_s: float = 20.0
    window_timeout_s: float = 120.0

    def available(self) -> bool:
        return bool(self.exe and self.instances_dir and self.instance_id)

    def close(self, stop_event: threading.Event | None = None) -> list[int]:
        return close_instance(self.instances_dir, self.instance_id, self.close_timeout_s, stop_event)

    def launch(self) -> None:
        launch_instance(self.exe, self.args_template, self.instance_id, self.server, self.nick)

    def wait_window(self, stop_event: threading.Event, exclude: set[int]):
        return wait_for_window(self.instance_id, self.window_timeout_s, stop_event, exclude)
