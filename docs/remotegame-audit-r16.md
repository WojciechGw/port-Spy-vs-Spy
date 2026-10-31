# Audyt deterministyczności R16

Data: 2026-10-30. Gałąź: `remotegame`.

## Wynik

R16 daje powtarzalne wyniki przy identycznym uruchomieniu w emulatorze, lecz
nie jest jeszcze gotowy do gry lockstep. Zmiana czasu spędzonego w menu lub
częstotliwości CPU może zmienić stan początkowy partii. Wspólne ziarno usuwa
różnice początkowego świata, ale pozostają różnice w czasie obsługi gry.

To wynik próby diagnostycznej, a nie dowód trwałej rozbieżności każdego
odmiennego bajtu. Próbki wykonano po określonej liczbie klatek VGA; nie
zatrzymywano procesorów na tej samej instrukcji ani granicy kroku symulacji.

## Materiał i odtwarzanie

- ROM R16 SHA-256:
  `0a1e8000007660ed7d89a209a805b4abe525b2f6a61d9aad7b9385f8e8ad92de`.
- Emulator: `Oct 13 2026 13:09:10`.
- Emulator SHA-256:
  `4c901529dc69134be8fac82c8c467feae124ce7773196f3aa27a75aae1991217`.
- Przypadek bazowy: 8 MHz, seed emulatora 123, dwóch graczy ludzkich.
- Oddzielny ROM diagnostyczny: seed gry `$A9` (169), zgodny z początkowym
  światem przypadku bazowego; nie jest to nowa wersja wydaniowa.
- 16 uruchomień: osiem wariantów dla każdego z dwóch ROM-ów.
- Każde uruchomienie: 49 punktów obserwacji i 2064 klatki scenariusza po
  sekwencji startowej, dodatkowo sześć klatek w wariancie opóźnionego wejścia.

```powershell
cmake --build build/cc65/release --target remotegame-audit
```

Bezpośrednie wywołanie, także z osobnym katalogiem wyników:

```powershell
python tools/audit_determinism.py --emulator tools/rp6502-emu.exe --build build/cc65/release --output build/remotegame/audit --jobs 4
```

Domyślny katalog to `build/cc65/release/remotegame/`. Zawiera raporty
`report.md`, `report.json`, osobny `fixed-seed.rp6502` oraz podkatalogi
`shipping/` i `fixed-seed/`. Dla każdego przypadku zapisano skrypt wejścia,
metadane obserwacji, stderr i ciąg zrzutów RAM. Każdy zrzut ma 65280 bajtów
(`$0000–$FEFF`); indeks zrzutu odpowiada indeksowi punktu w pliku JSON.

Zwykły ROM, źródła gry i archiwum R12 pozostają niezmienione.

## Porównania

„Różnice” oznaczają liczbę punktów, w których różnił się przynajmniej jeden
badany fragment stanu. Zgodność świata/pozycji dotyczy wszystkich punktów,
a nie wyłącznie stanu końcowego.

| Zmiana względem bazy | R16: różnice / 49 | Wspólny seed: różnice / 49 | Świat i pozycje przy wspólnym seedzie |
| --- | ---: | ---: | --- |
| Identyczne powtórzenie | 0 | 0 | zgodne |
| Seed emulatora 456 zamiast 123 | 0 | 0 | zgodne |
| Splash dłuższy o 17 klatek | 0 | 0 | zgodne |
| Menu dłuższe o 1 klatkę | 49 | 39 | różnice od `new-room` |
| Menu dłuższe o 17 klatek | 49 | 39 | różnice od `new-room` |
| CPU 7,9 MHz zamiast 8 MHz | 49 | 3 | zgodne |
| Dodatkowe 6 klatek przed pierwszym ruchem | 45 | 35 | zgodne |

Kontrola identycznego powtórzenia obejmowała także całe zrzuty RAM, a nie
wyłącznie wybrane pola. Kontrola z innym seedem emulatora sprawdza wpływ jego
inicjalizacji; nie zastępuje testu dwóch fizycznych komputerów.

W R16 przy 7,9 MHz oraz po dodatkowych 17 klatkach menu różne są już pierwsze
rekordy pokojów po rozpoczęciu gry. Przy wspólnym seedzie i 7,9 MHz pozostają
trzy różnice licznika bomby, każda o jeden krok: `arm-time-bomb`, `bomb-armed`
i `bomb-wait`. Późniejsze próbki ponownie się zgadzają. Konieczny jest pomiar
na granicach logicznych kroków, aby oddzielić fazę próbkowania od kolejności
wykonania operacji.

