"""
Modulo AnimeWorld — Download Center upgrade-3
Logica adattata da Stream4me/addon channels/animeworld.py
UI e integrazione seguono il pattern di handlers_animeunity.py
(Core, url_manager, progress.spinner, ui).
"""

from __future__ import annotations

import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.core.logger import get_logger, log_debug

logger = get_logger(__name__)

MODULE_KEY = "animeworld"
MODULE_NAME = "AnimeWorld"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_BASE_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Regex patterns (da Stream4me/addon channels/animeworld.py, adattati) ──────

# Cookie SecurityAW dal JS inline
_RE_SECURITY_COOKIE = re.compile(r'document\.cookie="([^\s;]+)', re.IGNORECASE)

# Lista anime da /filter (titoli, thumb, url)
_RE_ANIME_LIST = re.compile(
    r'<div class="inner">\s*<a href="(?P<url>[^"]+)" class[^>]+>\s*'
    r'<img[^>]+src="(?P<thumb>[^"]+)" alt?="(?P<title>[^\("]+)'
    r'(?:\((?P<lang>[^\)]+)\))?[^"]*"',
    re.DOTALL | re.IGNORECASE,
)

# Lista ultimi episodi da /updated (include numero episodio)
_RE_UPDATED_LIST = re.compile(
    r'<div class="inner">\s*<a href="(?P<url>[^"]+)" class[^>]+>\s*'
    r'<img[^>]+src="(?P<thumb>[^"]+)" alt?="(?P<title>[^\("]+)'
    r'(?:\((?P<lang>[^\)]+)\))?"[^>]+>[^>]+>.*?'
    r'<div class="ep">[^\d]+(?P<episode>\d+)[^<]*</div>',
    re.DOTALL | re.IGNORECASE,
)

# Paginazione
_RE_NEXT_PAGE = re.compile(r'<a href="([^"]+)" class="[^"]+" id="go-next', re.IGNORECASE)

# Blocco server attivo sulla pagina episodio/serie
_RE_SERVER_BLOCK = re.compile(
    r'<div class="server\s*active\s*"(?P<block>.*?)(?:<div class="server|<link)',
    re.DOTALL | re.IGNORECASE,
)

# Link episodi dentro il blocco server
_RE_EPISODE_LINK = re.compile(
    r'<li[^>]*>\s*<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<episode>[^-<]+)(?:-(?P<ep2>[^<]+))?',
    re.IGNORECASE,
)

# Server data-name e data-id per l'API episode info
_RE_DATA_NAME = re.compile(r'data-name="(\d+)">([^<]+)<', re.IGNORECASE)
_RE_DATA_ID = re.compile(r'data-id="([^"]+)"', re.IGNORECASE)

# Fallback: link download diretto
_RE_ALT_DOWNLOAD = re.compile(r'href="([^"]+)"\s*id="alternativeDownloadLink"', re.IGNORECASE)

# Cache cookie per sessione (base_url -> cookie string)
_cookie_cache: Dict[str, str] = {}


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _http_session() -> requests.Session:
    log_debug(f"[{MODULE_KEY}] → _http_session()")
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update(_BASE_HEADERS)
    return s


def _base_url(core) -> Optional[str]:
    log_debug(f"[{MODULE_KEY}] → _base_url()")
    url = core.url_manager.get_url(MODULE_KEY, "base_url")
    return url.rstrip("/") if url else None


def _refresh_cookie(base: str, html: str) -> str:
    """Estrae e memorizza il cookie SecurityAW dal JS nella pagina."""
    log_debug(f"[{MODULE_KEY}] → _refresh_cookie()")
    m = _RE_SECURITY_COOKIE.search(html)
    if m:
        cookie = m.group(1)
        _cookie_cache[base] = cookie
        log_debug(f"[{MODULE_KEY}] SecurityAW cookie aggiornato")
        return cookie
    return _cookie_cache.get(base, "")


def _request_headers(base: str) -> dict:
    """Headers con cookie corrente."""
    h = dict(_BASE_HEADERS)
    cookie = _cookie_cache.get(base, "")
    if cookie:
        h["Cookie"] = cookie
    h["Referer"] = base + "/"
    return h


