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

# Metadati pagina serie (per watchlist)
_RE_STATO       = re.compile(r'<dt>\s*Stato\s*:?\s*</dt>\s*<dd>\s*([^<]+?)\s*</dd>', re.IGNORECASE)
_RE_EP_TOT      = re.compile(r'<dt>\s*Episodi\s*:?\s*</dt>\s*<dd>\s*(\d+)\s*</dd>', re.IGNORECASE)
_RE_GENERE_META = re.compile(r'<dt>\s*Genere\s*:?\s*</dt>\s*<dd>(.*?)</dd>', re.IGNORECASE | re.DOTALL)
_RE_ANNO        = re.compile(r'<dt>\s*Anno\s*:?\s*</dt>\s*<dd>\s*([^<]+?)\s*</dd>', re.IGNORECASE)

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
        lang = (m.group("lang") or "").strip()
        display_title = f"{title} ({lang})" if lang else title
        results.append({
            "titolo": display_title,
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


def _fetch_ongoing(base: str) -> List[dict]:
    """Serie in corso da /ongoing (max 3 pagine)."""
    log_debug(f"[{MODULE_KEY}] → _fetch_ongoing()")
    results: List[dict] = []
    url: Optional[str] = f"{base}/ongoing"
    pages = 0
    while url and pages < 3:
        html = _get_page(url, base)
        if not html:
            break
        results.extend(_parse_anime_list(html, base, updated=False))
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


def _parse_episode_selection(scelta: str, count: int) -> List[int]:
    """Singolo (3), intervallo (1-5), lista (1,3,7), tutti."""
    log_debug(f"[{MODULE_KEY}] → _parse_episode_selection()")
    s = (scelta or "").strip().lower()
    if not s or s == "0":
        return []
    if s in ("tutti", "all", "*"):
        return list(range(count))
    if "-" in s:
        try:
            a, b = s.split("-", 1)
            start = int(a.strip()) - 1
            end = int(b.strip())
            return [i for i in range(start, end) if 0 <= i < count]
        except ValueError:
            return []
    if "," in s:
        out: List[int] = []
        for part in s.split(","):
            part = part.strip()
            if part.isdigit():
                i = int(part) - 1
                if 0 <= i < count:
                    out.append(i)
        return sorted(set(out))
    if s.isdigit():
        i = int(s) - 1
        return [i] if 0 <= i < count else []
    return []


def _collect_episode_links(
    core,
    episodes: List[dict],
    indices: List[int],
    base: str,
) -> List[str]:
    """Risolve e raccoglie i link video degli episodi selezionati."""
    log_debug(f"[{MODULE_KEY}] → _collect_episode_links()")
    lines: List[str] = []
    for i in indices:
        ep = episodes[i]
        label = ep.get("label") or str(i + 1)
        core.progress.spinner_start(f"Ep. {label} — estrazione link...")
        try:
            url = _resolve_episode_video(base, ep["url"])
        finally:
            core.progress.spinner_stop()
        if url:
            lines.append(f"Ep. {label}\t{url}")
        else:
            lines.append(f"Ep. {label}\t[non disponibile]")
    return lines


def _export_episode_links(
    core,
    episodes: List[dict],
    titolo: str,
    base: str,
) -> None:
    """Esporta link video episodi selezionati in varie/Link."""
    log_debug(f"[{MODULE_KEY}] → _export_episode_links()")
    print()
    core.ui.show_info(
        "Esportazione in varie/Link — formati: 1 | 1-5 | 1,3,7 | tutti"
    )
    sel = core.ui.ask_input("Episodi da esportare (0=annulla)")
    if sel == "0" or not sel:
        return

    indices = _parse_episode_selection(sel, len(episodes))
    if not indices:
        core.ui.warning("Selezione non valida.")
        core.ui.pause()
        return

    lines = _collect_episode_links(core, episodes, indices, base)
    ok = [ln for ln in lines if "[non disponibile]" not in ln]
    if not ok:
        core.ui.warning("Nessun link estratto.")
        core.ui.pause()
        return

    if core.link_extractor:
        path = core.link_extractor.save_links_file(
            titolo, MODULE_KEY, lines, suffix="episodi"
        )
    else:
        from scripts.core.file_manager import FileManager
        from scripts.core.settings_core import VARIE_DIR
        from pathlib import Path

        safe = FileManager.sanitize_folder_name(titolo)
        d = Path(VARIE_DIR) / "Link" / safe
        d.mkdir(parents=True, exist_ok=True)
        path = str(d / f"{safe}_{MODULE_KEY}_episodi.txt")
        Path(path).write_text(
            f"{titolo} - {MODULE_KEY}\n\n" + "\n".join(lines),
            encoding="utf-8",
        )

    core.ui.show_success(f"Salvati {len(ok)} link in:\n{path}")


def _fetch_show_meta(base: str, show_url: str) -> dict:
    """
    Scarica la pagina serie e ne estrae stato, episodi_totali, genere, anno.
    Ritorna dict con 'stato': 'finito' | 'in_corso'.
    Effettua una richiesta separata (la pagina è già scaricata da _fetch_episodes,
    ma manteniamo la separazione delle responsabilità).
    """
    log_debug(f"[{MODULE_KEY}] → _fetch_show_meta()")
    out: dict = {"stato": "in_corso", "episodi_totali": 0, "genere": "N/D", "anno": "N/D"}
    html = _get_page(show_url, base)
    if not html:
        return out
    m = _RE_STATO.search(html)
    if m:
        stato_raw = m.group(1).strip().lower()
        out["stato"] = "finito" if "finit" in stato_raw else "in_corso"
    m = _RE_EP_TOT.search(html)
    if m:
        try:
            out["episodi_totali"] = int(m.group(1))
        except ValueError:
            pass
    m = _RE_GENERE_META.search(html)
    if m:
        raw = re.sub(r"<[^>]+>", "", m.group(1))
        out["genere"] = raw.strip() or "N/D"
    m = _RE_ANNO.search(html)
    if m:
        out["anno"] = m.group(1).strip() or "N/D"
    log_debug(
        f"[{MODULE_KEY}] meta → stato={out['stato']} ep={out['episodi_totali']}"
    )
    return out


def _aggiungi_watchlist(core, meta: dict, titolo: str, show_url: str) -> None:
    """
    Aggiunge la serie alla watchlist corretta in base allo stato scraped.
    'finito' → add_finite | qualsiasi altro → add_in_corso.
    Controlla duplicati prima di aggiungere.
    """
    log_debug(f"[{MODULE_KEY}] → _aggiungi_watchlist()")
    from scripts.anime.moduli.Utilita.Watchlist.handlers_watchlist import (
        add_in_corso,
        add_finite,
        get_in_corso,
        get_finite,
    )
    # Verifica duplicati (confronto per URL o titolo)
    titolo_norm = titolo.strip().lower()
    url_norm = show_url.strip().rstrip("/")
    for item in get_in_corso():
        if item.get("url", "").rstrip("/") == url_norm or item.get("titolo", "").strip().lower() == titolo_norm:
            core.ui.warning(f'"{_trunc(titolo, 35)}" e\' gia\' in Watchlist Serie in corso.')
            return
    for item in get_finite():
        if item.get("url", "").rstrip("/") == url_norm or item.get("titolo", "").strip().lower() == titolo_norm:
            core.ui.warning(f'"{_trunc(titolo, 35)}" e\' gia\' in Watchlist Serie finite.')
            return
    dati = {
        "titolo": titolo,
        "episodi_totali": meta.get("episodi_totali", 0),
        "url": show_url,
        "modulo": MODULE_KEY,
        "genere": meta.get("genere", "N/D"),
        "data_uscita_titolo": meta.get("anno", "N/D"),
    }
    if meta.get("stato") == "finito":
        add_finite(dati)
        core.ui.show_success(f'"{_trunc(titolo, 35)}" → Watchlist Serie finite.')
    else:
        dati["episodi_in_corso"] = 0
        add_in_corso(dati)
        core.ui.show_success(f'"{_trunc(titolo, 35)}" → Watchlist Serie in corso.')


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
        meta     = _fetch_show_meta(base, show_url)
    finally:
        core.progress.spinner_stop()

    if not episodes:
        core.ui.warning(f"Nessun episodio trovato per: {titolo}")
        core.ui.pause()
        return

    _extra = [
        {
            "key": "E",
            "icon": "",
            "label": "Esporta link episodi",
            "desc": "1 | 1-5 | tutti → Link",
        },
        {
            "key": "W",
            "icon": "",
            "label": "Aggiungi a Watchlist",
            "desc": f"{'finita' if meta.get('stato') == 'finito' else 'in corso'}",
        },
    ]

    while True:
        menu: List[dict] = []
        for i, ep in enumerate(episodes, start=1):
            menu.append({
                "key": str(i),
                "icon": "",
                "label": ep.get("label") or f"Ep. {i}",
                "desc": "",
            })
        menu.extend(_extra)
        c = core.ui.show_menu(
            f"{MODULE_NAME} — {_trunc(titolo, 30)}",
            menu,
            show_version=False,
        )
        if c == "0":
            return
        if c == "E":
            _export_episode_links(core, episodes, titolo, base)
            core.ui.pause()
            continue
        if c == "W":
            _aggiungi_watchlist(core, meta, titolo, show_url)
            core.ui.pause()
            continue

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


def _serie_in_corso(core) -> None:
    """Mostra le serie in corso da /ongoing."""
    log_debug(f"[{MODULE_KEY}] → _serie_in_corso()")
    base = _base_url(core)
    if not base:
        core.ui.error("URL AnimeWorld non configurato.")
        _pause_continue(core)
        return

    core.ui.clear()
    core.progress.spinner_start("Caricamento serie in corso...")
    try:
        items = _fetch_ongoing(base)
    finally:
        core.progress.spinner_stop()

    if not items:
        core.ui.warning("Nessun risultato trovato.")
        core.ui.pause()
        return

    picked = _pick_from_list(
        core,
        f"{MODULE_NAME} — Serie in corso",
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
        {"key": "1", "icon": "", "label": "Ultime uscite",   "desc": "Ultimi episodi pubblicati"},
        {"key": "2", "icon": "", "label": "Ricerca",          "desc": "Cerca per titolo"},
        {"key": "3", "icon": "", "label": "Serie in corso",   "desc": "Anime attualmente in corso"},
    ]
    while True:
        c = core.ui.show_menu(MODULE_NAME, items)
        if c == "0":
            return
        if c == "1":
            _ultime_uscite(core)
        elif c == "2":
            _ricerca(core)
        elif c == "3":
            _serie_in_corso(core)
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


def get_show_meta(show_url: str) -> dict:
    """
    [SILENT] Restituisce i metadati della serie (stato, episodi_totali, genere, anno).
    Usato da handlers_ricerca_globale per arricchire i dati watchlist.
    Ritorna dict vuoto in caso di errore.
    """
    log_debug(f"[{MODULE_KEY}] → get_show_meta()")
    try:
        from scripts.core import Core
        core = Core.get()
        base = _base_url(core)
        if not base:
            return {}
        return _fetch_show_meta(base, show_url)
    except Exception:
        return {}


def show_menu() -> None:
    """Alias retrocompatibile."""
    run()
