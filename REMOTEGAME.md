# Spy vs Spy — koncepcja gry dwuosobowej przez internet

Data zapisu: 2026-10-30, Europe/Warsaw.

Status: notatka z dyskusji, do wznowienia w przyszłości. Nie rozpoczęto
implementacji trybu sieciowego. Użytkownik poprosił wyłącznie o zachowanie
koncepcji. R12 pozostaje zaakceptowaną wersją referencyjną gry lokalnej,
działającą na emulatorze i fizycznym Picocomputerze.

## Cel

Umożliwić dwóm osobom grę na dwóch Picocomputerach połączonych przez internet.
Każda osoba sterowałaby jednym szpiegiem. Pierwszy wariant mógłby zachować
obecny podzielony ekran na obu monitorach i oryginalne zasady gry.

Port ma już lokalny tryb dwóch graczy i obsługę dwóch joysticków. Główne
wyzwanie to utrzymanie zgodnego stanu rozgrywki na dwóch niezależnych maszynach.

## Dostęp do sieci

W dokumentacji sprawdzonej podczas dyskusji konfiguracja RP6502-PICO-W
wykorzystuje Pico 2 W jako RIA oraz firmware RIA-W. Program 6502 może otworzyć
urządzenie `AT:`, obsługujące emulację modemu Hayes i połączenia przez surowy
TCP lub Telnet. Stos sieciowy wykonuje RIA, a nie procesor 6502.