Sześć dodatkowych klatek modeluje dostarczenie sterowania z opóźnieniem bez
wspólnego zatrzymania symulacji. Nie jest to pomiar opóźnienia TCP. Po restarcie
partii ten wariant R16 generuje też inny świat, bo zmieniła się chwila siewu PRNG.

## Potwierdzone sytuacje gry

W obu przypadkach bazowych (R16 i wspólny seed) stwierdzono na podstawie
stanu gry:

- zmianę pokoju;
- wejście do Trapulatora przez podwójny Fire;
- otwarcie i zamknięcie mapy;
- uzbrojenie bomby zegarowej i wygaśnięcie jej licznika;
- obrażenia przeciwnika podczas walki;
- obsługę końca czasu i powrót do menu.

Ostatni punkt używa jawnego testowego zapisu `03 03 00 00 00 00` do liczników
`$00C2–$00C7`. To przyspieszony test zakończenia po czasie, nie naturalne
przejście całej partii. Zwycięstwo przez zebranie przedmiotów i ucieczkę nie
zostało sprawdzone. Warianty powodujące rozbieżności nie muszą wykonać wszystkich
działań tak samo; ich pokrycie zapisano osobno w plikach przypadków.

## Źródła rozbieżności i mapa stanu

Oryginalna procedura `$2EC5` czyta `$D20A`, dodaje bajty `$0003–$00FF`, a
następnie zapisuje ziarno do `$0368–$036C`. Nie wolno synchronizować wyłącznie
emulowanego `$D20A`: strona zerowa zawiera także zmienne robocze zależne od
wykonania kodu. Procedura `$2EE0` rozwija właściwy stan generatora gry.

Eksperyment zmienia tylko sześć bajtów osobnej kopii pamięci gry przy `$2EC5`:
`LDA #$A9 / JMP $2ED8 / NOP`. Zachowuje oryginalny generator i jego odbiorców.
Przed zmianą narzędzie sprawdza instrukcje w miejscu poprawki.

Badane pola obejmują pozycje `$88–$8D`, pokoje `$90–$91`, stan Trapulatora,
wybór ikony, obrażenia, mapę, bombę zegarową, fazę gry, flagi zakończenia,
liczniki `$C2–$C9` oraz PRNG `$0368–$036C`. Rekordy aktywnych pokojów mają po
41 bajtów; ich adresy pochodzą z tablic `$57C9/$57ED`, a liczba z `$0345 + 1`.
Adresowanie potwierdzono w procedurach `$2904`, `$376D` i inicjalizacji świata.

Oddzielnie zapisywane są `$D20A`, aktualnie obsługiwany gracz oraz liczniki
hosta. Stos, bufory obrazu, stan audio i zmienne robocze hosta nie wchodzą do
sumy kandydującego stanu symulacji. Całe zrzuty pozostają dostępne diagnostycznie.
Mapa jest niepełna: nie stanowi jeszcze specyfikacji sum kontrolnych protokołu.

## Następne zadanie po audycie R16

Kolejny eksperyment opisano w [raporcie zegara logicznego](remotegame-clock.md).
Poniżej zachowano plan wynikający z pierwszego audytu.

1. Wyznaczyć granicę logicznego kroku i miejsce obserwacji po zakończeniu
   odpowiednich procedur gry. Uwzględnić naprzemienną obsługę szpiegów oraz
   opóźnienia wywoływane wewnątrz kodu gry.
2. Zaprojektować wspólną inicjalizację partii: ustawienia, seed PRNG, gracz
   rozpoczynający obieg, liczniki oraz numer pierwszego kroku.
3. Rozdzielić działania VBI/DLI należące do symulacji od prezentacji. Przy
   braku wejścia na kolejny krok liczniki gry nie mogą biec samodzielnie.
4. Powtórzyć test z tym samym numerowanym wejściem i różnymi przerwami w jego
   dostarczaniu. Dopiero taki test pozwoli oceniać gotowość do lockstep.
5. Osobno przygotować pomiar `AT:`/TCP na dwóch komputerach z Wi-Fi,
   których dostępność użytkownik potwierdził. Sprzętowego transportu nie
   testowano w ramach tego audytu.
