from __future__ import annotations

import html as html_lib
import json
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote, quote_plus, urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.core import Core
from scripts.core.file_manager import FileManager
from scripts.core.logger import get_logger, log_debug

logger = get_logger(__name__)

MODULE_KEY = "animeclick"
MODULE_NAME = "AnimeClick"

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

_DETAIL_LABELS = [
    "Titolo originale",
    "Titolo inglese",
    "Titolo breve",
    "Titolo Kanji",
    "Nazionalita",
    "Nazionalità",
    "Categoria",
    "Genere",
    "Anno",
    "Tratto da",
    "Stagioni",
    "Episodi",
    "Stato in patria",
    "Stato in Italia",
    "Disponibilita",
    "Disponibilità",
    "Sito Ufficiale",
    "Distributori",
    "Valutazione cc",
    "Opinioni",
    "Immagini",
    "Tag generici",
    "Nella tua lista",
    "Trama:",
    "Per favore",
    "Utente",
    "Email",
]


def _http_session() -> requests.Session:
    log_debug(f"[{MODULE_KEY}] → _http_session()")
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(_BASE_HEADERS)
    return session


def _base_url(core) -> Optional[str]:
    log_debug(f"[{MODULE_KEY}] → _base_url()")
    url = core.url_manager.get_url(MODULE_KEY, "base_url")
    return url.rstrip("/") if url else None


def _search_url(base: str, page: int = 1) -> str:
    log_debug(f"[{MODULE_KEY}] → _search_url()")
    return f"{base}/ricerca/anime?page={page}"


