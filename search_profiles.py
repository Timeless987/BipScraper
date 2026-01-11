"""
Profile wyszukiwania - predefiniowane zestawy źródeł dla różnych trybów wyszukiwania.
"""

from typing import List, Dict

# Top 10 największych miast biznesowych w Polsce
TOP_10_CITIES = [
    "warszawa", "krakow", "wroclaw", "poznan", "gdansk",
    "lodz", "katowice", "szczecin", "lublin", "bydgoszcz"
]

# Specjalne Strefy Ekonomiczne - gminy z SSE
# Lista gmin, w których znajdują się SSE lub ich podstrefy
SSE_MUNICIPALITIES = [
    # Katowicka SSE
    "gliwice", "zabrze", "tychy", "sosnowiec", "dabrowa-gornicza",
    "jastrzebie-zdroj", "rybnik", "zory", "bielsko-biala", "czechowice-dziedzice",
    "pszczyna", "mikolow", "knurow", "czerwionka-leszczyny", "pyskowice",

    # Wałbrzyska SSE
    "walbrzych", "swidnica", "dzierzoniow", "klodzko", "nowa-ruda",
    "jelenia-gora", "boleslawiec", "luban", "zgorzelec", "legnica",

    # Łódzka SSE
    "lodz", "ozorkow", "zgierz", "pabianice", "kutno",
    "lowicz", "rawa-mazowiecka", "tomaszow-mazowiecki", "piotrkow-trybunalski",

    # Pomorska SSE
    "gdansk", "gdynia", "tczew", "starogard-gdanski", "kwidzyn",
    "malbork", "sztum", "elblag", "koscierzyna",

    # Warmińsko-Mazurska SSE
    "olsztyn", "elk", "ilawa", "ostroda", "szczytno",
    "mragowo", "bartoszyce", "lidzbark-warminski",

    # Krakowska SSE
    "krakow", "niepolomice", "skawina", "wieliczka", "bochnia",
    "tarnow", "debica", "mielec", "rzeszow", "stalowa-wola",

    # Kostrzyńsko-Słubicka SSE
    "kostrzyn-nad-odra", "slubice", "gorzow-wielkopolski", "rzepin",
    "sulecin", "miedzyrzecz", "strzelce-krajenskie",

    # Suwalska SSE
    "suwalki", "elblag", "elk",

    # Starachowicka SSE
    "starachowice", "skarzysko-kamienna", "ostrowiec-swietokrzyski",
    "konskie", "kielce",

    # Słupska SSE
    "slupsk", "lebork", "bytow", "czluchow", "ustka",

    # Tarnobrzeska SSE
    "tarnobrzeg", "stalowa-wola", "nisko", "sandomierz",

    # Mielecka SSE
    "mielec", "debica", "rzeszow", "lancut",

    # Kamiennogórska SSE
    "kamienna-gora", "lubawka", "boguszow-gorce",

    # Poznańska/Wielkopolska
    "poznan", "kalisz", "konin", "leszno", "pila",
    "gniezno", "sroda-wielkopolska", "swarzedz", "lubon",

    # Dolnośląska
    "wroclaw", "olesnica", "oława", "trzebnica", "sroda-slaska",
    "kobierzyce", "siechnice",
]

# Wszystkie miasta na prawach powiatu (66) + miasta z BIP bez prefiksu
CITIES_WITH_COUNTY_RIGHTS = [
    "warszawa", "krakow", "lodz", "wroclaw", "poznan", "gdansk", "szczecin",
    "bydgoszcz", "lublin", "bialystok", "katowice", "gdynia", "czestochowa",
    "radom", "torun", "sosnowiec", "rzeszow", "kielce", "gliwice", "zabrze",
    "olsztyn", "bielsko-biala", "bytom", "zielona-gora", "rybnik", "ruda-slaska",
    "opole", "tychy", "gorzow-wielkopolski", "elblag", "plock", "dabrowa-gornicza",
    "walbrzych", "wloclawek", "tarnow", "chorzow", "koszalin", "kalisz",
    "legnica", "grudziadz", "jaworzno", "slupsk", "jastrzebie-zdroj",
    "nowy-sacz", "jelenia-gora", "siedlce", "myslowice", "konin", "piotrkow-trybunalski",
    "inowroclaw", "lubin", "ostrow-wielkopolski", "suwalki", "gniezno",
    "glogow", "stargard", "przemysl", "siemianowice-slaskie", "ostroleka",
    "zamosc", "piekary-slaskie", "leszno", "lomza", "tarnowskie-gory",
    "swietochlowice", "skierniewice", "sopot",
    # Dodatkowe miasta które są w BIP bez prefiksu
    "pabianice", "zory", "pruszkow", "tarnobrzeg", "stalowa-wola",
]

