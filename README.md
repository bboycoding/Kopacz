# Kopacz Julci

Program do automatycznego kopania na stoniarkach w Minecrafcie. Działa na kilku oknach gry jednocześnie. Postać trzyma lewy przycisk myszy (kopie), idzie w prawo o ustaloną liczbę bloków, a potem wraca w lewo, cały czas kopiąc. Robi tak w kółko, bez Twojej obsługi, nawet przez kilka godzin.

> ⚠️ Zanim zaczniesz, sprawdź regulamin serwera. Na wielu serwerach makra AFK są zakazane i grozi za nie ban.

**Wymagania:** Windows 10 lub 11 i Python 3.10 albo nowszy.

---

## 1. Instalacja Pythona (jednorazowo)

1. Wejdź na **https://www.python.org/downloads/** i kliknij żółty przycisk **Download Python 3.x.x**.
2. Uruchom pobrany instalator.
3. **WAŻNE:** na pierwszym ekranie instalatora zaznacz na dole pole **„Add python.exe to PATH”**.
4. Kliknij **Install Now** i poczekaj, aż instalacja się skończy.
5. Sprawdź, czy wszystko działa:
   - wciśnij `Win + R`, wpisz `cmd` i wciśnij Enter,
   - w czarnym oknie wpisz:
     ```
     python --version
     ```
   - Jeśli pojawi się np. `Python 3.12.4`, wszystko jest OK.
   - Jeśli pojawi się błąd albo otworzy się Microsoft Store, to znaczy, że przy instalacji nie zaznaczyłeś „Add python.exe to PATH”. Uruchom instalator jeszcze raz, wybierz **Modify**, a potem **Next** i zaznacz **„Add Python to environment variables”**.

## 2. Pobranie programu

1. Pobierz folder `moj_kopacz`. Jeśli dostałeś go jako plik `.zip`, kliknij go prawym przyciskiem myszy i wybierz **Wyodrębnij wszystkie…**.
2. Wypakowany folder możesz zostawić w dowolnym miejscu, np. na Pulpicie.

## 3. Instalacja potrzebnych bibliotek (jednorazowo)

1. Otwórz folder `moj_kopacz` w Eksploratorze plików.
2. Kliknij w pasek adresu u góry okna, wpisz `cmd` i wciśnij Enter. Otworzy się konsola od razu w tym folderze.
3. Wpisz:
   ```
   python -m pip install -r requirements.txt
   ```
4. Poczekaj, aż instalacja się skończy. Instalują się dwie biblioteki: `customtkinter` (okno programu) i `pywin32` (sterowanie oknami Minecrafta).

## 4. Uruchomienie programu

W konsoli otwartej w folderze `moj_kopacz` wpisz:
```
python main.py
```

**Wygodniej:** w folderze programu jest plik **`start.bat`**. Wystarczy go dwukrotnie kliknąć. Jeśli program się nie uruchomi, okno konsoli zostanie otwarte i będzie widać w nim komunikat błędu.

## 5. Przygotowanie Minecrafta (za każdym razem)

Zrób to w **każdym** oknie gry, w którym ma kopać bot:

1. Wejdź na serwer i stań na początku rzędu stoniarek, przodem do kamienia.
2. Weź kilof do ręki.
3. Kliknij w okno gry, żeby **nie było otwartego żadnego menu**. Myszka ma sterować kamerą.
4. Wciśnij **F3 + P**. Na czacie pojawi się komunikat o wyłączeniu pauzy po utracie fokusu. Bez tego gra zatrzymuje się w menu pauzy, gdy przełączysz się na inne okno.