def _normalize_url(url: str, base: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _normalize_url()")
    return url if url.startswith("http") else urljoin(base + "/", url.lstrip("/"))


def _strip_tags(raw: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _strip_tags()")
    text = re.sub(r"<br\s*/?>", " ", raw or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_list_section(raw_html: str, title: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _extract_list_section()")
    pattern = re.compile(
        r"<strong>\s*" + re.escape(title) + r"\s*</strong>.*?<ul[^>]*>(?P<ul>.*?)</ul>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(raw_html or "")
    if not match:
        return ""
    values = [_strip_tags(item) for item in re.findall(r"<li[^>]*>(.*?)</li>", match.group("ul"), re.DOTALL)]
    return ", ".join(value for value in values if value)


def _extract_tooltip(block: str) -> dict:
    log_debug(f"[{MODULE_KEY}] → _extract_tooltip()")
    match = re.search(r'data-content="(?P<data>.*?)"\s+data-original-title', block, re.DOTALL)
    tooltip = html_lib.unescape(match.group("data")) if match else ""
    out = {
        "plot": "",
        "categoria": "",
        "tipo": "",
        "genere": "",
        "anno": "",
        "valutazione_cc": "",
    }
    if not tooltip:
        return out

    title_match = re.search(r"<h5>\s*(.*?)\s*</h5>", tooltip, re.DOTALL | re.IGNORECASE)
    if title_match:
        out["titolo_tooltip"] = _strip_tags(title_match.group(1))

    plot_match = re.search(r"<p>\s*(.*?)\s*</p>", tooltip, re.DOTALL | re.IGNORECASE)
    if plot_match:
        out["plot"] = _strip_tags(plot_match.group(1))

    year_match = re.search(r"fa-calendar-o[^<]*</i>\s*([^<]+)", tooltip, re.IGNORECASE)
    if year_match:
        out["anno"] = _strip_tags(year_match.group(1))

    rating_match = re.search(r"fa-star-o[^<]*</i>\s*([^<]+)", tooltip, re.IGNORECASE)
    if rating_match:
        out["valutazione_cc"] = _strip_tags(rating_match.group(1))

    category = _extract_list_section(tooltip, "Categorie")
    genre = _extract_list_section(tooltip, "Genere")
    out["categoria"] = category
    out["tipo"] = category
    out["genere"] = genre
    return out


def _parse_search_results(html: str, base: str, titolo: str = "", autore: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _parse_search_results()")
    log_debug(f"[{MODULE_KEY}] html len={len(html or '')}")
    results: List[Dict] = []
    seen = set()

    pattern = re.compile(
        r'<div class="thumbnail[^"]*opera-info-lista[^"]*"(?P<block>.*?)'
        r'<div class="caption text-center">\s*<h5>\s*'
        r'<a href="(?P<url>/anime/\d+/[^"]+)">(?P<title>.*?)</a>\s*</h5>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html or ""):
        url = _normalize_url(match.group("url"), base)
        if url in seen:
            continue
        seen.add(url)

        block = match.group("block")
        title = _strip_tags(match.group("title"))
        tooltip = _extract_tooltip(block)
        thumb_match = re.search(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)
        thumb = _normalize_url(thumb_match.group(1), base) if thumb_match else ""

        info_text = _strip_tags(block)
        year = tooltip.get("anno") or _first_match(info_text, r"\b(19\d{2}|20\d{2})\b")
        rating = tooltip.get("valutazione_cc") or _first_match(info_text, r"\b(\d+[,.]\d+)\b")

        item = {
            "titolo": title or tooltip.get("titolo_tooltip", ""),
            "url": url,
            "url_piena": url,
            "thumb": thumb,
            "plot": tooltip.get("plot", ""),
            "trama": tooltip.get("plot", ""),
            "tipo": tooltip.get("tipo", "") or "N/D",
            "categoria": tooltip.get("categoria", "") or "N/D",
            "genere": tooltip.get("genere", "") or "N/D",
            "anno": year or "N/D",
            "valutazione_cc": rating or "N/D",
            "modulo": MODULE_KEY,
        }
        if _matches_query(item, titolo, autore):
            results.append(item)

    log_debug(f"[{MODULE_KEY}] risultati trovati: {len(results)}")
    return results


def _first_match(text: str, pattern: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _first_match()")
    match = re.search(pattern, text or "", re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _matches_query(item: Dict, titolo: str = "", autore: str = "") -> bool:
    log_debug(f"[{MODULE_KEY}] → _matches_query()")
    haystack = " ".join(
        str(item.get(key, "")) for key in ("titolo", "plot", "trama", "genere", "categoria", "tipo")
    ).lower()
    return not titolo or titolo.strip().lower() in haystack


def _payloads(titolo: str, autore: str = "") -> List[dict]:
    log_debug(f"[{MODULE_KEY}] → _payloads()")
    # AnimeClick usa una ricerca AJAX su /ricerca/anime; teniamo piu' varianti
    # di nome campo per tollerare cambi strutturali del form.
    return [
        {"search_manga[title]": titolo, "search_manga[staff]": autore},
        {"titolo": titolo, "staff": autore, "ordine": "titolo", "sort": "titolo"},
        {"title": titolo, "staff": autore, "sort": "titolo", "order": "1"},
        {"q": titolo, "autore": autore, "tipo": "anime", "sort": "titolo"},
        {"name": titolo, "staff": autore, "tipo": "anime", "sort": "titolo"},
        {"filter[titolo]": titolo, "filter[staff]": autore, "sort": "titolo"},
        {"ricerca[titolo]": titolo, "ricerca[staff]": autore, "sort": "titolo"},
        {"opera[titolo]": titolo, "opera[staff]": autore, "sort": "titolo"},
        {"titolo_opera": titolo, "autore": autore, "sort": "titolo"},
    ]


def _fetch_search(base: str, titolo: str, autore: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _fetch_search()")
    candidates: List[List[Dict]] = []
    direct = _fetch_direct_search(base, titolo, autore)
    if direct:
        candidates.append(direct)

    session = _http_session()
    try:
        session.get(f"{base}/ricerca/anime", timeout=20)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] preload ricerca error: {exc}")

    headers = {
        **_BASE_HEADERS,
        "Referer": f"{base}/ricerca/anime",
        "X-Requested-With": "XMLHttpRequest",
    }
    best: List[Dict] = []
    for payload in _payloads(titolo, autore):
        try:
            response = session.post(
                _search_url(base),
                data=payload,
                headers=headers,
                timeout=25,
            )
            if response.status_code != 200:
                log_debug(f"[{MODULE_KEY}] search status={response.status_code}")
                continue
            parsed = _parse_search_results(_extract_html_payload(response), base, titolo, autore)
            if parsed:
                candidates.append(parsed)
                if len(parsed) > len(best):
                    best = parsed
        except Exception as exc:
            log_debug(f"[{MODULE_KEY}] search payload error: {exc}")

    fallback = _fetch_general_search(base, titolo, autore)
    if fallback:
        candidates.append(fallback)

    browser_results = _fetch_browser_search(base, titolo, autore)
    if browser_results:
        candidates.append(browser_results)

    if not candidates:
        return best
    return _dedupe_results(max(candidates, key=len))


def _dedupe_results(results: List[Dict]) -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _dedupe_results()")
    out: List[Dict] = []
    seen = set()
    for item in results or []:
        key = (item.get("url") or item.get("url_piena") or item.get("titolo") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _fetch_direct_search(base: str, titolo: str, autore: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _fetch_direct_search()")
    params = [f"search_manga%5Btitle%5D={quote(titolo)}"]
    if autore:
        params.append(f"search_manga%5Bstaff%5D={quote(autore)}")
    url = f"{base}/ricerca/anime?{'&'.join(params)}"
    try:
        response = _http_session().get(
            url,
            headers={**_BASE_HEADERS, "Referer": f"{base}/ricerca/anime"},
            timeout=25,
        )
        if response.status_code != 200:
            log_debug(f"[{MODULE_KEY}] direct search status={response.status_code}")
            return []
        return _parse_search_results(response.text, base, titolo, autore)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] direct search error: {exc}")
        return []


def _fetch_browser_search(base: str, titolo: str, autore: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _fetch_browser_search()")
    try:
        core = Core.get()
        browser = getattr(core, "browser", None)
        if not browser:
            return []
        launched = browser.launch(headless=core.config.is_headless())
        if not launched:
            return []
        page = browser.new_page()
        if not page:
            browser.close()
            return []

        params = [f"search_manga%5Btitle%5D={quote(titolo)}"]
        if autore:
            params.append(f"search_manga%5Bstaff%5D={quote(autore)}")
        direct_url = f"{base}/ricerca/anime?{'&'.join(params)}"
        try:
            page.goto(direct_url, wait_until="domcontentloaded", timeout=25000)
            try:
                page.wait_for_selector("#row-elenco-opere", timeout=10000)
            except Exception:
                pass
            page.wait_for_timeout(1000)
            results = _parse_search_results(page.content(), base, titolo, autore)
            if results:
                return results

            page.goto(f"{base}/ricerca/anime", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(800)
            for selector in (
                "#search_manga_title",
                "input[name='search_manga[title]']",
                "input[name*='title']",
            ):
                try:
                    page.wait_for_selector(selector, timeout=4000)
                    page.fill(selector, titolo)
                    if autore:
                        for staff_selector in ("#search_manga_staff", "input[name='search_manga[staff]']"):
                            try:
                                page.fill(staff_selector, autore)
                                break
                            except Exception:
                                continue
                    page.press(selector, "Enter")
                    break
                except Exception:
                    continue
            try:
                page.wait_for_selector("#row-elenco-opere", timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(1200)
            return _parse_search_results(page.content(), base, titolo, autore)
        finally:
            browser.close()
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] browser search error: {exc}")
        return []


def _fetch_general_search(base: str, titolo: str, autore: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _fetch_general_search()")
    query = titolo if not autore else f"{titolo} {autore}"
    url = f"{base}/ricerca?s={quote_plus(query)}"
    try:
        response = _http_session().get(url, headers={**_BASE_HEADERS, "Referer": base + "/"}, timeout=25)
        if response.status_code != 200:
            log_debug(f"[{MODULE_KEY}] general search status={response.status_code}")
            return []
        parsed = _parse_search_results(response.text, base, titolo, autore)
        if parsed:
            return parsed
        return _parse_generic_anime_links(response.text, base, titolo)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] general search error: {exc}")
        return []


def _parse_generic_anime_links(html: str, base: str, titolo: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → _parse_generic_anime_links()")
    results: List[Dict] = []
    seen = set()
    pattern = re.compile(r'<a[^>]+href="(?P<url>/anime/\d+/[^"]+)"[^>]*>(?P<title>.*?)</a>', re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(html or ""):
        url = _normalize_url(match.group("url"), base)
        title = _strip_tags(match.group("title"))
        if not title or url in seen:
            continue
        seen.add(url)
        item = {
            "titolo": title,
            "url": url,
            "url_piena": url,
            "thumb": "",
            "plot": "",
            "trama": "",
            "tipo": "N/D",
            "categoria": "N/D",
            "genere": "N/D",
            "anno": "N/D",
            "valutazione_cc": "N/D",
            "modulo": MODULE_KEY,
        }
        if _matches_query(item, titolo):
            results.append(item)
    log_debug(f"[{MODULE_KEY}] risultati generic search: {len(results)}")
    return results


def _extract_html_payload(response) -> str:
    log_debug(f"[{MODULE_KEY}] → _extract_html_payload()")
    text = response.text or ""
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower() and not text.lstrip().startswith(("{", "[")):
        return text
    try:
        data = response.json()
    except Exception:
        try:
            data = json.loads(text)
        except Exception:
            return text
    chunks: List[str] = []

    def _walk(value) -> None:
        log_debug(f"[{MODULE_KEY}] → _walk()")
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, dict):
            for inner in value.values():
                _walk(inner)
        elif isinstance(value, list):
            for inner in value:
                _walk(inner)

    _walk(data)
    return "\n".join(chunks) or text


def _fetch_detail(base: str, url: str) -> Dict:
    log_debug(f"[{MODULE_KEY}] → _fetch_detail()")
    full_url = _normalize_url(url, base)
    try:
        response = _http_session().get(full_url, timeout=25)
        if response.status_code != 200:
            log_debug(f"[{MODULE_KEY}] detail status={response.status_code}")
            return {"url": full_url, "url_piena": full_url}
        return _parse_detail(response.text, full_url)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] detail error: {exc}")
        return {"url": full_url, "url_piena": full_url}


def _parse_detail(html: str, url: str) -> Dict:
    log_debug(f"[{MODULE_KEY}] → _parse_detail()")
    log_debug(f"[{MODULE_KEY}] html len={len(html or '')}")
    title = _strip_tags(_first_match(html, r"<title>(.*?)</title>"))
    title = re.sub(r"\s*\(Anime\)\s*\|\s*AnimeClick\.it\s*$", "", title, flags=re.IGNORECASE).strip()
    text = _strip_tags(html)

    out = {
        "titolo": title or "N/D",
        "titolo_originale": _extract_labeled_value(text, "Titolo originale"),
        "titolo_inglese": _extract_labeled_value(text, "Titolo inglese"),
        "categoria": _extract_labeled_value(text, "Categoria"),
        "tipo": _extract_labeled_value(text, "Categoria"),
        "genere": _extract_labeled_value(text, "Genere"),
        "anno": _extract_labeled_value(text, "Anno"),
        "episodi": _extract_labeled_value(text, "Episodi"),
        "episodi_totali": _extract_labeled_value(text, "Episodi"),
        "stato_in_patria": _extract_labeled_value(text, "Stato in patria"),
        "stato_in_italia": _extract_labeled_value(text, "Stato in Italia"),
        "valutazione_cc": _extract_labeled_value(text, "Valutazione cc"),
        "trama": _extract_labeled_value(text, "Trama:"),
        "url": url,
        "url_piena": url,
        "modulo": MODULE_KEY,
    }
    _clean_detail_fields(out, text)
    return {key: (value if value else "N/D") for key, value in out.items()}


def _clean_detail_fields(out: Dict, page_text: str) -> None:
    log_debug(f"[{MODULE_KEY}] → _clean_detail_fields()")
    title_eng = str(out.get("titolo_inglese") or "")
    out["titolo_inglese"] = re.split(r"\s+Titolo breve\s+", title_eng, maxsplit=1)[0].strip()

    normalized = re.sub(r"\s+", " ", page_text or "").strip()
    ep_match = re.search(r"\bEpisodi\s+(\d+|N\.?D\.?)\s+Stato in patria\b", normalized, re.IGNORECASE)
    if ep_match:
        out["episodi"] = ep_match.group(1).strip()
        out["episodi_totali"] = out["episodi"]

    trama = str(out.get("trama") or "")
    trama = re.split(r"\s+Per favore\s+", trama, maxsplit=1)[0]
    trama = re.split(r"\s+Utente\s+Email\b", trama, maxsplit=1)[0]
    out["trama"] = trama.strip()


def _extract_labeled_value(text: str, label: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _extract_labeled_value()")
    normalized = re.sub(r"\s+", " ", text or "").strip()
    start = normalized.lower().find(label.lower())
    if start < 0:
        return ""
    start += len(label)
    stops = [item for item in _DETAIL_LABELS if item.lower() != label.lower()]
    stop_positions = [
        pos
        for stop in stops
        for pos in [normalized.lower().find(" " + stop.lower() + " ", start)]
        if pos >= 0
    ]
    end = min(stop_positions) if stop_positions else len(normalized)
    value = normalized[start:end].strip(" :-")
    return value


def _format_scheda(res: Dict) -> str:
    log_debug(f"[{MODULE_KEY}] → _format_scheda()")
    fields = [
        ("Titolo", res.get("titolo")),
        ("Titolo originale", res.get("titolo_originale")),
        ("Titolo inglese", res.get("titolo_inglese")),
        ("Categoria", res.get("categoria") or res.get("tipo")),
        ("Genere", res.get("genere")),
        ("Anno", res.get("anno")),
        ("Episodi", res.get("episodi") or res.get("episodi_totali")),
        ("Stato in patria", res.get("stato_in_patria")),
        ("Stato in Italia", res.get("stato_in_italia")),
        ("Valutazione cc", res.get("valutazione_cc")),
        ("Trama", res.get("trama") or res.get("plot")),
        ("URL scheda", res.get("url") or res.get("url_piena")),
    ]
    return "\n".join(f"{label}: {value or 'N/D'}" for label, value in fields)


def _table_rows(res: Dict) -> List[tuple]:
    log_debug(f"[{MODULE_KEY}] → _table_rows()")
    return [
        ("Titolo", _fit_value(res.get("titolo"), 38)),
        ("Titolo originale", _fit_value(res.get("titolo_originale"), 38)),
        ("Titolo inglese", _fit_value(res.get("titolo_inglese"), 38)),
        ("Categoria", _fit_value(res.get("categoria") or res.get("tipo"), 38)),
        ("Genere", _fit_value(res.get("genere"), 38)),
        ("Anno", _fit_value(res.get("anno"), 38)),
        ("Episodi", _fit_value(res.get("episodi") or res.get("episodi_totali"), 38)),
        ("Stato in patria", _fit_value(res.get("stato_in_patria"), 38)),
        ("Stato in Italia", _fit_value(res.get("stato_in_italia"), 38)),
        ("Valutazione cc", _fit_value(res.get("valutazione_cc"), 38)),
        ("URL scheda", _fit_value(res.get("url") or res.get("url_piena"), 38)),
    ]


def _trama_rows(res: Dict) -> List[tuple]:
    log_debug(f"[{MODULE_KEY}] → _trama_rows()")
    trama = str(res.get("trama") or res.get("plot") or "N/D").strip()
    lines = textwrap.wrap(trama, width=38) or ["N/D"]
    return [("Trama", lines[0])] + [("", line) for line in lines[1:8]]


def _fit_value(value, width: int) -> str:
    log_debug(f"[{MODULE_KEY}] → _fit_value()")
    text = re.sub(r"\s+", " ", str(value or "N/D")).strip()
    return text if len(text) <= width else text[: width - 3] + "..."


def _show_scheda_table(core, res: Dict) -> None:
    log_debug(f"[{MODULE_KEY}] → _show_scheda_table()")
    core.ui.show_info_table(res.get("titolo", MODULE_NAME), _table_rows(res))
    core.ui.show_info_table("Trama", _trama_rows(res))


def esporta_scheda(core, res: Dict, titolo_ricerca: str = "") -> Path:
    log_debug(f"[{MODULE_KEY}] → esporta_scheda()")
    export_dir = Path(core.config.get_export_dir())
    export_dir.mkdir(parents=True, exist_ok=True)
    titolo = res.get("titolo") or titolo_ricerca or "animeclick"
    safe = _safe_filename(titolo) or "animeclick"
    path = export_dir / f"{safe}_animeclick.txt"
    path.write_text(f"{MODULE_NAME} - Scheda anime\n\n{_format_scheda(res)}", encoding="utf-8")
    return path


def _safe_filename(value: str) -> str:
    log_debug(f"[{MODULE_KEY}] → _safe_filename()")
    safe = FileManager.sanitize_filename(str(value or ""))
    for char in ('/', '\\', '"'):
        safe = safe.replace(char, '-')
    return safe.strip(" .")


def search_scheda(titolo: str, autore: str = "") -> List[Dict]:
    log_debug(f"[{MODULE_KEY}] → search_scheda()")
    try:
        core = Core.get()
        base = _base_url(core)
        if not base:
            return []
        return _fetch_search(base, titolo, autore)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] search_scheda error: {exc}")
        return []


def get_scheda_details(url: str) -> Dict:
    log_debug(f"[{MODULE_KEY}] → get_scheda_details()")
    try:
        core = Core.get()
        base = _base_url(core)
        if not base:
            return {}
        return _fetch_detail(base, url)
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] get_scheda_details error: {exc}")
        return {}


def _pause_continue(core) -> None:
    log_debug(f"[{MODULE_KEY}] → _pause_continue()")
    core.ui.pause()
    core.ui.clear()


def _build_results_menu(results: List[Dict]) -> List[dict]:
    log_debug(f"[{MODULE_KEY}] → _build_results_menu()")
    items = []
    for index, row in enumerate(results, start=1):
        desc_parts = [row.get("tipo") or row.get("categoria"), row.get("anno"), row.get("valutazione_cc")]
        desc = " | ".join(str(part) for part in desc_parts if part and part != "N/D")
        items.append({"key": str(index), "icon": "", "label": row.get("titolo", ""), "desc": desc})
    return items


def _ricerca_titolo(core) -> None:
    log_debug(f"[{MODULE_KEY}] → _ricerca_titolo()")
    titolo = core.ui.ask_input("Titolo [0=Esci]")
    if titolo == "0" or not titolo:
        return
    autore = core.ui.ask_input("Autore/Staff opzionale [Invio=salta]")

    core.progress.spinner_start("Ricerca AnimeClick...")
    try:
        results = search_scheda(titolo, autore)
    finally:
        core.progress.spinner_stop()

    if not results:
        core.ui.warning(f'Nessun risultato su AnimeClick per "{titolo}".')
        core.ui.pause()
        return

    while True:
        choice = core.ui.show_menu(f'{MODULE_NAME} - Risultati "{titolo}"', _build_results_menu(results), show_version=False)
        if choice == "0":
            return
        try:
            index = int(choice) - 1
        except ValueError:
            core.ui.error("Voce non valida.")
            _pause_continue(core)
            continue
        if 0 <= index < len(results):
            _apri_dettaglio(core, results[index], titolo)
        else:
            core.ui.error("Voce non valida.")
            _pause_continue(core)


def _ricerca_url_diretto(core) -> None:
    log_debug(f"[{MODULE_KEY}] → _ricerca_url_diretto()")
    url = core.ui.ask_input("URL scheda AnimeClick [0=Esci]")
    if url == "0" or not url:
        return
    core.progress.spinner_start("Caricamento scheda AnimeClick...")
    try:
        detail = get_scheda_details(url)
    finally:
        core.progress.spinner_stop()
    if not detail:
        core.ui.warning("Scheda AnimeClick non trovata.")
        core.ui.pause()
        return
    _apri_dettaglio(core, detail, detail.get("titolo", "animeclick"))


def _apri_dettaglio(core, res: Dict, titolo_ricerca: str = "") -> None:
    log_debug(f"[{MODULE_KEY}] → _apri_dettaglio()")
    detail = dict(res)
    if res.get("url"):
        core.progress.spinner_start("Caricamento dettagli AnimeClick...")
        try:
            fetched = get_scheda_details(res["url"])
            if fetched:
                detail.update({key: value for key, value in fetched.items() if value and value != "N/D"})
        finally:
            core.progress.spinner_stop()

    while True:
        core.ui.clear()
        _show_scheda_table(core, detail)
        print()
        core.ui.show_info("E. Esporta scheda")
        core.ui.show_info("0. Esci / Indietro")
        print()
        choice = core.ui.ask_input("Scelta").strip().upper()
        if choice == "0":
            return
        if choice == "E":
            path = esporta_scheda(core, detail, titolo_ricerca)
            core.ui.show_success(f"Scheda salvata:\n{path}")
            core.ui.pause()
            return
        core.ui.error("Voce non valida.")
        _pause_continue(core)


def run() -> None:
    log_debug(f"[{MODULE_KEY}] → run()")
    core = Core.get()
    if not _base_url(core):
        core.ui.error("URL AnimeClick non configurato. Vai in Impostazioni -> URL moduli.")
        core.ui.pause()
        return

    items = [
        {"key": "1", "icon": "", "label": "Ricerca titolo", "desc": "Titolo oppure titolo + autore"},
        {"key": "2", "icon": "", "label": "Ricerca per URL diretto", "desc": "Apri dettagli scheda"},
    ]
    while True:
        choice = core.ui.show_menu(MODULE_NAME, items)
        if choice == "0":
            return
        if choice == "1":
            _ricerca_titolo(core)
        elif choice == "2":
            _ricerca_url_diretto(core)
        else:
            core.ui.error("Voce non valida.")
            _pause_continue(core)


def show_menu() -> None:
    log_debug(f"[{MODULE_KEY}] → show_menu()")
    run()
