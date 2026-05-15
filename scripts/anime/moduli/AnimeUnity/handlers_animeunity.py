# =============================================================================
# handlers_animeunity.py — Modulo AnimeUnity
# Progetto: PID1381/downloadcenter | Branch: upgrade-3
# Data: 15 Maggio 2026
#
# Descrizione:
#   Scraper per AnimeUnity (animeunity.so) — streaming anime in italiano.
#   Accede alle API REST JSON di AnimeUnity per elencare anime recenti,
#   effettuare ricerche e recuperare episodi con link di streaming.
#
# Funzioni pubbliche:
#   - get_updated()     → Elenca gli anime con nuovi episodi recenti
#   - get_episodes(id)  → Recupera tutti gli episodi di un anime
#   - search_anime(q)   → Ricerca anime per titolo
#   - show_menu()       → Menu principale del modulo
# =============================================================================

import re
import time
import requests

from scripts.core.logger import get_logger, log_debug, log_info, log_error
from scripts.core import ui as core_ui
from scripts.core.url_manager import get_url

logger = get_logger(__name__)

# ─── SEZIONE 2 — COSTANTI E CONFIGURAZIONE ───────────────────────────────────

BASE_URL = get_url("animeunity")          # es. "https://www.animeunity.so"
API_BASE = f"{BASE_URL}/api/v1"

# Timeout e retry
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2

# Headers HTTP standard
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": BASE_URL,
}

# Pattern regex per validazione slug/id
RE_ANIME_ID = re.compile(r"^\d+$")
RE_SLUG     = re.compile(r"^[a-z0-9\-]+$", re.IGNORECASE)

# ─── SEZIONE 3 — FUNZIONE DI CARICAMENTO PAGINA ──────────────────────────────

