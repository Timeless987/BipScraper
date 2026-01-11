"""
Zaawansowany scraper dla stron BIP.
Wykorzystuje bazę znanych ścieżek, paginację i inteligentne odkrywanie sekcji.
"""

import asyncio
import aiohttp
import json
import re
import os
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-Agent rotation
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# Precyzyjne słowa kluczowe do filtrowania wyników
REQUIRED_KEYWORDS = [
    # Decyzje środowiskowe - różne odmiany
    'środowiskowych uwarunkowań',
    'środowiskowe uwarunkowania',
    'decyzji o środowiskowych',
    'decyzja o środowiskowych',
    'decyzje o środowiskowych',
    # Skróty
    'duś', 'ooś',
    # Postępowania
    'postępowania w sprawie wydania decyzji',
    'postępowanie w sprawie wydania decyzji',
    'wszczęcie postępowania',
    'wszczęciu postępowania',
    'wznowienie postępowania',
    'zawieszenie postępowania',
    'umorzenie postępowania',
    'podjęcie postępowania',
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
    # Sygnatury
    '6220',
    # Inne formy
    'wydaniu decyzji',
    'wydania decyzji',
    'materiału dowodowego',
    'zapoznania się z aktami',
]

BLACKLIST_KEYWORDS = [
    'program ochrony środowiska',
    'programu ochrony środowiska',
    'odszkodowanie',
    'plan zagospodarowania',
    'studium uwarunkowań',
    'warunkach zabudowy',
    'pozwolenie na budowę',
    'wybory',
    'przetarg',
    'konkurs',
    'nabór wniosków',
    'dotacje',
    'rekrutacja',
]


class RateLimiter:
    """Kontroler prędkości requestów per domena."""

    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request: Dict[str, float] = {}

    async def wait(self, domain: str):
        current = time.time()
        if domain in self.last_request:
            elapsed = current - self.last_request[domain]
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
        self.last_request[domain] = time.time()


