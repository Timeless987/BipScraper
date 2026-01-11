"""
Silnik scrapowania dla wyszukiwarki decyzji środowiskowych BIP.
Obsługuje różne struktury stron BIP, RDOŚ i GDOŚ.
"""

import asyncio
import aiohttp
import json
import re
import os
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, AsyncGenerator, Callable
from urllib.parse import urljoin, urlparse, quote
from bs4 import BeautifulSoup
import logging

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# User-Agent rotation dla uniknięcia blokowania
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# Słowa kluczowe do wyszukiwania
SEARCH_KEYWORDS = [
    "decyzja środowiskowa",
    "decyzja o środowiskowych uwarunkowaniach",
    "wszczęcie postępowania środowiskowego",
    "obwieszczenie środowiskowe",
    "ocena oddziaływania na środowisko",
]

# Typowe ścieżki do decyzji środowiskowych
COMMON_ENV_PATHS = [
    "/obwieszczenia",
    "/decyzje-srodowiskowe",
    "/ochrona-srodowiska",
    "/ogloszenia",
    "/tablica-ogloszen",
    "/srodowisko",
    "/ochrona-srodowiska/decyzje",
]

# Słowa kluczowe do identyfikacji sekcji środowiskowych w menu/linkach
SECTION_KEYWORDS = [
    'środowisk', 'ochrona środowiska', 'ochrony środowiska',
    'obwieszczen', 'obwieszczenia', 'ogłoszen', 'ogłoszenia',
    'decyzje', 'decyzji', 'postępowania',
    'klimat', 'ekologia', 'ekologii',
    'tablica ogłoszeń', 'tablicy ogłoszeń',
    'wydział', 'referat',
]

# Słowa kluczowe które wskazują na listę ogłoszeń (nie pojedyncze ogłoszenie)
LIST_INDICATORS = [
    'lista', 'wykaz', 'archiwum', 'rejestr',
    'wszystkie', 'aktualności', 'news',
]


class RateLimiter:
    """Kontroler prędkości requestów."""

    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Dict[str, float] = {}

    async def wait(self, domain: str):
        """Czeka odpowiedni czas przed kolejnym requestem do tej samej domeny."""
        current_time = time.time()
        if domain in self.last_request_time:
            elapsed = current_time - self.last_request_time[domain]
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)

        self.last_request_time[domain] = time.time()


class ScraperResult:
    """Wynik scrapowania pojedynczej strony."""

    def __init__(self, source_id: str, source_name: str, source_voivodeship: str):
        self.source_id = source_id
        self.source_name = source_name
        self.source_voivodeship = source_voivodeship
        self.results: List[Dict] = []
        self.error: Optional[str] = None
        self.success = False


