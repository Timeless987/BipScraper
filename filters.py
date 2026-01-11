"""
Moduł filtrowania branżowego dla wyszukiwarki decyzji środowiskowych BIP.
Automatycznie klasyfikuje przedsięwzięcia według branży na podstawie słów kluczowych.
"""

import re
from typing import Optional, List, Dict
from datetime import datetime
from dateutil import parser as date_parser


# Słowa kluczowe dla poszczególnych branż
INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "OZE": [
        # Fotowoltaika
        "fotowoltaik", "fotowoltaiczn", "solar", "pv ", "panel", "paneli słoneczn", "panele słoneczn",
        "elektrownia słoneczna", "instalacja solarna", "ogniwa słoneczne",
        # Wiatr
        "wiatrow", "wiatrak", "turbina wiatrowa", "farma wiatrowa",
        "elektrownia wiatrowa", "siłownia wiatrowa",
        # Biomasa/Biogaz
        "biogaz", "biomasa", "biogazownia", "bioelektrownia",
        # Ogólne OZE
        "odnawialne źródła energii", "oze", "energia odnawialna",
        # Magazyny energii (uwaga: kolejność ważna - te frazy muszą być przed ogólnym "magazyn")
        "magazyn energii", "magazynu energii", "magazyny energii", "magazynów energii",
        "akumulator", "bess", "bateria energetyczna",
        "storage energii", "magazynowanie energii",
        # Wodór
        "elektrolizer", "wodór", "hydrogen", "zielony wodór",
        # Pompy ciepła
        "pompa ciepła", "pomp ciepła", "pompy ciepła", "pompą ciepła",
        "geotermia", "geotermaln",
    ],

    "Przemysł/Produkcja": [
        # Zakłady produkcyjne - różne odmiany
        "zakład produkcyjn", "zakładu produkcyjn", "zakładzie produkcyjn",
        "zakład przemysłow", "zakładu przemysłow", "zakładzie przemysłow",
        "zakład przetw", "zakładu przetw", "przetwórni", "przetwórnia",
        # Hale i budynki przemysłowe
        "hala produkcyjn", "hali produkcyjn", "halę produkcyjn",
        "hala przemysłow", "hali przemysłow", "halę przemysłow",
        "hala magazynowo-produkcyjn", "hali magazynowo-produkcyjn",
        "budynek produkcyjn", "budynku produkcyjn",
        "obiekt produkcyjn", "obiektu produkcyjn",
        # Fabryki i wytwórnie
        "fabryk", "wytwórni", "wytwórnia", "manufaktur",
        "montowni", "montownia",
        # Linie i instalacje
        "linia produkcyjn", "linii produkcyjn", "linie produkcyjn",
        "linia technologiczn", "linii technologiczn",
        "instalacja produkcyjn", "instalacji produkcyjn",
        "instalacja przemysłow", "instalacji przemysłow",
        "ciąg technologiczn", "ciągu technologiczn",
        # Parki przemysłowe
        "park przemysłow", "parku przemysłow", "parkiem przemysłow",
        "strefa przemysłow", "strefie przemysłow", "strefy przemysłow",
        "teren przemysłow", "terenu przemysłow",
        # Obróbka i przetwórstwo
        "zakład obróbki", "zakładu obróbki", "obróbka metal", "obróbki metal",
        "obróbka drew", "obróbki drew", "obróbka plastik", "obróbki plastik",
        "zakład mięsn", "zakładu mięsn", "ubojni", "ubojnia", "rzeźni", "rzeźnia",
        "zakład spożywcz", "zakładu spożywcz", "mleczarni", "mleczarnia",
        "piekarni", "piekarnia", "browar", "gorzelni", "gorzelnia",
        # Przemysł ciężki
        "zakład chemiczn", "zakładu chemiczn", "zakład farmaceutyczn", "zakładu farmaceutyczn",
        "cementowni", "cementownia", "betoniarni", "betoniarnia", "asfaltowni", "asfaltownia",
        "odlewni", "odlewnia", "walcowni", "walcownia", "stalowni", "stalownia",
        "huty", "huta", "hutą",
        # Recykling i odpady
        "zakład recykling", "zakładu recykling", "sortowni", "sortownia",
        "spalarni", "spalarnia", "instalacja termiczn", "instalacji termiczn",
        # Produkcja ogólna
        "produkcj", "produkować", "produkuje",
        "przedsiębiorstwem produkcyjn", "przedsiębiorstwa produkcyjn",
        # Prefabrykaty i materiały budowlane
        "zakład prefabrykat", "zakładu prefabrykat", "wytwórni prefabrykat",
        "zakład materiałów budowlan", "wytwórni materiałów",
        # Centra produkcyjno-logistyczne
        "centrum produkcyjn", "centra produkcyjn",
        "produkcyjno-logistyczn", "produkcyjno logistyczn",
        # Specjalistyczne zakłady
        "lakierni", "lakiernia", "lakierowanie",
        "spawalni", "spawalnia", "spawalniczej",
        "galwanizerni", "galwanizernia", "galwanizacyjn",
        "hartowni", "hartownia",
        "cynkowni", "cynkownia", "cynkowniczej",
        "tłoczni", "tłocznia",
        "stolarni", "stolarnia",
        "ślusarni", "ślusarnia",
        "warsztatu produkcyjn", "warsztatem produkcyjn",
    ],

    "IT/Data Centers": [
        # Centra danych
        "centrum danych", "centrów danych", "centra danych",
        "data center", "data centre", "datacenter",
        # Serwerownie
        "serwerowni", "serwerownia", "serwerów",
        # Kolokacja
        "infrastruktura it", "kolokacj", "colocation",
        # Chmura i obliczenia
        "cloud computing", "chmura obliczeniow", "chmurze obliczeniow",
        "centrum obliczeniow", "centrów obliczeniow",
        "centrum przetwarzania danych",
        # Technologie
        "hyperscale", "edge computing",
    ],

    "Energetyka": [
        # Elektrownie i ciepłownie
        "elektrowni", "elektrownia", "elektrociepłowni", "elektrociepłownia",
        "ciepłowni", "ciepłownia",
        # Linie i sieci energetyczne
        "linia energetyczn", "linii energetyczn", "linie energetyczn",
        "sieć energetyczn", "sieci energetyczn",
        "linia elektroenergetyczn", "linii elektroenergetyczn",
        "sieć elektroenergetyczn", "sieci elektroenergetyczn",
        "kabel energetyczn", "kabla energetyczn",
        # Stacje i transformatory
        "stacja transformatorow", "stacji transformatorow",
        "gpz", "główny punkt zasilania",
        "110 kv", "220 kv", "400 kv", "110kv", "220kv", "400kv",
        "przesył energii", "przesyłu energii",
        "rozdzielni", "rozdzielnia", "podstacj", "transformator",
        # Bloki energetyczne
        "blok energetyczn", "bloku energetyczn", "turbogenerator",
        "elektrownia jądrow", "elektrowni jądrow", "reaktor jądrow", "reaktora jądrow",
        "elektrownia gazow", "elektrowni gazow", "turbina gazow", "turbiny gazow",
        "kogeneracj", "trigeneracj",
    ],

    "Logistyka/Magazyny": [
        # Centra logistyczne
        "centrum logistyczn", "centrów logistyczn", "centra logistyczn",
        "hub logistyczn", "park logistyczn", "parku logistyczn",
        "centrum dystrybucj", "centrum dystrybucji",
        # Magazyny
        "magazyn", "magazynu", "magazynie", "magazynow",
        "hala magazynow", "hali magazynow", "halę magazynow",
        "obiekt magazynow", "obiektu magazynow",
        "składowisk", "plac składow", "placu składow",
        # Terminale i przeładunek
        "terminal", "terminalu", "terminale",
        "centrum przeładunkow", "przeładunk",
        "cross-dock", "cross dock",
        # Chłodnie
        "chłodni", "chłodnia", "mroźni", "mroźnia", "cold storage",
        "depot",
    ],

    "Infrastruktura": [
        # Drogi - różne odmiany
        "droga ", "drogi ", "drogę ", "drogą ", "drodze ", "dróg ",
        "drogow", "autostrad", "obwodnic", "węzeł drogow", "węzła drogow",
        "skrzyżowani", "rondo", "chodnik", "ścieżk",
        # Kolej
        "linia kolejow", "linii kolejow", "kolej", "tory kolejow", "torów kolejow",
        "przejazd kolejow",
        # Mosty i tunele
        "most", "mostu", "wiadukt", "tunel", "estakad",
        # Porty i lotniska
        "port", "portu", "terminal portow", "nabrzeż",
        "lotnisk", "pas startow", "terminal lotnicz",
        # Woda i kanalizacja
        "oczyszczalni", "stacja uzdatniani", "uzdatniania wody",
        "wodociąg", "kanalizacj", "kolektor", "sieć wodociągow", "sieci kanalizacyj",
        # Gaz
        "gazociąg", "rurociąg", "tłoczni gaz",
    ],

    "Górnictwo/Wydobycie": [
        # Kopalnie i odkrywki
        "kopaln", "odkrywk", "odkrywkow",
        # Złoża i wydobycie
        "złoż", "wydobyci", "wydobywani", "eksploatacj",
        # Materiały
        "kruszyw", "żwirowni", "żwirownia", "piaskowni", "piaskownia",
        "kamieniołom", "kamieniołomu",
        # Górnictwo
        "górnictw", "górniczej", "górniczy",
    ],
}

