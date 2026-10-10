@echo off
rem Buduje dist\MojKopacz.exe (jeden plik, bez okna konsoli).
cd /d "%~dp0"

python -m PyInstaller --version >nul 2>&1 || python -m pip install pyinstaller || goto :error

rem customtkinter wczytuje w trakcie dzialania swoje motywy (.json) i fonty - trzeba je dolaczyc.
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MojKopacz --collect-data customtkinter main.py || goto :error

rem Ustawienia (config.json) i zaszyfrowane sekrety (secrets.json) program tworzy sam obok exe (config.BASE_DIR).
rem Nie kopiujemy tu prywatnych plikow - exe ma trafiac do innych osob bez Twoich kont i hasel.

echo.
echo Gotowe: dist\MojKopacz.exe
pause
exit /b 0

:error
echo.
echo Budowanie nie powiodlo sie.
pause
exit /b 1
