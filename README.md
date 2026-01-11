# BIP Search - Wyszukiwarka decyzji środowiskowych

Aplikacja do przeszukiwania Biuletynów Informacji Publicznej (BIP) w Polsce pod kątem decyzji o środowiskowych uwarunkowaniach (DUŚ), wniosków, wszczęć postępowań i obwieszczeń środowiskowych.

## Funkcje

- **2894 źródeł BIP** - pełna baza samorządów w Polsce:
  - 1 GDOŚ (Generalna Dyrekcja Ochrony Środowiska)
  - 16 RDOŚ (Regionalne Dyrekcje Ochrony Środowiska)
  - 16 Urzędów Marszałkowskich
  - 66 miast na prawach powiatu
  - 314 powiatów
  - 398 gmin miejskich
  - 745 gmin miejsko-wiejskich
  - 1338 gmin wiejskich
- Filtrowanie po zakresie dat
- Automatyczna klasyfikacja branżowa (OZE, Przemysł, IT/Data Centers, Energetyka, Logistyka, Infrastruktura, Górnictwo)
- Eksport wyników do CSV i Excel
- Intuicyjny interfejs w przeglądarce

## Wymagania

- macOS / Linux / Windows
- Python 3.9 lub nowszy
- Przeglądarka internetowa (Safari, Chrome, Firefox)

## Instalacja (krok po kroku)

### 1. Otwórz Terminal

Znajdziesz go w: **Aplikacje → Narzędzia → Terminal**

Lub użyj Spotlight: naciśnij `Cmd + Spacja`, wpisz "Terminal" i naciśnij Enter.

### 2. Przejdź do folderu z aplikacją

Skopiuj i wklej tę komendę w Terminal:

```bash
cd ~/Documents/Claude\ Code/bip-search
```

### 3. Zainstaluj zależności (tylko za pierwszym razem)

```bash
pip3 install -r requirements.txt
```

Poczekaj aż instalacja się zakończy (może potrwać 1-2 minuty).

### 4. Uruchom aplikację

```bash
python3 app.py
```

Powinieneś zobaczyć:
```
============================================================
  BIP Search - Wyszukiwarka decyzji środowiskowych
============================================================

  Otwórz przeglądarkę i wejdź na adres:
  http://localhost:5000

  Aby zatrzymać aplikację, naciśnij Ctrl+C
============================================================
```

### 5. Otwórz przeglądarkę

Wejdź na adres: **http://localhost:5000**

## Jak używać

1. **Wybierz daty** - ustaw zakres dat (domyślnie ostatnie 14 dni)
2. **Wybierz branże** - zaznacz interesujące Cię branże (domyślnie wszystkie)
3. **Kliknij "Rozpocznij wyszukiwanie"**
4. **Poczekaj** - przeszukiwanie 2894 źródeł zajmuje około 30-60 minut (w zależności od połączenia)
5. **Pobierz wyniki** - kliknij "Pobierz CSV" lub "Pobierz Excel"

## Kolumny w wynikach

| Kolumna | Opis |
|---------|------|
| Lokalizacja / Województwo | Nazwa gminy/miasta i województwo |
| Data obwieszczenia | Data publikacji dokumentu |
| Etap postępowania | Wniosek / Wszczęcie / Zebranie materiału / Decyzja |
| Branża | Automatycznie wykryta kategoria |
| Opis przedsięwzięcia | Tytuł/opis projektu |
| Sygnatura | Numer sprawy |
| Źródło (link) | Bezpośredni link do dokumentu |

## Rozwiązywanie problemów

### "command not found: python3"

Zainstaluj Python ze strony: https://www.python.org/downloads/

### "No module named 'flask'"

Uruchom ponownie instalację zależności:
```bash
pip3 install -r requirements.txt
```

### Aplikacja nie odpowiada

1. Zamknij Terminal (lub naciśnij `Ctrl+C`)
2. Otwórz nowy Terminal
3. Uruchom aplikację ponownie

### Brak wyników

- Spróbuj rozszerzyć zakres dat
- Zaznacz więcej branż
- Niektóre BIP-y mogą mieć inne struktury stron

## Struktura plików

```
bip-search/
├── app.py              # Główna aplikacja Flask
├── scraper.py          # Silnik scrapowania stron BIP
├── filters.py          # Filtrowanie branżowe i przetwarzanie danych
├── sources_full.json   # Pełna baza źródeł BIP (2894 URL-i)
├── requirements.txt    # Zależności Python
├── templates/
│   └── index.html      # Interfejs użytkownika
├── static/
│   └── style.css       # Style CSS
├── data/               # Cache (tworzony automatycznie)
└── README.md           # Ten plik
```

## Źródła danych

Aplikacja przeszukuje **2894 źródeł BIP** obejmujących:
- **GDOŚ** - Generalna Dyrekcja Ochrony Środowiska (1)
- **RDOŚ** - 16 Regionalnych Dyrekcji Ochrony Środowiska
- **Urzędy Marszałkowskie** - 16 województw
- **Miasta na prawach powiatu** - 66 największych miast
- **Powiaty** - 314 powiatów ziemskich
- **Gminy miejskie** - 398 gmin
- **Gminy miejsko-wiejskie** - 745 gmin
- **Gminy wiejskie** - 1338 gmin

## Ograniczenia

- Nie wszystkie BIP-y mają ujednoliconą strukturę - niektóre wyniki mogą być niepełne
- Czas przeszukiwania zależy od szybkości połączenia internetowego
- Niektóre BIP-y mogą być czasowo niedostępne

## Licencja

Dane pochodzą z publicznych Biuletynów Informacji Publicznej i są udostępniane zgodnie z ustawą o dostępie do informacji publicznej.

## Autor

Wygenerowane przez Claude Code
