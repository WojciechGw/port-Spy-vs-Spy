# Pomiar Pico–PC z PROBE 4

Network addresses in this document are anonymized examples in `192.168.1.0/24`.
Use your actual addresses at runtime. Raw measurement files are kept locally
and excluded from Git. Loopback addresses retain their technical meaning.

Program `tools/net_probe_peer.py` jest partnerem TCP dla obecnego ROM-u
`net-probe.rp6502`. Wymaga tylko Pythona 3; nie wymaga pip, cc65 ani przebudowy
ROM-u. Obsługuje LISTEN i DIAL oraz te same ramki co PROBE 2–4.

Celem jest oddzielne porównanie każdego Pico z jednym PC. Program nie łączy
jeszcze gry przez sieć. Testy automatyczne potwierdzają zgodność protokołu,
ale nie stanowią pomiaru Wi-Fi ani próby na fizycznym Pico. Pierwsze dwie
próby sprzętowe, opisane poniżej, zakończyły się PASS bez RTT ponad 200 ms.

## Pierwsze dwie próby

Odczyt konfiguracji Windows 2026-10-31 wskazał adres Ethernet PC
**192.168.1.100/24**. Jeżeli konfiguracja sieci się zmieniła, sprawdź bieżący
adres przez `ipconfig`. Korzystaj z adresu Ethernet, nie z adresów WSL/VPN.

Na obu Pico pozostaw PROBE 4 i PHI2 **8000 kHz**. Uruchom PowerShell w katalogu
projektu. Najpierw testuj tylko pierwszy komputer (nazwijmy go Pico A):

```powershell
python tools/net_probe_peer.py listen --bind 192.168.1.100 --output build/net-probe-pc/pico-a-load1
```

Po komunikacie `Listening on 192.168.1.100:6502` uruchom PROBE 4 na Pico A:

| Ustawienie Pico | Wartość |
| --- | --- |
| Role | `dial` |
| IPv4:port | `192.168.1.100:6502` |
| Graphics load | `1` |

PC przyjmuje jedno połączenie i kończy program po serii. Następnie uruchom go
ponownie z inną nazwą raportu i wykonaj identyczną próbę na Pico B:

```powershell
python tools/net_probe_peer.py listen --bind 192.168.1.100 --output build/net-probe-pc/pico-b-load1
```

Pico B: również `dial`, `192.168.1.100:6502`, `load=1`. Domyślnie Pico wysyła
300 próbek, `chunk=32`. Nie uruchamiaj obu Pico jednocześnie przeciw jednemu
nasłuchowi. Zachowaj położenie urządzeń i pozostałą konfigurację między próbami.

Jeśli Windows wyświetli pytanie zapory, zezwól Pythonowi na przychodzące
połączenia w używanej zaufanej sieci lokalnej. Program sam nie zmienia zapory.
Natychmiastowy błąd odmowy połączenia nie oznacza upływu 120 sekund: PC musi
już wyświetlać `Listening`, a adres i dostęp do portu muszą być poprawne.

Zachowaj pełny wynik DIAL z każdego Pico oraz oba pliki każdej próby:

- `build/net-probe-pc/pico-a-load1.json` i `.csv`;
- `build/net-probe-pc/pico-b-load1.json` i `.csv`.

JSON zawiera wynik PASS/FAIL, adresy partnerów, wszystkie ukończone próbki,
etap i błąd przy przerwaniu oraz podsumowanie. CSV ułatwia porównanie tych
samych numerów próbek z wydrukiem Pico. Jawne `--output` zastępuje poprzednie
raporty o tej nazwie; dla powtórki użyj np. `pico-a-load1-run2`. Bez `--output`
program tworzy nazwę z czasem UTC w `build/net-probe-pc`.

## Opcjonalna zmiana ról

Po porównaniu obu komputerów można sprawdzić kierunek inicjowania połączenia.
Najpierw uruchom na Pico `listen`, port `6502`, `load=1`, a dopiero potem PC:

```powershell
python tools/net_probe_peer.py dial --host 192.168.1.10 --samples 300 --output build/net-probe-pc/pc-dial-pico-a
```

Adres `192.168.1.10` pochodzi z dotychczasowych prób — zastąp go adresem
konkretnego Pico, jeżeli jest inny. W tej roli RTT mierzy PC, a Pico raportuje
lokalne fazy LISTEN. PC utrzymuje co najmniej 17 ms między początkami żądań,
bez nadrabiania serią pakietów po opóźnieniu. `--samples` dotyczy tylko DIAL;
LISTEN obsługuje liczbę uzgodnioną ramką zakończenia, najwyżej 300 próbek.

## Znaczenie pomiarów i ograniczenia

Połączenie ma limit 120 sekund, pojedyncza ramka i zapis 5 sekund. Wcześniejsza
odmowa połączenia, rozłączenie, błędna ramka lub Ctrl+C kończą próbę wcześniej.
Przy błędzie zachowywane są ukończone pomiary; nieukończona próbka jest oznaczona
przez `pending_sample`, a błąd końcowego Q/A przez etap `FINISH`.