# Słowa kluczowe identyfikujące etap postępowania
STAGE_KEYWORDS: Dict[str, List[str]] = {
    "Wniosek": [
        "wniosek o wydanie", "wniosku o wydanie",
        "złożenie wniosku", "wpłynął wniosek",
        "wniosek o ustalenie", "wniosek o zmianę",
    ],
    "Wszczęcie postępowania": [
        "wszczęcie postępowania", "wszczęciu postępowania",
        "wszczyna postępowanie", "wszczęto postępowanie",
        "zawiadomienie o wszczęciu",
    ],
    "Zebranie materiału dowodowego": [
        "zebranie materiału dowodowego", "zebraniu materiału dowodowego",
        "zakończenie zbierania", "zakończono zbieranie",
        "zgromadzenie materiału", "materiał dowodowy",
        "możliwość zapoznania się", "możliwość wypowiedzenia",
    ],
    "Decyzja": [
        "decyzja o środowiskowych", "decyzję o środowiskowych",
        "wydanie decyzji", "wydano decyzję",
        "decyzja nr", "decyzja znak",
        "decyzja z dnia", "ostateczna decyzja",
        "decyzja odmowna", "decyzja pozytywna",
    ],
    "Zmiana decyzji": [
        "zmiana decyzji", "zmieniająca decyzję",
        "zmianę decyzji", "przeniesienie decyzji",
    ],
}