# Lista województw
VOIVODESHIPS = [
    "dolnoslaskie", "kujawsko-pomorskie", "lubelskie", "lubuskie",
    "lodzkie", "malopolskie", "mazowieckie", "opolskie",
    "podkarpackie", "podlaskie", "pomorskie", "slaskie",
    "swietokrzyskie", "warminsko-mazurskie", "wielkopolskie", "zachodniopomorskie"
]

# Profile wyszukiwania
SEARCH_PROFILES = {
    "top10": {
        "name": "Top 10 miast (Quick Check)",
        "description": "Szybki przegląd największych miast biznesowych w Polsce",
        "estimated_time": "~5 minut",
        "source_types": ["miasta_na_prawach_powiatu"],
        "filter_ids": TOP_10_CITIES,
        "include_rdos": False,
        "include_gdos": False,
    },
    "cities": {
        "name": "Miasta na prawach powiatu",
        "description": "Wszystkie 66 miast na prawach powiatu + RDOŚ/GDOŚ",
        "estimated_time": "~15 minut",
        "source_types": ["miasta_na_prawach_powiatu"],
        "filter_ids": None,
        "include_rdos": True,
        "include_gdos": True,
    },
    "all_municipalities": {
        "name": "Wszystkie gminy",
        "description": "Wszystkie gminy miejskie, wiejskie i miejsko-wiejskie (~2500)",
        "estimated_time": "~3-4 godziny",
        "source_types": ["miasta_na_prawach_powiatu", "gminy_miejskie", "gminy_miejsko_wiejskie", "gminy_wiejskie"],
        "filter_ids": None,
        "include_rdos": True,
        "include_gdos": True,
    },
    "urban_municipalities": {
        "name": "Gminy miejskie i miejsko-wiejskie",
        "description": "Gminy miejskie + miejsko-wiejskie (~1200)",
        "estimated_time": "~1.5-2 godziny",
        "source_types": ["miasta_na_prawach_powiatu", "gminy_miejskie", "gminy_miejsko_wiejskie"],
        "filter_ids": None,
        "include_rdos": True,
        "include_gdos": True,
    },
    "sse": {
        "name": "Strefy przemysłowe (SSE)",
        "description": "Gminy ze Specjalnymi Strefami Ekonomicznymi",
        "estimated_time": "~30 minut",
        "source_types": ["miasta_na_prawach_powiatu", "gminy_miejskie", "gminy_miejsko_wiejskie"],
        "filter_ids": SSE_MUNICIPALITIES,
        "include_rdos": True,
        "include_gdos": True,
    },
    "full": {
        "name": "Pełne skanowanie",
        "description": "Wszystkie źródła BIP w Polsce (~2900)",
        "estimated_time": "~5-6 godzin",
        "source_types": None,
        "filter_ids": None,
        "include_rdos": True,
        "include_gdos": True,
    }
}


