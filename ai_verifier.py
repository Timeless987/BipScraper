"""
Moduł weryfikacji wyników przez AI (Claude).
Używa Claude Haiku do taniego i szybkiego filtrowania wyników.
"""

import os
import json
import logging
from typing import List, Dict, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Konfiguracja
BATCH_SIZE = 20  # Ile wyników przetwarzać naraz
MODEL = "claude-3-5-haiku-latest"  # Najtańszy model

# Prompt systemowy do weryfikacji
SYSTEM_PROMPT = """Jesteś ekspertem od polskiego prawa ochrony środowiska. Twoim zadaniem jest weryfikacja wyników wyszukiwania decyzji o środowiskowych uwarunkowaniach (DUŚ).

KRYTERIA AKCEPTACJI - wynik jest POPRAWNY jeśli dotyczy:
1. Decyzji o środowiskowych uwarunkowaniach (DUŚ)
2. Postępowania w sprawie wydania DUŚ (wszczęcie, zawieszenie, podjęcie, umorzenie)
3. Oceny oddziaływania na środowisko (OOŚ)
4. Obwieszczenia o możliwości zapoznania się z aktami sprawy DUŚ
5. Raportu o oddziaływaniu na środowisko
6. Karty informacyjnej przedsięwzięcia

KRYTERIA ODRZUCENIA - wynik jest NIEPOPRAWNY jeśli dotyczy:
1. Programu ochrony środowiska (to inny dokument)
2. Pozwolenia na budowę (to osobna procedura)
3. Warunków zabudowy
4. Planu zagospodarowania przestrzennego
5. Przetargów, konkursów, naborów
6. Wyborów
7. Innych spraw niezwiązanych z DUŚ/OOŚ

Dla każdego wyniku określ:
- is_valid: true/false - czy wynik dotyczy DUŚ/OOŚ
- confidence: 0.0-1.0 - pewność oceny
- reason: krótkie uzasadnienie (max 50 znaków)
- industry: branża jeśli można określić (energia, transport, przemysł, rolnictwo, budownictwo, odpady, inne, nieznana)
- stage: etap postępowania (wszczęcie, decyzja, zawieszenie, podjęcie, umorzenie, obwieszczenie, nieznany)

Odpowiedz w formacie JSON."""


def create_verification_prompt(results: List[Dict], search_criteria: Dict) -> str:
    """Tworzy prompt do weryfikacji wyników."""

    industries = search_criteria.get('industries', [])
    date_from = search_criteria.get('date_from', '')
    date_to = search_criteria.get('date_to', '')

    criteria_text = f"""
Kryteria wyszukiwania użytkownika:
- Okres: {date_from} do {date_to}
- Branże: {', '.join(industries) if industries else 'wszystkie'}
"""

    results_text = "Wyniki do weryfikacji:\n"
    for i, r in enumerate(results):
        results_text += f"""
---
ID: {i}
Tytuł: {r.get('title', 'Brak')}
Źródło: {r.get('source_name', 'Nieznane')}
Data: {r.get('date', 'Brak')}
URL: {r.get('url', 'Brak')}
"""

    return f"""{criteria_text}

{results_text}

Przeanalizuj każdy wynik i zwróć JSON w formacie:
{{
  "results": [
    {{"id": 0, "is_valid": true/false, "confidence": 0.0-1.0, "reason": "...", "industry": "...", "stage": "..."}},
    ...
  ]
}}"""