class BIPScraper:
    """
    Główna klasa scrapera dla stron BIP.
    """

    def __init__(self, max_concurrent: int = 10, requests_per_second: float = 1.0):
        self.max_concurrent = max_concurrent
        self.rate_limiter = RateLimiter(requests_per_second)
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def get_random_headers(self) -> Dict[str, str]:
        """Zwraca losowe nagłówki HTTP."""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    async def fetch_page(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Pobiera stronę HTML z podanego URL.
        """
        domain = urlparse(url).netloc

        async with self.semaphore:
            await self.rate_limiter.wait(domain)

            try:
                async with self.session.get(
                    url,
                    headers=self.get_random_headers(),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False,  # Niektóre BIP-y mają problemy z certyfikatami
                ) as response:
                    if response.status == 200:
                        # Próbuj różne kodowania
                        try:
                            return await response.text(encoding='utf-8')
                        except UnicodeDecodeError:
                            try:
                                return await response.text(encoding='iso-8859-2')
                            except UnicodeDecodeError:
                                return await response.text(encoding='windows-1250', errors='ignore')
                    else:
                        logger.warning(f"HTTP {response.status} dla {url}")
                        return None

            except asyncio.TimeoutError:
                logger.warning(f"Timeout dla {url}")
                return None
            except aiohttp.ClientError as e:
                logger.warning(f"Błąd połączenia dla {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Nieoczekiwany błąd dla {url}: {e}")
                return None

    def parse_gov_pl(self, html: str, base_url: str) -> List[Dict]:
        """
        Parser dla stron gov.pl (RDOŚ, GDOŚ).
        """
        results = []
        soup = BeautifulSoup(html, 'lxml')

        # Szukaj artykułów/wpisów
        selectors = [
            'article',
            '.article-area article',
            '.news-list li',
            '.list-group-item',
            '.editor-content a',
            'table tr',
        ]

        for selector in selectors:
            items = soup.select(selector)
            for item in items:
                try:
                    # Szukaj tytułu
                    title_elem = item.select_one('h2, h3, h4, a, .title, td:first-child')
                    title = title_elem.get_text(strip=True) if title_elem else ''

                    # Szukaj linku
                    link_elem = item.select_one('a[href]')
                    link = ''
                    if link_elem and link_elem.get('href'):
                        link = urljoin(base_url, link_elem['href'])

                    # Szukaj daty
                    date_elem = item.select_one('.date, time, .news-date, td.date, span.date')
                    date = date_elem.get_text(strip=True) if date_elem else ''

                    # Szukaj dodatkowej treści
                    content = item.get_text(strip=True)

                    if title and len(title) > 10:
                        results.append({
                            'title': title,
                            'url': link or base_url,
                            'date': date,
                            'content': content[:500],
                        })

                except Exception as e:
                    logger.debug(f"Błąd parsowania elementu: {e}")
                    continue

        return results

    def parse_bip_generic(self, html: str, base_url: str) -> List[Dict]:
        """
        Uniwersalny parser dla stron BIP.
        """
        results = []
        soup = BeautifulSoup(html, 'lxml')

        # Usuń skrypty i style
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # Szukaj różnych struktur
        selectors = [
            '.news-list li',
            '.article-list .item',
            '.bip-list .element',
            'table.list tr',
            '.ogloszenia-lista li',
            '.document-list li',
            '.announcement-list .item',
            'ul.list li',
            '.content-main article',
            '.entry',
            'div[class*="news"] div[class*="item"]',
            'div[class*="ogloszeni"]',
        ]

        found_items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                found_items.extend(items)
                break  # Użyj pierwszego działającego selektora

        # Jeśli nie znaleziono przez selektory, szukaj po linkach
        if not found_items:
            found_items = soup.find_all('a', href=True)

        for item in found_items:
            try:
                # Dla linków bezpośrednio
                if item.name == 'a':
                    title = item.get_text(strip=True)
                    link = urljoin(base_url, item['href'])
                    parent = item.parent
                    date = ''
                    if parent:
                        date_match = re.search(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}', parent.get_text())
                        if date_match:
                            date = date_match.group(0)
                else:
                    # Dla innych elementów
                    title_elem = item.select_one('a, h2, h3, h4, .title')
                    title = title_elem.get_text(strip=True) if title_elem else item.get_text(strip=True)[:200]

                    link_elem = item.select_one('a[href]')
                    link = urljoin(base_url, link_elem['href']) if link_elem else base_url

                    date_elem = item.select_one('.date, time, .data')
                    date = date_elem.get_text(strip=True) if date_elem else ''

                    if not date:
                        date_match = re.search(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}', item.get_text())
                        if date_match:
                            date = date_match.group(0)

                # Filtruj wyniki - szukaj PRECYZYJNYCH słów kluczowych dla decyzji środowiskowych
                title_lower = title.lower()

                # Słowa kluczowe które MUSZĄ wystąpić (przynajmniej jedno)
                required_keywords = [
                    # Decyzje środowiskowe - różne odmiany
                    'środowiskowych uwarunkowań',
                    'środowiskowe uwarunkowania',
                    'decyzji o środowiskowych',
                    'decyzja o środowiskowych',
                    'decyzje o środowiskowych',
                    'wydania decyzji o środowiskowych',
                    'wydanie decyzji o środowiskowych',
                    # Skróty DUŚ, OOŚ
                    'duś', 'ooś',
                    'obowiązek przeprowadzenia ooś',
                    # Postępowania
                    'postępowania w sprawie wydania decyzji',
                    'postępowanie w sprawie wydania decyzji',
                    'postępowania administracyjnego w sprawie',
                    'podjęcie postępowania',
                    'wszczęcie postępowania',
                    'wszczęciu postępowania',
                    'wznowienie postępowania',
                    'zawieszenie postępowania',
                    'umorzenie postępowania',
                    # Ocena oddziaływania
                    'ocena oddziaływania na środowisko',
                    'oceny oddziaływania na środowisko',
                    'oddziaływania na środowisko',
                    # Przedsięwzięcia
                    'przedsięwzięcie mogące znacząco',
                    'przedsięwzięcia mogącego znacząco',
                    'przedsięwzięciu mogącym',
                    'planowanym przedsięwzięciu',
                    'planowanego przedsięwzięcia',
                    # Dokumenty
                    'karta informacyjna przedsięwzięcia',
                    'raport o oddziaływaniu',
                    'raportu o oddziaływaniu',
                    # Materiał dowodowy
                    'materiału dowodowego',
                    'materiał dowodowy',
                    'zapoznania się z aktami',
                    'zapoznania się oraz wypowiedzenia',
                    'możliwości zapoznania',
                    # Uzupełnienia i wezwania
                    'uzupełnienia dokumentacji',
                    'uzupełnienie dokumentacji',
                    'wezwanie inwestora',
                    'wezwaniu inwestora',
                    'uzupełnienie wniosku',
                    'uzupełnienia wniosku',
                    # Opinie i uzgodnienia
                    'wystąpienie o opinie',
                    'wystąpienie o uzgodnienia',
                    'opinie rdoś',
                    'uzgodnienia rdoś',
                    # Terminy
                    'przedłużenie terminu',
                    'przedłużeniu terminu',
                    # Sygnatury typowe dla DUŚ
                    '6220',  # sygnatura decyzji środowiskowych
                    # Decyzje - inne formy
                    'wydaniu decyzji',
                    'wydania decyzji',
                    'wydanie decyzji',
                    # Przedsięwzięcia (bez "mogące znacząco")
                    'w sprawie przedsięwzięcia',
                    'dla przedsięwzięcia',
                    'przedsięwzięcia polegającego',
                    # Obwieszczenia bez pełnej frazy
                    'decyzje_dot_wydania',
                    'decyzji_dot_wydania',
                    'decyzje dot wydania',
                    'decyzji dot wydania',
                ]

                # Słowa kluczowe do WYKLUCZENIA
                blacklist_keywords = [
                    'program ochrony środowiska',
                    'programu ochrony środowiska',
                    'odszkodowanie',
                    'odszkodowania',
                    'konsultacje społeczne programu',
                    'plan zagospodarowania',
                    'studium uwarunkowań',
                    'warunkach zabudowy',
                    'pozwolenie na budowę',
                    'wybory',
                    'przetarg',
                    'konkurs',
                    'nabór wniosków',
                ]

                # Sprawdź blacklistę
                is_blacklisted = any(bl in title_lower for bl in blacklist_keywords)

                # Sprawdź wymagane słowa kluczowe
                is_environmental = any(kw in title_lower for kw in required_keywords)

                if title and len(title) > 15 and is_environmental and not is_blacklisted:
                    results.append({
                        'title': title[:300],
                        'url': link,
                        'date': date,
                        'content': item.get_text(strip=True)[:500] if hasattr(item, 'get_text') else '',
                    })

            except Exception as e:
                logger.debug(f"Błąd parsowania elementu: {e}")
                continue

        return results

    def find_env_sections(self, html: str, base_url: str) -> List[str]:
        """
        Znajduje linki do sekcji środowiskowych na stronie.
        Zwraca listę URL-i do przeszukania.
        """
        soup = BeautifulSoup(html, 'lxml')
        found_urls = set()
        base_domain = urlparse(base_url).netloc

        # Szukaj linków w menu i na stronie
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()

            # Sprawdź czy tekst linku zawiera słowa kluczowe sekcji
            is_env_section = any(kw in text for kw in SECTION_KEYWORDS)

            # Sprawdź też href
            href_lower = href.lower()
            is_env_path = any(kw in href_lower for kw in [
                'srodowisk', 'obwieszcz', 'decyzj', 'oglosz',
                'klimat', 'ekolog', 'environment', 'tablica'
            ])

            if is_env_section or is_env_path:
                full_url = urljoin(base_url, href)
                # Upewnij się że to ta sama domena
                if urlparse(full_url).netloc == base_domain:
                    found_urls.add(full_url)

        return list(found_urls)[:20]  # Limit 20 podstron

    def find_announcement_lists(self, html: str, base_url: str) -> List[str]:
        """
        Znajduje linki do list ogłoszeń na podstronie.
        """
        soup = BeautifulSoup(html, 'lxml')
        found_urls = set()
        base_domain = urlparse(base_url).netloc

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()

            # Szukaj linków do list/archiwów ogłoszeń
            is_list = any(kw in text for kw in LIST_INDICATORS)
            is_obwieszczenia = 'obwieszcz' in text or 'ogłosz' in text or 'decyzj' in text

            if is_list or is_obwieszczenia:
                full_url = urljoin(base_url, href)
                if urlparse(full_url).netloc == base_domain:
                    found_urls.add(full_url)

        return list(found_urls)[:10]  # Limit 10 list

    async def deep_search_bip(self, source: Dict, date_from: datetime, date_to: datetime) -> ScraperResult:
        """
        Głębokie przeszukiwanie BIP - sprawdza podstrony.
        """
        result = ScraperResult(
            source_id=source.get('id', ''),
            source_name=source.get('name', ''),
            source_voivodeship=source.get('voivodeship', '')
        )

        base_url = source.get('bip_url', source.get('url', ''))
        if not base_url:
            result.error = "Brak URL"
            return result

        all_items = []
        visited_urls = set()

        # Krok 1: Pobierz stronę główną
        html = await self.fetch_page(base_url)
        if not html:
            result.error = "Nie udało się pobrać strony głównej"
            return result

        visited_urls.add(base_url)

        # Krok 2: Parsuj stronę główną
        try:
            if 'gov.pl' in base_url:
                items = self.parse_gov_pl(html, base_url)
            else:
                items = self.parse_bip_generic(html, base_url)
            all_items.extend(items)
        except Exception as e:
            logger.debug(f"Błąd parsowania głównej {base_url}: {e}")

        # Krok 3: Znajdź sekcje środowiskowe na stronie głównej
        env_sections = self.find_env_sections(html, base_url)

        # Dodaj standardowe ścieżki
        for path in COMMON_ENV_PATHS:
            env_sections.append(urljoin(base_url, path))

        # Krok 4: Przeszukaj każdą sekcję środowiskową
        for section_url in env_sections:
            if section_url in visited_urls:
                continue
            visited_urls.add(section_url)

            section_html = await self.fetch_page(section_url)
            if not section_html:
                continue

            # Parsuj sekcję
            try:
                if 'gov.pl' in base_url:
                    items = self.parse_gov_pl(section_html, section_url)
                else:
                    items = self.parse_bip_generic(section_html, section_url)
                all_items.extend(items)
            except Exception as e:
                logger.debug(f"Błąd parsowania sekcji {section_url}: {e}")

            # Krok 5: Znajdź listy ogłoszeń w sekcji
            announcement_lists = self.find_announcement_lists(section_html, section_url)

            for list_url in announcement_lists:
                if list_url in visited_urls:
                    continue
                visited_urls.add(list_url)

                list_html = await self.fetch_page(list_url)
                if not list_html:
                    continue

                try:
                    if 'gov.pl' in base_url:
                        items = self.parse_gov_pl(list_html, list_url)
                    else:
                        items = self.parse_bip_generic(list_html, list_url)
                    all_items.extend(items)
                except Exception as e:
                    logger.debug(f"Błąd parsowania listy {list_url}: {e}")

        # Usuń duplikaty (po URL)
        seen_urls = set()
        unique_items = []
        for item in all_items:
            item_url = item.get('url', '')
            if item_url not in seen_urls:
                seen_urls.add(item_url)
                unique_items.append(item)

        # Dodaj informacje o źródle
        for item in unique_items:
            item['source_id'] = result.source_id
            item['source_name'] = result.source_name
            item['source_voivodeship'] = result.source_voivodeship

        result.results = unique_items
        result.success = True

        logger.debug(f"{source.get('name')}: przeszukano {len(visited_urls)} stron, znaleziono {len(unique_items)} wyników")

        return result

    async def search_bip(self, source: Dict, date_from: datetime, date_to: datetime) -> ScraperResult:
        """
        Przeszukuje pojedynczy BIP pod kątem decyzji środowiskowych.
        Używa głębokiego przeszukiwania.
        """
        # Użyj głębokiego przeszukiwania
        return await self.deep_search_bip(source, date_from, date_to)

    async def scrape_all(
        self,
        sources: List[Dict],
        date_from: datetime,
        date_to: datetime,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[ScraperResult]:
        """
        Przeszukuje wszystkie źródła równolegle.
        """
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=2,
            ssl=False,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            self.session = session

            results = []
            total = len(sources)

            for i, source in enumerate(sources):
                try:
                    result = await self.search_bip(source, date_from, date_to)
                    results.append(result)

                    if progress_callback:
                        progress_callback(i + 1, total, source.get('name', 'Nieznane'))

                except Exception as e:
                    logger.error(f"Błąd dla {source.get('name', 'Nieznane')}: {e}")
                    result = ScraperResult(
                        source_id=source.get('id', ''),
                        source_name=source.get('name', ''),
                        source_voivodeship=source.get('voivodeship', '')
                    )
                    result.error = str(e)
                    results.append(result)

            return results


class SourcesLoader:
    """Ładuje źródła z pliku JSON."""

    def __init__(self, sources_file: str = 'sources_full.json'):
        self.sources_file = sources_file
        self.sources: List[Dict] = []

    def load(self) -> List[Dict]:
        """Ładuje wszystkie źródła z pliku."""
        if not os.path.exists(self.sources_file):
            raise FileNotFoundError(f"Plik {self.sources_file} nie istnieje")

        with open(self.sources_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        sources = []

        # GDOŚ
        if 'gdos' in data:
            sources.extend(data['gdos'])

        # RDOŚ
        if 'rdos' in data:
            sources.extend(data['rdos'])

        # Województwa
        if 'voivodeships' in data:
            sources.extend(data['voivodeships'])

        # Miasta na prawach powiatu
        if 'miasta_na_prawach_powiatu' in data:
            sources.extend(data['miasta_na_prawach_powiatu'])

        # Powiaty
        if 'powiaty' in data:
            sources.extend(data['powiaty'])
        elif 'powiaty_sample' in data:
            sources.extend(data['powiaty_sample'])

        # Gminy miejskie
        if 'gminy_miejskie' in data:
            sources.extend(data['gminy_miejskie'])

        # Gminy miejsko-wiejskie
        if 'gminy_miejsko_wiejskie' in data:
            sources.extend(data['gminy_miejsko_wiejskie'])

        # Gminy wiejskie
        if 'gminy_wiejskie' in data:
            sources.extend(data['gminy_wiejskie'])

        self.sources = sources
        return sources

    def get_sources_count(self) -> int:
        """Zwraca liczbę załadowanych źródeł."""
        return len(self.sources)


async def run_scraper(
    date_from: datetime,
    date_to: datetime,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    sources: Optional[List[Dict]] = None
) -> List[Dict]:
    """
    Główna funkcja uruchamiająca scraper.
    Zwraca listę surowych wyników.

    Args:
        date_from: Data początkowa
        date_to: Data końcowa
        progress_callback: Callback do raportowania postępu
        sources: Opcjonalna lista źródeł (jeśli None, załaduje wszystkie)
    """
    # Załaduj źródła jeśli nie podano
    if sources is None:
        loader = SourcesLoader()
        sources = loader.load()

    logger.info(f"Załadowano {len(sources)} źródeł")

    # Uruchom scraper
    scraper = BIPScraper(max_concurrent=10, requests_per_second=1.0)
    results = await scraper.scrape_all(sources, date_from, date_to, progress_callback)

    # Zbierz wszystkie znalezione wpisy
    all_items = []
    successful = 0
    failed = 0

    for result in results:
        if result.success:
            successful += 1
            all_items.extend(result.results)
        else:
            failed += 1
            logger.debug(f"Błąd dla {result.source_name}: {result.error}")

    logger.info(f"Przeszukano: {successful} udanych, {failed} nieudanych")
    logger.info(f"Znaleziono {len(all_items)} potencjalnych wyników")

    return all_items


# Test modułu
if __name__ == "__main__":
    async def test():
        date_from = datetime.now() - timedelta(days=14)
        date_to = datetime.now()

        def progress(current, total, name):
            print(f"[{current}/{total}] Przeszukuję: {name}")

        results = await run_scraper(date_from, date_to, progress)
        print(f"\nZnaleziono {len(results)} wyników")

        for r in results[:5]:
            print(f"- {r.get('title', '')[:80]}...")

    asyncio.run(test())
