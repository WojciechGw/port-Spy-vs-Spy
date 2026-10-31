# Remote game — wspólna inicjalizacja i zegar logiczny

Eksperyment na gałęzi `remotegame`, 2026-10-30. Kontynuacja
[audytu R16](remotegame-audit-r16.md). Nie zawiera transportu sieciowego.

## Zmiana

Oddzielny ROM wykonuje jeden krok VBI/DLI, dźwięku i odpowiedniej pracy
głównej pętli po przyjęciu numerowanego wejścia obu graczy. Zegar VGA nie
wykonuje samodzielnie kroków rozgrywki. Oryginalna naprzemienna obsługa szpiegów
pozostaje zachowana. Przy docelowym dopływie 60 kroków/s jeden szpieg otrzymuje
do 30 obiegów/s; procedury opóźnień mogą zużyć kroki bez kolejnego obiegu.

Granice oczekiwania są w głównej pętli, obu procedurach opóźniających oraz
w trzech fazach oryginalnej pauzy: zwolnienie Escape, ponowne naciśnięcie,
zwolnienie. Po przejściu do zakończenia kontroler może obejrzeć zatrzymany stan
i dopiero potem odblokować powrót do menu.

Start partii stosuje wspólne ustawienia, piątkę bajtów oryginalnego PRNG
inicjuje wspólnym ziarnem i normalizuje liczniki, wejście i stan muzyki.
Wyłączone jest odtwarzanie wejścia trybu demonstracyjnego. Przy pierwszej
granicy rozgrywki numer następnego kroku wynosi zero. Wewnętrzne opóźnienia
inicjalizacji wykonują się deterministycznie z neutralnym wejściem.

Kod jest w `src/remote-clock.asm`, dodatkowe rozgałęzienia `src/spy.asm`
są aktywne wyłącznie z `REMOTE_CLOCK=1`. Skrypt budowania sprawdza oryginalne
bajty przed podmianą wywołań startu, pauzy i powrotu do menu. Nie wymaga XEX.

## Budowanie i powtórzenie prób

```powershell
cmake --preset cc65/Release
cmake --build build/cc65/release --target remote-clock
cmake --build build/cc65/release --target python-deps
cmake --build build/cc65/release --target remote-clock-test
```

ROM: `build/cc65/release/remote-clock/remote-clock.rp6502`.
**Samodzielne uruchomienie zatrzyma się po starcie partii:** pakiety wejściowe
w tej wersji dostarcza skrypt emulatora przez zapisy do RAM. Nie jest to ROM
do normalnego grania ani wersja z działającym Wi-Fi.

Wyniki, skrypty odtwarzania, zrzuty RAM i obraz kontrolny trafiają do
`build/cc65/release/remote-clock/audit/`. `protocol.json` obok ROM-u zawiera
adresy pól z aktualnego linkowania oraz sumy ROM-ów. Test inicjalizacji
`tests/test_remote_clock.py` wykonuje kod 65C02, sprawdza skrajne ustawienia,
niezależność fazy audio od poprzednich wartości oraz zatrzymanie dla błędnych
parametrów. `tools/audit_remote_clock.py` prowadzi pełny emulator.

## Skrzynka wejścia LS01

To interfejs testowego kontrolera w RAM, **nie protokół TCP**. Liczby dwubajtowe
mają porządek little-endian. Adresy należy pobierać z `protocol.json`.

| Adres | Pole | Znaczenie |
| --- | --- | --- |
| `$D100–D103` | sygnatura | ASCII `LS01` |
| `$D104` | status | 0 lokalne menu, 1 oczekiwanie, 2 wykonanie, 3 zakończona partia, 4 błąd ustawień |
| `$D105` | ready | 0 pusto, 1 opublikowany krok, 2 odblokowanie menu po statusie 3 |
| `$D106–D107` | sequence | numer przesłanego kroku |
| `$D108–D109` | next | oczekiwany numer, zwiększany po wykonaniu VBI/DLI |
| `$D10A–D10B` | p0, p1 | bity 0–4: góra, dół, lewo, prawo, Fire; zero oznacza wciśnięcie; neutralne `$1F` |
| `$D10C` | console | aktywne zerem START/SELECT/OPTION; neutralne 7, OPTION = 3 |
| `$D10D` | key | 0 brak, 1 Escape, 2 przełączenie muzyki |
| `$D10E` | seed | ziarno 0–255; domyślnie 169 |
| `$D10F` | level | 1–8; domyślnie 1 |
| `$D110` | ai | 1–5; zachowana wspólna opcja menu, obaj szpiedzy są ludźmi |
| `$D111` | exit | 1–2; domyślnie 1 |
| `$D112` | error | 0 brak, 1 zły numer, 2 złe ustawienia, 3 nieobsługiwany klawisz |
| `$D113` | kind | 1 główna pętla, 2 opóźnienie, 3 pauza |
| `$D114` | active | 0 lokalnie, 1 inicjalizacja, 2 rozgrywka |

Kontroler zapisuje ustawienia przed fizycznym uruchomieniem partii z menu.
Lokalnie wybrane wartości są zastępowane wspólnymi; ten prototyp nie ma jeszcze
ekranu uzgadniania ustawień. Po statusie 1 kontroler zapisuje numer i wejście,
a `ready=1` **jako ostatni zapis**. Następnie czeka na zwiększenie `next`
i ponowny status 1 albo status 3. Sam zastany status 1 nie potwierdza wykonania
nowego kroku. Zrzut przy kolejnym oczekiwaniu obejmuje pracę główną wykonaną
po poprzednim wejściu. Wszystkie pola wejściowe są poziomami przycisków;
podwójny Fire wymaga dwóch naciśnięć oddzielonych zwolnieniem.

