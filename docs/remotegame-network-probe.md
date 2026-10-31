# Remote game — pierwsza próba AT/TCP na dwóch Pico

Network addresses in this document are anonymized examples in `192.168.1.0/24`.
Use your actual addresses at runtime. Raw measurement files are kept locally
and excluded from Git. Loopback addresses retain their technical meaning.

Aktualizacja 2026-10-31, gałąź `remotegame`. Pierwsza próba użytkownika na dwóch
komputerach zakończyła się `WRITE TIMEOUT` po obu stronach. Poprawka jest w
wersji **SPY NETWORK PROBE 2**. Użytkownik potwierdził następnie udaną serię
300 próbek na obu maszynach bez obciążenia grafiki oraz serię z grafiką przy
PHI2 8000 kHz. Kolejna seria PROBE 3 wykazała 12 odpowiedzi ponad sekundę.
PROBE 4 wykazał 5 takich odpowiedzi, z opóźnieniem w fazie `wait` DIAL
przy czasie obsługi LISTEN najwyżej 31 ms; wyniki poniżej.
Gra, prototyp zegara logicznego i archiwalne ROM-y pozostają oddzielne.

## Wersja 4 — pomiary faz po obu stronach

Aktualny ROM wyświetla **SPY NETWORK PROBE 4**. Zaktualizuj oba komputery,
uruchom najpierw LISTEN, potem DIAL, przy 8 MHz i `load=1`. Zapisz pełne
raporty obu stron, w szczególności sekcje `phases ms`.

Każdy odcinek jest mierzony lokalnym zegarem; nie odejmujemy wskazań zegarów
dwóch komputerów. Format ramek pozostaje zgodny z wersjami 2 i 3.

- DIAL: `span` to RTT; `tx` mierzy wysyłanie żądania, `wait` czas od zakończenia
  zapisu do odebrania i sprawdzenia CRC odpowiedzi, `other` pozostałą pracę
  (m.in. przygotowanie żądania i porównanie odpowiedzi).
- LISTEN: `span` trwa od pobrania pierwszego bajtu ramki przez parser do
  przyjęcia całej odpowiedzi przez API. `rx` obejmuje odbiór kolejnych bajtów
  i sprawdzenie CRC, `prep` sprawdzenie treści i przygotowanie odpowiedzi,
  `tx` jej wysyłanie. Czas przed pobraniem pierwszego bajtu nie jest objęty
  tym pomiarem.

W obu rolach suma faz daje `span`. Zakończenie `tx` oznacza przyjęcie danych
przez firmware, a nie dostarczenie ich do partnera. Długi `wait` sam w sobie
nie rozstrzyga, w którym kierunku transmisji powstało opóźnienie. Czas LISTEN
jest już zawarty w RTT, więc nie należy go dodawać do wyniku DIAL.

Numery `#` są wspólne dla żądań i zaczynają się od 1. DIAL wypisuje fazy
pięciu najwolniejszych RTT, LISTEN pięciu najdłuższych lokalnych `span`;
te zestawy numerów mogą się różnić. Dodatkowe `Max` podaje maksimum każdej
fazy i numer próbki ze wszystkich ukończonych pomiarów. Nieukończona próbka
jest wyłączona ze statystyk. Raportowanie odbywa się po zamknięciu połączenia.

## Wersja 3 — lokalizacja skoków RTT

Wersja **SPY NETWORK PROBE 3** dodała diagnostykę zachowaną w wersji 4. Po zakończeniu serii DIAL
wypisuje dodatkowo:

```text
RTT counts: >200ms=... >500ms=... >1000ms=...
First: #1 at=0 ms rtt=... ms
Slowest (1-based sample; at=start since first sample):
#... at=... ms rtt=... ms
```

`#` to numer próbki od **1**, a `at` to czas rozpoczęcia tej próbki w ms od
startu pierwszej próbki pomiarowej. Nie jest to czas od uruchomienia ROM-u ani
od początku łączenia. Raport pokazuje do pięciu największych RTT, malejąco;
przy równych wartościach wcześniejsza próbka jest pierwsza. Pierwsza próbka
jest wypisywana niezależnie, także gdy nie mieści się w pierwszej piątce.