def _get_page(url: str, base: str, retry_on_challenge: bool = True) -> Optional[str]:
    """
    Scarica una pagina AnimeWorld gestendo il challenge SecurityAW.
    Se la pagina contiene 'SecurityAW', estrae il cookie e ritenta una volta.
    """
    log_debug(f"[{MODULE_KEY}] → _get_page() url={url[:80]}")
    try:
        s = _http_session()
        r = s.get(url, headers=_request_headers(base), timeout=25, allow_redirects=True)
        html = r.text
        if "SecurityAW" in html and retry_on_challenge:
            log_debug(f"[{MODULE_KEY}] SecurityAW challenge rilevato — aggiorno cookie e riprovo")
            _refresh_cookie(base, html)
            r2 = s.get(url, headers=_request_headers(base), timeout=25, allow_redirects=True)
            html = r2.text
            if "SecurityAW" in html:
                log_debug(f"[{MODULE_KEY}] Challenge SecurityAW persiste dopo retry")
                return None
        return html
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _get_page error: {exc}")
        return None


# ── Parsing ────────────────────────────────────────────────────────────────────

def _parse_anime_list(html: str, base: str, updated: bool = False) -> List[dict]:
    """
    Parsa la lista anime da /filter o /updated.
    updated=True usa il pattern con numero episodio.
    """
    log_debug(f"[{MODULE_KEY}] → _parse_anime_list()")
    log_debug(f"[{MODULE_KEY}] html len={len(html)}")
    results: List[dict] = []
    pat = _RE_UPDATED_LIST if updated else _RE_ANIME_LIST
    for m in pat.finditer(html):
        url = (m.group("url") or "").strip()
        title = (m.group("title") or "").strip()
        if not title or not url:
            continue
        if not url.startswith("http"):
            url = base + url
        ep = m.group("episode") if updated else None
        results.append({
            "titolo": title,
            "url": url,
            "thumb": m.group("thumb") or "",
            "ep_label": f"Ep. {ep}" if ep else "",
            "modulo": MODULE_KEY,
        })
    log_debug(f"[{MODULE_KEY}] risultati trovati: {len(results)}")
    return results


def _fetch_updated(base: str) -> List[dict]:
    """Ultimi episodi pubblicati da /updated (max 2 pagine)."""
    log_debug(f"[{MODULE_KEY}] → _fetch_updated()")
    results: List[dict] = []
    url: Optional[str] = f"{base}/updated"
    pages = 0
    while url and pages < 2:
        html = _get_page(url, base)
        if not html:
            break
        results.extend(_parse_anime_list(html, base, updated=True))
        pages += 1
        m = _RE_NEXT_PAGE.search(html)
        if m:
            nxt = m.group(1)
            url = nxt if nxt.startswith("http") else base + nxt
        else:
            break
    return results


def _fetch_search(base: str, keyword: str) -> List[dict]:
    """Cerca anime per keyword su /filter (max 3 pagine)."""
    log_debug(f"[{MODULE_KEY}] → _fetch_search() keyword={keyword}")
    results: List[dict] = []
    url: Optional[str] = f"{base}/filter?keyword={quote(keyword)}&sort="
    pages = 0
    while url and pages < 3:
        html = _get_page(url, base)
        if not html:
            break
        results.extend(_parse_anime_list(html, base, updated=False))
        pages += 1
        m = _RE_NEXT_PAGE.search(html)
        if m and len(results) < 200:
            nxt = m.group(1)
            url = nxt if nxt.startswith("http") else base + nxt
        else:
            break
    return results


def _fetch_episodes(base: str, show_url: str) -> List[dict]:
    """
    Restituisce la lista episodi di una serie dalla pagina show.
    Parsa il blocco 'server active' → lista <li><a href=...>.
    """
    log_debug(f"[{MODULE_KEY}] → _fetch_episodes() url={show_url[:80]}")
    html = _get_page(show_url, base)
    if not html:
        return []
    block_m = _RE_SERVER_BLOCK.search(html)
    block = block_m.group("block") if block_m else html
    episodes: List[dict] = []
    for m in _RE_EPISODE_LINK.finditer(block):
        ep_url = (m.group("url") or "").strip()
        ep_label = (m.group("episode") or "").strip()
        if not ep_url:
            continue
        if not ep_url.startswith("http"):
            ep_url = base + ep_url
        episodes.append({"url": ep_url, "label": ep_label})
    log_debug(f"[{MODULE_KEY}] episodi trovati: {len(episodes)}")
    return episodes