# Słowa kluczowe dla decyzji środowiskowych (do filtrowania wyników)
# Te frazy są używane do identyfikacji decyzji środowiskowych w wynikach
ENVIRONMENTAL_KEYWORDS: List[str] = [
    # Decyzje o środowiskowych uwarunkowaniach (DUŚ) - różne odmiany
    "decyzja o środowiskowych uwarunkowaniach",
    "decyzji o środowiskowych uwarunkowaniach",
    "decyzję o środowiskowych uwarunkowaniach",
    "decyzje o środowiskowych uwarunkowaniach",
    "środowiskowych uwarunkowań",
    "środowiskowe uwarunkowania",
    # Skróty DUŚ, OOŚ
    "duś", "ooś",
    "obowiązek przeprowadzenia ooś",
    # Wnioski
    "wniosek o wydanie decyzji o środowiskowych",
    "wniosku o wydanie decyzji o środowiskowych",
    "wniosek o ustalenie środowiskowych",
    # Postępowania - wszystkie formy
    "wszczęcie postępowania w sprawie wydania decyzji",
    "wszczęciu postępowania w sprawie wydania decyzji",
    "wszczęto postępowanie w sprawie wydania decyzji",
    "postępowania w sprawie wydania decyzji",
    "postępowanie administracyjne w sprawie wydania decyzji",
    "postępowania administracyjnego w sprawie",
    "podjęcie postępowania",
    "wszczęcie postępowania",
    "wszczęciu postępowania",
    "wznowienie postępowania",
    "zawieszenie postępowania",
    "umorzenie postępowania",
    # Zebranie materiału dowodowego
    "zebraniu materiału dowodowego",
    "zakończeniu zbierania materiału dowodowego",
    "możliwości zapoznania się z materiałem dowodowym",
    "możliwości wypowiedzenia się co do zebranych dowodów",
    "materiału dowodowego",
    "materiał dowodowy",
    "zapoznania się z aktami",
    "zapoznania się oraz wypowiedzenia",
    "możliwości zapoznania",
    # Ocena oddziaływania
    "ocena oddziaływania na środowisko",
    "oceny oddziaływania na środowisko",
    "oddziaływania na środowisko",
    "raport o oddziaływaniu przedsięwzięcia na środowisko",
    "raportu o oddziaływaniu na środowisko",
    "raport o oddziaływaniu",
    "raportu o oddziaływaniu",
    "karta informacyjna przedsięwzięcia",
    # Przedsięwzięcia
    "przedsięwzięcie mogące znacząco oddziaływać na środowisko",
    "przedsięwzięcia mogącego znacząco oddziaływać",
    "przedsięwzięciu mogącym znacząco oddziaływać",
    "przedsięwzięciu mogącym",
    "planowanym przedsięwzięciu",
    "planowanego przedsięwzięcia",
    "w sprawie przedsięwzięcia",
    "dla przedsięwzięcia",
    "przedsięwzięcia polegającego",
    # Uzupełnienia i wezwania
    "uzupełnienia dokumentacji",
    "uzupełnienie dokumentacji",
    "wezwanie inwestora",
    "wezwaniu inwestora",
    "uzupełnienie wniosku",
    "uzupełnienia wniosku",
    # Opinie i uzgodnienia
    "wystąpienie o opinie",
    "wystąpienie o uzgodnienia",
    # Terminy
    "przedłużenie terminu",
    "przedłużeniu terminu",
    # Decyzje - inne formy
    "wydaniu decyzji",
    "wydania decyzji",
    "wydanie decyzji",
    # Sygnatury typowe dla DUŚ
    "6220",
    "przedsięwzięcia mogące potencjalnie znacząco oddziaływać",
    "przedsięwzięcia mogące zawsze znacząco oddziaływać",
]