PC nie wypisuje ani nie zapisuje na dysk poszczególnych próbek w trakcie
pomiaru. Raporty powstają po zamknięciu połączenia. `TCP_NODELAY` jest włączone
na gnieździe PC. Każda ramka jest sprawdzana pod względem nagłówka, CRC,
numeru, znacznika i pełnego wzorca danych, również przy częściowych odczytach.

Wszystkie pola `*_ms` używają lokalnego monotonicznego zegara PC:

- `start_ms`, `first_rx_ms`, `end_ms`: momenty względem wejścia PC do pomiaru
  po połączeniu. Nie porównuj ich bezpośrednio z czasami zegara Pico.
- PC DIAL: `span_ms` to RTT, `tx_ms` czas zapisu, `wait_ms` czas od zakończenia
  zapisu do odebrania i pełnej walidacji odpowiedzi, `other_ms` przygotowanie
  żądania przed zapisem. Suma faz równa się RTT.
- PC LISTEN: `span_ms` trwa od powrotu pierwszego niepustego odczytu do
  zakończenia zapisu odpowiedzi. `rx_ms` obejmuje pozostały odbiór i walidację,
  `prep_ms` przygotowanie odpowiedzi, `tx_ms` zapis. Suma daje lokalny span.

Granice walidacji w fazach PC są nieco inne niż w kodzie Pico; do lokalizacji
sekundowych przerw porównuj przede wszystkim cały span LISTEN z RTT DIAL.
Zapis zakończony na PC oznacza przyjęcie danych przez gniazdo, nie dotarcie do
Pico. Odcinek LISTEN nie obejmuje czasu przed pierwszym odczytanym bajtem.
`sample` zaczyna się od 1 i odpowiada numerowi `#` na Pico. Q/A nie jest próbką.
Zestawienie span LISTEN z RTT nie wymaga synchronizacji zegarów; nie należy
tych czasów dodawać, ponieważ obsługa LISTEN jest już częścią RTT.

Wynik PC–Pico zmienia również partnera TCP i koszt obliczeń odpowiedzi,
dlatego sam spadek mediany nie dowodzi naprawienia firmware. Najważniejsze
są skoki ponad sekundę i to, czy powtarzają się z oboma Pico. Zapis ruchu TCP
na PC może być kolejnym krokiem, jeżeli raporty nie rozstrzygną przyczyny.

## Wyniki sprzętowe 2026-10-31 — Pico A/B jako DIAL

Źródła: pełne raporty ekranowe użytkownika oznaczone PICOCOMPUTER A i B oraz
odczytane lokalnie pliki PC LISTEN:

- `tools/build/net-probe-pc/20261031T062300.536267Z-listen.json`, peer
  `192.168.1.10`, 300 próbek, PASS;
- `tools/build/net-probe-pc/20261031T062543.808038Z-listen.json`, peer
  `192.168.1.11`, 300 próbek, PASS.

Pliki znajdują się pod `tools/build`, ponieważ program uruchomiono z katalogu
`tools`; domyślny katalog wyjściowy jest względny wobec katalogu uruchomienia.
Przyporządkowanie A do pierwszego raportu i B do drugiego wynika z kolejności
prób i zgodności przebiegów czasowych. Obie role Pico: `dial`, cel
`192.168.1.100:6502`, `load=1`, `chunk=32`, `samples=300`. Zalecenie próby:
PHI2 8000 kHz; częstotliwości nie zapisuje program ani aktualny wydruk.