> 💡 Do odpalenia kilku kont naraz polecamy **Prism Launcher** (https://prismlauncher.org). Pozwala uruchomić kilka instancji gry jednocześnie, każdą w osobnym oknie.

## 6. Pierwsze uruchomienie: test i kalibracja

### Test okna
1. W programie kliknij **Odśwież**. Na liście pojawią się okna Minecrafta.
   - Przycisk **Pokaż** miga danym oknem na pasku zadań, dzięki czemu wiesz, które okno to które konto.
2. Zostaw zaznaczone **tylko jedno** okno i kliknij **Test okna (3 s)**.
3. Przełącz się na grę i sprawdź, czy postać przez 3 sekundy idzie w prawo i kopie.
   - **Działa:** zostaw metodę inputu **„W tle (PostMessage)”**. Wszystkie okna będą kopać jednocześnie, a Ty możesz w tym czasie używać komputera.
   - **Nie działa:** zmień **Metoda inputu** na **„Pierwszy plan (po kolei)”** i powtórz test. Ten tryb działa zawsze, ale program sam przełącza się między oknami gry. Przy kilku oknach kopią one na zmianę, a komputera nie da się w tym czasie normalnie używać.

### Kalibracja odległości
Program mierzy odległość czasem, a nie liczbą bloków. Dlatego trzeba raz sprawdzić, ile czasu postać potrzebuje na przejście jednego bloku.

1. Kliknij **Kalibruj: idź 10 bloków**.
2. Policz w grze, ile bloków faktycznie przeszła postać.
3. Wpisz tę liczbę w pole **Przeszło bloków** i kliknij **Przelicz**.
4. Powtórz kalibrację, aż postać będzie przechodzić równo 10 bloków. Wynik zapisuje się automatycznie.

## 7. Kopanie

1. Wpisz **Ilość bloków**, czyli o ile bloków postać ma iść w każdą stronę (np. długość rzędu stoniarek).
2. Zaznacz okna, w których ma kopać bot.
3. Kliknij **▶ Start zaznaczone**.
4. Przy każdym oknie widać jego stan, liczbę cykli i czas pracy. Pojedyncze okno możesz włączyć lub wyłączyć jego własnym przyciskiem **Start/Stop**.
5. **Klawisz F8 zatrzymuje wszystko** i działa nawet wtedy, gdy okno programu nie jest na wierzchu.

## Ustawienia: co oznacza każde pole

| Pole | Opis | Domyślnie |
|---|---|---|
| Ilość bloków | O ile bloków postać idzie w prawo i z powrotem | 5 |
| Sekundy na blok | Czas przejścia jednego bloku (ustawiany przez kalibrację) | 0.231 |
| Pauza na zawrotce [s] | Krótki postój na końcu rzędu | 0.3 |
| Klawisz w prawo / w lewo | Klawisze ruchu z ustawień gry | D / A |
| Odśwież LPM co N cykli | Co ile cykli bot puszcza i wciska LPM na nowo (zabezpieczenie przed „zgubieniem” kliknięcia przy lagu); 0 = nigdy | 5 |
| Dociąg do ściany [%] | Bot idzie o tyle procent dłużej, żeby oprzeć się o ścianę na końcu rzędu | 0 |
| Rozrzut czasu ±[%] | Losowa zmiana długości każdego przejścia | 0 |
| Metoda inputu | „W tle” (wszystkie okna naraz) albo „Pierwszy plan” (po kolei) | W tle |

Ustawienia zapisują się w pliku `config.json` w folderze programu.

### Kopanie przez kilka godzin bez przesuwania się postaci
Przy każdym przejściu postać może przejść odrobinę za dużo albo za mało. Po kilku godzinach takie drobne różnice mogą się zsumować i postać zjedzie ze swojego miejsca. Jak temu zapobiec:
- Jeśli rząd stoniarek ma **ścianę na obu końcach**, ustaw **Dociąg do ściany** na **10–15%**. Postać przy każdej zawrotce opiera się o ścianę i wraca dokładnie w to samo miejsce.
- **Rozrzut czasu** ustawiaj tylko razem z dociągiem do ściany. Bez ścian rozrzut sprawi, że postać szybciej zjedzie z toru.

## Najczęstsze problemy

| Problem | Rozwiązanie |
|---|---|
| `'python' is not recognized…` | Python nie jest dodany do PATH, wróć do kroku 1.5 |
| `No module named 'customtkinter'` / `'win32api'` | Nie zostały zainstalowane biblioteki, wykonaj krok 3 |
| Lista okien jest pusta | Uruchom grę (nie sam launcher) i kliknij **Odśwież** |
| Postać stoi albo gra pokazuje menu pauzy | Wciśnij F3+P w tym oknie i zamknij menu |
| Postać chodzi, ale nie kopie | Kliknij w okno gry (nie może być otwartego menu ani ekwipunku); jeśli to nie pomoże, użyj metody „Pierwszy plan” |
| Postać przechodzi za daleko lub za mało | Zrób kalibrację jeszcze raz (punkt 6) |
| F8 nie działa | Inny program zajął już klawisz F8 (program pokaże o tym komunikat), wtedy używaj przycisku **Stop wszystkie** |
| Grasz na innych klawiszach niż WASD | Wpisz swoje klawisze ruchu w pola „Klawisz w prawo/w lewo”; obsługiwane są litery, cyfry oraz `SPACE`, `SHIFT`, `CTRL`, `LEFT`, `RIGHT`, `UP`, `DOWN` |