# Słowa kluczowe do WYKLUCZENIA - jeśli występują, wynik jest odrzucany
BLACKLIST_KEYWORDS: List[str] = [
    # Programy ochrony środowiska (nie są decyzjami o uwarunkowaniach)
    "program ochrony środowiska",
    "programu ochrony środowiska",
    "projekt programu ochrony środowiska",
    "konsultacje społeczne programu",
    "konsultacji społecznych projektu",
    # Odszkodowania
    "odszkodowanie za grunt",
    "odszkodowania za grunt",
    "ustalenie odszkodowania",
    "ustalenia odszkodowania",
    "wysokość odszkodowania",
    "wypłata odszkodowania",
    # Ogólne informacje o środowisku
    "informacja o stanie środowiska",
    "stan środowiska",
    "raport o stanie środowiska",
    "sprawozdanie z realizacji programu",
    # Plany/strategie (nie decyzje)
    "strategia rozwoju",
    "plan zagospodarowania przestrzennego",  # to inna procedura
    "studium uwarunkowań",
    # Wybory i inne
    "wybory",
    "referendum",
    "nabór wniosków",
    "konkurs",
    "przetarg",
    "zamówienie publiczne",
    # Decyzje inne niż środowiskowe
    "decyzja o warunkach zabudowy",
    "decyzji o warunkach zabudowy",
    "pozwolenie na budowę",
    "pozwolenia na budowę",
    "decyzja o lokalizacji inwestycji celu publicznego",
    "decyzja o zezwoleniu na realizację inwestycji drogowej",
    # Inne procedury środowiskowe (nie DUŚ)
    "pozwolenie wodnoprawne",
    "pozwolenia wodnoprawnego",
    "pozwolenie zintegrowane",
    "pozwolenia zintegrowanego",
    "zgłoszenie instalacji",
]


