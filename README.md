# Spy vs Spy — Picocomputer 6502

Natywny port dostarczonego `xex/SpyVsSpy.xex` (Atari XL/XE, HOMESOFT).
Gotowy program: **`build/cc65/release/spy-vs-spy.rp6502`**.
Kopia z numerem wersji: **`build/cc65/release/spy-vs-spy-r12.rp6502`**.
Na dole menu tej wersji widnieje `SPY R12 MUSIC 49.6125 HZ`.

R11 dodaje oryginalny ekran startowy z `xex/Spy Vs Spy (v2).xex`,
łącznie ze zmianami palety w trzech procedurach DLI. Ekran jest widoczny
przez 8 sekund; Spacja, Enter, fire lub Start na padzie pomija oczekiwanie.
Przycisk trzeba puścić przed przejściem do menu, aby nie uruchomić od razu gry.
Kod rozgrywki pochodzi nadal z `SpyVsSpy.xex`, a tempo muzyki zachowuje
zaakceptowane na sprzęcie ustawienie R10: 49,6125 Hz.

R12 oddziela start splasha od inicjalizacji gry. Po splashu wyłącza mapowanie
klawiatury i padów, a następnie wykonuje pełny start R10, zerując również
emulowane rejestry Atari. Kod obsługi gry i jego adresy są identyczne z R10;
tablice różnią się jedynie numerem wersji w stopce. Splash zajmuje osobny
obszar $E000–$E3FB i uruchamia się z wektora resetu $E000.
Pominięcie ekranu wymaga nowego naciśnięcia po zwolnieniu przycisków,
więc klawisz trzymany podczas uruchamiania nie zamyka go od razu.
Konfiguracja F5 w VS Code jawnie ustawia zegar emulatora na 8 MHz.

Oryginalny kod rozgrywki wykonuje się bezpośrednio na procesorze 6502.
Nowa warstwa obsługuje grafikę VGA, klawiaturę, dwa pady i dźwięk PSG.

## Stan wersji

Wersja testowa. W RP6502-EMU przy 8 MHz sprawdzono menu, wybór dwóch graczy,
rozpoczęcie gry, ruch obu szpiegów, przyciski akcji, pad, powrót do menu
oraz dłuższe działanie bez uszkadzania kodu. Test sprawdza także 60 wywołań
VBI na sekundę w menu. Oryginalne znaki 4×8 w czterech kolorach trafiają
do XRAM bez konwersji. VGA wyświetla je jako małe sprite'y, podwajając
szerokość do 8 pikseli. Obrazy znaków zajmują $0000–$21FF, a ich stałe
deskryptory $4000–$6A2F. W każdej obsłudze VSYNC przesyłane jest całe
górne lub dolne pole oraz wiersz statusu. Oba pola są odświeżane w dwóch
przerwaniach, około 33 ms przy 60 Hz, bez cache ani kolejki zmian.

Test z oddzielnymi kopiami pamięci RIA/VGA sprawdza pozycje, palety i format
znaków, pełne przerysowanie i odzyskanie obrazu po utracie serii zapisów PIX.
W tych przypadkach limit wynosi dwa przerwania. Dodatkowe zgłoszenie IRQ
w tej samej klatce VGA nie wykonuje ponownie VBI ani aktualizacji muzyki.
Użytkownik potwierdził poprawne działanie R10 na Pico. W R11 zgłosił zawieszanie
menu na sprzęcie oraz szybkie pomijanie splasha w emulatorze. Zmiany startu
w R12 sprawdzono testami; usunięcie zawieszania wymaga potwierdzenia na Pico.

Nie przeprowadzono pełnej rozgrywki do zwycięstwa.
Kolory są przybliżeniem palety Atari. Oryginalne procedury muzyki i efektów
korzystają z przybliżonej syntezy POKEY przez PSG; nie odtwarza ona dokładnie
wielomianów szumu ani wszystkich trybów łączenia kanałów.

## Uruchomienie

W emulatorze:

```powershell
.\tools\rp6502-emu.exe build/cc65/release/spy-vs-spy.rp6502 --phi2 8000
```