Zły numer i nieznany klawisz zerują `ready` bez wykonania kroku. Poprawne
wejście zeruje poprzedni błąd. Numer zawija się po 65535. Skrzynka ma jeden
slot, bez kolejki, identyfikatora sesji, kontroli integralności ani negocjacji
wersji. Ustawienia poza zakresem zatrzymują start ze statusem 4; potrzebny reset.

Po statusie 3 tylko `ready=2` odblokowuje menu. Kontroler powinien najpierw
porównać stan zakończenia obu instancji. Kolejny start ponownie zaczyna od zera.
Nie wolno używać starego pakietu w nowej sesji; identyfikator sesji należy dodać
przy projektowaniu transportu.

## Wyniki i zakres sprawdzenia

Scenariusz ma 58 zrzutów na granicach logicznych i obejmuje przejście do innego
pokoju, podwójny Fire, mapę, bombę zegarową i jej wygaśnięcie, drugiego szpiega,
pauzę i wznowienie, wyjście do menu, ponowny start, walkę i przełączanie muzyki.
Odrębna próba skraca oba liczniki czasu do trzech jednostek i obserwuje animację
zakończenia. Nie jest to pełne przejście gry. Zawinięcie numeru kroku również
ma jawny testowy zapis liczników na 65535.

Porównywane warianty: kontrolny i jego powtórzenie, inne początkowe losowanie
RAM emulatora, start późniejszy o 17 klatek, menu dłuższe o 17 klatek,
CPU 7,9 MHz, CPU 2 MHz oraz sześcioklatkowe przerwy przed co dziewiętnastym
wejściem. Wariant kontrolny działa przy 8 MHz.

Badane pola rozszerzają mapę z audytu R16 o fazę gracza, stan muzyki,
włączenie liczników i fazę zegara logicznego. Przechowywane są pełne zrzuty
`$0000–$FEFF`; rejestry sprzętowe `$FFxx` są pomijane. Sprawdzenia obejmują:

- zgodność badanych pól we wszystkich punktach wszystkich ośmiu wariantów;
- identyczne pełne zrzuty dla dwóch identycznych uruchomień;
- całkowity brak zmian badanego RAM przez 60 klatek bez pakietu, również przy
  wciśniętych fizycznych klawiszach, i po zatrzymanym zakończeniu;
- brak postępu po pakiecie przyszłym, powtórzonym lub z błędnym klawiszem;
- zatrzymanie liczników podczas pauzy, działające wznowienie i przełączanie muzyki;
- zgodne zakończenie po czasie przy 2 i 8 MHz, po przyjęciu kroku 276
  (`next=277`), bez dalszego postępu po zakończeniu.

Końcowy maszynowy wynik jest w `audit/report.json`. Wszystkie 10 istniejących
testów lokalnego portu także przeszły. Ponowne zbudowanie lokalnego R16 daje
niezmienione SHA-256:
`0a1e8000007660ed7d89a209a805b4abe525b2f6a61d9aad7b9385f8e8ad92de`.
Eksperymentalny ROM:
`e1c0d026aa977a195d7e5033b6839ffc38f8b553ad490637e19ffb252d6fd165`.

## Pamięć i ograniczenia

Nowy kod zajmuje 614 bajtów `$D500–$D765` w rezerwacji 768 bajtów, skrzynka
27 bajtów `$D100–$D11A` w rezerwacji 256 bajtów. Kod hosta zajmuje 3989 bajtów
z 4096, tablice 1961 z 2048. Startup nie narusza `$E3FC–$E3FF`.
Zastosowano osobny skrypt linkera; dotychczasowe obrazy R12 i R16 są zachowane.

To wynik dla badanych scenariuszy, nie dowód pełnej deterministyczności:

- Mapa stanu nadal jest niepełna. Różnice w roboczych licznikach i buforach
  wymagają rozpoznania przed zdefiniowaniem sum kontrolnych transmisji.
- Testy zaczynają się od świeżego załadowania ROM-u na obu instancjach, a potem
  identycznej historii wejścia. Oryginał zachowuje część danych między partiami:
  po restarcie z tym samym seedem niektóre pola rekordów pokojów, kursor pułapek
  i nieaktywny numer pokoju bomby różnią się od pierwszego startu. Zgodny restart
  obu maszyn sprawdzono, lecz dołączenie maszyny po innej historii wymaga
  kanonicznego resetu lub odtworzenia pełnego stanu. Na razie należy ładować
  ROM od początku na obu maszynach.
- VBI/DLI oraz publikacja obrazu i dźwięku są wykonywane wspólnie w kroku.
  Nie ma jeszcze niezależnej, płynnej prezentacji podczas oczekiwania. VGA
  wyświetla ostatnie dane; przy zatrzymaniu może zostać obraz sprzed częściowej
  aktualizacji, a generator dźwięku utrzymuje ostatnią nutę. Obsługa przerwy
  sieciowej, ciszy i ponownego uzgodnienia będzie osobnym zadaniem.
- Kontroler emulatora nie reguluje tempa do 60 Hz czasu rzeczywistego.
  Nie używać tego ROM-u do oceny końcowego tempa muzyki ani komfortu gry.
- Nie sprawdzono zwycięstwa, wszystkich poziomów w pełnej grze, fizycznego
  sprzętu, Wi-Fi, TCP, rozłączenia ani ponownego dołączenia.

Następny eksperyment sprzętowy: mały program pomiarowy `AT:`/TCP na dwóch
komputerach użytkownika, z pomiarem opóźnień i częściowych transmisji. Przed
połączeniem go z grą trzeba także domknąć reset sesji, mapę stanu i uzgodnienie
zgodności ROM-u, ustawień i numeru sesji.