Progi są ścisłe: 200 ms nie zwiększa `>200ms`; 201 ms już tak. Liczniki są
zagnieżdżone — wynik ponad 1000 ms zwiększa wszystkie trzy. Pełne podsumowanie,
sortowanie i zliczanie odbywają się dopiero po zamknięciu połączenia. Podczas
pomiaru dodatkowo zapamiętywany jest czas rozpoczęcia próbki, bez nowego
wywołania zegara ani wypisywania komunikatów na każdą próbkę.

Jeśli seria przerwie się w trakcie próby, `Incomplete sample #...` wskazuje
niedokończoną próbkę; jest ona wyłączona ze statystyk RTT. Po poprawnym zebraniu
próbek błąd końcowego potwierdzenia również może dać wynik FAIL, lecz nie dodaje
fikcyjnej próbki do pomiaru. Podsumowanie nie obejmuje RTT ramki zakończenia.

Do uzyskania nowej diagnostyki zaktualizuj rolę **DIAL**. Format ramek pozostaje
zgodny z PROBE 2, więc LISTEN może używać wersji 2 lub 3. Powtórz serię przy
8 MHz z `load=1`, wklej cały wynik DIAL, w szczególności `First`, `RTT counts`
i `Slowest`. Następnie można porównać kolejną serię i `load=0`.
Sam numer najwolniejszej próbki nie rozstrzyga przyczyny opóźnienia.

## Pomiar sprzętowy 2026-10-31 — seria 1

Źródło: pełne wyniki konsol przekazane przez użytkownika. Obie strony używały
PROBE 2, `load=0`, `chunk=32`, `samples=300`; adres listenera
`192.168.1.10:6502`. DIAL i LISTEN zakończyły się PASS z 300 próbkami.
Częstotliwości CPU, dokładnych wersji firmware obu urządzeń i układu AP nie
podano przy tej serii; wcześniejsze informacje o sprzęcie nie zastępują
potwierdzenia warunków tego pomiaru.

| Pomiar | DIAL | LISTEN |
| --- | ---: | ---: |
| RTT min / średnia / p50 / p95 / max [ms] | 52 / 74 / 62 / 100 / 1368 | — |
| Wywołania read / write | 33346 / 301 | 32983 / 301 |
| Puste read / write | 33045 / 0 | 32682 / 0 |
| Krótkie read / write | 0 / 0 | 0 / 0 |
| Maks. czas read / write [ms] | 1 / 1 | 1 / 1 |
| Maks. przerwa pętli [ms] | 20 | 20 |
| Aktualizacje / pominięcia grafiki | 0 / 0 | 0 / 0 |
| Bajty odrzucone poza ramką | 0 | 0 |

W tej serii potwierdzono zestawienie połączenia i poprawną wymianę wszystkich
próbek oraz zakończenia. Nie wystąpił raportowany błąd integralności ani timeout
aplikacji. Nie oznacza to braku retransmisji TCP — program ich nie mierzy.
Liczne puste odczyty są skutkiem odpytywania nieblokującego interfejsu,
nie liczbą utraconych pakietów. 301 zapisów obejmuje też ramkę zakończenia.

95% próbek miało RTT nie większy niż 100 ms, ale maksimum wyniosło 1368 ms.
Zbiorcze statystyki nie wskazują numeru tej próbki ani liczby i przyczyny dużych
skoków. Nie można przypisać ich do Wi-Fi, TCP czy innej warstwy na podstawie
samego podsumowania. Maksima lokalnych wywołań read/write wynosiły po 1 ms,
a największe obserwowane przerwy obsługi pętli po 20 ms.

Wniosek dla integracji: nie czekać na odpowiedź każdego kroku przed wysłaniem
następnego. Potrzebne pozostają numerowane wejścia z wyprzedzeniem i wspólne
zatrzymanie symulacji przy wyczerpaniu bufora. Bufor 4–6 kroków przy 60 Hz nie
pokryje czasu odpowiedzi 1368 ms; nie należy też traktować RTT/2 jako zmierzonego
opóźnienia w jedną stronę ani dobierać ostatecznego bufora z jednej serii.

Próbę z obciążeniem wykonano następnie w serii 2. Pozostają powtórzenia,
zamiana ról oraz określenie momentu i częstości dużych skoków.