def normalize_text(text: str) -> str:
    """Normalizuje tekst do porównania (lowercase, usunięcie zbędnych znaków)."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def classify_industry(text: str) -> List[str]:
    """
    Klasyfikuje tekst według branży na podstawie słów kluczowych.
    Zwraca listę pasujących branż (może być więcej niż jedna).
    """
    if not text:
        return []

    normalized = normalize_text(text)
    matched_industries = []

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in normalized:
                if industry not in matched_industries:
                    matched_industries.append(industry)
                break

    return matched_industries if matched_industries else ["Inne"]


def detect_stage(text: str) -> str:
    """
    Wykrywa etap postępowania na podstawie tekstu.
    Zwraca nazwę etapu lub "Brak danych".
    """
    if not text:
        return "Brak danych"

    normalized = normalize_text(text)

    # Sprawdzamy w odwrotnej kolejności - od najbardziej zaawansowanych
    stage_order = [
        "Zmiana decyzji",
        "Decyzja",
        "Zebranie materiału dowodowego",
        "Wszczęcie postępowania",
        "Wniosek",
    ]

    for stage in stage_order:
        keywords = STAGE_KEYWORDS[stage]
        for keyword in keywords:
            if keyword.lower() in normalized:
                return stage

    return "Brak danych"


def extract_signature(text: str) -> Optional[str]:
    """
    Próbuje wyciągnąć sygnaturę sprawy z tekstu.
    Sygnatury mają różne formaty, np.:
    - OŚ-IV-UII.6220.13.2025.SPA
    - RDOŚ-Gd-WOO.420.60.2024.JP.23
    - WGK.6220.1.2025
    """
    if not text:
        return None

    # Wzorce sygnatur
    patterns = [
        # Standardowy format: XX-XX-XXX.1234.56.2024.XXX
        r'[A-Z]{2,}[-.]?[A-Z]{0,4}[-.]?\d{4}[-.]\d{1,4}[-.]\d{4}(?:[-.][A-Z]{2,5})?(?:[-.]\d{1,3})?',
        # Format: LITERKI.1234.1.2024.LITERKI
        r'[A-Z]{2,6}[-.]\d{4}[-.]\d{1,4}[-.]\d{4}[-.][A-Z]{2,5}',
        # Format: LITERKI-XX-XXX.1234.56.2024.XX.12
        r'[A-Z]{2,6}[-][A-Z]{2}[-][A-Z]{2,4}[.]\d{3}[.]\d{1,4}[.]\d{4}[.][A-Z]{2,4}[.]\d{1,3}',
        # Format prosty: XX.1234.1.2024
        r'[A-Z]{2,4}[.]\d{4}[.]\d{1,4}[.]\d{4}',
        # Format ze znakiem: znak: XXXX
        r'znak[:\s]+([A-Z0-9.\-/]+)',
        # Format sygnatura: XXXX
        r'sygnatur[ay]?[:\s]+([A-Z0-9.\-/]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Jeśli pattern ma grupę, zwróć grupę, inaczej całe dopasowanie
            return match.group(1) if match.lastindex else match.group(0)

    return None


def parse_date(text: str) -> Optional[datetime]:
    """
    Próbuje sparsować datę z tekstu.
    Obsługuje różne formaty dat używane w BIP-ach.
    """
    if not text:
        return None

    # Usuń zbędne znaki
    text = text.strip()

    # Najpierw spróbuj znaleźć datę w tekście
    date_patterns = [
        # DD.MM.YYYY lub DD-MM-YYYY
        r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
        # YYYY-MM-DD
        r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',
        # DD miesiąc YYYY (słownie)
        r'(\d{1,2})\s+(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\s+(\d{4})',
    ]

    months_pl = {
        'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4,
        'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8,
        'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12
    }

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 3:
                    if groups[1].lower() in months_pl:
                        # Format: DD miesiąc YYYY
                        day = int(groups[0])
                        month = months_pl[groups[1].lower()]
                        year = int(groups[2])
                    elif len(groups[0]) == 4:
                        # Format: YYYY-MM-DD
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                    else:
                        # Format: DD.MM.YYYY
                        day = int(groups[0])
                        month = int(groups[1])
                        year = int(groups[2])

                    return datetime(year, month, day)
            except (ValueError, TypeError):
                continue

    # Fallback: spróbuj użyć dateutil
    try:
        return date_parser.parse(text, dayfirst=True)
    except (ValueError, TypeError):
        return None


def is_blacklisted(text: str) -> bool:
    """
    Sprawdza czy tekst zawiera słowa z blacklisty (do wykluczenia).
    """
    if not text:
        return False

    normalized = normalize_text(text)

    for keyword in BLACKLIST_KEYWORDS:
        if keyword.lower() in normalized:
            return True

    return False


def is_environmental_decision(text: str) -> bool:
    """
    Sprawdza czy tekst dotyczy decyzji środowiskowej (DUŚ).
    Musi zawierać słowo kluczowe I NIE może być na blackliście.
    """
    if not text:
        return False

    normalized = normalize_text(text)

    # Najpierw sprawdź blacklistę - jeśli pasuje, od razu odrzuć
    if is_blacklisted(text):
        return False

    # Sprawdź czy zawiera słowa kluczowe dla decyzji środowiskowych
    for keyword in ENVIRONMENTAL_KEYWORDS:
        if keyword.lower() in normalized:
            return True

    return False


def filter_by_date_range(date: Optional[datetime], date_from: datetime, date_to: datetime, strict: bool = True) -> bool:
    """
    Sprawdza czy data mieści się w podanym zakresie.

    Args:
        date: Data do sprawdzenia
        date_from: Data początkowa zakresu
        date_to: Data końcowa zakresu
        strict: Jeśli True, wyniki bez daty są odrzucane. Jeśli False, przepuszczane.
    """
    if not date:
        return not strict  # W trybie strict odrzucamy wyniki bez daty

    return date_from <= date <= date_to


def extract_location(text: str, source_name: str, source_voivodeship: str) -> str:
    """
    Wyciąga lub konstruuje lokalizację.
    """
    # Jeśli mamy informacje ze źródła, użyj ich
    if source_name and source_voivodeship:
        return f"{source_name}, woj. {source_voivodeship}"

    return source_name or "Brak danych"


class ResultFilter:
    """
    Klasa do filtrowania i przetwarzania wyników wyszukiwania.
    """

    def __init__(self, date_from: datetime, date_to: datetime, industries: List[str] = None, strict_dates: bool = True):
        self.date_from = date_from
        self.date_to = date_to
        self.industries = industries or list(INDUSTRY_KEYWORDS.keys())
        self.strict_dates = strict_dates  # Jeśli True, odrzuca wyniki bez daty

    def process_result(self, raw_result: Dict) -> Optional[Dict]:
        """
        Przetwarza surowy wynik i zwraca sformatowany słownik lub None jeśli nie pasuje.
        """
        title = raw_result.get('title', '')
        content = raw_result.get('content', '')
        full_text = f"{title} {content}"

        # Sprawdź czy to decyzja środowiskowa (zawiera wymagane słowa I nie jest na blackliście)
        if not is_environmental_decision(full_text):
            return None

        # Parsuj datę
        date_str = raw_result.get('date', '')
        parsed_date = parse_date(date_str) if date_str else None

        # Jeśli nie ma daty w polu date, spróbuj wyciągnąć z tytułu/treści
        if not parsed_date:
            parsed_date = parse_date(full_text)

        # Sprawdź zakres dat (z opcją strict)
        if not filter_by_date_range(parsed_date, self.date_from, self.date_to, strict=self.strict_dates):
            return None

        # Klasyfikuj branżę
        industries = classify_industry(full_text)

        # Sprawdź czy pasuje do wybranych branż
        # "Inne" jest traktowane jak normalna branża - musi być zaznaczone aby przepuścić
        if not any(ind in self.industries for ind in industries):
            return None

        # Wykryj etap postępowania
        stage = detect_stage(full_text)

        # Wyciągnij sygnaturę
        signature = extract_signature(full_text)

        return {
            'lokalizacja': extract_location(
                full_text,
                raw_result.get('source_name', ''),
                raw_result.get('source_voivodeship', '')
            ),
            'data_obwieszczenia': parsed_date.strftime('%Y-%m-%d') if parsed_date else 'Brak danych',
            'etap_postepowania': stage,
            'branza': ', '.join(industries),
            'przedsiewziecie': title[:200] if title else 'Brak danych',
            'sygnatura': signature or 'Brak danych',
            'zrodlo_url': raw_result.get('url', ''),
            'zrodlo_nazwa': raw_result.get('source_name', ''),
        }

    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """
        Filtruje listę wyników i zwraca przetworzone.
        """
        processed = []
        for result in results:
            processed_result = self.process_result(result)
            if processed_result:
                processed.append(processed_result)

        # Sortuj po dacie (od najnowszych)
        processed.sort(
            key=lambda x: x['data_obwieszczenia'] if x['data_obwieszczenia'] != 'Brak danych' else '0000-00-00',
            reverse=True
        )

        return processed


# Testy modułu
if __name__ == "__main__":
    # Test klasyfikacji branży
    test_texts = [
        "Budowa farmy fotowoltaicznej o mocy 50 MW",
        "Budowa zakładu produkcyjnego mebli",
        "Budowa centrum danych data center",
        "Budowa linii 110 kV Gdańsk-Rumia",
        "Budowa centrum logistycznego",
        "Budowa drogi krajowej nr 7",
    ]

    print("=== Test klasyfikacji branży ===")
    for text in test_texts:
        industries = classify_industry(text)
        print(f"'{text[:50]}...' -> {industries}")

    print("\n=== Test wykrywania etapu ===")
    stage_texts = [
        "Obwieszczenie o wszczęciu postępowania w sprawie wydania decyzji",
        "Obwieszczenie o zebraniu materiału dowodowego",
        "Obwieszczenie o wydaniu decyzji o środowiskowych uwarunkowaniach",
        "Wniosek o wydanie decyzji środowiskowej",
    ]

    for text in stage_texts:
        stage = detect_stage(text)
        print(f"'{text[:50]}...' -> {stage}")

    print("\n=== Test parsowania dat ===")
    date_texts = [
        "15.01.2026",
        "2026-01-15",
        "15 stycznia 2026",
        "Data publikacji: 09-01-2026",
    ]

    for text in date_texts:
        parsed = parse_date(text)
        print(f"'{text}' -> {parsed}")

    print("\n=== Test ekstrakcji sygnatury ===")
    sig_texts = [
        "Sygnatura: OŚ-IV-UII.6220.13.2025.SPA",
        "znak: RDOŚ-Gd-WOO.420.60.2024.JP.23",
        "Decyzja WGK.6220.1.2025 z dnia",
    ]

    for text in sig_texts:
        sig = extract_signature(text)
        print(f"'{text[:50]}...' -> {sig}")
