"""
Modulo AnimeUnity - Download Center upgrade-3
Logica allineata a Stream4me/addon channels/animeunity.py (API archivio + info_api).
UI e integrazione come handlers_animeworld (Core, url_manager, ricerca globale).
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.core.logger import get_logger, log_debug

logger = get_logger(__name__)

MODULE_KEY = "animeunity"
MODULE_NAME = "AnimeUnity"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_BASE_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "application/json, text/html, */*",
}

_RE_ANIME_URL = re.compile(r"/anime/(\d+)-([^/?#]+)")
_RE_EMBED_URL_ATTR = re.compile(r'embed_url="([^"]+)"', re.IGNORECASE)
_RE_SCWS_IFRAME = re.compile(
    r'src=["\']([^"\']*(?:scws|vixcloud|embed)[^"\']*)["\']',
    re.IGNORECASE,
)
_RE_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_RE_MASTER_PLAYLIST = re.compile(
    r"window\.masterPlaylist\s*=\s*\{[^{]*(\{[^}]+\}),\s*url:\s*['\"]([^'\"]+)['\"]"
    r".*?canPlayFHD\s*=\s*(true|false)",
    re.DOTALL | re.IGNORECASE,
)
_RE_M3U8 = re.compile(r'["\']([^"\']+\.m3u8[^"\']*)["\']')
_RE_M3U8_GREEDY = re.compile(r"https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*", re.IGNORECASE)
_RE_FILE_JS = re.compile(r'file:\s*["\']([^"\']+)["\']')
_SCWS_TOKEN_SALT = " Yc8U6r8KjAKAepEA"

_api_headers_cache: Dict[str, dict] = {}


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


def _api_headers(core, force_refresh: bool = False) -> Tuple[Optional[str], Optional[dict]]:
    """CSRF + cookie da /archivio (pattern Stream4me)."""
    log_debug(f"[{MODULE_KEY}] → _api_headers()")
    base = _base_url(core)
    if not base:
        return None, None
    if not force_refresh and base in _api_headers_cache:
        return base, _api_headers_cache[base]

    try:
        s = _http_session()
        r = s.get(f"{base}/archivio", timeout=20)
        r.raise_for_status()
        m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
        if not m:
            log_debug(f"[{MODULE_KEY}] csrf-token non trovato")
            return base, None
        csrf = m.group(1)
        cookie = "; ".join(f"{c.name}={c.value}" for c in r.cookies)
        headers = {
            **_BASE_HEADERS,
            "content-type": "application/json;charset=UTF-8",
            "x-csrf-token": csrf,
            "Referer": f"{base}/archivio",
            "Cookie": cookie,
        }
        _api_headers_cache[base] = headers
        return base, headers
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _api_headers error: {exc}")
        return base, None


def _decode_embedded_json(raw: str) -> Any:
    log_debug(f"[{MODULE_KEY}] → _decode_embedded_json()")
    if not raw:
        return None
    text = raw.replace("&quot;", '"').replace("&#39;", "'")
    return json.loads(text)


def _parse_anime_id(anime_url: str) -> Optional[str]:
    log_debug(f"[{MODULE_KEY}] → _parse_anime_id()")
    m = _RE_ANIME_URL.search(anime_url)
    return m.group(1) if m else None


def _anime_page_url(base: str, anime_id: int | str, slug: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _anime_page_url()")
    return f"{base}/anime/{anime_id}-{slug}"


def _normalize_url(url: str, base: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _normalize_url()")
    if url.startswith("http"):
        return url
    return base.rstrip("/") + "/" + url.lstrip("/")


def _lang_suffix(it: dict) -> str:
    """
    Restituisce il suffisso lingua da aggiungere al titolo.
    Campi API AnimeUnity: 'type' (es. 'ITA', 'SUB ITA', 'SUB'), 'language'.
    Formato: ' (ITA)' per doppiaggio, ' (Sub ITA)' per sottotitoli.
    """
    log_debug(f"[{MODULE_KEY}] → _lang_suffix()")
    raw = (it.get("type") or it.get("language") or "").strip().upper()
    if not raw:
        return ""
    if raw in ("ITA", "ITALIAN", "DOPPIATO"):
        return " (ITA)"
    if "SUB" in raw:
        return " (Sub ITA)"
    return ""


def _records_to_items(records: list, base: str) -> List[dict]:
    log_debug(f"[{MODULE_KEY}] → _records_to_items()")
    out: List[dict] = []
    for it in records or []:
        title = (it.get("title") or "").strip() or (it.get("title_eng") or "").strip()
        if not title:
            continue
        aid = it.get("id")
        slug = it.get("slug") or ""
        if not aid:
            continue
        title = title + _lang_suffix(it)
        url = _anime_page_url(base, aid, slug)
        out.append({
            "titolo": title,
            "url": url,
            "url_piena": url,
            "thumb": it.get("imageurl") or "",
            "plot": it.get("plot") or "",
            "tipo": it.get("type") or "",
            "modulo": MODULE_KEY,
        })
    return out


def _fetch_records(core, args: dict) -> List[dict]:
    log_debug(f"[{MODULE_KEY}] → _fetch_records()")
    base, headers = _api_headers(core)
    if not base or not headers:
        return []
    payload = json.dumps(args or {})
    try:
        r = _http_session().post(
            f"{base}/archivio/get-animes",
            headers=headers,
            data=payload,
            timeout=20,
        )
        if r.status_code != 200:
            log_debug(f"[{MODULE_KEY}] get-animes status={r.status_code}")
            if r.status_code == 403:
                _api_headers_cache.pop(base, None)
            return []
        data = r.json()
        records = data.get("records") if isinstance(data, dict) else []
        return _records_to_items(records, base)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _fetch_records error: {exc}")
        return []


def _fetch_news(core) -> List[dict]:
    """Ultimi episodi - items-json homepage (Stream4me news())."""
    log_debug(f"[{MODULE_KEY}] → _fetch_news()")
    base, headers = _api_headers(core)
    if not base or not headers:
        return []

    try:
        r = _http_session().get(base, headers=headers, timeout=20)
        r.raise_for_status()
        m = re.search(r'items-json="([^"]+)"', r.text)
        if not m:
            return []
        full_js = _decode_embedded_json(m.group(1))
        if not isinstance(full_js, dict):
            return []
        items = full_js.get("data") or []
        out: List[dict] = []
        for it in items:
            anime = it.get("anime") or {}
            title = anime.get("title") or anime.get("title_eng") or ""
            if not title:
                continue
            aid = anime.get("id")
            slug = anime.get("slug") or ""
            if not aid:
                continue
            title = title + _lang_suffix(anime)
            ep_id = it.get("id")
            ep_url = f"{base}/anime/{aid}-{slug}/{ep_id}" if ep_id else _anime_page_url(base, aid, slug)
            out.append({
                "titolo": title,
                "url": _anime_page_url(base, aid, slug),
                "url_ep": ep_url,
                "ep_label": it.get("file_name") or "",
                "thumb": anime.get("imageurl") or "",
                "modulo": MODULE_KEY,
            })
        return out
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _fetch_news error: {exc}")
        return []


def _fetch_episode_entries(core, anime_url: str) -> List[dict]:
    """Episodi via info_api (Stream4me episodios())."""
    log_debug(f"[{MODULE_KEY}] → _fetch_episode_entries()")
    base, headers = _api_headers(core)
    if not base or not headers:
        return []

    m = _RE_ANIME_URL.search(anime_url)
    if not m:
        return []
    anime_id, slug = m.group(1), m.group(2)

    api_base = f"{base}/info_api/{anime_id}/"
    start = 1
    limit = 120
    entries: List[dict] = []

    try:
        while True:
            url = f"{api_base}1?start_range={start}&end_range={start + limit - 1}"
            r = _http_session().get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                break
            full = r.json() if r.headers.get("content-type", "").startswith("application/json") else json.loads(r.text)
            count = int(full.get("episodes_count") or 0)
            for ep in full.get("episodes") or []:
                ep_id = ep.get("id")
                num = ep.get("number")
                if not ep_id:
                    continue
                page_url = f"{base}/anime/{anime_id}-{slug}/{ep_id}"
                entries.append({
                    "number": str(num) if num is not None else "?",
                    "episode_id": str(ep_id),
                    "url": page_url,
                    "scws_id": ep.get("scws_id") or ep.get("scws") or "",
                    "link": ep.get("link") or "",
                    "embed_url": ep.get("embed_url") or "",
                })
            if count > start:
                start += limit
            else:
                break
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _fetch_episode_entries error: {exc}")

    return entries


def _referer_headers(referer: str) -> dict:
    log_debug(f"[{MODULE_KEY}] → _referer_headers()")
    return {**_BASE_HEADERS, "Referer": referer}


def _get_page_html(url: str, referer: str) -> Optional[str]:
    log_debug(f"[{MODULE_KEY}] → _get_page_html()")
    try:
        r = _http_session().get(url, headers=_referer_headers(referer), timeout=25)
        if r.status_code != 200:
            log_debug(f"[{MODULE_KEY}] GET {url} status={r.status_code}")
            return None
        return r.text
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _get_page_html error: {exc}")
        return None


def _first_m3u8(html: str) -> Optional[str]:
    log_debug(f"[{MODULE_KEY}] → _first_m3u8()")
    if not html:
        return None
    m = _RE_M3U8.search(html)
    if m:
        return m.group(1)
    m2 = _RE_M3U8_GREEDY.search(html)
    return m2.group(0) if m2 else None


def _extract_embed_url(html: str, base: str) -> Optional[str]:
    """embed_url attribute o iframe (pattern Stream4me streamingcommunityws)."""
    log_debug(f"[{MODULE_KEY}] → _extract_embed_url()")
    m = _RE_EMBED_URL_ATTR.search(html)
    if m:
        return _normalize_url(m.group(1), base)
    m = _RE_SCWS_IFRAME.search(html)
    if m:
        return _normalize_url(m.group(1), base)
    m = _RE_IFRAME.search(html)
    if m:
        return _normalize_url(m.group(1), base)
    return None


def _get_client_ip() -> str:
    log_debug(f"[{MODULE_KEY}] → _get_client_ip()")
    try:
        r = _http_session().get("http://ip-api.com/json/", timeout=8)
        ip = r.json().get("query")
        if ip:
            return str(ip)
    except Exception:
        pass
    return "127.0.0.1"


def _build_scws_direct_url(scws_id: str, client_ip: Optional[str] = None) -> str:
    """URL HLS diretto scws.work (fallback da Stream4me animeunity.py)."""
    log_debug(f"[{MODULE_KEY}] → _build_scws_direct_url()")
    if not client_ip:
        client_ip = _get_client_ip()
    expires = int(time.time() + 172800)
    raw = f"{expires}{client_ip}{_SCWS_TOKEN_SALT}"
    token = (
        base64.b64encode(hashlib.md5(raw.encode("utf-8")).digest())
        .decode("utf-8")
        .replace("=", "")
        .replace("+", "-")
        .replace("/", "_")
    )
    return f"https://scws.work/master/{scws_id}?token={token}&expires={expires}&n=1"


def _resolve_master_playlist(embed_html: str, embed_url: str) -> Optional[str]:
    """
    Parsa window.masterPlaylist come server streamingcommunityws (Stream4me).
    """
    log_debug(f"[{MODULE_KEY}] → _resolve_master_playlist()")
    m = _RE_MASTER_PLAYLIST.search(embed_html)
    if not m:
        return _first_m3u8(embed_html)

    params_raw, stream_url, can_fhd = m.group(1), m.group(2), m.group(3)
    try:
        master_params = ast.literal_eval(params_raw)
        if not isinstance(master_params, dict):
            master_params = {}
    except Exception:
        master_params = {}

    if can_fhd.lower() == "true":
        master_params["h"] = 1

    if not stream_url.startswith("http"):
        stream_url = urljoin(embed_url, stream_url)

    split = urlsplit(stream_url)
    extra = dict(parse_qsl(split.query, keep_blank_values=True))
    master_params.update(extra)

    final = urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(master_params), "")
    )
    log_debug(f"[{MODULE_KEY}] masterPlaylist URL: {final[:100]}...")
    return final


def _resolve_embed_player(embed_url: str, referer: str) -> Optional[str]:
    log_debug(f"[{MODULE_KEY}] → _resolve_embed_player() | {embed_url[:90]}")
    html = _get_page_html(embed_url, referer)
    if not html:
        return None
    url = _resolve_master_playlist(html, embed_url)
    if url:
        return url
    m = _RE_FILE_JS.search(html)
    return m.group(1) if m else None


def _resolve_episode_hls(
    episode_url: str,
    base: str,
    entry: Optional[dict] = None,
) -> Optional[str]:
    """
    Risoluzione HLS episodio:
      1) link/scws_id da info_api
      2) pagina episodio → embed_url → masterPlaylist
      3) endpoint /embed-url/{id}
      4) regex m3u8 su pagina episodio
    """
    log_debug(f"[{MODULE_KEY}] → _resolve_episode_hls() | {episode_url}")
    entry = entry or {}
    referer = episode_url

    link = (entry.get("link") or "").strip()
    if link.startswith("http"):
        if ".m3u8" in link:
            return link
        resolved = _resolve_embed_player(link, referer)
        if resolved:
            return resolved

    scws_id = str(entry.get("scws_id") or "").strip()
    if scws_id:
        direct = _build_scws_direct_url(scws_id)
        log_debug(f"[{MODULE_KEY}] uso scws_id diretto")
        return direct

    embed_hint = (entry.get("embed_url") or "").strip()
    if embed_hint.startswith("http"):
        resolved = _resolve_embed_player(embed_hint, referer)
        if resolved:
            return resolved

    ep_html = _get_page_html(episode_url, base + "/")
    if ep_html:
        if not scws_id:
            m_scws = re.search(
                r'scws[_-]?id["\']?\s*[:=]\s*["\']?(\d+)',
                ep_html,
                re.IGNORECASE,
            )
            if m_scws:
                return _build_scws_direct_url(m_scws.group(1))
        embed = _extract_embed_url(ep_html, base)
        if embed:
            resolved = _resolve_embed_player(embed, referer)
            if resolved:
                return resolved
        direct_m3u8 = _first_m3u8(ep_html)
        if direct_m3u8:
            return direct_m3u8

    ep_id = entry.get("episode_id")
    if ep_id:
        embed_endpoint = f"{base}/embed-url/{ep_id}"
        resolved = _resolve_embed_player(embed_endpoint, referer)
        if resolved:
            return resolved
        emb_html = _get_page_html(embed_endpoint, referer)
        if emb_html:
            found = _first_m3u8(emb_html)
            if found:
                return found

    log_debug(f"[{MODULE_KEY}] _resolve_episode_hls: nessun URL trovato")
    return None


def _trunc(text: str, max_len: int = 44) -> str:
    log_debug(f"[{MODULE_KEY}] → _trunc()")
    s = str(text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _pause_continue(core) -> None:
    log_debug(f"[{MODULE_KEY}] → _pause_continue()")
    core.ui.pause()
    core.ui.clear()


def _build_list_menu(
    rows: List[dict],
    label_key: str = "titolo",
    desc_key: str = "ep_label",
    extra: Optional[List[dict]] = None,
) -> List[dict]:
    log_debug(f"[{MODULE_KEY}] → _build_list_menu()")
    menu: List[dict] = []
    for i, row in enumerate(rows, start=1):
        menu.append({
            "key": str(i),
            "icon": "",
            "label": _trunc(row.get(label_key, "?"), 40),
            "desc": _trunc(row.get(desc_key) or "", 28),
        })
    for ex in extra or []:
        menu.append(ex)
    return menu


def _menu_index(choice: str, count: int) -> Optional[int]:
    log_debug(f"[{MODULE_KEY}] → _menu_index()")
    if not choice or choice == "0":
        return None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < count:
            return idx
    return -1


def _parse_episode_selection(scelta: str, count: int) -> List[int]:
    """Singolo (3), intervallo (1-5), tutti."""
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
    entries: List[dict],
    indices: List[int],
    base: str,
) -> List[str]:
    log_debug(f"[{MODULE_KEY}] → _collect_episode_links()")
    lines: List[str] = []
    for i in indices:
        ep = entries[i]
        core.progress.spinner_start(f"Ep. {ep['number']} - estrazione link...")
        try:
            url = _resolve_episode_hls(ep["url"], base, ep)
        finally:
            core.progress.spinner_stop()
        if url:
            lines.append(f"Ep. {ep['number']}\t{url}")
        else:
            lines.append(f"Ep. {ep['number']}\t[non disponibile]")
    return lines


def _export_episode_links(
    core,
    entries: List[dict],
    titolo: str,
    base: str,
) -> None:
    log_debug(f"[{MODULE_KEY}] → _export_episode_links()")
    print()
    core.ui.show_info(
        "Esportazione in varie/Link - formati: 1 | 1-5 | 1,3,7 | tutti | 0=annulla"
    )
    sel = core.ui.ask_input("Episodi da esportare (0=annulla)")
    if sel == "0" or not sel:
        return

    indices = _parse_episode_selection(sel, len(entries))
    if not indices:
        core.ui.warning("Selezione non valida.")
        return

    lines = _collect_episode_links(core, entries, indices, base)
    ok = [ln for ln in lines if "[non disponibile]" not in ln]
    if not ok:
        core.ui.warning("Nessun link estratto.")
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


def _fetch_show_meta(core, anime_url: str) -> dict:
    """
    Recupera metadati serie da info_api: stato, episodi_totali, genere, anno.
    Chiama info_api/{anime_id}/1 con range minimo (1-1) per soli metadati.
    Ritorna dict con 'stato': 'finito' | 'in_corso'.
    """
    log_debug(f"[{MODULE_KEY}] → _fetch_show_meta()")
    out: dict = {"stato": "in_corso", "episodi_totali": 0, "genere": "N/D", "anno": "N/D"}
    base, headers = _api_headers(core)
    if not base or not headers:
        return out
    m = _RE_ANIME_URL.search(anime_url)
    if not m:
        return out
    anime_id = m.group(1)
    try:
        url = f"{base}/info_api/{anime_id}/1?start_range=1&end_range=1"
        r = _http_session().get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            log_debug(f"[{MODULE_KEY}] info_api meta status={r.status_code}")
            return out
        ct = r.headers.get("content-type", "")
        full = r.json() if ct.startswith("application/json") else json.loads(r.text)
        # episodi totali
        count = int(full.get("episodes_count") or 0)
        out["episodi_totali"] = count
        # stato
        status_raw = (full.get("status") or "").strip().lower()
        if "finit" in status_raw or status_raw in ("finished", "completed"):
            out["stato"] = "finito"
        # generi - lista di dict {"name":...} oppure lista di stringhe
        genres = full.get("genres") or full.get("genre") or []
        if isinstance(genres, list):
            nomi = []
            for g in genres:
                nomi.append(g.get("name", g) if isinstance(g, dict) else str(g))
            out["genere"] = ", ".join(nomi) or "N/D"
        elif isinstance(genres, str):
            out["genere"] = genres or "N/D"
        # anno / data
        date_val = (
            full.get("date") or full.get("season")
            or full.get("year") or full.get("created_at") or ""
        )
        out["anno"] = str(date_val).strip()[:10] or "N/D"
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] _fetch_show_meta error: {exc}")
    log_debug(
        f"[{MODULE_KEY}] meta → stato={out['stato']} ep={out['episodi_totali']}"
    )
    return out


def _aggiungi_watchlist(core, meta: dict, titolo: str, anime_url: str) -> None:
    """
    Aggiunge la serie alla watchlist corretta in base allo stato.
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
    url_norm = anime_url.strip().rstrip("/")
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
        "url": anime_url,
        "modulo": MODULE_KEY,
        "genere": meta.get("genere", "N/D"),
        "data_uscita_titolo": meta.get("anno", "N/D"),
    }
    if meta.get("stato") == "finito":
        add_finite(dati)
        core.ui.show_success(f'"{_trunc(titolo, 35)}" → Watchlist Serie finite.')
    else:
        dati["episodi_in_corso"] = int(meta.get("episodi_in_corso") or 0)
        add_in_corso(dati)
        core.ui.show_success(f'"{_trunc(titolo, 35)}" → Watchlist Serie in corso.')