## Pomiar sprzętowy 2026-10-31 — seria 2, grafika

Użytkownik podał PHI2 **8000 kHz (8 MHz)**. PROBE 2, `load=1` na obu stronach,
`chunk=32`, `samples=300`, listener `192.168.1.10:6502`. Obie strony PASS.
Dokładnych wersji firmware i układu AP ponownie nie podano. Potwierdzenie
częstotliwości dotyczy tej serii; warunków poprzedniej nie uzupełniono wstecz.

| Pomiar | DIAL | LISTEN |
| --- | ---: | ---: |
| RTT min / średnia / p50 / p95 / max [ms] | 59 / 94 / 74 / 120 / 1390 | — |
| Wywołania read / write | 37301 / 301 | 36899 / 301 |
| Puste read / write | 37000 / 0 | 36598 / 0 |
| Krótkie read / write | 0 / 0 | 0 / 0 |
| Maks. czas read / write [ms] | 1 / 1 | 1 / 1 |
| Maks. przerwa pętli [ms] | 22 | 22 |
| Aktualizacje / pominięcia grafiki | 1656 / 45 | 1720 / 39 |
| Bajty odrzucone poza ramką | 0 | 0 |

W porównaniu z serią 1 średnia RTT wzrosła o 20 ms (około 27%), mediana
o 12 ms, p95 o 20 ms, maksimum o 22 ms. To porównanie dwóch serii, nie
kontrolowane wyznaczenie samego kosztu renderowania. Czasy wywołań API nadal
nie przekroczyły raportowanych 1 ms, a przerwy pętli wzrosły z 20 do 22 ms.

Udział pominiętych taktów aktualizacji wyniósł około 2,6% po stronie DIAL
(45 / 1701) i 2,2% po stronie LISTEN (39 / 1759). Są to pominięcia pracy
testowej aplikacji, nie dowód uszkodzenia obrazu ani utraty synchronizacji VGA.
Listener wykonuje też końcowe oczekiwanie na opróżnienie nadajnika, dlatego
liczb aktualizacji obu komputerów nie należy oczekiwać równych.

Komunikacja z syntetyczną aktualizacją grafiki działa przy 8 MHz w sprawdzonej
serii. Skoki RTT do około 1,4 s wystąpiły zarówno z obciążeniem, jak i bez niego;
statystyki nie pozwalają wskazać ich przyczyny ani częstości. W wersji 3 dodano
numery i czasy najwolniejszych próbek oraz liczby przekroczeń 200/500/1000 ms.
Pozwoli to odróżnić opóźnienie początku sesji od powtarzalnych przerw;
wynik pierwszej próby sprzętowej tej wersji znajduje się w serii 3 poniżej.
Parametrów bufora gry nadal nie ustalono; test pozostaje wymianą pojedynczych
żądań i odpowiedzi, bez ciągłego strumienia wejścia obu graczy.

## Pomiar sprzętowy 2026-10-31 — seria 3, PROBE 3

Obie strony PROBE 3, `load=1`, `chunk=32`, `samples=300`, listener
`192.168.1.10:6502`. Obie strony PASS. Seria kontynuuje poprzednie próby;
użytkownik nie podał ponownie częstotliwości ani zmian konfiguracji sprzętu.

| Pomiar | DIAL | LISTEN |
| --- | ---: | ---: |
| RTT min / średnia / p50 / p95 / max [ms] | 60 / 140 / 76 / 128 / 2091 | — |
| RTT >200 / >500 / >1000 ms | 12 / 12 / 12 | — |
| Pierwsza próbka: początek / RTT [ms] | 0 / 75 | — |
| Wywołania read / write | 63806 / 301 | 63393 / 301 |
| Puste read / write | 63505 / 0 | 63092 / 0 |
| Krótkie read / write | 0 / 0 | 0 / 0 |
| Maks. czas read / write [ms] | 1 / 1 | 1 / 1 |
| Maks. przerwa pętli [ms] | 22 | 22 |
| Aktualizacje / pominięcia grafiki | 2482 / 49 | 2542 / 48 |
| Bajty odrzucone poza ramką | 0 | 0 |

Pięć najwolniejszych próbek (numery od 1, czas początku od pierwszej próbki):

