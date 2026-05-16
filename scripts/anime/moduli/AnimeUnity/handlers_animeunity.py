# =============================================================================
# handlers_animeunity.py
# Modulo: AnimeUnity
# Branch: upgrade-3
# Struttura: /scripts/anime/moduli/animeunity/handlers_animeunity.py
# Riferimento: prompt_nuovo_modulo.txt + logica handlers_animeworld.py
# =============================================================================

import re
import json
import requests

from core.logger import log_debug, log_info, log_error
from core import ui as core_ui
from core.url_manager import get_url

# ---------------------------------------------------------------------------
# COSTANTI E HEADERS
# ---------------------------------------------------------------------------

_BASE_URL: str = ""          # Popolato a runtime da get_url()
_TIMEOUT: int = 15
_MAX_RETRIES: int = 3

_HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.animeunity.so/",
    "X-Requested-With": "XMLHttpRequest",
}

# ---------------------------------------------------------------------------
# REGEX PATTERNS (fallback su HTML se API non disponibile)
# ---------------------------------------------------------------------------

_RE_ANIME_TITLE  = re.compile(r'"title"\s*:\s*"([^"]+)"')
_RE_ANIME_ID     = re.compile(r'"id"\s*:\s*(\d+)')
_RE_EPISODE_ID   = re.compile(r'"id"\s*:\s*(\d+).*?"number"\s*:\s*"([^"]+)"', re.DOTALL)
_RE_VIDEO_URL    = re.compile(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)')
_RE_EMBED_SRC    = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

# ---------------------------------------------------------------------------
# HELPERS PRIVATI
# ---------------------------------------------------------------------------

def _get_base_url() -> str:
    """
    Recupera il base URL da url_manager (lazy init).
    Non hard-coda mai l'URL: usa sempre urls_config.json.
    """
    global _BASE_URL
    if not _BASE_URL:
        _BASE_URL = get_url("animeunity")
        log_debug(f"[animeunity] Base URL caricato: {_BASE_URL}")
    return _BASE_URL


def _get_page(url: str) -> str | None:
    """
    Esegue una richiesta HTTP GET con retry e gestione errori.
    Restituisce il testo della risposta o None in caso di fallimento.
    Gestisce Cloudflare tramite headers realistici (no JS challenge).
    """
    log_debug(f"[animeunity] → _get_page() | URL: {url}")

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=_HEADERS,
                timeout=_TIMEOUT,
                allow_redirects=True,
            )
            log_debug(
                f"[animeunity] _get_page() | "
                f"Tentativo {attempt} | Status: {response.status_code}"
            )

            if response.status_code == 200:
                return response.text

            if response.status_code == 403:
                log_error(
                    f"[animeunity] _get_page() | "
                    f"403 Forbidden — possibile challenge Cloudflare | URL: {url}"
                )
                # Non ritentiamo su 403: inutile senza rotazione IP/cookie
                return None

            if response.status_code == 404:
                log_error(f"[animeunity] _get_page() | 404 Not Found | URL: {url}")
                return None

        except requests.exceptions.Timeout:
            log_error(
                f"[animeunity] _get_page() | "
                f"Timeout al tentativo {attempt} | URL: {url}"
            )
        except requests.exceptions.ConnectionError as exc:
            log_error(
                f"[animeunity] _get_page() | "
                f"Errore connessione al tentativo {attempt}: {exc}"
            )
        except requests.exceptions.RequestException as exc:
            log_error(
                f"[animeunity] _get_page() | "
                f"Errore richiesta al tentativo {attempt}: {exc}"
            )

    log_error(
        f"[animeunity] _get_page() | "
        f"Tutti i {_MAX_RETRIES} tentativi falliti | URL: {url}"
    )
    return None