def _get_json(endpoint: str, params: dict = None) -> dict | None:
    """
    Esegue una richiesta GET all'API di AnimeUnity e restituisce il JSON.
    Gestisce retry automatici e logging degli errori.

    Args:
        endpoint: path relativo all'API (es. '/anime/new-season')
        params:   parametri query opzionali

    Returns:
        dict con la risposta JSON, oppure None in caso di errore.
    """
    log_debug(f"[animeunity] → _get_json() endpoint={endpoint}")

    url = f"{API_BASE}{endpoint}"
    log_debug(f"[animeunity] GET {url} params={params}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=_HEADERS,
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            log_debug(
                f"[animeunity] HTTP {resp.status_code} "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429:
                # Rate limit: attendi prima del retry
                log_info("[animeunity] Rate limit (429) — attendo 3s")
                time.sleep(3)
                continue

            log_error(
                f"[animeunity] Risposta non valida: "
                f"HTTP {resp.status_code} per {url}"
            )
            return None

        except requests.exceptions.Timeout:
            log_error(
                f"[animeunity] Timeout (attempt {attempt}/{MAX_RETRIES}) "
                f"per {url}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(1)

        except requests.exceptions.ConnectionError as e:
            log_error(f"[animeunity] Errore connessione: {e}")
            return None

        except Exception as e:
            log_error(f"[animeunity] Errore imprevisto in _get_json(): {e}")
            return None

    return None


# ─── SEZIONE 4 — FUNZIONI DI PARSING ─────────────────────────────────────────

def _parse_anime_list(data: dict) -> list[dict]:
    """
    Parsa una risposta API contenente una lista di anime.

    Args:
        data: dict con chiave 'data' (lista) o lista diretta

    Returns:
        Lista di dict con chiavi: id, title, cover, episodes_count, slug
    """
    log_debug("[animeunity] → _parse_anime_list()")

    if not data:
        log_debug("[animeunity] data vuoto in _parse_anime_list()")
        return []

    # La risposta può essere paginata {'data': [...]} o lista diretta
    items = data.get("data", data) if isinstance(data, dict) else data

    if not isinstance(items, list):
        log_debug(f"[animeunity] items non è lista: {type(items)}")
        return []

    log_debug(f"[animeunity] html len={len(str(data))}")

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue

        anime_id = item.get("id")
        title    = item.get("title") or item.get("title_it") or "N/D"
        cover    = item.get("imageurl") or item.get("cover") or ""
        ep_count = item.get("episodes_count", 0)
        slug     = item.get("slug", "")

        if anime_id is None:
            continue

        result.append({
            "id":             anime_id,
            "title":          title,
            "cover":          cover,
            "episodes_count": ep_count,
            "slug":           slug,
        })

    log_debug(f"[animeunity] _parse_anime_list() → {len(result)} anime")
    return result


def _parse_episodes(data: dict) -> list[dict]:
    """
    Parsa la risposta API per la lista episodi di un anime.

    Args:
        data: dict con chiave 'episodes' o lista diretta

    Returns:
        Lista di dict con chiavi: id, number, title, video_url
    """
    log_debug("[animeunity] → _parse_episodes()")

    if not data:
        log_debug("[animeunity] data vuoto in _parse_episodes()")
        return []

    episodes = data.get("episodes", data.get("data", []))

    if not isinstance(episodes, list):
        log_debug(f"[animeunity] episodes non è lista: {type(episodes)}")
        return []

    log_debug(f"[animeunity] html len={len(str(data))}")

    result = []
    for ep in episodes:
        if not isinstance(ep, dict):
            continue

        ep_id     = ep.get("id")
        ep_number = ep.get("number", ep.get("episode", "?"))
        ep_title  = ep.get("title") or f"Episodio {ep_number}"
        ep_url    = ep.get("link") or ep.get("video_url") or ""

        if ep_id is None:
            continue

        # Se non c'è URL diretto, costruiamo l'embed URL
        if not ep_url:
            ep_url = f"{BASE_URL}/embed-url/{ep_id}"

        result.append({
            "id":        ep_id,
            "number":    ep_number,
            "title":     ep_title,
            "video_url": ep_url,
        })

    log_debug(f"[animeunity] _parse_episodes() → {len(result)} episodi")
    return result


# ─── SEZIONE 5 — FUNZIONI PUBBLICHE PRINCIPALI ───────────────────────────────

def get_updated() -> list[dict]:
    """
    Entry point: recupera gli anime con episodi recenti/aggiornati.

    Returns:
        Lista di dict anime, oppure lista vuota.
    """
    log_debug("[animeunity] → get_updated()")

    data = _get_json("/anime/new-season")

    if data is None:
        _show_warning_connection()
        return []

    anime_list = _parse_anime_list(data)

    if not anime_list:
        _show_warning_empty("aggiornamenti recenti")
        return []

    log_info(f"[animeunity] get_updated() → {len(anime_list)} anime trovati")
    return anime_list


def get_episodes(anime_id: int | str) -> list[dict]:
    """
    Recupera tutti gli episodi di un anime dato il suo ID.

    Args:
        anime_id: ID numerico dell'anime su AnimeUnity

    Returns:
        Lista di dict episodi, oppure lista vuota.
    """
    log_debug(f"[animeunity] → get_episodes() anime_id={anime_id}")

    if not anime_id:
        log_error("[animeunity] get_episodes() chiamato con anime_id vuoto")
        return []

    data = _get_json(f"/anime/{anime_id}")

    if data is None:
        _show_warning_connection()
        return []

    episodes = _parse_episodes(data)

    if not episodes:
        _show_warning_empty(f"episodi per anime ID {anime_id}")
        return []

    log_info(
        f"[animeunity] get_episodes({anime_id}) → "
        f"{len(episodes)} episodi trovati"
    )
    return episodes


def search_anime(query: str) -> list[dict]:
    """
    Ricerca anime per titolo tramite API AnimeUnity.

    Args:
        query: stringa di ricerca (titolo parziale o completo)

    Returns:
        Lista di dict anime corrispondenti, oppure lista vuota.
    """
    log_debug(f"[animeunity] → search_anime() query='{query}'")

    if not query or not query.strip():
        log_error("[animeunity] search_anime() chiamato con query vuota")
        core_ui.show_warning("Inserisci un termine di ricerca valido.")
        core_ui.pause()
        return []

    data = _get_json("/anime", params={"title": query.strip()})

    if data is None:
        _show_warning_connection()
        return []

    anime_list = _parse_anime_list(data)

    if not anime_list:
        _show_warning_empty(f"risultati per '{query}'")
        return []

    log_info(
        f"[animeunity] search_anime('{query}') → "
        f"{len(anime_list)} risultati"
    )
    return anime_list


# ─── SEZIONE 6 — FUNZIONI UI E MENU ──────────────────────────────────────────

def show_menu() -> None:
    """
    Menu principale del modulo AnimeUnity.
    Mostra le opzioni disponibili e gestisce il routing.
    """
    log_debug("[animeunity] → show_menu()")

    options = [
        "📺  Ultimi aggiornamenti",
        "🔍  Cerca anime",
        "⬅️  Torna al menu principale",
    ]

    choice = core_ui.menu(options)
    log_debug(f"[animeunity] show_menu() scelta={choice}")

    if choice == 0:
        # Ultimi aggiornamenti
        anime_list = get_updated()
        if anime_list:
            _show_anime_list(anime_list)

    elif choice == 1:
        # Ricerca
        query = core_ui.input_text("Cerca anime su AnimeUnity:")
        if query:
            results = search_anime(query)
            if results:
                _show_anime_list(results)

    elif choice == 2:
        # Torna indietro — nessuna azione, il chiamante gestisce il ritorno
        log_debug("[animeunity] Utente ha scelto 'Torna al menu principale'")

    else:
        log_debug(f"[animeunity] Scelta non riconosciuta: {choice}")


def _show_anime_list(anime_list: list[dict]) -> None:
    """
    Mostra la lista degli anime e permette di selezionarne uno
    per visualizzarne gli episodi.

    Args:
        anime_list: lista di dict anime da mostrare
    """
    log_debug(f"[animeunity] → _show_anime_list() n={len(anime_list)}")

    titles = [
        f"{a['title']}  [{a['episodes_count']} ep.]"
        for a in anime_list
    ]
    titles.append("⬅️  Indietro")

    choice = core_ui.menu(titles)

    if choice < 0 or choice >= len(anime_list):
        # Indietro o selezione non valida
        return

    selected = anime_list[choice]
    log_debug(
        f"[animeunity] Selezionato anime: "
        f"id={selected['id']} title='{selected['title']}'"
    )

    episodes = get_episodes(selected["id"])
    if episodes:
        _show_episode_list(selected["title"], episodes)


def _show_episode_list(anime_title: str, episodes: list[dict]) -> None:
    """
    Mostra la lista degli episodi di un anime e permette di
    copiare/visualizzare il link di streaming.

    Args:
        anime_title: titolo dell'anime (per header UI)
        episodes:    lista di dict episodi
    """
    log_debug(
        f"[animeunity] → _show_episode_list() "
        f"anime='{anime_title}' n={len(episodes)}"
    )

    ep_titles = [
        f"Ep. {ep['number']} — {ep['title']}"
        for ep in episodes
    ]
    ep_titles.append("⬅️  Indietro")

    core_ui.show_info(f"Episodi di: {anime_title}")
    choice = core_ui.menu(ep_titles)

    if choice < 0 or choice >= len(episodes):
        return

    selected_ep = episodes[choice]
    video_url   = selected_ep["video_url"]

    log_info(
        f"[animeunity] Episodio selezionato: "
        f"Ep.{selected_ep['number']} — URL: {video_url}"
    )
    core_ui.show_success(
        f"Link episodio {selected_ep['number']}:\n{video_url}"
    )
    core_ui.pause()


# ─── FUNZIONI DI WARNING INTERNE ─────────────────────────────────────────────

def _show_warning_connection() -> None:
    """Mostra avviso di errore di connessione e attende input utente."""
    log_debug("[animeunity] → _show_warning_connection()")
    core_ui.show_warning(
        "[AnimeUnity] Impossibile raggiungere il server.\n"
        "Controlla la connessione o l'URL in urls_config.json."
    )
    core_ui.pause()   # OBBLIGATORIO dopo ogni warning


def _show_warning_empty(risorsa: str) -> None:
    """
    Mostra avviso lista vuota e attende input utente.

    Args:
        risorsa: descrizione della risorsa non trovata (per il messaggio)
    """
    log_debug("[animeunity] → _show_warning_empty()")
    core_ui.show_warning(
        f"[AnimeUnity] Nessun risultato trovato per: {risorsa}."
    )
    core_ui.pause()   # OBBLIGATORIO dopo ogni warning