def normalize_id(text: str) -> str:
    """Normalizuje ID do porównania."""
    import re
    text = text.lower()
    text = re.sub(r'[ąàáâã]', 'a', text)
    text = re.sub(r'[ćç]', 'c', text)
    text = re.sub(r'[ęèéêë]', 'e', text)
    text = re.sub(r'[łľ]', 'l', text)
    text = re.sub(r'[ńñ]', 'n', text)
    text = re.sub(r'[óòôõ]', 'o', text)
    text = re.sub(r'[śš]', 's', text)
    text = re.sub(r'[źżž]', 'z', text)
    text = re.sub(r'[ůúùû]', 'u', text)
    text = re.sub(r'[^a-z0-9]', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text


def infer_source_type(source: Dict, category_hint: str = None) -> str:
    """
    Określa typ źródła na podstawie dostępnych danych.
    """
    # Jeśli jest pole type, użyj go
    if source.get('type'):
        return source['type']

    source_id = source.get('id', '').lower()

    # Rozpoznaj po ID
    if source_id == 'gdos':
        return 'gdos'
    if source_id.startswith('rdos-'):
        return 'rdos'
    if source_id.startswith('woj-'):
        return 'voivodeship'
    if source_id.startswith('pow-'):
        return 'powiat'
    if source_id.startswith('gm-'):
        return 'gmina_miejska'
    if source_id.startswith('gmw-'):
        return 'gmina_miejsko_wiejska'
    if source_id.startswith('gw-'):
        return 'gmina_wiejska'

    # Dla miast na prawach powiatu - nie mają prefiksu
    # Sprawdź czy ID pasuje do listy miast
    normalized_id = normalize_id(source_id)
    if normalized_id in [normalize_id(c) for c in CITIES_WITH_COUNTY_RIGHTS]:
        return 'miasto_na_prawach_powiatu'

    return 'unknown'


def filter_sources_by_profile(sources: List[Dict], profile_id: str) -> List[Dict]:
    """
    Filtruje źródła według wybranego profilu.

    Args:
        sources: Lista wszystkich źródeł
        profile_id: ID profilu z SEARCH_PROFILES

    Returns:
        Przefiltrowana lista źródeł
    """
    if profile_id not in SEARCH_PROFILES:
        return sources  # Nieznany profil - zwróć wszystko

    profile = SEARCH_PROFILES[profile_id]
    filtered = []

    # Mapowanie typów z profilu na typy w danych
    type_mapping = {
        'miasta_na_prawach_powiatu': ['miasto_na_prawach_powiatu'],
        'gminy_miejskie': ['gmina_miejska'],
        'gminy_miejsko_wiejskie': ['gmina_miejsko_wiejska'],
        'gminy_wiejskie': ['gmina_wiejska'],
        'powiaty': ['powiat'],
        'voivodeships': ['voivodeship'],
    }

    for source in sources:
        source_type = infer_source_type(source)
        source_id = source.get('id', '')
        source_name = normalize_id(source.get('name', ''))

        # Zawsze dodaj GDOŚ i RDOŚ jeśli profile to przewiduje
        if source_type == 'gdos' and profile.get('include_gdos', True):
            filtered.append(source)
            continue

        if source_type == 'rdos' and profile.get('include_rdos', True):
            filtered.append(source)
            continue

        # Sprawdź czy typ źródła pasuje
        if profile.get('source_types') is not None:
            # Rozwiń typy z profilu do rzeczywistych typów
            allowed_types = []
            for profile_type in profile['source_types']:
                if profile_type in type_mapping:
                    allowed_types.extend(type_mapping[profile_type])
                else:
                    allowed_types.append(profile_type)

            if source_type not in allowed_types:
                continue

        # Sprawdź czy ID/nazwa pasuje do filtra
        if profile.get('filter_ids') is not None:
            # Sprawdź dopasowanie po ID lub nazwie
            matched = False
            normalized_source_id = normalize_id(source_id)

            for filter_id in profile['filter_ids']:
                normalized_filter = normalize_id(filter_id)
                if (normalized_filter == normalized_source_id or
                    normalized_filter == source_name or
                    normalized_source_id == normalized_filter or
                    source_name == normalized_filter):
                    matched = True
                    break

            if not matched:
                continue

        filtered.append(source)

    return filtered


def get_profile_info(profile_id: str) -> Dict:
    """Zwraca informacje o profilu."""
    if profile_id in SEARCH_PROFILES:
        return SEARCH_PROFILES[profile_id]
    return SEARCH_PROFILES['full']


def get_available_profiles() -> List[Dict]:
    """Zwraca listę dostępnych profili."""
    return [
        {
            'id': pid,
            'name': profile['name'],
            'description': profile['description'],
            'estimated_time': profile['estimated_time']
        }
        for pid, profile in SEARCH_PROFILES.items()
    ]


def filter_sources_by_voivodeship(sources: List[Dict], voivodeships: List[str]) -> List[Dict]:
    """
    Filtruje źródła po województwach.

    Args:
        sources: Lista źródeł
        voivodeships: Lista nazw województw (np. ['mazowieckie', 'wielkopolskie'])

    Returns:
        Lista źródeł z wybranych województw
    """
    if not voivodeships:
        return sources

    # Normalizuj nazwy województw
    normalized_voivs = [normalize_id(v) for v in voivodeships]

    filtered = []
    for source in sources:
        source_voiv = source.get('voivodeship', '')
        if source_voiv:
            normalized_source_voiv = normalize_id(source_voiv)
            if normalized_source_voiv in normalized_voivs:
                filtered.append(source)

    return filtered


def get_sources_by_voivodeship(sources: List[Dict]) -> Dict[str, int]:
    """
    Grupuje źródła według województw.

    Returns:
        Słownik {województwo: liczba_źródeł}
    """
    voiv_counts = {}
    for source in sources:
        voiv = source.get('voivodeship', 'nieznane')
        voiv_counts[voiv] = voiv_counts.get(voiv, 0) + 1
    return dict(sorted(voiv_counts.items()))
