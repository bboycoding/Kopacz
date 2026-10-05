# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projekt

„Mój Kopacz” — autorski bot AFK do kopania na stoniarkach (blok endu + generujący się stone) w Minecrafcie, w wielu oknach naraz. Cykl: trzyma LPM, idzie klawiszem w prawo przez `bloki × sec_per_block`, pauza, wraca w lewo tyle samo — w pętli. Windows-only (pywin32). Cały interfejs i komunikaty po polsku.

## Komendy

- Instalacja: `python -m pip install -r requirements.txt`
- Uruchomienie: `python main.py`
- Exe (opcjonalnie): `pyinstaller --onefile --windowed --name MojKopacz main.py` — `config.json` jest wtedy obok exe (`config.BASE_DIR`).
- Brak testów automatycznych; logikę `Miner` da się sprawdzić bez MC, podmieniając `miner.make_sender` na atrapę nagrywającą wywołania.

## Architektura

- `windows.py` — wykrywanie okien gry po klasie (`GLFW30` dla 1.13+, `LWJGL` dla 1.8–1.12), fallback po tytule `^Minecraft` bez launcherów.
- `win_input.py` — dwa backendy o wspólnym interfejsie (`session()`, `key_down/up`, `lmb_down/up`, `hold_tick`, `release_all`):
  - `PostMessageBackend` — `WM_KEYDOWN/UP` i `WM_LBUTTONDOWN/UP` do okna w tle; wszystkie okna naprawdę równolegle. lParam musi zawierać scan code (bity 16–23), bo GLFW mapuje klawisze po scan code, nie po VK.
  - `ForegroundBackend` — `SetForegroundWindow` + `keybd_event`/`mouse_event`; globalny `_FOREGROUND_LOCK` sprawia, że przy wielu oknach odcinki ruchu idą po kolei. Input fizyczny wysyłany tylko wewnątrz `session()`; `lmb_down` poza sesją tylko zapamiętuje intencję.
- `miner.py` — `Miner(threading.Thread)` na okno; `_hold()` trzyma klawisz w kawałkach co `HOLD_TICK` (stop reaguje szybko). `finally` zawsze woła `release_all()` — nie usuwać, inaczej postać zostaje z wciśniętym klawiszem. Nie nazywać atrybutu `_stop` (koliduje z `threading.Thread._stop`).
- `gui.py` — customtkinter; wątki kopaczy nigdy nie dotykają widgetów — GUI odpytuje `miner.status/cycles/runtime` w `_tick()` co 500 ms. Skrót F8 (`hotkey.py`, `RegisterHotKey` + własna pętla komunikatów w wątku) tylko ustawia eventy/stop, resztę robi `_tick()`.
- `config.py` — dataclass `Config` ↔ `config.json`; uszkodzony plik → wartości domyślne. `validate()` trzyma zakresy pól.

## Uwagi dot. gry

- W każdym oknie MC trzeba wcisnąć F3+P (brak pauzy po utracie fokusu) i mieć złapaną mysz (bez otwartego menu), inaczej w trybie PostMessage gra ignoruje atak.
- Dystans jest czasowy: `sec_per_block` kalibrowany w GUI („idź 10 bloków” → „Przelicz”). `wall_push_pct` > 0 dociąga postać do ścian na końcach toru, co eliminuje dryf przy wielogodzinnej pracy; `jitter_pct` bez ścian powoduje dryf (błądzenie losowe).