def _episodio_azioni(core, ep: dict, base: str, serie_titolo: str) -> None:
    log_debug(f"[{MODULE_KEY}] → _episodio_azioni()")
    while True:
        c = core.ui.show_menu(
            f"{MODULE_NAME} - Ep. {ep['number']}",
            [
                {"key": "1", "icon": "", "label": "Mostra URL video", "desc": "Anteprima HLS"},
                {"key": "2", "icon": "", "label": "Esporta link episodio", "desc": "varie/Link"},
            ],
            show_version=False,
        )
        if c == "0":
            return
        if c == "1":
            core.progress.spinner_start("URL video...")
            try:
                hls = _resolve_episode_hls(ep["url"], base, ep)
            finally:
                core.progress.spinner_stop()
            if hls:
                core.ui.show_success(f"URL video (HLS):\n{hls}")
            else:
                core.ui.warning("URL video non trovato per questo episodio.")
            _pause_continue(core)
        elif c == "2":
            lines = _collect_episode_links(core, [ep], [0], base)
            if lines and "[non disponibile]" not in lines[0]:
                if core.link_extractor:
                    path = core.link_extractor.save_links_file(
                        serie_titolo, MODULE_KEY, lines, suffix=f"ep{ep['number']}"
                    )
                else:
                    path = ""
                core.ui.show_success(f"Link salvato in:\n{path}")
            else:
                core.ui.warning("Link non disponibile.")
            _pause_continue(core)
        else:
            core.ui.error("Voce non valida.")
            _pause_continue(core)


