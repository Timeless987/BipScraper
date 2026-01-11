"""
Test głębokiego przeszukiwania BIP.
"""
import asyncio
from datetime import datetime, timedelta
from scraper import BIPScraper

# Testowe źródła - z Twoich przykładów
TEST_SOURCES = [
    {
        "id": "poznan",
        "name": "Poznań",
        "bip_url": "https://bip.poznan.pl",
        "voivodeship": "wielkopolskie"
    },
    {
        "id": "gdansk",
        "name": "Gdańsk",
        "bip_url": "https://bip.gdansk.pl",
        "voivodeship": "pomorskie"
    },
    {
        "id": "gw-wisznia-mala",
        "name": "Wisznia Mała",
        "bip_url": "https://bip.wiszniamala.pl",
        "voivodeship": "dolnośląskie"
    },
    {
        "id": "gw-dopiewo",
        "name": "Dopiewo",
        "bip_url": "https://bip.dopiewo.pl",
        "voivodeship": "wielkopolskie"
    },
    {
        "id": "radom",
        "name": "Radom",
        "bip_url": "https://bip.radom.pl",
        "voivodeship": "mazowieckie"
    },
]

async def test_single_bip(scraper, source):
    """Testuje pojedynczy BIP."""
    print(f"\n{'='*60}")
    print(f"Testowanie: {source['name']} ({source['bip_url']})")
    print('='*60)

    date_from = datetime.now() - timedelta(days=30)
    date_to = datetime.now()

    result = await scraper.search_bip(source, date_from, date_to)

    if result.error:
        print(f"BŁĄD: {result.error}")
    else:
        print(f"Znaleziono {len(result.results)} wyników")

        # Pokaż pierwsze 5 wyników
        for i, item in enumerate(result.results[:5]):
            print(f"\n  {i+1}. {item.get('title', 'Brak tytułu')[:80]}...")
            print(f"     URL: {item.get('url', 'Brak URL')[:60]}...")
            if item.get('date'):
                print(f"     Data: {item.get('date')}")

    return result

async def main():
    """Główna funkcja testowa."""
    import aiohttp

    print("="*60)
    print("TEST GŁĘBOKIEGO PRZESZUKIWANIA BIP")
    print("="*60)

    scraper = BIPScraper(max_concurrent=5, requests_per_second=2.0)

    connector = aiohttp.TCPConnector(
        limit=5,
        limit_per_host=2,
        ssl=False,
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        scraper.session = session

        total_results = 0
        for source in TEST_SOURCES:
            result = await test_single_bip(scraper, source)
            total_results += len(result.results)

    print(f"\n{'='*60}")
    print(f"PODSUMOWANIE: Znaleziono łącznie {total_results} wyników")
    print('='*60)

if __name__ == "__main__":
    asyncio.run(main())
