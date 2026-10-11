# Kopacz Julci

Program do automatycznego kopania na stoniarkach w Minecrafcie. Działa na kilku oknach gry jednocześnie. Postać trzyma lewy przycisk myszy (kopie), idzie w prawo o ustaloną liczbę bloków, a potem wraca w lewo, cały czas kopiąc. Robi tak w kółko, bez Twojej obsługi, nawet przez kilka godzin.

Oprócz samego kopania program potrafi (każdą z tych rzeczy włączasz osobno, w zakładkach okna):
- **wysyłać komendy na czacie** według harmonogramu, osobno dla każdego konta,
- **samodzielnie wracać na serwer** po restarcie serwera (przeniesienie do lobby), po rozłączeniu, a w ostateczności po restarcie samej instancji gry,
- **przesyłać logi i alerty na Discorda** przez webhook, żebyś mógł zdalnie sprawdzać, co się dzieje.

Nic nie jest przypisane do jednego serwera: konta, profile serwerów, komendy (`/login`, `/server skyblock`…) i wzorce logu ustawiasz w programie. Opis jest w sekcji [8](#8-konta-serwer-i-powrót-na-serwer-opcjonalnie).

> ⚠️ Zanim zaczniesz, sprawdź regulamin serwera. Na wielu serwerach makra AFK są zakazane i grozi za nie ban. Automatyczne wracanie na serwer i komendy według harmonogramu zwiększają ryzyko, że bot zostanie zauważony.

**Wymagania:** Windows 10 lub 11.

Program możesz uruchomić na dwa sposoby:
- **Sposób A: gotowy plik `.exe`** (polecany). Nic nie instalujesz, wystarczy pobrać jeden plik.
- **Sposób B: z kodu źródłowego.** Potrzebny jest Python. Przydaje się, gdy chcesz zmieniać program albo sposób A nie działa.

---

## Sposób A: gotowy program (.exe)

### 1. Pobranie
1. Wejdź na **https://github.com/bboycoding/Kopacz/releases/latest**.
2. W sekcji **Assets** kliknij **`MojKopacz.exe`**, żeby go pobrać.
3. Utwórz na komputerze osobny folder, np. `Pulpit\Kopacz`, i przenieś do niego pobrany plik. Program zapisuje ustawienia w pliku `config.json`, a hasła i adres webhooka Discorda w zaszyfrowanym pliku `secrets.json`, oba obok siebie, więc najlepiej, żeby miał własny folder.

### 2. Uruchomienie
1. Kliknij dwa razy **`MojKopacz.exe`**.
2. Przy pierwszym uruchomieniu Windows może pokazać niebieskie okno **„System Windows ochronił ten komputer”**. Program nie ma płatnego podpisu cyfrowego, dlatego Windows go nie zna. Kliknij **Więcej informacji**, a potem **Uruchom mimo to**. Zrobisz to tylko raz.
3. Pierwsze uruchomienie może potrwać kilka sekund, bo program się rozpakowuje.

Gdy wyjdzie nowa wersja, pobierz nowy `MojKopacz.exe` i podmień stary plik w tym samym folderze. Ustawienia (`config.json`) i sekrety (`secrets.json`) zostaną.

Przejdź teraz do punktu **[5. Przygotowanie Minecrafta](#5-przygotowanie-minecrafta-za-każdym-razem)**.

---

## Sposób B: uruchomienie z kodu (Python)

### 1. Instalacja Pythona (jednorazowo)

1. Wejdź na **https://www.python.org/downloads/** i kliknij żółty przycisk **Download Python 3.x.x** (potrzebny jest Python 3.10 albo nowszy).
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

### 2. Pobranie programu z GitHuba

1. Wejdź na **https://github.com/bboycoding/Kopacz**.
2. Kliknij zielony przycisk **Code**, a potem **Download ZIP**.
3. Kliknij pobrany plik `Kopacz-main.zip` prawym przyciskiem myszy i wybierz **Wyodrębnij wszystkie…**.
4. Wypakowany folder `Kopacz-main` możesz zostawić w dowolnym miejscu, np. na Pulpicie.

> Jeśli znasz Gita, możesz zamiast tego wpisać `git clone https://github.com/bboycoding/Kopacz.git`. Później aktualizujesz program komendą `git pull`.

> ⚠️ **Aktualizacja z wersji 1.x przez Gita:** w wersji 2.0 plik `config.json` przestał być częścią repozytorium, więc `git pull` (albo merge) **usunie go z dysku**. Przed aktualizacją skopiuj `config.json` w bezpieczne miejsce i po aktualizacji przenieś go z powrotem. `secrets.json` nie jest dotknięty.

### 3. Instalacja potrzebnych bibliotek (jednorazowo)

1. Otwórz folder programu w Eksploratorze plików.
2. Kliknij w pasek adresu u góry okna, wpisz `cmd` i wciśnij Enter. Otworzy się konsola od razu w tym folderze.
3. Wpisz:
   ```
   python -m pip install -r requirements.txt
   ```
4. Poczekaj, aż instalacja się skończy. Instalują się trzy biblioteki: `customtkinter` (okno programu), `pywin32` (sterowanie oknami Minecrafta i szyfrowanie haseł) oraz `psutil` (rozpoznawanie, która instancja gry to które okno).

### 4. Uruchomienie programu

Kliknij dwa razy plik **`start.bat`** w folderze programu. Jeśli program się nie uruchomi, okno konsoli zostanie otwarte i będzie widać w nim komunikat błędu.

Możesz też w konsoli otwartej w folderze programu wpisać:
```
python main.py
```

**Własny plik .exe:** kliknij dwa razy **`build.bat`**. Po około minucie gotowy program pojawi się w folderze `dist` jako `MojKopacz.exe` i możesz go przenieść, gdzie chcesz (razem z `config.json`).

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

Ustawienia zapisują się w pliku `config.json` obok programu (obok `MojKopacz.exe` albo w folderze z kodem). Gdy plik się uszkodzi, program nie nadpisuje go po cichu: kopiuje go do `config.json.bad`, pokazuje komunikat i startuje z ustawieniami domyślnymi.

### Kopanie przez kilka godzin bez przesuwania się postaci
Przy każdym przejściu postać może przejść odrobinę za dużo albo za mało. Po kilku godzinach takie drobne różnice mogą się zsumować i postać zjedzie ze swojego miejsca. Jak temu zapobiec:
- Jeśli rząd stoniarek ma **ścianę na obu końcach**, ustaw **Dociąg do ściany** na **10–15%**. Postać przy każdej zawrotce opiera się o ścianę i wraca dokładnie w to samo miejsce.
- **Rozrzut czasu** ustawiaj tylko razem z dociągiem do ściany. Bez ścian rozrzut sprawi, że postać szybciej zjedzie z toru.

## 8. Konta, serwer i powrót na serwer (opcjonalnie)

Ta część jest potrzebna tylko do komend na czacie, powrotu na serwer i Discorda. Samo kopanie (punkty 5–7) działa bez niej. Wszystko ustawiasz w zakładkach u góry okna programu; nic nie trzeba edytować w plikach.

### 8.1 Launcher i konta

1. Zakładka **Zaawansowane → Launcher → Wykryj → Zapisz**. Program obsługuje launchery oparte na MultiMC (**Prism, Fjord, PolyMC, MultiMC**): rozpoznaje instancje i wie, które okno gry należy do której instancji, więc konto nie ginie, gdy okno dostanie nowy numer po restarcie gry. Szablon argumentów uruchomienia (`-l {instance} -s {server} -a {nick}`) został sprawdzony na Fjord Launcherze (`--help`). Przy innym launcherze sprawdź jego `--help` i popraw szablon.
2. Zakładka **Konta → Dodaj konto** (albo przycisk **+ Konto** przy oknie na liście kopania). Wypełnij: instancję, nick w grze, profil serwera, hasło do logowania na serwerze (opcjonalnie) i, jeśli chcesz, harmonogram komend. Pole „Komenda po powrocie na serwer” zostaw puste, jeśli po wejściu do trybu postać jest od razu na miejscu.

### 8.2 Profil serwera

Zakładka **Serwer**: kliknij **+ bfsmc.pl (przykład)** (gotowy przykład) albo **+ Pusty profil** i uzupełnij:

| Pole | Do czego służy |
|---|---|
| Adres serwera | Sprawdzenie, czy gra łączy z właściwym serwerem, i restart instancji (`-s`) |
| Komenda logowania | Np. `/login {password}`. Znacznik `{password}` zamieniany jest na hasło konta. Puste = serwer bez logowania |
| Komendy z lobby do gry | Np. `/server skyblock`. Wpisywane po przeniesieniu do lobby |
| Wzorce logu | Fragmenty linii z `latest.log`, po których bot rozpoznaje: prośbę o logowanie, zalogowanie, lobby, wejście do gry, przeniesienie do lobby i ban. To wyrażenia regularne |

Przycisk **Wybierz log i sprawdź…** przepuszcza wskazany `latest.log` (albo spakowany `.log.gz` ze starych sesji) przez Twoje wzorce i pokazuje, ile zdarzeń wykryto, z przykładowymi liniami. Dzięki temu dopasujesz bota do swojego serwera bez zgadywania. Linie czatu graczy (wzorzec „Czat graczy”) nigdy nie wywołują zdarzeń, więc nikt nie wymusi na bocie powrotu, wpisując na czacie np. „Rozłączono z lobby”.

### 8.3 Komendy według harmonogramu

W oknie konta, sekcja **Harmonogram komend na czacie**: wpisz komendę, co ile minut ma być wysyłana (minimum 0,1 min) i losowy rozrzut w sekundach (żeby kilka kont nie pisało w tej samej sekundzie). **Teraz** wysyła komendę od razu, bez zapisywania.

- Komenda wychodzi tylko wtedy, gdy konto kopie i okno jest połączone z serwerem. Na chwilę wstrzymuje ruch, wpisuje komendę przez klawisz czatu (domyślnie `T`, zmienisz go w **Zaawansowane → Czat i komendy**) i wznawia kopanie.
- **Gdy przegapiona:** jeśli termin minie, kiedy konto nie kopało (np. trwał powrót na serwer), **Odłóż** wysyła komendę raz po powrocie (po 60 s nieprzerwanego kopania, bez nadrabiania zaległości), a **Pomiń** czeka na kolejny termin.
- Limit gry to 256 znaków. Po otwarciu czatu program naciska jeszcze Backspace, żeby usunąć ewentualną zbędną literę „t”.

### 8.3a Jedzenie

W oknie konta, sekcja **Jedzenie**: zaznacz „Jedz co określoną liczbę cykli” i wpisz slot jedzenia (1–9), slot kilofa (1–9), co ile cykli jeść i jak długo trzymać prawy przycisk myszy (domyślnie 2,5 s; samo jedzenie w grze trwa 1,6 s).

- Na końcu co N-tego cyklu, gdy postać stoi przy ścianie, bot puszcza LPM, przełącza na slot z jedzeniem, trzyma PPM, wraca na slot z kilofem i kopie dalej. W wierszu konta widać wtedy status **JE**.
- Przy starcie kopania i po każdej pauzie bot sam bierze kilof do ręki.
- W slocie jedzenia **nie trzymaj bloków** — PPM by je postawił. Przy pełnym pasku głodu gra nie pozwala jeść, więc nic się nie stanie.
- Sprawdź ustawienia na jednym koncie: `python devtools.py eat-test <instancja>` (bez chodzenia: kilof → jedzenie → kilof).

### 8.4 Powrót na serwer

Włącz w **Zaawansowane → Powrót na serwer** (zaznacz pole, **Zapisz**). Obowiązuje od następnego startu kopania na koncie. Potrzebujesz: konta przypisanego do instancji, profilu serwera z komendami lobby i wzorcami, hasła konta (jeśli serwer wymaga logowania) i, dla restartu gry, ustawionego launchera.

| Sytuacja | Co robi program |
|---|---|
| **Przeniesienie do lobby** (np. restart trybu gry) | Natychmiast wstrzymuje kopanie. Po krótkiej pauzie wpisuje komendy lobby → gra z profilu, czeka na wzorzec „wejście do gry” i wznawia kopanie. Bez potwierdzenia ponawia z rosnącym odstępem (domyślnie 10, 20, 40, 80, 160, 300 s) |
| **Rozłączenie** (np. Timed out) | Wstrzymuje kopanie, naciska klawisze w menu (domyślnie `TAB, ENTER, wait:2, ENTER`), czeka na połączenie z właściwym serwerem, wpisuje komendę logowania z hasłem, a po wejściu do lobby wraca jak wyżej. Gdy serwer loguje sam, pomija logowanie |
| **Nic nie pomaga albo okno gry zniknęło** (crash) | Ostateczność: zamyka **tylko proces tej jednej instancji** (najpierw łagodnie, po 20 s siłą), uruchamia ją przez launcher, przepina kopacza na nowe okno i czeka na wejście na serwer |
| **Ban** | Tylko wstrzymanie i alert, bez ponawiania |
| **Wyczerpane próby** | Konto przechodzi w stan BŁĄD, kopanie jest wstrzymane, a Ty dostajesz **jeden** alert z pingiem i ostatnimi liniami logu. Przy włączonym „wolnym ponawianiu” (domyślnie co 30 min) bot próbuje dalej, bez kolejnych pingów |

Zabezpieczenia: gdy tytuł okna wskazuje, że postać jest w świecie gry, bot **nie naciska klawiszy menu** (Enter w grze mógłby coś zrobić). Po restarcie serwera wszystkie konta wracają **po kolei**, z odstępem co najmniej 10 s. F8 przerywa też powrót. Hasło nigdy nie trafia do komunikatów, logów ani na Discorda.

> ⚠️ Sekwencja klawiszy w menu zależy od wersji gry i od tego, który serwer jest zaznaczony na liście. **Sprawdź ją najpierw na jednym koncie**: przy ekranie „Disconnected” albo w menu wpisz `python devtools.py keys <instancja> TAB ENTER wait:2 ENTER` i zobacz, czy gra dołącza do właściwego serwera. Jeśli trafia gdzie indziej, popraw sekwencję w ustawieniach (np. dodaj `DOWN`). Program sprawdza adres w „Connecting to…” i przy złym serwerze anuluje połączenie.

Do próby prawdziwego rozłączenia tylko jednej instancji użyj programu **TCPView** (Sysinternals): znajdź połączenie procesu `javaw` tej instancji i wybierz **Close Connection**. Pozostałe konta nie zostaną ruszone.

### 8.5 Discord

1. W Discordzie: kanał → **Edytuj kanał → Integracje → Webhooki → Nowy webhook → Kopiuj adres**.
2. Zakładka **Discord**: zaznacz „Wysyłaj logi i alerty”, wklej adres webhooka, wpisz swoje ID użytkownika (do pingów), **Zapisz**, a potem **Wyślij test**.

Na kanał trafiają: zdarzenia bota (rozłączenie, przeniesienie do lobby, wejście do gry, ban, postęp powrotu, wysłane komendy), linie z nickiem konta (np. „Gracz <Twój nick> zdobył klucz…”) oraz linie pasujące do Twoich wzorców „Wysyłaj także”. Wzorce „Nigdy nie wysyłaj” odfiltrowują szum (przykładowy profil bfsmc.pl ustawia je za Ciebie), ale nie wycinają linii z nickiem Twojego konta — klucze innych graczy znikają, Twoje przychodzą. Linie z wielu kont łączą się w jedną wiadomość co kilka sekund, a alert o tym samym problemie na kilku kontach naraz to jedna wiadomość, np. „Rozłączone: 3/4 kont”. **Ping dostajesz tylko przy stanie BŁĄD i banie.** Awaria Discorda nigdy nie zatrzymuje kopania.

**Podsumowanie kluczy:** co godzinę (o pełnej godzinie; zmienisz to w polu „Podsumowanie kluczy co [min]”, 0 = wyłączone) przychodzi jedna wiadomość z liczbą kluczy każdego konta w tej godzinie i sumą od uruchomienia programu. Klucze są liczone według wzorca „Zdobycie nagrody (licznik kluczy)” w profilu serwera — w przykładzie bfsmc.pl to `Gracz {nick} zdobył klucz`, gdzie `{nick}` zastępowany jest nickiem konta. Liczone są tylko komunikaty serwera, nie czat graczy. Pojedyncze klucze nadal przychodzą na bieżąco.

### 8.6 Bezpieczeństwo i prywatność

- **Hasła i adres webhooka** są w pliku `secrets.json`, **zaszyfrowane Windows DPAPI**: odczyta je tylko ten sam użytkownik Windows na tym samym komputerze. Po przeniesieniu programu na inny komputer wpisz je ponownie. Ich nie ma w `config.json`.
- `config.json` zawiera konta, komendy i ustawienia, ale nie zawiera haseł. Mimo to nie wysyłaj go ani `secrets.json` nikomu; oba są w `.gitignore`. W repozytorium jest tylko `config.example.json` jako wzór.
- Program zamyka wyłącznie proces gry wybranej instancji. Launchera ani innych instancji nie rusza.

### 8.7 Narzędzia diagnostyczne (konsola)

W folderze z kodem (`python devtools.py …`):

| Polecenie | Co robi |
|---|---|
| `instances` | Launcher, instancje, okna gry i przypisane konta |
| `replay <plik> [preset]` | Zdarzenia wykryte w starym logu (`.log` / `.log.gz`) |
| `tail <instancja>` | Na żywo: zdarzenia z `latest.log` instancji |
| `discord-test` | Wiadomość testowa na zapisany webhook |
| `chat <instancja> "<tekst>"` | Wpisuje tekst lub komendę na czacie okna (prawdziwa wysyłka) |
| `keys <instancja> KLAWISZ…` | Naciska klawisze w oknie, np. `TAB ENTER wait:2 ENTER` |
| `pause-test <instancja>` | Kopanie → pauza → wznowienie → stop na prawdziwym oknie |
| `eat-test <instancja>` | Raz wykonuje jedzenie z ustawień konta (kilof → jedzenie → kilof) |
| `relaunch <instancja> [--yes]` | Restart jednej instancji; bez `--yes` tylko pokazuje, co by zrobił |

## Najczęstsze problemy

| Problem | Rozwiązanie |
|---|---|
| „System Windows ochronił ten komputer” | Kliknij **Więcej informacji** → **Uruchom mimo to** (sposób A, krok 2) |
| `'python' is not recognized…` | Python nie jest dodany do PATH, wróć do sposobu B, krok 1.5 |
| `No module named 'customtkinter'` / `'win32api'` | Nie zostały zainstalowane biblioteki, wykonaj sposób B, krok 3 |
| Lista okien jest pusta | Uruchom grę (nie sam launcher) i kliknij **Odśwież** |
| Postać stoi albo gra pokazuje menu pauzy | Wciśnij F3+P w tym oknie i zamknij menu |
| Postać chodzi, ale nie kopie | Kliknij w okno gry (nie może być otwartego menu ani ekwipunku); jeśli to nie pomoże, użyj metody „Pierwszy plan” |
| Postać przechodzi za daleko lub za mało | Zrób kalibrację jeszcze raz (punkt 6) |
| F8 nie działa | Inny program zajął już klawisz F8 (program pokaże o tym komunikat). Najczęściej to druga, wcześniej uruchomiona kopia Kopacza, więc ją zamknij. W ostateczności używaj przycisku **Stop wszystkie** |
| Okno nie przypisuje się do konta („brak konta”) | Ustaw launcher (**Zaawansowane → Wykryj**) i wybierz w koncie właściwą instancję. Okno rozpoznawane jest po instancji, więc działa tylko z launcherami typu Prism/MultiMC |
| „Nie udało się odczytać secrets.json” | Plik pochodzi z innego komputera albo użytkownika Windows. Wpisz hasła i webhook ponownie (zakładki Konta i Discord) |
| „Test nieudany: HTTP 404/401” w zakładce Discord | Adres webhooka jest nieprawidłowy albo usunięty. Utwórz nowy w ustawieniach kanału |
| Bot po rozłączeniu nie wraca na serwer | Sprawdź, czy powrót jest włączony (**Zaawansowane → Powrót na serwer**), czy konto ma hasło, a profil serwera komendę logowania, i czy sekwencja klawiszy w menu działa (punkt 8.4) |
| Konto w stanie „Błąd: nie udało się wrócić na serwer” | Wyczerpały się próby powrotu. Kopanie jest wstrzymane, a alert z ostatnimi liniami logu poszedł na Discorda. Gdy włączone jest wolne ponawianie, bot próbuje dalej sam |
| „Profil serwera nie ma komend lobby → gra” | W zakładce **Serwer** uzupełnij „Komendy z lobby do gry” |
| Grasz na innych klawiszach niż WASD | Wpisz swoje klawisze ruchu w pola „Klawisz w prawo/w lewo”; obsługiwane są litery, cyfry oraz `SPACE`, `SHIFT`, `CTRL`, `LEFT`, `RIGHT`, `UP`, `DOWN` |