def _get_api(endpoint: str, params: dict | None = None) -> dict | list | None:
    """
    Esegue una chiamata all'API JSON di AnimeUnity.
    Restituisce il dato JSON parsato o None in caso di errore.
    """
    log_debug(f"[animeunity] → _get_api() | endpoint: {endpoint} | params: {params}")

    base = _get_base_url()
    url  = f"{base}/api/v1/{endpoint}"

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=_HEADERS,
                params=params or {},
                timeout=_TIMEOUT,
                allow_redirects=True,
            )
            log_debug(
                f"[animeunity] _get_api() | "
                f"Tentativo {attempt} | Status: {response.status_code}"
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    log_debug(
                        f"[animeunity] _get_api() | "
                        f"JSON ricevuto, tipo: {type(data).__name__}"
                    )
                    return data
                except json.JSONDecodeError as exc:
                    log_error(
                        f"[animeunity] _get_api() | "
                        f"Errore parsing JSON: {exc}"
                    )
                    return None

            if response.status_code in (403, 404):
                log_error(
                    f"[animeunity] _get_api() | "
                    f"HTTP {response.status_code} | endpoint: {endpoint}"
                )
                return None

        except requests.exceptions.RequestException as exc:
            log_error(
                f"[animeunity] _get_api() | "
                f"Errore al tentativo {attempt}: {exc}"
            )

    return None


def _parse_updated(data: list | dict) -> list[dict]:
    """
    Analizza la risposta API degli aggiornamenti recenti.
    Restituisce una lista di dict: [{title, anime_id, episode, url}, ...]
    """
    log_debug("[animeunity] → _parse_updated()")

    results: list[dict] = []

    try:
        # L'API restituisce {"data": [...]} oppure direttamente [...]
        items = data.get("data", data) if isinstance(data, dict) else data

        log_debug(f"[animeunity] _parse_updated() | Items ricevuti: {len(items)}")

        for item in items:
            title      = item.get("title_it") or item.get("title") or "N/D"
            anime_id   = item.get("id")
            episode    = item.get("last_episode") or item.get("episodes_count", "?")
            slug       = item.get("slug") or ""
            base       = _get_base_url()
            url        = f"{base}/anime/{anime_id}-{slug}" if anime_id else base

            if anime_id:
                results.append({
                    "title":    title,
                    "anime_id": str(anime_id),
                    "episode":  str(episode),
                    "url":      url,
                })

        log_debug(
            f"[animeunity] _parse_updated() | "
            f"Risultati validi: {len(results)}"
        )

    except (TypeError, AttributeError, KeyError) as exc:
        log_error(f"[animeunity] _parse_updated() | Errore parsing: {exc}")

    return results


def _parse_episodes(data: dict) -> list[dict]:
    """
    Analizza la risposta API degli episodi di un anime.
    Restituisce lista di dict: [{number, episode_id, title, url}, ...]
    """
    log_debug("[animeunity] → _parse_episodes()")

    results: list[dict] = []

    try:
        episodes = data.get("data", data) if isinstance(data, dict) else data

        log_debug(f"[animeunity] _parse_episodes() | Episodi ricevuti: {len(episodes)}")

        for ep in episodes:
            ep_id  = ep.get("id")
            number = ep.get("number") or ep.get("episode") or "?"
            title  = ep.get("title") or f"Episodio {number}"
            base   = _get_base_url()
            url    = f"{base}/embed-url/{ep_id}" if ep_id else ""

            if ep_id:
                results.append({
                    "number":     str(number),
                    "episode_id": str(ep_id),
                    "title":      title,
                    "url":        url,
                })

        log_debug(
            f"[animeunity] _parse_episodes() | "
            f"Episodi validi: {len(results)}"
        )

    except (TypeError, AttributeError, KeyError) as exc:
        log_error(f"[animeunity] _parse_episodes() | Errore parsing: {exc}")

    return results


def _parse_video_url(html: str) -> str | None:
    """
    Estrae l'URL video diretto (m3u8 o mp4) dall'HTML della pagina embed.
    Prima cerca m3u8 (HLS), poi mp4 come fallback.
    """
    log_debug(
        f"[animeunity] → _parse_video_url() | "
        f"HTML length: {len(html)}"
    )

    # Tentativo 1: m3u8 HLS (Vixcloud)
    match_m3u8 = _RE_VIDEO_URL.search(html)
    if match_m3u8:
        url = match_m3u8.group(1)
        log_debug(f"[animeunity] _parse_video_url() | m3u8 trovato: {url[:80]}")
        return url

    # Tentativo 2: src iframe embed
    match_embed = _RE_EMBED_SRC.search(html)
    if match_embed:
        url = match_embed.group(1)
        log_debug(f"[animeunity] _parse_video_url() | Embed src trovato: {url[:80]}")
        return url

    # Tentativo 3: ricerca JSON inline per "url" o "stream"
    match_json = re.search(
        r'"(?:url|stream_url|file)"\s*:\s*"(https?://[^"]+)"',
        html
    )
    if match_json:
        url = match_json.group(1)
        log_debug(f"[animeunity] _parse_video_url() | JSON url trovato: {url[:80]}")
        return url

    log_error("[animeunity] _parse_video_url() | Nessun URL video trovato")
    return None


# ---------------------------------------------------------------------------
# API PUBBLICHE
# ---------------------------------------------------------------------------

def get_updated() -> list[dict]:
    """
    Recupera la lista degli anime aggiornati di recente da AnimeUnity.
    Restituisce lista di dict: [{title, anime_id, episode, url}, ...]
    """
    log_debug("[animeunity] → get_updated()")

    data = _get_api("anime", params={"order": "updated_at", "page": 1})

    if data is None:
        show_warning_no_results()
        return []

    results = _parse_updated(data)

    if not results:
        show_warning_no_results()

    return results


def get_episodes(anime_id: str) -> list[dict]:
    """
    Recupera la lista degli episodi per un dato anime_id.
    Restituisce lista di dict: [{number, episode_id, title, url}, ...]
    """
    log_debug(f"[animeunity] → get_episodes() | anime_id: {anime_id}")

    data = _get_api(
        f"anime/{anime_id}/episodes",
        params={"start": 1, "end": 500}
    )

    if data is None:
        core_ui.show_warning(
            f"[AnimeUnity] Impossibile recuperare gli episodi per ID: {anime_id}"
        )
        core_ui.pause()
        return []

    results = _parse_episodes(data)

    if not results:
        core_ui.show_warning(
            f"[AnimeUnity] Nessun episodio trovato per ID: {anime_id}"
        )
        core_ui.pause()

    return results


def get_video_url(episode_id: str) -> str | None:
    """
    Recupera l'URL video diretto per un dato episode_id.
    Usa l'endpoint embed-url e poi parsifica l'HTML risultante.
    Restituisce l'URL stringa o None.
    """
    log_debug(f"[animeunity] → get_video_url() | episode_id: {episode_id}")

    base = _get_base_url()
    url  = f"{base}/embed-url/{episode_id}"
    html = _get_page(url)

    if html is None:
        core_ui.show_error(
            f"[AnimeUnity] Impossibile caricare la pagina embed per ID: {episode_id}"
        )
        core_ui.pause()
        return None

    video_url = _parse_video_url(html)

    if not video_url:
        core_ui.show_warning(
            "[AnimeUnity] URL video non trovato nella pagina embed."
        )
        core_ui.pause()

    return video_url


def search_anime(query: str) -> list[dict]:
    """
    Cerca anime per titolo tramite API AnimeUnity.
    Restituisce lista di dict: [{title, anime_id, url}, ...]
    """
    log_debug(f"[animeunity] → search_anime() | query: '{query}'")

    data = _get_api("anime", params={"title": query, "page": 1})

    if data is None:
        core_ui.show_warning(f"[AnimeUnity] Nessun risultato per: {query}")
        core_ui.pause()
        return []

    results: list[dict] = []
    items = data.get("data", data) if isinstance(data, dict) else data

    for item in items:
        title    = item.get("title_it") or item.get("title") or "N/D"
        anime_id = item.get("id")
        slug     = item.get("slug") or ""
        base     = _get_base_url()
        url      = f"{base}/anime/{anime_id}-{slug}" if anime_id else base

        if anime_id:
            results.append({
                "title":    title,
                "anime_id": str(anime_id),
                "url":      url,
            })

    log_debug(f"[animeunity] search_anime() | Risultati: {len(results)}")

    if not results:
        core_ui.show_warning(f"[AnimeUnity] Nessun risultato per: {query}")
        core_ui.pause()

    return results


# ---------------------------------------------------------------------------
# UI — WARNING HELPERS
# ---------------------------------------------------------------------------

def show_warning_no_results() -> None:
    """Mostra un avviso quando non ci sono aggiornamenti disponibili."""
    log_debug("[animeunity] → show_warning_no_results()")
    core_ui.show_warning(
        "[AnimeUnity] Nessun aggiornamento disponibile al momento."
    )
    core_ui.pause()


def show_warning_connection() -> None:
    """Mostra un avviso in caso di errore di connessione."""
    log_debug("[animeunity] → show_warning_connection()")
    core_ui.show_warning(
        "[AnimeUnity] Errore di connessione. Verifica la tua rete o riprova più tardi."
    )
    core_ui.pause()


# ---------------------------------------------------------------------------
# MENU PRINCIPALE DEL MODULO
# ---------------------------------------------------------------------------

def show_menu() -> None:
    """
    Mostra il menu principale del modulo AnimeUnity.
    Entry point chiamato da main_menu.py.
    """
    log_debug("[animeunity] → show_menu()")

    while True:
        scelta = core_ui.menu({
            "1": "📺  Ultimi aggiornamenti",
            "2": "🔍  Cerca anime",
            "0": "← Torna al menu principale",
        })

        if scelta == "1":
            log_debug("[animeunity] show_menu() | Scelta: Ultimi aggiornamenti")
            aggiornamenti = get_updated()
            if aggiornamenti:
                _show_updated_list(aggiornamenti)

        elif scelta == "2":
            log_debug("[animeunity] show_menu() | Scelta: Cerca anime")
            query = core_ui.input_text("Inserisci il titolo da cercare: ")
            if query and query.strip():
                risultati = search_anime(query.strip())
                if risultati:
                    _show_search_results(risultati)

        elif scelta == "0":
            log_debug("[animeunity] show_menu() | Uscita menu")
            break

        else:
            core_ui.show_warning("[AnimeUnity] Scelta non valida.")
            core_ui.pause()


# ---------------------------------------------------------------------------
# UI — HELPERS INTERNI MENU
# ---------------------------------------------------------------------------

def _show_updated_list(aggiornamenti: list[dict]) -> None:
    """Mostra la lista aggiornamenti e permette di selezionare un anime."""
    log_debug(
        f"[animeunity] → _show_updated_list() | "
        f"Aggiornamenti: {len(aggiornamenti)}"
    )

    opzioni: dict = {}
    for i, item in enumerate(aggiornamenti, start=1):
        label = f"{item['title']}  [Ep. {item['episode']}]"
        opzioni[str(i)] = label
    opzioni["0"] = "← Indietro"

    scelta = core_ui.menu(opzioni)

    if scelta == "0" or not scelta:
        return

    try:
        idx  = int(scelta) - 1
        item = aggiornamenti[idx]
        log_debug(
            f"[animeunity] _show_updated_list() | "
            f"Selezionato: {item['title']} (ID: {item['anime_id']})"
        )
        _show_episodes_menu(item["anime_id"], item["title"])
    except (ValueError, IndexError):
        core_ui.show_warning("[AnimeUnity] Selezione non valida.")
        core_ui.pause()


def _show_search_results(risultati: list[dict]) -> None:
    """Mostra i risultati di ricerca e permette di selezionare un anime."""
    log_debug(
        f"[animeunity] → _show_search_results() | "
        f"Risultati: {len(risultati)}"
    )

    opzioni: dict = {}
    for i, item in enumerate(risultati, start=1):
        opzioni[str(i)] = item["title"]
    opzioni["0"] = "← Indietro"

    scelta = core_ui.menu(opzioni)

    if scelta == "0" or not scelta:
        return

    try:
        idx  = int(scelta) - 1
        item = risultati[idx]
        log_debug(
            f"[animeunity] _show_search_results() | "
            f"Selezionato: {item['title']} (ID: {item['anime_id']})"
        )
        _show_episodes_menu(item["anime_id"], item["title"])
    except (ValueError, IndexError):
        core_ui.show_warning("[AnimeUnity] Selezione non valida.")
        core_ui.pause()


def _show_episodes_menu(anime_id: str, anime_title: str) -> None:
    """Mostra la lista episodi di un anime e gestisce la selezione."""
    log_debug(
        f"[animeunity] → _show_episodes_menu() | "
        f"anime_id: {anime_id} | title: {anime_title}"
    )

    core_ui.show_info(f"[AnimeUnity] Caricamento episodi: {anime_title} ...")
    episodi = get_episodes(anime_id)

    if not episodi:
        return

    opzioni: dict = {}
    for ep in episodi:
        label = f"Ep. {ep['number']} — {ep['title']}"
        opzioni[ep["episode_id"]] = label
    opzioni["0"] = "← Indietro"

    scelta = core_ui.menu(opzioni)

    if scelta == "0" or not scelta:
        return

    # Cerca l'episodio selezionato
    ep_selezionato = next(
        (ep for ep in episodi if ep["episode_id"] == scelta),
        None
    )

    if ep_selezionato:
        log_debug(
            f"[animeunity] _show_episodes_menu() | "
            f"Episodio selezionato: {ep_selezionato['number']} "
            f"(ID: {ep_selezionato['episode_id']})"
        )
        core_ui.show_info(
            f"[AnimeUnity] Recupero URL video per "
            f"Ep. {ep_selezionato['number']} ..."
        )
        video_url = get_video_url(ep_selezionato["episode_id"])

        if video_url:
            core_ui.show_success(f"[AnimeUnity] URL Video:\n{video_url}")
            core_ui.pause()
        # Se None: i warning sono già gestiti in get_video_url()
    else:
        core_ui.show_warning("[AnimeUnity] Episodio non trovato.")
        core_ui.pause()