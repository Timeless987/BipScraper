"""
BIP Search - Wyszukiwarka decyzji środowiskowych w Biuletynach Informacji Publicznej
Główna aplikacja Flask
"""

# Załaduj zmienne środowiskowe z pliku .env
import os
from pathlib import Path
from dotenv import load_dotenv

# Znajdź plik .env w katalogu aplikacji
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from io import BytesIO, StringIO

from flask import Flask, render_template, request, jsonify, Response, send_file
import pandas as pd

from scraper import SourcesLoader
from advanced_scraper import run_advanced_scraper
from filters import ResultFilter, INDUSTRY_KEYWORDS
from search_profiles import (
    filter_sources_by_profile, get_available_profiles, get_profile_info,
    filter_sources_by_voivodeship, get_sources_by_voivodeship, VOIVODESHIPS
)
from ai_verifier import AIVerifier

# Inicjalizacja aplikacji Flask
app = Flask(__name__)

# Przechowywanie stanu wyszukiwań
search_sessions = {}


class SearchSession:
    """Klasa przechowująca stan sesji wyszukiwania."""

    def __init__(self, session_id: str, date_from: datetime, date_to: datetime,
                 industries: list, profile: str = "full", voivodeships: list = None,
                 use_ai_verification: bool = False):
        self.session_id = session_id
        self.date_from = date_from
        self.date_to = date_to
        self.industries = industries
        self.profile = profile  # profil wyszukiwania: top10, cities, sse, full, all_municipalities, urban_municipalities
        self.voivodeships = voivodeships or []  # filtr województw (puste = wszystkie)
        self.use_ai_verification = use_ai_verification  # czy używać AI do weryfikacji
        self.status = "pending"  # pending, running, verifying, completed, error
        self.progress = 0
        self.total = 0
        self.current_source = ""
        self.results = []
        self.raw_results_count = 0  # liczba wyników przed weryfikacją AI
        self.error = None
        self.started_at = None
        self.completed_at = None
        self.ai_verified = False  # czy wyniki zostały zweryfikowane przez AI
        self.stop_requested = False  # czy użytkownik poprosił o przerwanie

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'status': self.status,
            'progress': self.progress,
            'total': self.total,
            'current_source': self.current_source,
            'results_count': len(self.results),
            'raw_results_count': self.raw_results_count,
            'ai_verified': self.ai_verified,
            'use_ai_verification': self.use_ai_verification,
            'error': self.error,
        }


def run_async_scraper(session: SearchSession):
    """Uruchamia scraper asynchronicznie w osobnym wątku."""

    def progress_callback(current: int, total: int, source_name: str):
        session.progress = current
        session.total = total
        session.current_source = source_name

    def ai_progress_callback(current: int, total: int, message: str):
        session.current_source = message

    def stop_check():
        return session.stop_requested

    async def async_search():
        try:
            session.status = "running"
            session.started_at = datetime.now()

            # Załaduj i przefiltruj źródła według profilu i województw
            loader = SourcesLoader()
            all_sources = loader.load()
            filtered_sources = filter_sources_by_profile(all_sources, session.profile)

            # Dodatkowe filtrowanie po województwach (jeśli wybrano)
            if session.voivodeships:
                filtered_sources = filter_sources_by_voivodeship(filtered_sources, session.voivodeships)

            # Uruchom ZAAWANSOWANY scraper z przefiltrowanymi źródłami
            raw_results = await run_advanced_scraper(
                filtered_sources,
                progress_callback,
                stop_check
            )

            # Przefiltruj wyniki (pierwszy etap - słowa kluczowe)
            result_filter = ResultFilter(
                session.date_from,
                session.date_to,
                session.industries
            )
            filtered_results = result_filter.filter_results(raw_results)

            # Zapisz liczbę wyników przed weryfikacją AI
            session.raw_results_count = len(filtered_results)

            # Weryfikacja AI (jeśli włączona)
            if session.use_ai_verification and filtered_results:
                session.status = "verifying"
                session.current_source = "Weryfikacja AI..."

                verifier = AIVerifier()
                if verifier.is_enabled():
                    search_criteria = {
                        'industries': session.industries,
                        'date_from': session.date_from.strftime('%Y-%m-%d'),
                        'date_to': session.date_to.strftime('%Y-%m-%d'),
                    }

                    filtered_results = verifier.verify_all(
                        filtered_results,
                        search_criteria,
                        progress_callback=ai_progress_callback
                    )
                    session.ai_verified = True

            session.results = filtered_results
            session.status = "completed"
            session.completed_at = datetime.now()

        except Exception as e:
            session.status = "error"
            session.error = str(e)
            session.completed_at = datetime.now()

    # Uruchom w nowej pętli zdarzeń
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_search())
    finally:
        loop.close()