def _resolve_episode_video(base: str, ep_url: str) -> Optional[str]:
    """
    Risolve URL video per un episodio AnimeWorld.
    Strategia (da Stream4me/addon channels/animeworld.py):
      1) Trova data-name / data-id nella pagina episodio
      2) Chiama /api/episode/info?id={ep_id}&alt=0 → JSON con chiave 'grabber'
      3) Fallback: href id='alternativeDownloadLink'
    """
    log_debug(f"[{MODULE_KEY}] → _resolve_episode_video() url={ep_url[:80]}")
    html = _get_page(ep_url, base)
    if not html:
        return None

    # Metodo 1: API episode info per ogni server
    for server_id, server_name in _RE_DATA_NAME.findall(html):
        # Cerca data-id nel contesto del server
        pat_block = re.compile(
            r'data-name="' + re.escape(server_id) + r'"[^>]*>(.*?)'
            r'(?:data-name="\d+"|</ul>|$)',
            re.DOTALL | re.IGNORECASE,
        )
        bm = pat_block.search(html)
        block_html = bm.group(1) if bm else html
        id_m = _RE_DATA_ID.search(block_html)
        if not id_m:
            continue
        ep_id = id_m.group(1)
        try:
            api_url = f"{base}/api/episode/info?id={ep_id}&alt=0"
            h = dict(_request_headers(base))
            h["Accept"] = "application/json, */*"
            r = _http_session().get(api_url, headers=h, timeout=15)
            if r.status_code == 200:
                data = r.json()
                grabber = (data.get("grabber") or "").strip()
                if grabber:
                    log_debug(f"[{MODULE_KEY}] grabber trovato: {grabber[:60]}")
                    return grabber
        except Exception as exc:
            log_debug(f"[{MODULE_KEY}] API episode info error: {exc}")

    # Fallback: alternativeDownloadLink
    dl_m = _RE_ALT_DOWNLOAD.search(html)
    if dl_m:
        url = dl_m.group(1).strip()
        log_debug(f"[{MODULE_KEY}] alternativeDownloadLink: {url[:60]}")
        return url

    log_debug(f"[{MODULE_KEY}] nessun URL video trovato per {ep_url}")
    return None


# ── UI helpers ─────────────────────────────────────────────────────────────────