Emulator nie jest częścią kodu źródłowego. W tym środowisku jego lokalna kopia
znajduje się w `tools/`. Na nowym komputerze potrzebny jest
[RP6502-EMU](https://picocomputer.github.io/emu.html) obsługujący własne
rozmiary sprite'ów VGA (mode 5 custom).

Na Picocomputerze można wgrać ROM narzędziem SDK:

```powershell
python tools/rp6502.py run build/cc65/release/spy-vs-spy.rp6502
```

Opcje połączenia szeregowego opisuje `python tools/rp6502.py run --help`.
Port jest przygotowany do pracy przy 8 MHz.

Tempo gry jest ograniczone w kodzie: główna pętla wykonuje maksymalnie
60 obiegów na sekundę, czyli do 30 aktualizacji na każdego z dwóch
obsługiwanych naprzemiennie graczy. Oczekiwanie korzysta z zegara VGA,
nie z liczby cykli CPU; po opóźnieniu nie ma serii przyspieszonych aktualizacji.
Opóźnienia menu i dłuższych sekwencji również korzystają z tego zegara,
z czasami obliczonymi dla 1,773447 MHz i zaokrąglonymi do klatek.
Jest to regulacja tempa portu, a nie dokładna emulacja czasowa Atari.
Pozostaw 8 MHz — przy 2 MHz obsługa grafiki może nie nadążać.

## Sterowanie

| Funkcja | Klawisze |
| --- | --- |
| Biały szpieg / joystick 1 | Strzałki + Spacja |
| Czarny szpieg / joystick 2 | WASD + lewy Shift |
| Start | Spacja lub Enter / F2 |
| Powrót do menu (Atari OPTION) | F4 |
| Pauza podczas gry | Esc |
| Włączanie/wyłączanie muzyki | M |

W menu góra/dół wybiera pozycję, lewo/prawo zmienia wartość, a fire
uruchamia grę. Dostępne są dwa pady: krzyżak lub lewy drążek porusza
szpiegiem, A/B wykonuje akcję, Start odpowiada START, a Home — OPTION.
W trybie jednoosobowym należy uwzględnić wybraną w menu stronę komputera
(`COMPUTER IS PLAYER`).

## Muzyka i efekty

Port zachowuje oryginalną melodię, sekwencje 19 efektów i ich obwiednie
głośności. Cztery kanały PSG obsługują dwa głosy muzyki i efekty obu szpiegów.
Rejestry dźwięku są odczytywane bezpośrednio po VBI, przed procedurami
rastrowymi — pierwszy głos muzyki nie jest już przypadkowo wyciszany co
drugą klatkę. Dla podtrzymywanych nut wykorzystywany jest również stan
sekwencera, ponieważ nie zapisuje on rejestrów POKEY w każdej klatce.
Tryby POKEY `$Ax` i `$Ex` dają czysty ton.

Sekwencer muzyki pracuje z tempem 49,6125 aktualizacji na sekundę, o 5% wyższym
od 47,25 Hz w R09. Jest to korekta tempa po odsłuchu na sprzęcie.
Przekierowanie oryginalnego wywołania pod $7550 wykonuje 1323 aktualizacje
na 1600 taktów VGA, bez zmiany wysokości dźwięków, tempa rozgrywki ani efektów.

Wysokość tonów jest obliczana dla zegara PAL 1,773447 MHz. Przeliczenie
głośności uwzględnia logarytmiczną skalę PSG i pozostawia zapas dla sumy
czterech kanałów. Subtelne stereo rozdziela efekty szpiegów i dwa głosy
melodii, zachowując wszystkie dźwięki w obu głośnikach. Klawisz **M** wycisza
samą muzykę; efekty pozostają aktywne.

Tryby szumu nadal korzystają z przybliżenia PSG, więc ich barwa różni się
od POKEY. Port nie emuluje dokładnie jego generatorów wielomianowych;
w sprawdzonych sekwencjach gry `AUDCTL=0`.

Test audio zapisuje ślady rejestrów w `build/cc65/release/audio/`.
Można z nich przygotować próbki do odsłuchu:

```powershell
python tools/preview_audio.py build/cc65/release/audio/menu.json build/cc65/release/audio/menu.wav
python tools/preview_audio.py build/cc65/release/audio/effects.json build/cc65/release/audio/effects.wav
```

WAV-y powstają w programowym modelu PSG, nie są nagraniem fizycznego
Picocomputera. Obok nich powstają pliki `*.stats.json` z poziomem szczytowym
i liczbą przesterowanych próbek.

## Budowanie i testy

Wymagane: Python 3, CMake 3.28+, Ninja oraz `ca65` i `ld65` z cc65 w PATH.
Nie jest potrzebny runtime C ani zmodyfikowany kompilator cc65.

```powershell
cmake --preset cc65/Release
cmake --build --preset cc65/Release
ctest --test-dir build/cc65/release --output-on-failure
```

Pakiet py65 wykonuje oryginalny dekompresor i DLI ekranu startowego podczas budowania
na komputerze. Nie trafia do programu RP6502. Można go również zainstalować
w aktywnym środowisku Pythona bez opcji `--target`.

Przed każdą kompilacją CMake sprawdza import wymaganych modułów `py65`
przy użyciu tego samego interpretera, który buduje ROM. Jeśli pakietu brakuje
lub jego instalacja jest niepełna, instaluje zależności z `requirements-build.txt`
do `build/python-deps` z opcją `--upgrade`. Ten krok wymaga dostępu do pakietu
przez pip; po poprawnej instalacji kolejne kompilacje działają bez sieci.
Dotyczy to także przycisku Build w VS Code. Ręczne przygotowanie zależności:

```powershell
python -m pip install --upgrade --target build/python-deps -r requirements-build.txt
```

Na Windows skrypt po instalacji włącza dziedziczenie uprawnień katalogu
zależności z projektu. Pip może przenieść katalogi z TEMP razem z uprawnieniami
prywatnymi dla konta instalującego; bez tego kroku inne konto uruchamiające
VS Code może otrzymać `ModuleNotFoundError` lub `WinError 5`.

Testy natywnego ekranu startowego, gry i audio są rejestrowane, gdy CMake znajdzie `rp6502-emu` w `tools/`
lub PATH. Można podać `-DSPY_EMULATOR=/ścieżka/do/rp6502-emu`.
Test uruchamia rzeczywisty ROM i używa klawiatury/pada bez haków testowych
ani ustawiania pozycji postaci. Zrzuty po teście: `test-game.png`
i `test-menu.png` w katalogu kompilacji.
Test audio dodatkowo zgłasza wszystkie 19 identyfikatorów efektów przez
oryginalną kolejkę gry i sprawdza rejestry PSG, dwa głosy muzyki,
równoczesne efekty obu szpiegów oraz wyciszanie i wznawianie klawiszem M.
Test `title-pixels` porównuje każdy piksel obrazu z danymi XEX i paletami DLI.
Test `native-title` sprawdza zawartość XRAM, pomijanie ekranu klawiaturą i oboma
padami, przytrzymany przycisk oraz automatyczne przejście do menu.
Sprawdza również klawisz Enter i fire pada trzymane już podczas uruchamiania:
ich zwolnienie nie może zamknąć splasha.
Zrzut ekranu startowego: `test-title.png`; obraz wyodrębniony z XEX: `title.png`.
CI buduje ROM i uruchamia testy XEX, obrazu startowego, opóźnień, grafiki i tempa muzyki; testy natywne wymagają
lokalnego emulatora.

Test `graphics` wykonuje zbudowaną procedurę 65C02 w modelu portali XRAM,
z osobnymi kopiami pamięci RIA i VGA. Sprawdza 1080 deskryptorów znaków,
odświeżanie obu pól, statusu oraz naprawę utraconych zapisów.
Nie modeluje opóźnień magistrali fizycznego Pico.
Test `music-tempo` porównuje stan oryginalnego sekwencera po 1323 wywołaniach
ze stanem portu po 1600 taktach VGA, sprawdzając nuty i obwiednie po każdym takcie.
Sprawdza też odrzucanie powtórnych IRQ, w tym przy przepełnieniu licznika VGA.

## Organizacja portu

- `tools/prepare_spy.py`: kontrola SHA-256, parsowanie XEX, dekompresja,
  odzyskanie pięciu nakładek i złożenie obrazu pamięci.
- `tools/prepare_title.py`: wyodrębnienie ekranu v2 do bitmapy VGA 320×200,
  4 bpp. ROM ładuje obraz i konfigurację do XRAM $0000–$807B. Po zamknięciu
  ekranu host czyści XRAM i przeznacza tę pamięć na grafikę gry.
- `src/spy.asm`, `src/ria.inc`: obsługa sprzętu bez pożyczania zmiennych
  ze strony zerowej gry.
- `src/spy.cfg`: host w $C000–$CFFF, tablice w $D800–$DFFF,
  procedura startu i splash w $E000–$E3FB.
  $E3FC–$E3FF pozostaje buforem loadera nakładek.
- `build/cc65/release/analysis.json`: mapa segmentów i nakładek.
- `tests/`: kontrola źródła i test uruchomieniowy.

Oryginalny start znajduje się pod $0C00. Procedury VBI i dziewięć DLI
wywołuje przerwanie RP6502; ich zmiany kolorów i sprite'ów trafiają
do pasów VGA. Usługa Atari SETVBV pod $E45C jest przekierowana do hosta.
Nakładki mieszczą się w RAM Picocomputera bez bankowania ROM Atari.

Adres $14 po przejęciu sprzętu przez grę oznacza pozycję kursora menu,
a nie zegar systemowy. Port celowo go nie inkrementuje.

Dokumentacja: [VGA](https://picocomputer.github.io/vga.html),
[RIA](https://picocomputer.github.io/ria.html).
XEX pozostaje niezmieniony. Gra i jej oryginalne zasoby należą do ich
właścicieli; kod portu nie nadaje im nowej licencji.