| Próbka | Początek [ms] | RTT [ms] |
| --- | ---: | ---: |
| 80 | 11536 | 2091 |
| 44 | 3549 | 2077 |
| 112 | 18624 | 2002 |
| 67 | 8961 | 1665 |
| 51 | 6141 | 1487 |

W tej serii **4% odpowiedzi przekroczyło 1000 ms**, pozostałe 288 miało RTT
nie większy niż 200 ms. Równe trzy liczniki oznaczają brak próbek w przedziale
(200, 1000] ms. Mediana 76 ms jest bliska poprzednim 74 ms, lecz średnia wzrosła
z 94 do 140 ms. p95=128 ms nie opisuje ogona obejmującego te 4% próbek.

Pierwsza próbka miała 75 ms, a ujawnione skoki nastąpiły w różnych momentach
serii. To wyklucza wyjaśnienie wszystkich opóźnień wyłącznie pierwszą próbką
po połączeniu. Zestawienie pięciu najwolniejszych nie ujawnia momentu pozostałych
siedmiu ani nie dowodzi okresowości. PASS oznacza poprawność i kompletność
wymiany, a nie wystarczającą płynność dla gry.

Raportowane maksima read/write po 1 ms i przerwy pętli po 22 ms nie pokazują
blokady aplikacji 6502 odpowiadającej długim RTT. Opóźnienie może powstawać poza
tymi wywołaniami, w kolejce firmware lub drodze transmisji; z samego raportu
nie da się rozstrzygnąć między tymi miejscami ani przypisać przyczyny Wi-Fi
lub retransmisjom TCP. Nie należy zwiększać docelowego opóźnienia sterowania
do ponad dwóch sekund tylko po to, aby przykryć zaobserwowane maksimum.

Następny krok diagnostyczny: rozdzielić czas wysyłania żądania i oczekiwania na
odpowiedź w DIAL oraz czas obsługi żądania w LISTEN, zachowując numer próbki.
Porównywać lokalnie mierzone odcinki czasu, bez odejmowania niesynchronizowanych
zegarów obu maszyn. Potem można izolować odcinek transmisji w próbach z innym
partnerem lub siecią. Pomiar faz jest już dostępny w PROBE 4 opisanym powyżej;
jego pierwszy wynik sprzętowy znajduje się w następnej sekcji.

## Pomiar sprzętowy 2026-10-31 — seria 4 (PROBE 4)

Źródło: pełne raporty użytkownika, obie strony PROBE 4, `load=1`, `chunk=32`,
300 próbek, listener `192.168.1.10:6502`. Obie strony PASS. Zalecono 8 MHz;
w tej wiadomości użytkownik nie podał ponownie częstotliwości.