class AdvancedBIPScraper:
    """
    Zaawansowany scraper wykorzystujący:
    1. Bazę znanych ścieżek (known_paths.json)
    2. Ścieżki z sources.json (env_path)
    3. Inteligentne odkrywanie sekcji środowiskowych
    4. Paginację
    """

    def __init__(self, max_concurrent: int = 15, requests_per_second: float = 3.0):
        self.max_concurrent = max_concurrent
        self.rate_limiter = RateLimiter(requests_per_second)
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.known_paths = self._load_known_paths()
        self.stop_requested = False

    def _load_known_paths(self) -> Dict:
        """Ładuje bazę znanych ścieżek."""
        paths_file = os.path.join(os.path.dirname(__file__), 'known_paths.json')
        if os.path.exists(paths_file):
            with open(paths_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

    async def fetch(self, url: str, timeout: int = 30) -> Optional[str]:
        """Pobiera stronę z rate limiting."""
        if self.stop_requested:
            return None

        domain = urlparse(url).netloc

        async with self.semaphore:
            await self.rate_limiter.wait(domain)

            try:
                async with self.session.get(
                    url,
                    headers=self.get_headers(),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False,
                ) as response:
                    if response.status == 200:
                        try:
                            return await response.text(encoding='utf-8')
                        except UnicodeDecodeError:
                            try:
                                return await response.text(encoding='iso-8859-2')
                            except:
                                return await response.text(encoding='windows-1250', errors='ignore')
                    else:
                        logger.debug(f"HTTP {response.status}: {url}")
                        return None
            except asyncio.TimeoutError:
                logger.debug(f"Timeout: {url}")
                return None
            except Exception as e:
                logger.debug(f"Error {url}: {e}")
                return None

    def is_environmental_result(self, text: str) -> bool:
        """Sprawdza czy tekst dotyczy decyzji środowiskowych."""
        text_lower = text.lower()

        # Sprawdź blacklistę
        if any(bl in text_lower for bl in BLACKLIST_KEYWORDS):
            return False

        # Sprawdź wymagane słowa kluczowe
        return any(kw in text_lower for kw in REQUIRED_KEYWORDS)

    def extract_date(self, text: str) -> str:
        """Wyciąga datę z tekstu - tylko poprawne daty."""
        patterns = [
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', 'dmy'),  # 31.12.2024
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', 'dmy'),    # 31-12-2024
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', 'dmy'),    # 31/12/2024
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'ymd'),    # 2024-12-31
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', 'ymd'),  # 2024.12.31
        ]
        for pattern, fmt in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if fmt == 'dmy':
                        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    else:  # ymd
                        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))

                    # Walidacja daty
                    if 1 <= d <= 31 and 1 <= m <= 12 and 2000 <= y <= 2030:
                        return f"{d:02d}.{m:02d}.{y}"
                except:
                    pass
        return ''

    def parse_gov_pl(self, html: str, base_url: str) -> List[Dict]:
        """Parser dla stron gov.pl (RDOŚ, GDOŚ)."""
        results = []
        seen_urls = set()
        soup = BeautifulSoup(html, 'lxml')

        # Usuń niepotrzebne elementy (nawigacja, stopka)
        for tag in soup.select('nav, footer, header, .nav, .footer, .header'):
            tag.decompose()

        # Znajdź główną treść strony
        main_content = soup.select_one('main, .content, #content, article, .article-area')

        # Jeśli nie znaleziono main, użyj body
        if not main_content:
            main_content = soup.body

        if not main_content:
            return results

        # Szukaj WSZYSTKICH linków w głównej treści
        all_links = main_content.select('a[href]')

        for link_elem in all_links:
            try:
                title = link_elem.get_text(strip=True)
                href = link_elem.get('href', '')

                if not title or len(title) < 25:
                    continue

                # Pomiń linki nawigacyjne
                href_lower = href.lower()
                if any(skip in href_lower for skip in ['#', 'javascript:', 'mailto:', 'facebook', 'twitter', 'katalog-jednostek']):
                    continue

                # Tylko linki do /web/
                if not href.startswith('/web/'):
                    continue

                # Pełny URL
                full_url = 'https://www.gov.pl' + href

                # Pomiń duplikaty
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Data - szukaj w tekście linku lub rodzica
                parent = link_elem.parent
                parent_text = parent.get_text(strip=True) if parent else title
                date = self.extract_date(parent_text)

                # Dla gov.pl - strona jest już wyselekcjonowana, więc łagodniejsze filtrowanie
                # Sprawdzamy czy to rzeczywiście obwieszczenie/zawiadomienie/decyzja
                title_lower = title.lower()
                is_announcement = any(kw in title_lower for kw in [
                    'obwieszczeni', 'zawiadomieni', 'postanowieni',
                    'decyzj', 'znak', 'wooś', 'dooś', 'rdoś',
                    'środowisk', 'oddziaływan', 'przedsięwzięc',
                    '.420.', '.6220.',  # sygnatury
                    'ochrony środowiska',
                ])

                if is_announcement:
                    results.append({
                        'title': title[:300],
                        'url': full_url,
                        'date': date,
                        'content': parent_text[:500] if parent_text != title else '',
                    })

            except Exception as e:
                logger.debug(f"Parse gov.pl error: {e}")
                continue

        return results

    def parse_bip_table(self, html: str, base_url: str) -> List[Dict]:
        """Parser dla stron BIP z tabelami."""
        results = []
        soup = BeautifulSoup(html, 'lxml')

        # Szukaj tabel
        tables = soup.select('table')

        for table in tables:
            rows = table.select('tr')

            for row in rows:
                try:
                    cells = row.select('td')
                    if not cells:
                        continue

                    # Szukaj linku
                    link_elem = row.select_one('a[href]')
                    if not link_elem:
                        continue

                    title = link_elem.get_text(strip=True)
                    href = link_elem.get('href', '')

                    if not title or len(title) < 10:
                        # Spróbuj pobrać tekst z całego wiersza
                        title = ' '.join(cell.get_text(strip=True) for cell in cells)

                    if not title or len(title) < 10:
                        continue

                    # URL
                    full_url = urljoin(base_url, href)

                    # Data
                    date = self.extract_date(row.get_text())

                    # Filtruj
                    if self.is_environmental_result(title):
                        results.append({
                            'title': title[:300],
                            'url': full_url,
                            'date': date,
                            'content': row.get_text(strip=True)[:500],
                        })

                except Exception as e:
                    logger.debug(f"Row parse error: {e}")
                    continue

        return results

    def parse_bip_list(self, html: str, base_url: str) -> List[Dict]:
        """Parser dla stron BIP z listami."""
        results = []
        soup = BeautifulSoup(html, 'lxml')

        # Usuń niepotrzebne elementy
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # Selektory dla list
        selectors = [
            '.news-list li',
            '.article-list li',
            '.document-list li',
            '.ogloszenia-lista li',
            'ul.list li',
            '.content li',
            'div[class*="news"] li',
            'div[class*="ogloszeni"] li',
            '.entry',
            'article',
        ]

        items = []
        for selector in selectors:
            found = soup.select(selector)
            if found:
                items.extend(found)
                break

        # Jeśli nie znaleziono przez selektory, szukaj po linkach
        if not items:
            items = soup.find_all('a', href=True)

        for item in items:
            try:
                if item.name == 'a':
                    title = item.get_text(strip=True)
                    href = item.get('href', '')
                    parent_text = item.parent.get_text(strip=True) if item.parent else ''
                else:
                    link_elem = item.select_one('a[href]')
                    if not link_elem:
                        continue
                    title = link_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    parent_text = item.get_text(strip=True)

                if not title or len(title) < 15:
                    continue

                # URL
                full_url = urljoin(base_url, href)

                # Data
                date = self.extract_date(parent_text or title)

                # Filtruj
                combined = f"{title} {parent_text}"
                if self.is_environmental_result(combined):
                    results.append({
                        'title': title[:300],
                        'url': full_url,
                        'date': date,
                        'content': parent_text[:500] if parent_text else '',
                    })

            except Exception as e:
                logger.debug(f"List parse error: {e}")
                continue

        return results

    def parse_generic(self, html: str, base_url: str, is_known_env_page: bool = False) -> List[Dict]:
        """
        Uniwersalny parser - próbuje różnych metod.

        Args:
            html: HTML strony
            base_url: URL strony
            is_known_env_page: czy to znana strona środowiskowa (łagodniejsze filtrowanie)
        """
        results = []

        # Spróbuj parsera gov.pl
        if 'gov.pl' in base_url:
            results = self.parse_gov_pl(html, base_url)
            # gov.pl zawsze zwraca wyniki - nie próbuj innych metod
            return results

        # Spróbuj parsera tabel
        results = self.parse_bip_table(html, base_url)
        if results:
            return results

        # Spróbuj parsera list
        results = self.parse_bip_list(html, base_url)

        return results

    def find_pagination_urls(self, html: str, base_url: str, max_pages: int = 5) -> List[str]:
        """Znajduje linki do kolejnych stron."""
        soup = BeautifulSoup(html, 'lxml')
        pages = set()

        # Szukaj linków do paginacji
        pagination_selectors = [
            '.pagination a',
            '.pager a',
            '.pages a',
            'a[href*="page="]',
            'a[href*="strona="]',
            'a[href*="PageNo="]',
            'a.next',
            'a[rel="next"]',
        ]

        for selector in pagination_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if href:
                    full_url = urljoin(base_url, href)
                    if full_url != base_url:
                        pages.add(full_url)

        # Ogranicz liczbę stron
        return list(pages)[:max_pages]

    def find_env_sections(self, html: str, base_url: str) -> List[str]:
        """Znajduje linki do sekcji środowiskowych."""
        soup = BeautifulSoup(html, 'lxml')
        found = set()
        scored_urls = []  # (url, score) - wyższy score = lepszy
        base_domain = urlparse(base_url).netloc

        # Słowa kluczowe z priorytetami (wyższy = ważniejszy)
        high_priority_keywords = [
            'decyzje środowiskowe', 'decyzji środowiskowych',
            'środowiskowych uwarunkowań', 'uwarunkowań środowiskowych',
            'karty informacyjne', 'wykaz danych o środowisku',
            'publicznie dostępny wykaz', '6220',
        ]

        medium_priority_keywords = [
            'ochrona środowiska', 'ochrony środowiska',
            'obwieszczenia', 'decyzje', 'środowisk',
        ]

        low_priority_keywords = [
            'ogłoszenia', 'tablica', 'komunikaty',
            'ekolog', 'klimat', 'aktualności',
        ]

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            href_lower = href.lower()
            text = link.get_text(strip=True).lower()

            # Pomiń linki zewnętrzne i nawigacyjne
            if any(x in href_lower for x in ['#', 'javascript:', 'mailto:', 'facebook', 'twitter']):
                continue

            # Oblicz score
            score = 0

            # Wysoki priorytet
            if any(kw in text for kw in high_priority_keywords):
                score += 10
            if any(kw in href_lower for kw in ['srodowisk', 'environment', '6220', 'karty-informacyjne']):
                score += 8

            # Średni priorytet
            if any(kw in text for kw in medium_priority_keywords):
                score += 5
            if any(kw in href_lower for kw in ['obwieszcz', 'decyzj', 'ochrona']):
                score += 4

            # Niski priorytet
            if any(kw in text for kw in low_priority_keywords):
                score += 2
            if any(kw in href_lower for kw in ['oglosz', 'tablica', 'komunikat']):
                score += 1

            if score > 0:
                full_url = urljoin(base_url, href)
                # Tylko ta sama domena
                if urlparse(full_url).netloc == base_domain:
                    scored_urls.append((full_url, score))

        # Sortuj po score (malejąco) i zwróć unikalne URL-e
        scored_urls.sort(key=lambda x: x[1], reverse=True)

        for url, score in scored_urls:
            if url not in found:
                found.add(url)
                if len(found) >= 15:
                    break

        return list(found)

    async def scrape_source_with_known_path(
        self,
        source: Dict,
        known_config: Dict
    ) -> List[Dict]:
        """Scrapuje źródło ze znaną konfiguracją."""
        results = []
        base_url = source.get('bip_url', source.get('url', ''))

        if not base_url:
            return results

        # Usuń trailing slash z base_url
        base_url = base_url.rstrip('/')

        # Pobierz ścieżki do sprawdzenia
        env_paths = known_config.get('env_paths', [])

        for path in env_paths:
            if self.stop_requested:
                break

            # Łącz URL-e bezpośrednio (nie używaj urljoin który może zepsuć ścieżkę)
            if path.startswith('/'):
                full_url = base_url + path
            elif path.startswith('http'):
                full_url = path
            else:
                full_url = base_url + '/' + path

            html = await self.fetch(full_url)

            if not html:
                continue

            # Parsuj stronę
            page_results = self.parse_generic(html, full_url)
            results.extend(page_results)

            # Sprawdź paginację
            if known_config.get('has_pagination'):
                pagination_urls = self.find_pagination_urls(html, full_url, max_pages=3)

                for page_url in pagination_urls:
                    if self.stop_requested:
                        break

                    page_html = await self.fetch(page_url)
                    if page_html:
                        page_results = self.parse_generic(page_html, page_url)
                        results.extend(page_results)

        return results

    async def scrape_source_with_discovery(self, source: Dict) -> List[Dict]:
        """Scrapuje źródło z odkrywaniem sekcji."""
        results = []
        base_url = source.get('bip_url', source.get('url', ''))
        env_path = source.get('env_path', '')

        if not base_url:
            return results

        visited = set()
        urls_to_check = []

        # Najpierw sprawdź env_path ze sources.json
        if env_path:
            urls_to_check.append(urljoin(base_url, env_path))

        # Dodaj standardowe ścieżki
        discovery_patterns = self.known_paths.get('discovery_patterns', {})
        common_paths = discovery_patterns.get('common_paths_to_try', [])

        for path in common_paths[:5]:  # Ogranicz do 5
            urls_to_check.append(urljoin(base_url, path))

        # Sprawdź stronę główną dla odkrycia sekcji
        main_html = await self.fetch(base_url)
        if main_html:
            env_sections = self.find_env_sections(main_html, base_url)
            urls_to_check.extend(env_sections[:5])

        # Scrapuj znalezione URL-e
        for url in urls_to_check:
            if self.stop_requested:
                break

            if url in visited:
                continue
            visited.add(url)

            html = await self.fetch(url)
            if not html:
                continue

            page_results = self.parse_generic(html, url)
            results.extend(page_results)

            # Sprawdź paginację
            pagination_urls = self.find_pagination_urls(html, url, max_pages=2)
            for page_url in pagination_urls:
                if page_url not in visited:
                    visited.add(page_url)
                    page_html = await self.fetch(page_url)
                    if page_html:
                        page_results = self.parse_generic(page_html, page_url)
                        results.extend(page_results)

        return results

    async def scrape_source(self, source: Dict) -> Tuple[str, List[Dict], Optional[str]]:
        """
        Główna metoda scrapowania źródła.
        Zwraca: (source_id, results, error)
        """
        source_id = source.get('id', '')
        source_name = source.get('name', '')
        results = []
        error = None

        try:
            # Sprawdź czy mamy znaną konfigurację
            verified_sources = self.known_paths.get('verified_sources', {})
            verified_sources_extra = self.known_paths.get('verified_sources_extra', {})
            verified_gminy = self.known_paths.get('verified_gminy', {})
            rdos_paths = self.known_paths.get('rdos_paths', {})
            gdos_paths = self.known_paths.get('gdos_paths', {})

            known_config = None

            # Szukaj w verified_sources
            if source_id in verified_sources:
                known_config = verified_sources[source_id]
            # Szukaj w verified_sources_extra
            elif source_id in verified_sources_extra:
                known_config = verified_sources_extra[source_id]
            # Szukaj w verified_gminy
            elif source_id in verified_gminy:
                known_config = verified_gminy[source_id]
            # Szukaj w rdos_paths
            elif source_id in rdos_paths:
                config = rdos_paths[source_id]
                # Konwertuj format
                paths = config.get('paths', [])
                if 'paths_by_year' in config:
                    current_year = str(datetime.now().year)
                    prev_year = str(datetime.now().year - 1)
                    paths = [
                        config['paths_by_year'].get(current_year, ''),
                        config['paths_by_year'].get(prev_year, ''),
                    ]
                    paths = [p for p in paths if p]

                known_config = {'env_paths': paths, 'has_pagination': False}
                source['bip_url'] = config.get('base_url', source.get('bip_url', ''))
            # Szukaj w gdos_paths
            elif source_id in gdos_paths:
                config = gdos_paths[source_id]
                known_config = {'env_paths': config.get('paths', []), 'has_pagination': False}
                source['bip_url'] = config.get('base_url', source.get('bip_url', ''))

            # Scrapuj
            if known_config:
                results = await self.scrape_source_with_known_path(source, known_config)
            else:
                results = await self.scrape_source_with_discovery(source)

            # Dodaj info o źródle
            for r in results:
                r['source_id'] = source_id
                r['source_name'] = source_name
                r['source_voivodeship'] = source.get('voivodeship', '')

            logger.debug(f"{source_name}: znaleziono {len(results)} wyników")

        except Exception as e:
            error = str(e)
            logger.error(f"Error scraping {source_name}: {e}")

        return source_id, results, error

    async def scrape_all(
        self,
        sources: List[Dict],
        progress_callback=None,
        stop_check=None,
    ) -> List[Dict]:
        """
        Scrapuje wszystkie źródła.

        Args:
            sources: Lista źródeł do przeszukania
            progress_callback: Funkcja (current, total, name) -> None
            stop_check: Funkcja () -> bool sprawdzająca czy przerwać
        """
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=3,
            ssl=False,
        )

        all_results = []
        seen_urls = set()

        async with aiohttp.ClientSession(connector=connector) as session:
            self.session = session
            total = len(sources)

            for i, source in enumerate(sources):
                # Sprawdź czy przerwać
                if stop_check and stop_check():
                    self.stop_requested = True
                    logger.info("Przerwano na żądanie użytkownika")
                    break

                if self.stop_requested:
                    break

                source_id, results, error = await self.scrape_source(source)

                # Deduplikacja
                for r in results:
                    url = r.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)

                if progress_callback:
                    progress_callback(i + 1, total, source.get('name', 'Nieznane'))

        logger.info(f"Znaleziono łącznie {len(all_results)} unikalnych wyników")
        return all_results