@app.route('/')
def index():
    """Strona główna z formularzem wyszukiwania."""
    # Pobierz liczbę źródeł
    try:
        loader = SourcesLoader()
        loader.load()
        sources_count = loader.get_sources_count()
    except Exception:
        sources_count = 0

    # Lista branż (dodaj "Inne" na końcu)
    industries = list(INDUSTRY_KEYWORDS.keys()) + ["Inne"]

    # Profile wyszukiwania
    profiles = get_available_profiles()

    # Województwa z liczbą źródeł
    voivodeships = VOIVODESHIPS

    # Domyślne daty (ostatnie 14 dni)
    date_to = datetime.now().strftime('%Y-%m-%d')
    date_from = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')

    return render_template(
        'index.html',
        sources_count=sources_count,
        industries=industries,
        profiles=profiles,
        voivodeships=voivodeships,
        date_from=date_from,
        date_to=date_to
    )


@app.route('/search', methods=['POST'])
def start_search():
    """Rozpoczyna nowe wyszukiwanie."""
    try:
        data = request.get_json()

        # Parsuj daty
        date_from_str = data.get('date_from')
        date_to_str = data.get('date_to')

        if not date_from_str or not date_to_str:
            return jsonify({'error': 'Brak dat'}), 400

        date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d')

        # Dodaj czas do date_to (koniec dnia)
        date_to = date_to.replace(hour=23, minute=59, second=59)

        # Pobierz branże
        industries = data.get('industries', list(INDUSTRY_KEYWORDS.keys()))

        # Pobierz profil wyszukiwania (domyślnie: full)
        profile = data.get('profile', 'full')

        # Pobierz wybrane województwa (pusta lista = wszystkie)
        voivodeships = data.get('voivodeships', [])

        # Czy używać weryfikacji AI
        use_ai = data.get('use_ai_verification', False)

        # Utwórz sesję
        session_id = str(uuid.uuid4())
        session = SearchSession(session_id, date_from, date_to, industries, profile, voivodeships, use_ai)
        search_sessions[session_id] = session

        # Uruchom wyszukiwanie w tle
        thread = threading.Thread(target=run_async_scraper, args=(session,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'session_id': session_id,
            'message': 'Wyszukiwanie rozpoczęte',
            'profile': profile
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status/<session_id>')
def get_status(session_id: str):
    """Zwraca status wyszukiwania."""
    session = search_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Sesja nie znaleziona'}), 404

    return jsonify(session.to_dict())


@app.route('/stop/<session_id>', methods=['POST'])
def stop_search(session_id: str):
    """Zatrzymuje wyszukiwanie."""
    session = search_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Sesja nie znaleziona'}), 404

    session.stop_requested = True
    session.status = "stopped"
    session.completed_at = datetime.now()

    return jsonify({'message': 'Wyszukiwanie zatrzymane'})


@app.route('/stream/<session_id>')
def stream_status(session_id: str):
    """Streamuje status wyszukiwania przez Server-Sent Events."""
    def generate():
        session = search_sessions.get(session_id)
        if not session:
            yield f"data: {json.dumps({'error': 'Sesja nie znaleziona'})}\n\n"
            return

        while session.status in ["pending", "running", "verifying"]:
            yield f"data: {json.dumps(session.to_dict())}\n\n"
            import time
            time.sleep(0.5)

        # Ostatnia aktualizacja
        yield f"data: {json.dumps(session.to_dict())}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
    )


@app.route('/results/<session_id>')
def get_results(session_id: str):
    """Zwraca wyniki wyszukiwania."""
    session = search_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Sesja nie znaleziona'}), 404

    if session.status != "completed":
        return jsonify({'error': 'Wyszukiwanie jeszcze trwa'}), 400

    return jsonify({
        'results': session.results,
        'count': len(session.results)
    })


@app.route('/export/<session_id>/<format>')
def export_results(session_id: str, format: str):
    """Eksportuje wyniki do CSV lub Excel."""
    session = search_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Sesja nie znaleziona'}), 404

    if session.status != "completed":
        return jsonify({'error': 'Wyszukiwanie jeszcze trwa'}), 400

    if not session.results:
        return jsonify({'error': 'Brak wyników do eksportu'}), 400

    # Utwórz DataFrame
    df = pd.DataFrame(session.results)

    # Zmień nazwy kolumn na bardziej czytelne
    column_names = {
        'lokalizacja': 'Lokalizacja / Województwo',
        'data_obwieszczenia': 'Data obwieszczenia',
        'etap_postepowania': 'Etap postępowania',
        'branza': 'Branża / Przedsięwzięcie',
        'przedsiewziecie': 'Opis przedsięwzięcia',
        'sygnatura': 'Sygnatura',
        'zrodlo_url': 'Źródło (link)',
        'zrodlo_nazwa': 'Źródło (nazwa)',
    }
    df = df.rename(columns=column_names)

    # Generuj plik
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if format == 'csv':
        output = StringIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')  # utf-8-sig dla poprawnego wyświetlania w Excel
        output.seek(0)

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=bip_search_{timestamp}.csv'
            }
        )

    elif format == 'xlsx':
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Wyniki')

            # Formatuj szerokości kolumn
            worksheet = writer.sheets['Wyniki']
            for i, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                ) + 2
                # Ogranicz maksymalną szerokość
                max_length = min(max_length, 50)
                worksheet.column_dimensions[chr(65 + i)].width = max_length

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'bip_search_{timestamp}.xlsx'
        )

    else:
        return jsonify({'error': 'Nieobsługiwany format'}), 400