def _trunc(text: str, max_len: int = 44) -> str:
    s = str(text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _pause_continue(core) -> None:
    core.ui.pause()
    core.ui.clear()


def _build_list_menu(
    rows: List[dict],
    label_key: str = "titolo",
    desc_key: str = "ep_label",
) -> List[dict]:
    menu: List[dict] = []
    for i, row in enumerate(rows, start=1):
        menu.append({
            "key": str(i),
            "icon": "",
            "label": _trunc(row.get(label_key, "?"), 40),
            "desc": _trunc(row.get(desc_key) or "", 28),
        })
    return menu


def _menu_index(choice: str, count: int) -> Optional[int]:
    if not choice or choice == "0":
        return None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < count:
            return idx
    return -1


def _pick_from_list(
    core,
    title: str,
    items: List[dict],
    label_key: str = "titolo",
    desc_key: str = "ep_label",
) -> Optional[dict]:
    """Menu selezione da lista con loop."""
    while True:
        menu = _build_list_menu(items, label_key=label_key, desc_key=desc_key)
        c = core.ui.show_menu(title, menu, show_version=False)
        if c == "0":
            return None
        idx = _menu_index(c, len(items))
        if idx is None:
            continue
        if idx < 0:
            core.ui.error("Voce non valida.")
            _pause_continue(core)
            continue
        return items[idx]


# ── Azioni principali ──────────────────────────────────────────────────────────

def _dettaglio_episodi(core, show_url: str, titolo: str) -> None:
    """Menu episodi di una serie: selezione + risoluzione URL video."""
    log_debug(f"[{MODULE_KEY}] → _dettaglio_episodi()")
    base = _base_url(core)
    if not base:
        core.ui.error("URL AnimeWorld non configurato.")
        _pause_continue(core)
        return

    core.ui.clear()
    core.progress.spinner_start("Caricamento episodi...")
    try:
        episodes = _fetch_episodes(base, show_url)
    finally:
        core.progress.spinner_stop()

    if not episodes:
        core.ui.warning(f"Nessun episodio trovato per: {titolo}")
        core.ui.pause()
        return

    while True:
        menu: List[dict] = []
        for i, ep in enumerate(episodes, start=1):
            menu.append({
                "key": str(i),
                "icon": "",
                "label": ep.get("label") or f"Ep. {i}",
                "desc": "",
            })
        c = core.ui.show_menu(
            f"{MODULE_NAME} — {_trunc(titolo, 30)}",
            menu,
            show_version=False,
        )
        if c == "0":
            return

        idx = _menu_index(c, len(episodes))
        if idx is None:
            continue
        if idx < 0:
            core.ui.error("Voce non valida.")
            _pause_continue(core)
            continue

        ep = episodes[idx]
        label = ep.get("label") or str(idx + 1)
        core.progress.spinner_start(f"Risoluzione URL ep. {label}...")
        try:
            video_url = _resolve_episode_video(base, ep["url"])
        finally:
            core.progress.spinner_stop()

        if video_url:
            core.ui.show_success(f"URL video:\n{video_url}")
        else:
            core.ui.warning("URL video non disponibile per questo episodio.")
        _pause_continue(core)


def _ultime_uscite(core) -> None:
    """Mostra gli ultimi episodi pubblicati da /updated."""
    log_debug(f"[{MODULE_KEY}] → _ultime_uscite()")
    base = _base_url(core)
    if not base:
        core.ui.error("URL AnimeWorld non configurato.")
        _pause_continue(core)
        return

    core.ui.clear()
    core.progress.spinner_start("Caricamento ultimi episodi...")
    try:
        items = _fetch_updated(base)
    finally:
        core.progress.spinner_stop()

    if not items:
        core.ui.warning("Nessun risultato trovato.")
        core.ui.pause()
        return

    picked = _pick_from_list(
        core,
        f"{MODULE_NAME} — Ultimi episodi",
        items,
        label_key="titolo",
        desc_key="ep_label",
    )
    if picked:
        _dettaglio_episodi(core, picked["url"], picked["titolo"])


def _ricerca(core) -> None:
    """Ricerca anime per titolo su /filter."""
    log_debug(f"[{MODULE_KEY}] → _ricerca()")
    base = _base_url(core)
    if not base:
        core.ui.error("URL AnimeWorld non configurato.")
        _pause_continue(core)
        return

    core.ui.clear()
    keyword = core.ui.ask_input("Titolo da cercare (0=annulla)")
    if keyword == "0" or not keyword:
        return

    core.progress.spinner_start("Ricerca in corso...")
    try:
        items = _fetch_search(base, keyword)
    finally:
        core.progress.spinner_stop()

    if not items:
        core.ui.warning(f'Nessun risultato per "{keyword}".')
        core.ui.pause()
        return

    picked = _pick_from_list(
        core,
        f'{MODULE_NAME} — "{_trunc(keyword, 20)}"',
        items,
        label_key="titolo",
        desc_key="ep_label",
    )
    if picked:
        _dettaglio_episodi(core, picked["url"], picked["titolo"])


# ── Entry point pubblici ───────────────────────────────────────────────────────

def run() -> None:
    """Entry point principale — richiesto da anime.json / handlers_anime_video."""
    log_debug(f"[{MODULE_KEY}] → run()")
    from scripts.core import Core

    core = Core.get()
    if not _base_url(core):
        core.ui.error(
            "URL AnimeWorld non configurato. "
            "Vai in Impostazioni → URL moduli."
        )
        core.ui.pause()
        return

    items = [
        {"key": "1", "icon": "", "label": "Ultime uscite", "desc": "Ultimi episodi pubblicati"},
        {"key": "2", "icon": "", "label": "Ricerca", "desc": "Cerca per titolo"},
    ]
    while True:
        c = core.ui.show_menu(MODULE_NAME, items)
        if c == "0":
            return
        if c == "1":
            _ultime_uscite(core)
        elif c == "2":
            _ricerca(core)
        else:
            core.ui.error("Voce non valida.")
            _pause_continue(core)


def search(titolo: str) -> List[dict]:
    """[SILENT] Ricerca silenziosa — usata da handlers_ricerca_globale."""
    log_debug(f"[{MODULE_KEY}] → search()")
    try:
        from scripts.core import Core
        core = Core.get()
        base = _base_url(core)
        if not base:
            return []
        return _fetch_search(base, titolo)
    except Exception:
        return []


def get_episodes(show_url: str) -> List[str]:
    """[SILENT] Restituisce URL video per ogni episodio (link_extractor)."""
    log_debug(f"[{MODULE_KEY}] → get_episodes()")
    try:
        from scripts.core import Core
        core = Core.get()
        base = _base_url(core)
        if not base:
            return []
        episodes = _fetch_episodes(base, show_url)
        urls: List[str] = []
        for ep in episodes:
            url = _resolve_episode_video(base, ep["url"])
            if url:
                urls.append(url)
        return urls
    except Exception:
        return []


def show_menu() -> None:
    """Alias retrocompatibile."""
    run()