class AIVerifier:
    """Weryfikator wyników oparty na Claude."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.client = None
        self.enabled = False

        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                self.enabled = True
                logger.info("AI Verifier zainicjalizowany pomyślnie")
            except Exception as e:
                logger.warning(f"Nie udało się zainicjalizować AI Verifier: {e}")
        else:
            logger.info("Brak klucza API - AI Verifier wyłączony")

    def is_enabled(self) -> bool:
        """Sprawdza czy weryfikator jest dostępny."""
        return self.enabled and self.client is not None

    def verify_batch(self, results: List[Dict], search_criteria: Dict) -> List[Dict]:
        """
        Weryfikuje partię wyników.
        Zwraca wyniki z dodatkowymi polami weryfikacji.
        """
        if not self.is_enabled():
            # Jeśli AI niedostępne, zwróć wszystkie jako potencjalnie poprawne
            for r in results:
                r['ai_verified'] = False
                r['ai_valid'] = True
                r['ai_confidence'] = 0.5
                r['ai_reason'] = 'AI niedostępne'
            return results

        prompt = create_verification_prompt(results, search_criteria)

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parsuj odpowiedź JSON
            response_text = response.content[0].text

            # Wyciągnij JSON z odpowiedzi
            try:
                # Spróbuj znaleźć JSON w odpowiedzi
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    verification = json.loads(json_str)
                else:
                    raise ValueError("Nie znaleziono JSON w odpowiedzi")

                # Zastosuj weryfikację do wyników
                verified_results = verification.get('results', [])

                for vr in verified_results:
                    idx = vr.get('id', -1)
                    if 0 <= idx < len(results):
                        results[idx]['ai_verified'] = True
                        results[idx]['ai_valid'] = vr.get('is_valid', True)
                        results[idx]['ai_confidence'] = vr.get('confidence', 0.5)
                        results[idx]['ai_reason'] = vr.get('reason', '')

                        # Aktualizuj branżę i etap jeśli AI je określiło
                        if vr.get('industry') and vr.get('industry') != 'nieznana':
                            results[idx]['ai_industry'] = vr.get('industry')
                        if vr.get('stage') and vr.get('stage') != 'nieznany':
                            results[idx]['ai_stage'] = vr.get('stage')

            except json.JSONDecodeError as e:
                logger.warning(f"Błąd parsowania odpowiedzi AI: {e}")
                # Oznacz wszystkie jako niezweryfikowane
                for r in results:
                    r['ai_verified'] = False
                    r['ai_valid'] = True
                    r['ai_confidence'] = 0.5
                    r['ai_reason'] = 'Błąd parsowania'

        except Exception as e:
            logger.error(f"Błąd weryfikacji AI: {e}")
            for r in results:
                r['ai_verified'] = False
                r['ai_valid'] = True
                r['ai_confidence'] = 0.5
                r['ai_reason'] = f'Błąd: {str(e)[:30]}'

        return results

    def verify_all(self, results: List[Dict], search_criteria: Dict,
                   progress_callback=None) -> List[Dict]:
        """
        Weryfikuje wszystkie wyniki w partiach.

        Args:
            results: Lista wyników do weryfikacji
            search_criteria: Kryteria wyszukiwania
            progress_callback: Opcjonalny callback (current, total, message)

        Returns:
            Lista zweryfikowanych wyników (tylko te uznane za poprawne)
        """
        if not results:
            return []

        all_verified = []
        total_batches = (len(results) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(results), BATCH_SIZE):
            batch = results[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1

            if progress_callback:
                progress_callback(
                    batch_num,
                    total_batches,
                    f"Weryfikacja AI: partia {batch_num}/{total_batches}"
                )

            verified_batch = self.verify_batch(batch, search_criteria)
            all_verified.extend(verified_batch)

        # Filtruj tylko poprawne wyniki (lub wszystkie jeśli AI niedostępne)
        valid_results = [
            r for r in all_verified
            if r.get('ai_valid', True) and r.get('ai_confidence', 0.5) >= 0.3
        ]

        logger.info(f"AI weryfikacja: {len(valid_results)}/{len(results)} wyników zaakceptowanych")

        return valid_results

    def estimate_cost(self, num_results: int) -> Dict:
        """
        Szacuje koszt weryfikacji.

        Returns:
            Dict z szacunkowym kosztem
        """
        # Szacunki dla Claude Haiku
        input_tokens_per_result = 150  # tytuł + metadane
        output_tokens_per_result = 50  # odpowiedź JSON

        total_input = num_results * input_tokens_per_result + 500  # + system prompt
        total_output = num_results * output_tokens_per_result

        # Ceny Haiku (przybliżone)
        input_cost = (total_input / 1_000_000) * 0.25
        output_cost = (total_output / 1_000_000) * 1.25

        return {
            "model": MODEL,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "estimated_cost_usd": round(input_cost + output_cost, 4),
            "estimated_cost_pln": round((input_cost + output_cost) * 4.0, 2),  # ~4 PLN/USD
        }


# Funkcja pomocnicza do szybkiego użycia
def verify_results(results: List[Dict], search_criteria: Dict,
                   api_key: Optional[str] = None) -> List[Dict]:
    """
    Weryfikuje wyniki przez AI.

    Args:
        results: Lista surowych wyników
        search_criteria: Kryteria wyszukiwania
        api_key: Opcjonalny klucz API (domyślnie z ANTHROPIC_API_KEY)

    Returns:
        Lista zweryfikowanych wyników
    """
    verifier = AIVerifier(api_key)
    return verifier.verify_all(results, search_criteria)


# Test modułu
if __name__ == "__main__":
    # Test z przykładowymi danymi
    test_results = [
        {
            "title": "Obwieszczenie o wszczęciu postępowania w sprawie wydania decyzji o środowiskowych uwarunkowaniach dla budowy farmy fotowoltaicznej",
            "source_name": "Poznań",
            "date": "2026-01-10",
            "url": "https://example.com/1"
        },
        {
            "title": "Program ochrony środowiska dla gminy na lata 2024-2030",
            "source_name": "Gdańsk",
            "date": "2026-01-09",
            "url": "https://example.com/2"
        },
        {
            "title": "Przetarg na dostawę sprzętu komputerowego",
            "source_name": "Radom",
            "date": "2026-01-08",
            "url": "https://example.com/3"
        },
    ]

    search_criteria = {
        "industries": ["energia"],
        "date_from": "2026-01-01",
        "date_to": "2026-01-15"
    }

    verifier = AIVerifier()

    print("=== Test AI Verifier ===")
    print(f"AI dostępne: {verifier.is_enabled()}")

    # Szacuj koszt
    cost = verifier.estimate_cost(100)
    print(f"\nSzacunkowy koszt dla 100 wyników:")
    print(f"  Model: {cost['model']}")
    print(f"  Tokeny wejściowe: {cost['input_tokens']}")
    print(f"  Tokeny wyjściowe: {cost['output_tokens']}")
    print(f"  Koszt: ${cost['estimated_cost_usd']} (~{cost['estimated_cost_pln']} PLN)")

    if verifier.is_enabled():
        print("\nWeryfikuję przykładowe wyniki...")
        verified = verifier.verify_all(test_results, search_criteria)

        print(f"\nWyniki weryfikacji ({len(verified)}/{len(test_results)} zaakceptowanych):")
        for r in test_results:
            status = "✓" if r.get('ai_valid') else "✗"
            conf = r.get('ai_confidence', 0)
            reason = r.get('ai_reason', 'N/A')
            print(f"  {status} [{conf:.0%}] {r['title'][:60]}... - {reason}")