| Pomiar | Pico A | Pico B |
| --- | ---: | ---: |
| Wynik | PASS, 300 | PASS, 300 |
| RTT min / średnia / p50 / p95 / max [ms] | 29 / 56 / 59 / 67 / 82 | 29 / 34 / 33 / 40 / 133 |
| RTT >200 / >500 / >1000 ms | 0 / 0 / 0 | 0 / 0 / 0 |
| Pierwsze RTT [ms] | 56 | 30 |
| Maks. tx [ms] (próbka) | 3 (#2) | 3 (#1) |
| Maks. wait [ms] (próbka) | 66 (#174) | 117 (#156) |
| Maks. other [ms] (próbka) | 14 (#2) | 14 (#3) |
| Wywołania read / write | 15836 / 301 | 2466 / 301 |
| Puste read / write | 15535 / 0 | 2165 / 0 |
| Krótkie read / write | 0 / 0 | 0 / 0 |
| Maks. czas read / write [ms] | 1 / 1 | 1 / 1 |
| Maks. przerwa pętli [ms] | 22 | 22 |
| Aktualizacje / pominięcia grafiki | 973 / 52 | 599 / 17 |
| Odrzucone bajty | 0 | 0 |
| Średni / maks. lokalny span PC LISTEN [ms] | 0,074571 / 0,240000 | 0,066235 / 0,131800 |
| Maks. odstęp kolejnych żądań na PC [ms] | 104,849 | 132,662 |

Pięć najwolniejszych próbek DIAL (czasy w ms):

| Pico | Próbka | Początek | RTT | tx | wait | other |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | 174 | 9835 | 82 | 3 | 66 | 13 |
| A | 88 | 4982 | 80 | 3 | 63 | 14 |
| A | 166 | 9416 | 80 | 3 | 64 | 13 |
| A | 62 | 3472 | 77 | 3 | 61 | 13 |
| A | 101 | 5696 | 75 | 3 | 59 | 13 |
| B | 156 | 5225 | 133 | 3 | 117 | 13 |
| B | 256 | 8673 | 122 | 3 | 105 | 14 |
| B | 93 | 3076 | 65 | 3 | 49 | 13 |
| B | 128 | 4288 | 50 | 3 | 34 | 13 |
| B | 91 | 2994 | 49 | 3 | 33 | 13 |

Wniosek: w 600 próbkach tych dwóch serii **nie odtworzono sekundowych skoków**
obserwowanych w Pico–Pico. Potwierdzają to teraz pełne RTT, a nie tylko odstępy
odbioru na PC. B ma niższą medianę, ale większe maksimum; sama jedna seria
nie wskazuje uszkodzonego urządzenia ani przyczyny różnicy.

Oba Pico były tutaj klientami DIAL. Próba zmieniła jednocześnie partnera
TCP na PC i drogę do partnera na Ethernet; nie wyklucza więc problemu
w roli LISTEN firmware Pico ani problemu występującego dopiero w połączeniu
dwóch urządzeń przez Wi-Fi. Nie ustalono jeszcze bezpiecznego bufora wejścia gry.

Następny krok: **PC DIAL → Pico LISTEN**, osobno dla każdego urządzenia,
przy zachowaniu `load=1`, 300 próbek i 8 MHz. Wtedy pełne RTT i wszystkie próbki
będą dostępne w pliku JSON na PC. Uruchom najpierw PROBE 4 na odpowiednim Pico
z rolą `listen`, portem `6502`, obciążeniem `1`, a następnie z katalogu projektu:

```powershell
python tools/net_probe_peer.py dial --host 192.168.1.10 --output build/net-probe-pc/pc-dial-a
python tools/net_probe_peer.py dial --host 192.168.1.11 --output build/net-probe-pc/pc-dial-b
```

Polecenia wykonuj osobno, po przygotowaniu właściwego Pico. Jeśli nadal
pracujesz w katalogu `tools`, użyj `python net_probe_peer.py ...`; raporty
wtedy ponownie znajdą się w `tools/build/net-probe-pc`.
Jeżeli obie próby również nie odtworzą skoków, należy powtórzyć Pico–Pico
z zamienionymi rolami i porównać tę samą parę przez inny punkt dostępowy.
To plan dalszej izolacji przyczyny, nie ustalona diagnoza Wi-Fi lub firmware.
Wynik wykonanej zmiany ról opisano poniżej: skoki powróciły dla B, ale jego
raport wykazał zmianę parametru na `chunk=1`; potrzebna jest powtórka z 32.

## Wyniki sprzętowe 2026-10-31 — PC jako DIAL, Pico A/B jako LISTEN

Odczytano bezpośrednio z `tools/build/net-probe-pc`:

- `20261031T063356.320614Z-dial.json`: PC → A (`192.168.1.10:6502`);
- `20261031T063435.318686Z-dial.json`: PC → B (`192.168.1.11:6502`).

Obie serie PASS, po 300 próbek. **Raport użytkownika z B potwierdził
`load=1, chunk=1`, a nie zakładane `chunk=32`.** Nie należy traktować tej
serii jako porównania obu urządzeń przy tych samych parametrach. Wcześniejszy
`20261031T063340.750643Z-dial.json` zawiera odmowę połączenia WinError 10061
w etapie CONNECT, zero próbek i brak adresu partnera w raporcie. Jest osobną
nieudaną próbą połączenia, nie pomiarem opóźnienia ani timeoutem ramki.

| RTT [ms] | PC → A | PC → B |
| --- | ---: | ---: |
| Minimum | 29,475 | 56,232 |
| Średnia | 57,067 | 143,984 |
| Mediana | 58,724 | 69,091 |
| p95 | 79,936 | 1117,340 |
| Maksimum | 114,420 | 1597,139 |
| Liczba >200 / >500 / >1000 ms | 0 / 0 / 0 | 16 / 16 / 16 |

W B **16/300 = 5,33%** odpowiedzi przekroczyło sekundę. Numery próbek:
11, 25, 27, 31, 54, 65, 100, 136, 145, 146, 220, 243, 244, 267, 277, 298.
Wszystkie te opóźnienia wystąpiły po pierwszym niepustym odczycie odpowiedzi.
Przykłady (lokalny zegar PC, ms od startu danego żądania):

| Próbka B | RTT | Pierwszy odczyt | Od pierwszego odczytu do końca walidacji |
| --- | ---: | ---: | ---: |
| 25 | 1597,139 | 43,444 | 1553,695 |
| 267 | 1515,069 | 40,122 | 1474,947 |
| 146 | 1483,822 | 40,271 | 1443,551 |
| 244 | 1478,218 | 40,110 | 1438,107 |
| 298 | 1477,685 | 39,897 | 1437,788 |

Dla 16 wolnych próbek pierwszy odczyt nastąpił po 39,475–49,201 ms, a późniejszy
odcinek trwał 1075,117–1553,695 ms. Dla A maksymalny odcinek po pierwszym
odczycie wynosił zaledwie 0,070 ms. To istotny ślad: odpowiedź B zaczynała
docierać szybko, lecz operacja odbioru i walidacji kończyła się znacznie później.
Obecny raport nie zapisuje długości i czasu każdego `recv`, więc nie rozdziela
oczekiwania na pozostałe bajty od przerwy w wykonywaniu procesu PC. Nie dowodzi
też retransmisji, problemu konkretnej warstwy sieci ani uszkodzenia Pico B.

Dostarczony raport B lokalizuje długie opóźnienie w pętli wysyłania bajtów
przez Pico, a nie wyłącznie w oczekiwaniu PC:

| LISTEN B, chunk=1 | Wynik |
| --- | --- |
| Maks. tx / rx / prep [ms] | 1556 (#25) / 23 (#4) / 14 (#2) |
| Wywołania read / write | 20137 / 52809 |
| Puste read / write | 10505 / 43177 |
| Krótkie read / write | 0 / 0 |
| Maks. read / write / przerwa pętli [ms] | 1 / 1 / 22 |
| Grafika: aktualizacje / pominięcia | 2572 / 84 |
| Odrzucone bajty | 0 |

| Próbka B | span [ms] | tx [ms] | rx [ms] | prep [ms] |
| --- | ---: | ---: | ---: | ---: |
| 25 | 1591 | 1556 | 22 | 13 |
| 267 | 1508 | 1472 | 23 | 13 |
| 244 | 1473 | 1438 | 22 | 13 |
| 243 | 1431 | 1395 | 22 | 14 |
| 54 | 1394 | 1358 | 22 | 14 |

`52809 - 43177 = 9632 = 301 × 32`: udane zapisy przekazywały po jednym bajcie
300 odpowiedzi i końcowego ACK. Zero krótkich zapisów nie oznacza zapisu całej
ramki naraz, ponieważ żądana długość każdego wywołania wynosiła 1. W #25
wysyłanie trwało 1556 ms, zgodnie z 1553,695 ms obserwowanymi na PC po pierwszym
odczycie. Wiele pustych zapisów oznacza czasowe nieprzyjmowanie kolejnych
danych przez API (licznik obejmuje także EAGAIN). Pojedyncze wywołania nadal
trwały najwyżej 1 ms. Powód nieprzyjmowania danych przez firmware nie został
jeszcze rozstrzygnięty.

Wniosek: w tej serii skoki występują podczas wysyłania odpowiedzi bajt po
bajcie. Nie można na tej podstawie przypisać problemu samemu Pico B ani
roli LISTEN. Wcześniejsze skoki Pico–Pico przy potwierdzonym `chunk=32`
miały inny profil (tx maks. 3 ms); nie zostały wyjaśnione tą obserwacją.

Następny krok: powtórzyć PC DIAL → B LISTEN przy 8 MHz, `load=1`, **chunk=32**.
Uruchom Pico bez argumentów, odpowiedz `listen`, `6502`, `1`: domyślny chunk
wynosi 32. Przed połączeniem sprawdź wydruk `Role=listen ... load=1 chunk=32`.
W wariancie z argumentami kolejność to `listen 6502 1 32` (load, potem chunk).
Na PC użyj ponownie `python net_probe_peer.py dial --host 192.168.1.11`
z katalogu `tools`; domyślna nazwa raportu zachowa poprzedni pomiar.

## Powtórka PC DIAL → B LISTEN z chunk=32

Źródła: `tools/build/net-probe-pc/20261031T063913.217304Z-dial.json` oraz
pełny raport LISTEN użytkownika. Potwierdzone ustawienia B: `load=1`,
`chunk=32`, 300 próbek; PC 192.168.1.100 → B 192.168.1.11:6502. Obie strony PASS.

| Pomiar | Wynik |
| --- | --- |
| RTT min / średnia / p50 / p95 / max [ms] | 29,494 / 42,420 / 32,390 / 39,711 / 1435,388 |
| RTT >200 / >500 / >1000 ms | 2 / 2 / 2 |
| Maks. LISTEN tx / rx / prep [ms] | 3 (#1) / 15 (#232) / 14 (#6) |
| Maks. LISTEN span [ms] | 31 |
| LISTEN read / write | 7170 / 301 |
| LISTEN puste read / write | 6869 / 0 |
| LISTEN krótkie read / write | 0 / 0 |
| LISTEN maks. read / write / przerwa pętli [ms] | 1 / 1 / 22 |
| LISTEN grafika aktualizacje / pominięcia | 817 / 9 |
| LISTEN odrzucone bajty | 0 |

Najwolniejsze lokalne odcinki LISTEN: #15, #36, #41, #49 i #63, każdy
`span=31 tx=3 rx=14 prep=14 ms`. Maksimum 31 ms obejmuje wszystkie żądania,
również te, dla których PC zmierzył długie RTT.

Pięć najwolniejszych próbek na PC (ms):

| Próbka | Początek | RTT | tx PC | wait PC | other PC |
| --- | ---: | ---: | ---: | ---: | ---: |
| 161 | 6545,989 | 1435,388 | 0,040 | 1435,338 | 0,010 |
| 128 | 4313,553 | 1172,595 | 0,043 | 1172,542 | 0,010 |
| 251 | 10957,166 | 124,878 | 0,060 | 124,803 | 0,014 |
| 69 | 2266,461 | 87,954 | 0,056 | 87,886 | 0,013 |
| 126 | 4216,453 | 63,948 | 0,061 | 63,873 | 0,014 |

**Skoki pozostały: 2/300, czyli około 0,67% próbek ponad sekundę.**
W #161 pierwszy niepusty odczyt odpowiedzi na PC nastąpił po 1435,345 ms,
a zakończenie odbioru/walidacji po kolejnych 0,044 ms. W #128 odpowiednio
1172,546 i 0,049 ms. Długie oczekiwanie jest teraz **przed pierwszym odczytem**,
odmiennie niż przy `chunk=1`.

Zmiana na chunk=32 usunęła w tej próbie puste zapisy i sekundowe fazy tx
Pico, lecz nie wszystkie skoki RTT. Wynik jest zbliżony profilem do wcześniejszej
próby Pico–Pico: szybka obsługa LISTEN i długie oczekiwanie DIAL. Nie wiadomo
jeszcze, czy opóźnia się dostarczenie żądania, odpowiedzi, czy obsługa kolejki
poza mierzonym odcinkiem. Nie należy utożsamiać wyniku z dowodem uszkodzenia B
ani konkretnej przyczyny w firmware. Spadek częstości skoków z 16 do 2 pochodzi
z pojedynczych serii o różnych parametrach.

Następny proponowany krok: zapis pakietów TCP na interfejsie Ethernet PC
podczas kolejnej próby PC DIAL → B LISTEN, bez zmiany `load=1` i `chunk=32`.
Zestawić numery/treść ramek z JSON i zbadać odstępy między żądaniem,
potwierdzeniami TCP i odpowiedzią. Taki zapis może ujawnić retransmisje lub
oczekiwanie po potwierdzonym żądaniu; sam nie pokazuje wszystkich kolejek
wewnątrz Pico ani nie dowodzi przyczyny radiowej. Przechwycenia jeszcze nie
wykonano. Nie ma potrzeby zmieniać teraz ROM-u lub dodawać kolejnych faz
czasowych do programu 6502. Gotowy sposób przechwycenia opisano poniżej.

## Przechwycenie TCP podczas jednej próby

Przygotowano `tools/capture_net_probe.py`. Używa wbudowanego w Windows PktMon
i tego samego programu PC, bez instalowania Wiresharka i bez zmiany ROM-u.
Próba odczytu sterownika PktMon z sesji agenta została odrzucona również poza
sandboxem: potrzebny jest token **administratora Windows**.

Otwórz PowerShell jako administrator w katalogu projektu:

```powershell
python tools/capture_net_probe.py --host 192.168.1.11
```

Jeśli terminal jest w katalogu `tools`, polecenie brzmi:

```powershell
python capture_net_probe.py --host 192.168.1.11
```

Skrypt zaczeka na Enter. W tym czasie uruchom na B PROBE 4: `listen`, `6502`,
`1`, przy 8 MHz. Sprawdź `load=1 chunk=32`; gdy Pico czeka na połączenie,
naciśnij Enter w terminalu PC. Skrypt uruchomi przechwytywanie, sam wykona
300 próbek DIAL, zatrzyma zapis i przekonwertuje ETL na PCAPNG.

Wszystkie pliki są w nowym katalogu **`build/net-probe-pc/<czas>-capture`**
względem katalogu projektu, niezależnie od miejsca uruchomienia:

- `packets.etl`: oryginalny zapis PktMon, z informacjami potrzebnymi do
  rozpoznawania komponentów stosu sieciowego;
- `packets.pcapng`: pakiety do analizy TCP;
- `probe.json`, `probe.csv`: wszystkie próbki i wynik zwykłego testu PC;
- `console.txt`: wydruk programu PC;
- `commands.json`, `capture.json`: stan, polecenia, adresy i wynik przechwycenia.

Filtr obejmuje tylko TCP/6502 między adresem PC wybranym przez routing a
adresem wskazanego Pico. Domyślnie zapis obejmuje komponenty NIC (`--comp nics`),
pełne pakiety, zapis `multi-file` z progiem 1024 MiB na plik (bez nadpisywania
wcześniejszych plików). Wszystkie powstałe ETL są konwertowane. Można zawęzić go do konkretnego ID z
`pktmon list` przez `--component ID`; ID może zmieniać się między uruchomieniami.
Nie należy uznawać identycznych kopii pakietu z różnych komponentów za dowód
retransmisji. ETL trzeba zachować wraz z PCAPNG. Przed interpretacją sprawdzić
komunikaty PktMon o utraconych zdarzeniach i zgodność liczby ramek z raportem.

Skrypt odmawia startu, gdy istnieje aktywna sesja PktMon, istniejące filtry
lub nierozpoznany stan. Nie usuwa cudzych filtrów ani nie zatrzymuje cudzej
sesji. W tej wersji PktMon usuwanie dotyczy wszystkich filtrów, więc skrypt
czyści listę tylko wtedy, gdy nadal zawiera wyłącznie jego własny, niezmieniony
filtr. Nie uruchamiaj równolegle innego sterowania PktMon. Skrypt nie zmienia
zapory. Przy błędzie lub Ctrl+C próbuje zatrzymać własny zapis; jeśli zatrzymanie
się nie uda, wypisuje polecenie naprawcze. Zamknięcie okna siłą może przerwać
sprzątanie — użyj Ctrl+C. Cała próba PC ma dodatkowy limit 180 sekund.

Przy problemie uprawnień przed startem nie są uruchamiane ani przechwycenie,
ani test. Przy awarii testu po starcie ETL jest zachowywany i konwertowany;
wymuszone zakończenie procesu PC może uniemożliwić zapis jego JSON. Błąd
połączenia wymaga ponownego przygotowania LISTEN na Pico i nowego uruchomienia
skryptu. Samo powstanie PCAPNG nie oznacza, że test przeszedł lub odtworzył skok.

Zweryfikowano składnię w pomocy lokalnego PktMon, tekst komunikatu pustej
listy w jego zasobach Windows oraz zachowanie skryptu w 7 testach z atrapą
poleceń (zakończenie, anulowanie, awarie, istniejąca sesja/filtry i zmiana filtrów).
Rzeczywiste przechwycenie wymaga uruchomienia z uprawnieniami administratora;
nie zostało jeszcze zweryfikowane na sprzęcie.

Pierwsze uruchomienie jako administrator (`20261031T064814.604196Z-capture`)
zatrzymało się przed zmianą filtrów i rozpoczęciem przechwytywania. PktMon
wyświetlił pustą listę jako `Packet Filters: None`, zamiast komunikatu
zakładanego przez parser. Dodano obsługę rzeczywistego formatu i test regresji;
wszystkie 8 testów sterowania przechwytywaniem przechodzi. Przy otwieraniu
osobnego okna używany jest teraz PowerShell z `-NoExit`, aby wynik pozostał
widoczny również po błędzie. Nie był to błąd połączenia z Pico.

Drugie uruchomienie (`20261031T065113.068399Z-capture`) ujawniło skracanie
długiej nazwy filtra w tabeli PktMon. Od tego momentu nazwa ma 16 znaków
(`SpyProbe` + losowy identyfikator), więc mieści się w kolumnie. Dodano testy
rzeczywistego wielowierszowego wydruku i odzyskiwania pozostawionego filtra;
łącznie przechodzi 11 testów. `--recover-from COMMANDS_JSON` usuwa filtr tylko
po potwierdzeniu braku aktywnego zapisu oraz dokładnej zgodności bieżącej
listy z zapisem poprzedniej operacji dodającej nasz pojedynczy filtr.

Sprawdzenie **rzeczywistego PktMon jako administrator** zakończyło się sukcesem
w `20261031T065329.191194Z-capture`: odzyskanie filtra, dodanie nowego,
start, stop, usunięcie własnego filtra i konwersja PCAPNG. Nie utracono zdarzeń.
Była to próba `--check`, bez połączenia z Pico (0 pakietów); potwierdza działanie
obsługi narzędzia, a nie wynik sieciowy. Launcher `tools/capture_net_probe.ps1`
wykonuje teraz taki test przed właściwą próbą i uruchamia pomiar tylko po jego
sukcesie. Właściwa próba oczekuje na Enter w osobnym katalogu wynikowym.

### Pierwszy zapis z rzeczywistą wymianą — niepełne pokrycie

`20261031T065330.098468Z-capture`: test PC → B PASS, 300 próbek.
RTT min/średnia/p50/p95/max: **29,460 / 39,720 / 32,833 / 47,325 / 1356,634 ms**.
Jedyna próbka ponad 200/500/1000 ms to #111, rozpoczęta w 3725,131 ms.
Pierwszy odczyt odpowiedzi nastąpił po 1356,586 ms; odbiór i walidacja skończyły
się 0,048 ms później. Test odtworzył długie oczekiwanie przed odpowiedzią.

Przechwycenie uruchomiło się i zakończyło poprawnie, a PktMon zgłosił
`No events lost`. Mimo tego ETL/PCAPNG zawiera tylko **80 rekordów pakietów**,
w tym 65 różnych żądań P i 4 różne odpowiedzi R (8 zapisów tych odpowiedzi).
Brakuje Q/A oraz zarówno żądania, jak i odpowiedzi #111. Zatem nie można
rozstrzygać retransmisji ani kierunku opóźnienia na podstawie tego zapisu.
Brak pakietów w pliku nie jest dowodem ich utraty w sieci. Konwersja ETL do
tekstu również pokazała tylko 80 zdarzeń pakietowych; to nie tylko problem
odczytu PCAPNG. Widoczne kopie przychodzących pakietów należą do komponentów
166 (NetCx) i 17 (Miniport) tej samej karty Realtek; nie są dowodem retransmisji.

Wynik audytu zapisano w `coverage.json`. Nowe narzędzie
`tools/audit_probe_capture.py KATALOG_PRÓBY` sprawdza numery poprawnych ramek
w odniesieniu do wszystkich ukończonych próbek JSON. Nie składa strumienia TCP:
fragmentacja ramki między segmentami oznacza brak potwierdzenia pokrycia,
a nie automatycznie brak pakietu. Nowe przechwycenia wykonują audyt automatycznie
i zgłaszają błąd, jeśli nie potwierdzą każdego żądania oraz odpowiedzi.

Zmiana konfiguracji przechwytywania: zamiast kołowego pliku 32 MiB używany jest
tryb `multi-file` z większym progiem i konwersją wszystkich części; przed stop
zapisywane są liczniki PktMon. Poprzedni log raportował 768 MiB pamięci PktMon.
Nowa konfiguracja usuwa możliwość nadpisania wcześniejszych części, ale
**przyczyna niepełnego pierwszego zapisu nie została jeszcze potwierdzona**.
Nie jest to zmiana gry, firmware ani protokołu.

Samodzielny test `--check-traffic` wykonał 300 poprawnych wymian TCP na
127.0.0.1 (`20261031T065855.798827Z-capture`), lecz PktMon nie zapisał ich jako
pakietów w PCAPNG. Audyt poprawnie zgłosił niepełne pokrycie. Ta próba lokalna
nie potwierdza kompletności przechwytywania z fizycznego interfejsu Ethernet.
Kontrola pokrycia ma 4 testy syntetyczne (pełny zapis, brak odpowiedzi pomimo
duplikatów, brak obu stron oraz ucięty blok); testy sterowania PktMon pozostają
na poziomie 11 przypadków. Do oceny retransmisji potrzebna jest kompletna
próba z fizycznym Pico.

### Drugi zapis z rzeczywistą wymianą — kompletny, bez długiego skoku

`20261031T070049.249215Z-capture`, PC DIAL → B LISTEN, 300 próbek, PASS.
RTT min/średnia/p50/p95/max: **29,381 / 34,069 / 32,658 / 39,851 / 73,021 ms**.
Liczniki >200/>500/>1000 ms: 0/0/0. Pięć najwolniejszych: #263 73,021 ms,
#264 57,824 ms, #91 54,163 ms, #109 51,779 ms, #93 50,316 ms.

Kontrola `coverage.json` potwierdziła wszystkie 300 żądań P, 300 odpowiedzi R
i Q/A. PktMon zgłosił brak utraconych zdarzeń. Zapis zawiera 1322 rekordy,
ponieważ każdy pakiet występuje w komponentach 166 i 17 tej samej karty.
Liczniki każdego komponentu: 305 Tx i 356 Rx, razem 661.

Wyeksportowano osobno komponent 17 (`ethernet17.pcapng`) i sprawdzono jego
661 pakietów. Zawiera 300 P, 300 R, po jednym Q/A oraz handshake/ACK/zamknięcie.
Nie ma powtórzeń segmentów danych o tym samym kierunku, numerze TCP i treści.
Podsumowanie: `tcp-summary.json`. Podwójne zapisy w pierwotnym PCAPNG były
obserwacją dwóch komponentów, a nie retransmisjami.

To potwierdza kompletność nowej konfiguracji przechwytywania w tej próbie.
Nie dowodzi usunięcia przyczyny wcześniejszych skoków: protokół, gra i firmware
nie zostały zmienione, a pojedyncza seria może nie trafić na rzadkie opóźnienie.
Potrzebna jest kolejna taka sama próba PC → B (8 MHz, load=1, chunk=32), aż
uzyskamy kompletny zapis obejmujący skok. Nie zmieniamy przy tym ustawień sieci,
żeby zachować porównywalność. Pliki poprzednich prób pozostają zachowane.

### Kolejne serie — pełny zapis ze skokami i retransmisjami

`20261031T071133.224695Z-capture`: kompletne pokrycie 300 próbek, PASS,
RTT min/średnia/p50/p95/max 29,467 / 33,834 / 32,597 / 40,899 / 84,364 ms,
bez RTT >200 ms. Następna seria dostarczyła potrzebnego zapisu ze skokami.

`20261031T071823.386893Z-capture`: PC → B, PASS, pełne pokrycie P/R i Q/A.
RTT min/średnia/p50/p95/max **29,406 / 62,658 / 32,662 / 49,685 / 1480,464 ms**.
Siedem próbek >200/>500/>1000 ms (7/300 = 2,33%). PktMon zapisał 1340 rekordów;
eksport komponentu 17 (`ethernet17.pcapng`) zawiera 670 pakietów, dzięki czemu
kopie z drugiego komponentu nie są liczone jako retransmisje.

W sześciu wolnych próbkach widać **ponowne wysłanie tego samego żądania TCP
przez PC**: ten sam numer TCP, ta sama 32-bajtowa treść, późniejszy czas i nowy
IP ID, wszystko na jednym komponencie karty. To retransmisje, odrębne od
podwójnych obserwacji PktMon. Czas poniżej jest mierzony względem pierwszego
wyjścia żądania na PC (ms); ACK oznacza pierwsze zaobserwowane potwierdzenie
pełnych 32 bajtów żądania przez TCP Pico.

| Próbka | RTT aplikacji | Ponowienie PC | ACK żądania | Odpowiedź na PC | Odpowiedź po ACK |
| --- | ---: | ---: | ---: | ---: | ---: |
| 85 | 1336,486 | brak | 2,151 | 1336,234 | 1334,083 |
| 89 | 1292,096 | 258,919 | 372,298 | 1291,884 | 919,586 |
| 100 | 1152,483 | 251,167 | 343,290 | 1152,272 | 808,982 |
| 128 | 1105,329 | 248,702 | 345,411 | 1105,114 | 759,703 |
| 134 | 1324,625 | 248,974 | 345,297 | 1324,408 | 979,111 |
| 150 | 1480,464 | 245,223 | 349,634 | 1480,271 | 1130,637 |
| 284 | 1043,051 | 248,592 | 352,797 | 1042,887 | 690,090 |

Surowe zdarzenia z numerami TCP, ACK, IP ID i czasem zapisano w
`tcp-events.json`, podsumowanie w `tcp-summary.json`, pełny tekst ETL w
`packets.txt`. Numer ACK osiąga `seq żądania + 32`. Zgodnie z
[RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.4) potwierdza
to odbiór bajtów przez TCP; nie oznacza wykonania kodu aplikacji 6502.

W sześciu próbkach z ponowieniem żądania pakiet ACK od B ma dodatkowo numer
SEQ o 32 większy niż numer później odebranej odpowiedzi. Jest to ślad zgodny
z wcześniejszym wysłaniem odpowiedzi przez stos TCP B i późniejszym jej
ponowieniem, ale na PC nie widać pierwotnej odpowiedzi: to **wniosek**, a nie
bezpośredni zapis dwóch transmisji odpowiedzi. Nie da się stąd wskazać miejsca
zgubienia/zatrzymania danych ani potwierdzić konkretnego timera retransmisji.

Użytkownik dostarczył raport LISTEN B z tej samej próby, potwierdzając
`load=1, chunk=32`, PASS i 300 próbek:

| Pomiar LISTEN B | Wynik |
| --- | --- |
| Maks. tx / rx / prep [ms] | 3 (#1) / 15 (#6) / 14 (#3) |
| Maks. lokalny span [ms] | 31 |
| Wywołania read / write | 18797 / 301 |
| Puste read / write | 18496 / 0 |
| Krótkie read / write | 0 / 0 |
| Maks. read / write / przerwa pętli [ms] | 1 / 1 / 21 |
| Aktualizacje / pominięcia grafiki | 1175 / 14 |
| Odrzucone bajty | 0 |

Najdłuższe spany: #6 i #53 `31=3+15+13 ms`, #15/#22/#46 `31=3+14+14 ms`.
To nie jest profil problemu `chunk=1`: nie ma sekundowego tx ani pustych
zapisów. W #85 żądanie zostało potwierdzone przez TCP niemal od razu, a
opóźnienie wystąpiło później. W pozostałych sześciu najpierw wystąpiła
retransmisja żądania, a po jego potwierdzeniu nadal pozostawało 690–1131 ms
do pojawienia się odpowiedzi na PC.

Wniosek: mamy potwierdzony udział retransmisji TCP i długiego oczekiwania poza
mierzonym przetwarzaniem ramki przez aplikację Pico. Pozostają do rozdzielenia
obsługa/kolejki firmware RIA oraz transmisja przez Wi-Fi/AP. Sam ACK nie mówi,
kiedy 6502 odebrał dane z firmware, a przyjęcie odpowiedzi przez API nie mówi,
kiedy dotarła ona do PC. Nie ma podstaw, aby uznać konkretny router, Pico lub
firmware za ustaloną przyczynę.

Dalszy krok powinien izolować drogę Wi-Fi, zamiast powtarzać tę samą serię
wyłącznie w poszukiwaniu kolejnego skoku. Zapytano o fizyczny AP dla A/B,
ewentualny mesh/repeater i model urządzenia. Na tej podstawie można dobrać
porównanie B na jednym innym AP lub w kontrolowanym położeniu, zachowując
firmware, 8 MHz, load=1, chunk=32 i przechwycenie PC. Jeśli problem pozostanie,
potrzebne będą znaczniki po stronie RIA (odbiór TCP, przekazanie do 6502,
przyjęcie odpowiedzi, wysłanie i ponowienia). Takiej instrumentacji jeszcze
nie wprowadzono.

Oficjalna dokumentacja: [PktMon](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon),
[filtry](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon-filter-add),
[konwersja i ograniczenia PCAPNG](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon-etl2pcap).

## Testy

```powershell
python tests/test_net_probe_peer.py -v
```

Osiem testów obejmuje wymianę 300 żądań przez lokalne TCP i końcowe Q/A,
uruchomienie obu ról z wiersza poleceń, zapis CSV/JSON, sumy faz, podział i
łączenie ramek w strumieniu, błędne ramki i numer odpowiedzi, przerwanie oraz
walidację argumentów. Wzorce ramek są porównywane z rzeczywistym `protocol.c`
skompilowanym dla `sim65`. Gdy cc65/sim65 nie ma na PC, ten jeden test jest
pomijany; na komputerze roboczym przeszedł. CTest zawiera test `net-probe-peer`.