Źródło: [RP6502-PICO-W — Modem Emulation](https://picocomputer.github.io/ria_w.html#modem-emulation).

Na pierwszy eksperyment proponowany jest surowy TCP. Lokalny kod firmware
zawiera obsługę częściowych odczytów i zapisów modemu. Należy uwzględnić je
w protokole oraz zmierzyć czas wywołań, aby komunikacja nie blokowała obsługi
gry, obrazu i dźwięku. Granice odczytów TCP nie są granicami wiadomości gry.

Do sprawdzenia przed prototypem:

- Czy konkretny komputer ma RIA z Wi-Fi i odpowiedni wariant firmware.
- Czy interfejs `AT:` oraz wymagany tryb TCP działają w używanym buildzie.
- Jak zachowują się odczyty, zapisy i utrata połączenia podczas pracy gry.
- Jak zapewnić transport w emulatorze używanym do testów. Dokumentacja
  sprawdzona podczas dyskusji opisywała sieć jako funkcję RP6502-PICO-W;
  nie zakładamy automatycznie takiej samej obsługi w emulatorze.

Znany kontekst sprzętowy R12: użytkownik podał firmware Version 0.42,
build po commicie `ad6293c`, a wcześniej gałąź `mtRAM+PCM`. Nie jest to
potwierdzenie dostępności wszystkich wymaganych funkcji sieciowych.
Dokumentację i zgodność firmware trzeba ponownie sprawdzić po wznowieniu prac.

## Preferowany pierwszy wariant: lockstep

Oba komputery uruchamiają identyczną wersję gry. Wymieniają wejście graczy
przypisane do konkretnych, numerowanych kroków symulacji. Kolejny krok jest
wykonywany dopiero wtedy, gdy dostępne są polecenia obu graczy dla tego kroku.

Proponowana zawartość wiadomości:

- Numer kroku gry.
- Kierunek ruchu i stan przycisku fire.
- Polecenia wspólne, takie jak rozpoczęcie gry lub pauza.
- Okresowa suma kontrolna istotnego stanu rozgrywki.

Przy nawiązywaniu sesji potrzebne byłyby także zgodna wersja ROM-u/protokołu,
ustawienia partii, przypisanie graczy i wspólny stan inicjalizacji losowości.

Przykładowa wiadomość o długości 12 bajtów wysyłana 60 razy na sekundę daje
720 bajtów danych gry na sekundę w jednym kierunku, przed narzutem protokołów.
To ilustracja małego zapotrzebowania na transfer, a nie ustalony format pakietu
ani wynik pomiaru.

## Najważniejszy problem: deterministyczność obecnego portu

Identyczne polecenia joysticka nie gwarantują obecnie identycznej rozgrywki.
W sprawdzonym kodzie R12:

- `pace_main` wiąże główną pętlę z lokalnym zegarem VGA.
- Obsługa IRQ wywołuje oryginalną procedurę VBI gry.
- Emulowany rejestr losowy `$D20A` jest aktualizowany w przerwaniu.
- Procedury DLI wpływają również na stan wykorzystywany przez grę.
- Lokalna pętla obsługuje graczy naprzemiennie: do 60 obiegów na sekundę
  oznacza do 30 aktualizacji na każdego szpiega.

Dwa komputery mają niezależne zegary. Potrzebny byłby wspólny logiczny krok
rozgrywki, jednakowa inicjalizacja, kontrolowana losowość i ustalona kolejność
wykonywania elementów symulacji.

Samo zatrzymanie głównej pętli w oczekiwaniu na dane sieciowe nie wystarczy:
odpowiednie liczniki i procedury wykonywane w przerwaniach także muszą
podlegać synchronizacji. Trzeba rozpoznać, które działania należą do symulacji,
a które można wykonywać lokalnie jako prezentację obrazu i dźwięku.

Sumy kontrolne należy liczyć dla ustalonego stanu logicznego w tym samym
kroku, a nie bezrefleksyjnie dla całej pamięci zawierającej również lokalne
liczniki i stan sprzętu. W pierwszym prototypie wykryta rozbieżność powinna
zatrzymać próbę i dostarczyć danych diagnostycznych.

## Opóźnienia i utrata danych

Proponowany mechanizm to bufor wejścia: polecenia wykonuje się kilka kroków
po ich zebraniu, dając sieci czas na dostarczenie danych.

Przykładowo 4–6 kroków przy 60 Hz oznacza około 67–100 ms dodatkowego
opóźnienia sterowania. Jest to punkt wyjścia do eksperymentów, nie docelowa
wartość ani gwarancja płynności. Szczególnie ważna będzie ocena walki szpiegów.

TCP zapewnia uporządkowany strumień, lecz retransmisja utraconych danych może
opóźnić dostarczenie kolejnych wiadomości. Pierwszy wariant lockstep może
wtedy chwilowo zatrzymać rozgrywkę. Trzeba zaprojektować ograniczone kolejki,
timeout, wspólną pauzę i zakończenie sesji po utracie połączenia. Nie zakładamy
na początku płynnego ponownego dołączania do trwającej partii.

## Porównanie wariantów

| Wariant | Zaleta | Główna trudność | Ocena na początek |
| --- | --- | --- | --- |
| Lockstep | Mały transfer; obie maszyny wykonują oryginalną grę | Identyczny przebieg symulacji i opóźnienie wejścia | Preferowany do pierwszej próby |
| Jeden komputer rozstrzyga stan gry | Jeden wiążący wynik zdarzeń | Rozpoznanie i przesyłanie stanu pokojów, pułapek, przedmiotów, postaci i liczników | Alternatywa wymagająca głębszej analizy gry |
| Przewidywanie i rollback | Szybka reakcja na lokalne sterowanie | Zapisywanie stanu, cofanie i ponowne wykonywanie kroków, obsługa dźwięku, koszt pamięci i CPU | Odłożyć do ewentualnych dalszych eksperymentów |

Obecny port ma mało wolnego miejsca w głównym obszarze kodu hosta
(135 bajtów według mapy R12). Bufory sieciowe i dodatkowy kod wymagają
osobnego planu pamięci. Sama dostępność połączenia TCP nie rozwiązuje
ograniczeń pamięci ani kosztu synchronizacji.

## Połączenie przez serwer pośredniczący

Proponowany układ:

```text
Picocomputer A <-> serwer pokoju <-> Picocomputer B
```

Oba Picocomputery nawiązują połączenia wychodzące. Serwer kojarzy graczy
kodem pokoju i przekazuje polecenia. W wariancie lockstep nie wykonuje gry.
Takie rozwiązanie ogranicza problemy z przekierowaniem portów i CGNAT.

Bezpośrednie połączenie w LAN nadaje się do wcześniejszego eksperymentu.
Hosting serwera, protokół sesji i sposób wybierania pokoju nie zostały jeszcze
ustalone; niczego nie wdrożono ani nie zamówiono.

## Kolejność ewentualnych prac

1. **Deterministyczność bez sieci.** Dwie instancje otrzymują identyczny zapis
   sterowania. Porównujemy stan po kolejnych krokach, uwzględniając zmianę
   pokojów, pułapki, walkę i zakończenie partii. To pierwsze kryterium decyzji
   o dalszych pracach nad lockstep.
2. **Osobny eksperyment komunikacyjny na Pico.** Sprawdzamy `AT:` i TCP,
   mierzymy opóźnienia, przerwy, częściowe transmisje oraz koszt obsługi przy
   aktualizacji grafiki. Ten etap nie wymaga jeszcze zmieniania gry.
3. **Dwie maszyny w LAN.** Wprowadzamy stały bufor wejścia, zgodną inicjalizację,
   kontrolę stanu oraz zatrzymanie po utracie połączenia.
4. **Internet przez serwer pośredniczący.** Dobieramy bufor na podstawie pomiarów
   i oceniamy komfort rozgrywki, zwłaszcza walki.
5. **Wygoda obsługi.** Dopiero po potwierdzeniu działania dodajemy pokoje,
   wybór szpiega i czytelne komunikaty o połączeniu.

## Ustalenie na moment zakończenia dyskusji

Tryb sieciowy jest technicznie obiecujący, ale jego wykonalność w tym porcie
wymaga najpierw próby deterministyczności i pomiarów komunikacji. Nie jest
małą zmianą polegającą wyłącznie na podłączeniu zdalnego joysticka.

Ewentualne prace należy prowadzić jako osobny wariant portu. Zachować
`releases/r12/` jako sprawdzony punkt odniesienia do gry lokalnej.
Powrót do tej notatki nie oznacza automatycznej zgody na implementację.