| Pomiar | DIAL | LISTEN |
| --- | ---: | ---: |
| RTT min / średnia / p50 / p95 / max [ms] | 61 / 106 / 78 / 124 / 1434 | — |
| RTT >200 / >500 / >1000 ms | 5 / 5 / 5 | — |
| Pierwsza próbka: początek / RTT [ms] | 0 / 108 | — |
| Maks. tx [ms] (próbka) | 3 (#1) | 3 (#2) |
| Maks. wait / rx [ms] (próbka) | 1418 (#274) | 15 (#26) |
| Maks. other / prep [ms] (próbka) | 14 (#1) | 14 (#1) |
| Maks. span LISTEN [ms] | — | 31 |
| Wywołania read / write | 44463 / 301 | 44029 / 301 |
| Puste read / write | 44162 / 0 | 43728 / 0 |
| Krótkie read / write | 0 / 0 | 0 / 0 |
| Maks. czas read / write [ms] | 1 / 1 | 1 / 1 |
| Maks. przerwa pętli [ms] | 22 | 22 |
| Aktualizacje / pominięcia grafiki | 1887 / 45 | 1925 / 63 |
| Bajty odrzucone poza ramką | 0 | 0 |

Wszystkie pięć wolnych próbek DIAL (czasy w ms):

| Próbka | Początek | RTT | tx | wait | other |
| --- | ---: | ---: | ---: | ---: | ---: |
| 274 | 28190 | 1434 | 2 | 1418 | 14 |
| 50 | 5453 | 1416 | 2 | 1400 | 14 |
| 228 | 23081 | 1377 | 3 | 1360 | 14 |
| 8 | 664 | 1295 | 2 | 1279 | 14 |
| 87 | 9960 | 1248 | 3 | 1232 | 13 |

Pięć najdłuższych lokalnych odcinków LISTEN (czasy w ms):

| Próbka | span | tx | rx | prep |
| --- | ---: | ---: | ---: | ---: |
| 2 | 31 | 3 | 14 | 14 |
| 7 | 31 | 3 | 14 | 14 |
| 16 | 31 | 3 | 14 | 14 |
| 24 | 31 | 3 | 14 | 14 |
| 26 | 31 | 3 | 15 | 13 |

Interpretacja: **5/300, czyli około 1,67% próbek przekroczyło sekundę**;
pozostałe 295 miało RTT nie większe niż 200 ms. W najwolniejszej próbce
1418 z 1434 ms przypada na `wait`. Wszystkie ukończone żądania LISTEN mają
lokalny `span` nie większy niż 31 ms, również te o numerach wolnych RTT DIAL.
To wyklucza sekundowe przetwarzanie ramki przez aplikację LISTEN w mierzonym
odcinku jako wyjaśnienie tych skoków. Nie obejmuje oczekiwania przed pobraniem
pierwszego bajtu ani dostarczenia odpowiedzi po przyjęciu jej przez firmware.
Brak sekundowych wywołań API i przerw pętli dodatkowo zawęża poszukiwania.

Nie ustalono jeszcze, czy opóźnia się żądanie czy odpowiedź, ani czy przyczyna
leży w kolejkach firmware, transmisji lub obsłudze sieci. Samo `rx=15 ms`
nie jest czasem transmisji przez Wi-Fi: zegar zaczyna się dopiero w parserze.
Spadek liczby skoków z 12 do 5 w jednej serii nie dowodzi poprawy transportu;
PROBE 4 dodał diagnostykę, a mediana pozostaje bliska poprzedniej (78 vs 76 ms).

Następny eksperyment: [partner pomiarowy na PC](remotegame-pc-peer.md), zgodny z tymi
samymi ramkami, następnie osobne próby każdego Pico z tym samym PC, najlepiej
podłączonym do routera przewodowo. Zachować 8 MHz, 300 próbek i `load=1`.
PC powinien zapisać numery i lokalne czasy odbioru/wysyłania; zapis ruchu TCP
może uzupełnić te pomiary. Pozwoli to porównać każde urządzenie osobno i usunąć
drugi odcinek radiowy z próby, bez zmiany kilku parametrów naraz. Program PC
jest gotowy i przeszedł testy lokalne. Pierwsze pomiary sprzętowe Pico DIAL →
PC LISTEN: A RTT 29/56/59/67/82 ms, B 29/34/33/40/133 ms (min/średnia/p50/p95/max),
po 300 próbek z `load=1`, bez RTT >200 ms. Pełny zapis i źródła znajdują się
w [raporcie PC](remotegame-pc-peer.md). Następny krok to PC DIAL → każde Pico
LISTEN; dotychczasowe próby z PC nie sprawdziły tej roli Pico. Nie jest to
jeszcze dowód winy konkretnego urządzenia, firmware ani punktu dostępowego.
Późniejsza próba z odwróconymi rolami odtworzyła skoki dla B LISTEN
(16/300 >1000 ms, max 1597,139 ms), ale nie dla A LISTEN (max 114,420 ms).
Raport LISTEN B ujawnił jednak `chunk=1`, tx do 1556 ms i 43177 pustych zapisów.
Powtórka B z chunk=32: 2/300 RTT ponad sekundę, max 1435,388 ms, lokalny
span LISTEN maks. 31 ms i tx maks. 3 ms, bez pustych zapisów. Długie
oczekiwanie nastąpiło przed pierwszym odczytem odpowiedzi na PC. Przyczyna
skoków przy chunk=32 nadal wymaga wyjaśnienia; następny proponowany pomiar
to przechwycenie TCP na PC. Szczegóły zapisano w raporcie PC.

## Poprawka wersji 2

Wersja 1 rozpoznawała odpowiedź `OK` już po CR, pozostawiając LF do odczytania.
Kod firmware blokuje zapisy, dopóki wygenerowana odpowiedź nie zostanie odebrana
w całości. Kolejna komenda kończyła się więc `WRITE TIMEOUT` po pięciu sekundach,
jeszcze przed oczekiwaniem na CONNECT. Odtworzono ten błąd w obu rolach po
uzupełnieniu atrapy modemu o blokadę zapisu obecnego firmware; poprzednie testy
nie modelowały tego ograniczenia.

Wersja 2 czyta odpowiedzi blokami i czeka na końcowy LF. Zachowuje przy tym
dane po CONNECT w tym samym buforze. Dodatkowo używa `AT\L6502`: lokalny parser
firmware `ad6293c` nie przyjmuje `=` w tym poleceniu. Błędy zawierają teraz
`Stage=...` i czas spędzony w danym etapie.

## Co uruchomić

```powershell
cmake --preset cc65/Release
cmake --build build/cc65/release --target net-probe
cmake --build build/cc65/release --target net-probe-test
```

Plik wynikowy: `build/cc65/release/net-probe/net-probe.rp6502`.
Budowanie wymaga `cl65` z biblioteką RP6502. Testy wymagają `sim65`;
jeżeli istnieje `tools/rp6502-emu.exe`, wykonują też próby natywnego runtime.
Nie są potrzebne XEX ani py65. Zwykły cel `all` nadal buduje lokalną grę.

Skopiuj **ten sam ROM** na oba komputery. Użyj ich działającego Wi-Fi w tej
samej sieci LAN, początkowo przy 8 MHz. Odczytaj adres IPv4 pierwszego
komputera z monitora (`status`). Uruchom ROM z menu/loadera albo poleceniem
`LOAD /net-probe.rp6502`, jeśli plik leży w katalogu głównym bieżącego nośnika.
Bez argumentów program wyświetla trzy pytania.

| Komputer | Role | Port / adres | Graphics load |
| --- | --- | --- | --- |
| A — uruchom pierwszy | `listen` | `6502` | `0` |
| B — uruchom drugi | `dial` | adres A, np. `192.168.1.50:6502` | `0` |

Adres w przykładzie zastąp rzeczywistym adresem A. Program czeka na połączenie
do 120 sekund **po komunikacie `Modem ready`**. Wcześniejsze konfigurowanie
modemu ma osobne limity pięciu sekund na komendę. Błąd modemu, np. NO CARRIER,
lub Escape może zakończyć próbę wcześniej. Następnie B wysyła 300 próbek i kończy serię uzgodnieniem z A.
Wynik pozostaje na konsoli. Escape przerywa oczekiwanie lub pomiar. Przy braku
kompletnej odpowiedzi przez pięć sekund próba kończy się komunikatem timeout.
Przy zatrzymaniu samego wywołania systemowego może być potrzebny standardowy
Break monitora — timeout aplikacji jest sprawdzany między wywołaniami API.

Powtórz próbę z `Graphics load = 1` na obu komputerach, potem zamień role A/B.
Dopiero potem porównaj 2 MHz. Wersja z obciążeniem aktualizuje kolorowy kwadrat
64×64 piksele, przesyłając 4096 bajtów do XRAM na zaobserwowaną klatkę VGA.
To **syntetyczne obciążenie**, a nie rendering Spy vs Spy. Nie wykonuje
nadrabiania zaległych klatek. Na czas próby włącza canvas 320×240, a po niej
przywraca domyślną konsolę.

Można również podać argumenty przy uruchomieniu ROM-u:

```text
listen 6502 0 32
dial 192.168.1.50:6502 0 32 300
```

Kolejne opcje to obciążenie 0/1, limit jednego odczytu/zapisu 1–64 bajty,
liczba próbek 1–300. Liczba próbek dotyczy `dial`; `listen` kończy serię na
żądanie drugiej strony. Domyślne wartości to 0, 32 i 300. Limit 1 albo 7
wymusza dzielenie ramek na wiele wywołań API i nadaje się do dodatkowej próby.
Początkowy interaktywny wariant używa wartości domyślnych.

## Co zapisać z obu konsol

| Pole | Znaczenie |
| --- | --- |
| `DIAL: PASS; samples=300` | Wszystkie odpowiedzi i końcowe potwierdzenie dotarły i były zgodne |
| `LISTEN: PASS` | Odebrano zakończenie i przekazano końcowe potwierdzenie do nadajnika firmware; sprawdź też wynik B |
| `RTT ms` | Minimum, średnia całkowita, mediana, p95 i maksimum czasu pełnej odpowiedzi |
| `IO calls read/write` | Liczba wywołań w fazie pomiaru, bez negocjacji AT |
| `empty` | Odczyty/zapisy zwracające zero lub `EAGAIN` |
| `short` | Dodatnie wyniki mniejsze niż żądana liczba bajtów |
| `Max ms: read/write` | Najdłuższe pojedyncze wywołania I/O, z narzutem zegara |
| `poll-gap` | Najdłuższa przerwa między obsługą pętli aplikacji |
| `Graphics draws/missed` | Wykonane aktualizacje i pominięte takty VGA przy obciążeniu |
| `discarded` | Bajty spoza ramki, np. końcowy LF komunikatu CONNECT lub tekst modemu po rozłączeniu |

RTT jest **czasem odpowiedzi całej aplikacji**, zawiera obie maszyny,
przetwarzanie ramek, CRC, wywołania RIA, obsługę grafiki i transmisję. Nie jest
samym czasem radiowym ani opóźnieniem w jedną stronę. Zegar ma rozdzielczość
milisekundową. Nadawca utrzymuje tylko jedną oczekującą odpowiedź; kolejne
próbki zaczyna nie częściej niż co 17 ms, bez nadrabiania opóźnień. Nie jest to
jeszcze test ciągłego strumienia dwóch graczy z buforem wejścia.

Zapisz osobno:

```text
RIA/VGA firmware A i B:
CPU A/B:
Sieć: ten sam AP / różne AP / inne:
Kierunek: A listen, B dial (lub odwrotnie):
Load A/B, chunk, samples:
Pełny wynik z A:
Pełny wynik z B:
Próba przerwania połączenia — komunikaty i zachowanie:
```

Brak dodatnich krótkich zapisów nie jest błędem: mała ramka mogła zmieścić się
w całości w buforze. Nie dobieramy jeszcze bufora gry na podstawie sztucznych
czasów z testów automatycznych.

## Próba przerwy i zakończenia

Uruchom kolejną serię, po czym przerwij program klawiszem Escape na jednym
komputerze. Drugi powinien zakończyć oczekiwanie timeoutem zamiast zawiesić
się na zawsze. Można osobno sprawdzić utratę Wi-Fi podczas trwania próby.
Zapisz komunikaty z obu stron. Program nie próbuje automatycznie łączyć się
ponownie; następną serię uruchamia się od początku.

`Cannot open AT:` wskazuje brak dostępnego urządzenia modemowego.
`ERROR` podczas przygotowania oznacza odrzucenie komendy AT, a `AT RESPONSE
TIMEOUT` — brak oczekiwanej odpowiedzi. `FRAME TIMEOUT` nie rozróżnia ciszy,
utraty sieci i wyjścia drugiej strony. Błąd CRC, numeru lub zawartości kończy
test zamiast ukrywać rozbieżność.

## Podstawa implementacji

Sprawdzono lokalny kod firmware `ad6293c513bf93ace087f0f3a1b35c70b0832439`
oraz bieżącą dokumentację producenta. W tym kodzie `modem_std_read()` może
zwrócić zero bajtów bez zamknięcia połączenia; `modem_std_write()` może zwrócić
zero lub zapis częściowy. Rozłączenie jest sygnalizowane tekstem modemu po
opróżnieniu odebranych danych. Program stosuje termin na kompletną ramkę;
nie interpretuje zera jako EOF. Odczyty są pojedynczymi `read_xstack()`, a zapisy
`write_xstack()`, do 64 bajtów, ze sprawdzaniem liczby faktycznie przeniesionych
bajtów. Brak danych i `EAGAIN` oznaczają ponowienie w granicach timeoutu.

Otwierane jest przejściowe `AT:`. Ustawienia: `E0`, `Q0`, `V1`, `X0`,
`\N0` (surowy TCP), `S2=128` (wyłączone przejście do komend przez `+++`).
Nasłuch dodaje `S0=1` i `\L6502`; połączenie wychodzące używa `ATD`.
Program nie zapisuje profilu przez `AT&W` ani nie zmienia SSID/hasła Wi-Fi.

Ramka ma 32 bajty: sygnaturę `A5 5A 4E 01`, typ, długość, 16-bitowy numer,
32-bitowy znacznik czasu, 18 bajtów wzorca oraz CRC-16/CCITT-FALSE. Liczby są
little-endian; CRC obejmuje pierwszych 30 bajtów. Wzorzec zawiera `00`, `FF`,
`+++` i CR/LF. Odbiorca kontroluje również numer i cały wzorzec. Typy to
`P`/`R` (próbka/odpowiedź) i `Q`/`A` (koniec/potwierdzenie). Nie jest to
docelowy protokół gry i nie używa skrzynki `LS01`.

Odczyt odpowiedzi AT używa bufora 64 bajtów niezależnie od opcji `chunk`;
rozpoznaje koniec wiersza dopiero po LF. Zachowuje początek binarnego strumienia,
nawet gdy CONNECT i pierwszy pakiet przychodzą razem. Parser binarny zachowuje
częściową ramkę i nadmiar odczytanych bajtów pomiędzy wywołaniami. Przy błędzie
integralności próba jest przerywana.

Źródła: [opis modemu](https://picocomputer.github.io/ria_w.html#modem-emulation),
[API RIA](https://picocomputer.github.io/api.html),
[VGA](https://picocomputer.github.io/vga.html),
[kod modemu ad6293c](https://github.com/picocomputer/rp6502/blob/ad6293c513bf93ace087f0f3a1b35c70b0832439/src/host/pico/ria-w/net/modem.c).

## Weryfikacja i ograniczenia

40 przypadków w `sim65` wykonuje właściwy kod aplikacji i protokołu z atrapą
modemu: podział na 1/7/32/64 bajty, krótkie transfery, zero i `EAGAIN`,
CONNECT wraz z danymi, CRC i wzorzec binarny, nieprawidłowy numer, uciętą ramkę,
brak odpowiedzi, błąd odczytu, odrzucenie AT, anulowanie, zawinięcie zegara i
walidację argumentów. CRC ma również test znanego wektora `123456789`.
Atrapa blokuje teraz zapis, gdy odpowiedź AT czeka na odczyt, i odrzuca
`AT\L=...`. Dodano próby obu ról: blokady odpowiedzi, połączenia po 60 sekundach
i pełnego 120-sekundowego limitu przy braku połączenia.
Diagnostyka wersji 3 ma testy dokładnych granic progów, równych RTT, zachowania
numerów i czasów, 0/1/300 wyników, skoku na pierwszej lub trzeciej próbce oraz
przerwania po dwóch poprawnych odpowiedziach. Czasy w tych testach są sztuczne.
Testy wersji 4 sprawdzają sumy faz, przypisanie opóźnienia do wysyłania,
oczekiwania lub odbioru fragmentów oraz odrzucenie 301. żądania pomiarowego.

Dziewięć prób natywnego emulatora sprawdza argumenty, interaktywne uruchomienie,
brak urządzenia modemowego oraz atrapę transmisji z rzeczywistym runtime RIA,
zegarem i VGA przy 2/8 MHz, a także opóźniony CONNECT i limit 120 sekund według
rzeczywistego zegara RIA emulatora. Obejmują raport faz DIAL i LISTEN.
Te próby **nie wykonują połączenia TCP/Wi-Fi**.
Wynik zbiorczy: `build/cc65/release/net-probe/test-report.json`.
Osobne ROM-y z `test` w nazwie są wyłącznie dla automatycznych testów — na Pico
kopiuj plik **`net-probe.rp6502`**.

Zegar pętli i timeouty nie przerwą pojedynczego zawieszonego wywołania API.
Licznik pominiętych klatek opiera się na 8-bitowym VSYNC; przerwa przekraczająca
pełny obieg licznika może być niedoszacowana. Dane RTT są wiarygodnym materiałem
do następnego etapu dopiero po rzeczywistym pomiarze. Ocenę wyciszania muzyki,
resetu wspólnej sesji, pełnych sum stanu i działania gry podczas rozłączenia
pozostawiono etapowi integracji.