# Funkcja pomocnicza do uruchomienia scrapera
async def run_advanced_scraper(
    sources: List[Dict],
    progress_callback=None,
    stop_check=None,
) -> List[Dict]:
    """
    Uruchamia zaawansowany scraper.
    """
    scraper = AdvancedBIPScraper(max_concurrent=15, requests_per_second=3.0)
    return await scraper.scrape_all(sources, progress_callback, stop_check)


# Test
if __name__ == "__main__":
    import sys

    async def test():
        # Testowe źródła
        test_sources = [
            {
                "id": "wroclaw",
                "name": "Wrocław",
                "voivodeship": "dolnośląskie",
                "bip_url": "https://bip.um.wroc.pl",
                "env_path": "/artykuly/385/wydane-decyzje-o-srodowiskowych-uwarunkowaniach"
            },
            {
                "id": "rdos-warszawa",
                "name": "RDOŚ Warszawa",
                "voivodeship": "mazowieckie",
                "bip_url": "https://www.gov.pl/web/rdos-warszawa",
            },
            {
                "id": "gdansk",
                "name": "Gdańsk",
                "voivodeship": "pomorskie",
                "bip_url": "https://bip.gdansk.pl",
                "env_path": "/urzad-miejski/Decyzje-o-srodowiskowych-uwarunkowaniach,a,108376"
            },
        ]

        def progress(current, total, name):
            print(f"[{current}/{total}] {name}")

        results = await run_advanced_scraper(test_sources, progress)

        print(f"\n=== Znaleziono {len(results)} wyników ===\n")

        for r in results[:10]:
            print(f"- [{r.get('source_name')}] {r.get('title', '')[:80]}...")
            print(f"  URL: {r.get('url', '')[:80]}")
            print()

    asyncio.run(test())