@app.route('/sources')
def get_sources():
    """Zwraca listę źródeł."""
    try:
        loader = SourcesLoader()
        sources = loader.load()

        return jsonify({
            'count': len(sources),
            'sources': [{'id': s.get('id'), 'name': s.get('name'), 'type': s.get('type')} for s in sources]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/industries')
def get_industries():
    """Zwraca listę branż."""
    return jsonify({
        'industries': list(INDUSTRY_KEYWORDS.keys())
    })


@app.route('/ai-status')
def get_ai_status():
    """Sprawdza dostępność weryfikacji AI."""
    verifier = AIVerifier()
    return jsonify({
        'enabled': verifier.is_enabled(),
        'model': 'claude-3-5-haiku-latest' if verifier.is_enabled() else None,
        'cost_estimate': verifier.estimate_cost(100) if verifier.is_enabled() else None
    })


# Obsługa błędów
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Nie znaleziono'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Błąd serwera'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  BIP Search - Wyszukiwarka decyzji środowiskowych")
    print("=" * 60)
    print("\n  Otwórz przeglądarkę i wejdź na adres:")
    print("  \033[1;32mhttp://localhost:8080\033[0m")
    print("\n  Aby zatrzymać aplikację, naciśnij Ctrl+C")
    print("=" * 60 + "\n")

    app.run(
        host='0.0.0.0',
        port=8080,
        debug=False,
        threaded=True
    )