def _dettaglio_episodi(core, anime_url: str, titolo: str) -> None:
    log_debug(f"[{MODULE_KEY}] → _dettaglio_episodi()")
    base = _base_url(core)
    if not base:
        core.ui.error("URL AnimeUnity non configurato.")
        _pause_continue(core)
        return

    core.ui.clear()
    core.progress.spinner_start("Caricamento episodi...")
    try:
        entries = _fetch_episode_entries(core, anime_url)
        meta    = _fetch_show_meta(core, anime_url)
        meta["episodi_in_corso"] = len(entries)
    finally:
        core.progress.spinner_stop()

    if not entries:
        core.ui.warning(f"Nessun episodio trovato per: {titolo}")
        _pause_continue(core)
        return

    extra = [
        {
            "key": "E",
            "icon": "",
            "label": "Esporta link episodi",
            "desc": "1 | 1-5 | tutti | 0 annulla",
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
        for i, ep in enumerate(entries, start=1):
            menu.append({
                "key": str(i),
                "icon": "",
                "label": f"Ep. {ep['number']}",
                "desc": f"id {ep['episode_id']}",
            })
        menu.extend(extra)

        c = core.ui.show_menu(
            f"{MODULE_NAME} - {titolo}",
            menu,
            show_version=False,
        )
        if c == "0":
            return
        if c == "E":
            _export_episode_links(core, entries, titolo, base)
            core.ui.pause()
            continue
        if c == "W":
            _aggiungi_watchlist(core, meta, titolo, anime_url)
            core.ui.pause()
            continue

        idx = _menu_index(c, len(entries))
        if idx is None:
            continue
        if idx < 0:
            core.ui.error("Voce non valida.")
            _pause_continue(core)
            continue

        _episodio_azioni(core, entries[idx], base, titolo)


def _pick_anime_from_list(
    core,
    title: str,
    items: List[dict],
    label_key: str = "titolo",
    desc_key: str = "ep_label",
) -> Optional[dict]:
    log_debug(f"[{MODULE_KEY}] → _pick_anime_from_list()")
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


def _ultime_uscite(core) -> None:
    log_debug(f"[{MODULE_KEY}] → _ultime_uscite()")
    core.ui.clear()
    core.progress.spinner_start("Ultimi aggiornamenti...")
    try:
        items = _fetch_news(core)
    finally:
        core.progress.spinner_stop()

    if not items:
        core.ui.warning("Nessun aggiornamento trovato.")
        _pause_continue(core)
        return

    picked = _pick_anime_from_list(
        core,
        f"{MODULE_NAME} - Ultimi episodi",
        items,
        label_key="titolo",
        desc_key="ep_label",
    )
    if picked:
        _dettaglio_episodi(core, picked["url"], picked["titolo"])


def _ricerca(core) -> None:
    log_debug(f"[{MODULE_KEY}] → _ricerca()")
    core.ui.clear()
    titolo = core.ui.ask_input("Titolo da cercare (0=annulla)")
    if titolo == "0" or not titolo:
        return

    core.progress.spinner_start("Ricerca in corso...")
    try:
        items = _fetch_records(core, {"title": titolo})
    finally:
        core.progress.spinner_stop()

    if not items:
        core.ui.warning(f'Nessun risultato per "{titolo}".')
        _pause_continue(core)
        return

    picked = _pick_anime_from_list(
        core,
        f'{MODULE_NAME} - Risultati per "{titolo}"',
        items,
        label_key="titolo",
        desc_key="tipo",
    )
    if picked:
        _dettaglio_episodi(core, picked["url"], picked["titolo"])


def run() -> None:
    """Entry point - richiesto da anime.json / handlers_anime_video."""
    log_debug(f"[{MODULE_KEY}] → run()")
    from scripts.core import Core

    core = Core.get()
    if not _base_url(core):
        core.ui.error(
            "URL AnimeUnity non configurato. "
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
    """[SILENT] Usato da handlers_ricerca_globale."""
    log_debug(f"[{MODULE_KEY}] → search()")
    try:
        from scripts.core import Core

        core = Core.get()
        if not _base_url(core):
            return []
        return _fetch_records(core, {"title": titolo})
    except Exception:
        return []


def get_episodes(anime_url: str) -> List[str]:
    """[SILENT] Restituisce URL HLS per ogni episodio (link_extractor)."""
    log_debug(f"[{MODULE_KEY}] → get_episodes()")
    try:
        from scripts.core import Core

        core = Core.get()
        base = _base_url(core)
        if not base:
            return []

        full_url = _normalize_url(anime_url, base)
        entries = _fetch_episode_entries(core, full_url)
        urls: List[str] = []
        for ep in entries:
            hls = _resolve_episode_hls(ep["url"], base, ep)
            if hls:
                urls.append(hls)
        return urls
    except Exception:
        return []


def get_episode_count(anime_url: str) -> int:
    """[SILENT] Restituisce il numero di episodi pubblicati senza risolvere gli HLS."""
    log_debug(f"[{MODULE_KEY}] → get_episode_count()")
    try:
        from scripts.core import Core

        core = Core.get()
        base = _base_url(core)
        if not base:
            return 0

        full_url = _normalize_url(anime_url, base)
        return len(_fetch_episode_entries(core, full_url))
    except Exception:
        return 0


def get_show_meta(anime_url: str) -> dict:
    """
    [SILENT] Restituisce i metadati della serie (stato, episodi_totali, genere, anno).
    Usato da handlers_ricerca_globale per arricchire i dati watchlist.
    Ritorna dict vuoto in caso di errore.
    """
    log_debug(f"[{MODULE_KEY}] → get_show_meta()")
    try:
        from scripts.core import Core
        core = Core.get()
        if not _base_url(core):
            return {}
        return _fetch_show_meta(core, anime_url)
    except Exception:
        return {}


def show_menu() -> None:
    """Alias retrocompatibile."""
    log_debug(f"[{MODULE_KEY}] → show_menu()")
    run()
