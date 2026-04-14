#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ultime_uscite_MCM.py v4.1 — FIX BLOCCO CSS
============================================
Modulo per le Ultime uscite e preorder manga di MangaComicsMarket.it.
Percorso: scripts/manga/ultime_uscite_MCM.py

FIX v4.1 (rispetto a v4.0 REFACTORED):
  - ROOT CAUSE RISOLTO: MangaPageSession.open() applicava BLOCK_EXTS
    (include .css) via ctx.route() -> catalogo MCM non renderizzava -> 0 titoli
  - _fetch_catalog_all_pages(): usa sync_playwright() + _new_page_mcm()
    SENZA blocco CSS/font/immagini (identico a v3.5 funzionante)
  - AGGIUNTO: _new_page_mcm() -- browser pulito, settings da manga_engine
  - AGGIUNTO: _dismiss_cookie_mcm() -- con fallback page.click() (come v3.5)
  - AGGIUNTO import: sync_playwright, get_headless_mode, COOKIE_SEL, COOKIE_TEXTS
  - MANTENUTA tutta la struttura v4.0 per il resto del modulo
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

_THIS_DIR = Path(__file__).parent.resolve()
_TEMP_DIR = _THIS_DIR.parent / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

for _p in [str(_THIS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# -- Import da manga_engine ---------------------------------------------------
try:
    from manga_engine import (
        MangaPageSession, get_link_dir, get_page_timeout,
        get_headless_mode,
        sanitize_filename, clear_screen, WIDTH,
        COOKIE_SEL, COOKIE_TEXTS,
    )
    _ENGINE_OK = True
except ImportError:
    _ENGINE_OK = False
    WIDTH = 56
    def clear_screen():
        import os; os.system("cls" if os.name == "nt" else "clear")
    def sanitize_filename(n): return re.sub(r'[\\/:*?"<>|]', "_", n).strip()[:200]
    def get_link_dir():
        import json
        try:
            with open(_TEMP_DIR / "prefs.json", encoding="utf-8") as f:
                return json.load(f).get("default_link_dir", "")
        except Exception: return ""
    def get_page_timeout():
        import json
        try:
            with open(_TEMP_DIR / "prefs.json", encoding="utf-8") as f:
                return int(json.load(f).get("page_timeout", 15_000))
        except Exception: return 15_000
    def get_headless_mode():
        import json
        try:
            with open(_TEMP_DIR / "prefs.json", encoding="utf-8") as f:
                return bool(json.load(f).get("browser_headless", False))
        except Exception: return False
    COOKIE_SEL = [
        "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "#cookie-accept", ".cc-btn.cc-allow",
        "#onetrust-accept-btn-handler",
        "button[id*='accept']", "button[class*='accept']",
        "button[class*='cookie']", "a[id*='accept']",
        ".accept-cookies",
    ]
    COOKIE_TEXTS = [
        "continua", "accetta", "accept", "ok", "agree",
        "accetto", "accetta tutto", "accetta i cookie",
    ]
    class MangaPageSession:
        def __init__(self): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def dismiss_cookies(self, page=None): pass

# -- Costanti MCM -------------------------------------------------------------
BASE_URL     = "https://www.mangacomicsmarket.it"
CATALOG_URL  = (
    "https://www.mangacomicsmarket.it/catalogo"
    "?genre=Manga-15&merchant=5&availability=1"
)
TARGET_ITEMS = 96
MAX_PAGES    = 5

_SEP  = "  " + "-" * (WIDTH - 2)
_EQ   = "=" * WIDTH
_EQS  = "-" * WIDTH
_TSEP = "  " + "-" * 70

_WARNING_BEFORE_MS = 5_000
_EXTEND_BY_MS      = 15_000
_PER_PAGE_SELECTOR = 'div[role="radio"][aria-label="96"]'

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins',   {get: () => [1, 2, 3]});
Object.defineProperty(navigator, 'languages', {get: () => ['it-IT','it','en-US','en']});
window.chrome = {runtime: {}};
"""

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class _TimeoutAbort(Exception):
    pass


# -- Helpers generali ---------------------------------------------------------

def _normalise(href: str) -> str:
    if not href: return ""
    return href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")

def _extract_preorder_date(span_elem) -> str:
    if not span_elem: return ""
    m = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})', span_elem.get_text(strip=True))
    return m.group(1) if m else ""

def _format_title_with_preorder(item: dict) -> str:
    t = item["titolo"]
    return f"{t} (preord. {item['preordine']})" if item.get("preordine") else t

def _truncate_title_smart(full_text: str, max_title_len: int = 35) -> str:
    m = re.search(r'\(preord\. \d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}\)', full_text)
    preorder_part = ""
    if m:
        preorder_part = " " + m.group(0)
        title_part = full_text[:m.start()].strip()
    else:
        title_part = full_text
    available = max_title_len - len(preorder_part)
    if available < 10: available = max_title_len - 5
    if len(title_part) > available: title_part = title_part[:max(5, available - 3)] + "..."
    return title_part + preorder_part

def _ensure_mcm_folder() -> str | None:
    link_dir = get_link_dir()
    if not link_dir:
        print("\n  Percorso 'default_link_dir' non configurato.")
        alt = input("  Inserisci percorso base alternativo (invio = annulla): ").strip()
        if not alt: print("  Operazione annullata."); return None
        link_dir = alt
    folder = str(Path(link_dir) / "Ultime uscite MCM")
    try:
        Path(folder).mkdir(parents=True, exist_ok=True); return folder
    except OSError as exc: print("  Errore creazione cartella: " + str(exc)); return None


# -- Browser helpers -- FIX v4.1: senza BLOCK_EXTS ---------------------------

_cookie_dismissed_mcm: bool = False


def _new_page_mcm(playwright, extra_timeout_ms: int = 0):
    """
    Crea browser + pagina Playwright SENZA blocco CSS/font/immagini.
    FIX v4.1: MangaPageSession.open() applicava BLOCK_EXTS (include .css)
    tramite ctx.route() -> MCM (Vue/React SPA) non renderizzava -> 0 titoli.
    Usa get_headless_mode() / get_page_timeout() da manga_engine.
    """
    headless = get_headless_mode()
    timeout  = get_page_timeout() + extra_timeout_ms
    browser  = playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    ctx = browser.new_context(
        locale="it-IT",
        user_agent=_USER_AGENT,
    )
    ctx.add_init_script(_STEALTH_JS)
    page = ctx.new_page()
    page.set_default_timeout(timeout)
    return browser, page


def _dismiss_cookie_mcm(page) -> None:
    """
    Dismissal cookie con fallback page.click() per singoli selettori CSS.
    FIX v4.1: ripristina la logica completa di v3.5 (incluso il fallback loop).
    Usa COOKIE_SEL / COOKIE_TEXTS da manga_engine.
    """
    global _cookie_dismissed_mcm
    if _cookie_dismissed_mcm:
        return
    clicked = page.evaluate(
        """([selectors, textCandidates]) => {
            for (const sel of selectors) {
                try {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) { el.click(); return 'css:' + sel; }
                } catch(e) {}
            }
            const all = document.querySelectorAll(
                'button, a, input[type="button"], input[type="submit"], [role="button"]'
            );
            for (const el of all) {
                const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                if (textCandidates.includes(txt) && el.offsetParent !== null) {
                    el.click(); return 'text:' + txt;
                }
            }
            return null;
        }""",
        [COOKIE_SEL, COOKIE_TEXTS],
    )
    if clicked:
        _cookie_dismissed_mcm = True
        page.wait_for_timeout(200)
        return
    for sel in COOKIE_SEL:
        try:
            page.click(sel, timeout=600)
            _cookie_dismissed_mcm = True
            page.wait_for_timeout(200)
            return
        except Exception:
            continue


# -- MCM page helpers ---------------------------------------------------------

def _select_96_per_page(page) -> None:
    try:
        page.wait_for_selector(_PER_PAGE_SELECTOR, timeout=8_000)
        already = page.evaluate(
            """() => { const btn = document.querySelector('div[role="radio"][aria-label="96"]');
                return btn ? btn.getAttribute('aria-checked') === 'true' : false; }"""
        )
        if not already: page.click(_PER_PAGE_SELECTOR); page.wait_for_timeout(1_000)
    except Exception: pass

def _click_next_page(page) -> bool:
    try:
        clicked = page.evaluate("""() => {
            const fixed = document.querySelectorAll('span.paginator__fixed');
            for (const s of fixed) {
                const t = (s.innerText || s.textContent || '').trim();
                if (t.includes('Succ')) { s.click(); return true; }
            }
            const spans = document.querySelectorAll('div.paginator span');
            for (const s of spans) {
                const t = (s.innerText || s.textContent || '').trim();
                if (t.startsWith('Succ')) { s.click(); return true; }
            }
            return false;
        }""")
        if clicked: page.wait_for_timeout(1_500); _wait_for_catalog_items(page); return True
    except Exception: pass
    return False

def _scroll_to_load_all(page, expected: int = TARGET_ITEMS, extra_timeout_ms: int = 0) -> None:
    timeout_ms = get_page_timeout() + extra_timeout_ms
    step_ms = 150; elapsed = 0; stall_ms = 0; last_count = 0; _warned = False
    while elapsed < timeout_ms:
        count = page.evaluate("""() => {
            const tags = document.querySelectorAll('p.card__name');
            return Array.from(tags).filter(p => {
                const cls = Array.from(p.classList);
                return cls.includes('card__name') && !cls.includes('card__name--big');
            }).length;
        }""")
        if count >= expected: page.wait_for_timeout(400); break
        if count == last_count:
            stall_ms += step_ms
            if stall_ms >= 2_500: break
        else: stall_ms = 0
        last_count = count
        remaining = timeout_ms - elapsed
        if not _warned and remaining <= _WARNING_BEFORE_MS:
            _warned = True
            print(f"\n\n  \u26a0  Timeout tra circa {max(0, remaining // 1000)} secondi ({count}/{expected} elementi).")
            ans = input(f"  Attendere altri {_EXTEND_BY_MS // 1000} sec? (s=aspetta / n=esci): ").strip().lower()
            if ans in ("s", "si", "y", "yes"):
                timeout_ms += _EXTEND_BY_MS; _warned = False
                print(f"  Attesa estesa di {_EXTEND_BY_MS // 1000} secondi.")
            else: raise _TimeoutAbort("Utente ha scelto di interrompere il caricamento.")
        page.evaluate("() => window.scrollBy(0, 800)")
        page.wait_for_timeout(step_ms); elapsed += step_ms

def _wait_for_catalog_items(page) -> None:
    for sel in ["p.card__name", ".card__name", "[class*='card__name']"]:
        try: page.wait_for_selector(sel, timeout=12_000); page.wait_for_timeout(400); return
        except Exception: continue
    page.wait_for_timeout(1_500)


# -- Fetch con sync_playwright() diretto -- FIX v4.1 -------------------------

def _fetch_catalog_all_pages(url: str = CATALOG_URL) -> list:
    """
    Carica il catalogo MCM su piu pagine.

    FIX v4.1: usa sync_playwright() + _new_page_mcm() SENZA blocco CSS.
    In v4.0 MangaPageSession.open() applicava BLOCK_EXTS (con .css incluso)
    tramite ctx.route() -> MCM non renderizzava -> 0 titoli -> stall -> pagina 1.
    Logica identica a v3.5 (funzionante); impostazioni lette da manga_engine.
    """
    global _cookie_dismissed_mcm
    pages_html: list = []
    extra_ms: int = 0

    while True:
        _cookie_dismissed_mcm = False
        pages_html = []
        try:
            with sync_playwright() as pw:
                browser, pg = _new_page_mcm(pw, extra_timeout_ms=extra_ms)
                try:
                    pg.goto(url, wait_until="domcontentloaded")
                    _dismiss_cookie_mcm(pg)
                    _wait_for_catalog_items(pg)
                    _select_96_per_page(pg)
                    _wait_for_catalog_items(pg)

                    for pg_num in range(1, MAX_PAGES + 1):
                        if pg_num > 1:
                            _select_96_per_page(pg)
                            _wait_for_catalog_items(pg)
                        print(f"\n  [{pg_num}/{MAX_PAGES}]  Caricamento pagina {pg_num}...     ", end="", flush=True)
                        _scroll_to_load_all(pg, TARGET_ITEMS, extra_timeout_ms=extra_ms)
                        _dismiss_cookie_mcm(pg)
                        pg.wait_for_timeout(300)
                        html = pg.content()
                        pages_html.append(html)
                        dbg = str(_TEMP_DIR / f"debug_mcm_p{pg_num}.html")
                        with open(dbg, "w", encoding="utf-8") as f: f.write(html)
                        n_found = len(_extract_catalog_page(html))
                        print(f"\n  [{pg_num}/{MAX_PAGES}]  Pagina {pg_num}  ->  {n_found} titoli          ")
                        if pg_num < MAX_PAGES:
                            if not _click_next_page(pg):
                                print(f"  Fine paginazione a pagina {pg_num}.")
                                break
                except _TimeoutAbort:
                    print("\n  Caricamento interrotto dall'utente.")
                finally:
                    browser.close()

        except PWTimeout:
            print("\n  Timeout durante il caricamento.")
            ans = input(f"\n  Riprovare con +{_EXTEND_BY_MS // 1000} s? (s/n): ").strip().lower()
            if ans in ("s", "si", "y", "yes"):
                extra_ms += _EXTEND_BY_MS; print(f"  Riprovo con {_EXTEND_BY_MS // 1000} s in piu..."); continue
            return []
        except Exception as exc:
            print(f"\n  Errore: {str(exc)}"); return []
        return pages_html


# -- Parsing ------------------------------------------------------------------

def _extract_catalog_page(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser"); results = []
    main_div = soup.find("div", class_="main") or soup
    for p_tag in main_div.find_all("p"):
        classes = p_tag.get("class") or []
        if "card__name" not in classes or "card__name--big" in classes: continue
        a_tag = p_tag.find("a", href=True)
        if not a_tag: continue
        titolo = a_tag.get_text(strip=True); link = _normalise(a_tag.get("href", ""))
        if not titolo or not link: continue
        presale_date = ""; prezzo = ""; node = p_tag.parent
        for _ in range(8):
            if node is None: break
            if not presale_date:
                pt = node.find("span", class_="presale-tag")
                if pt:
                    lead = pt.find("span", class_="leading-normal")
                    if lead: presale_date = _extract_preorder_date(lead)
            if not prezzo:
                for span in node.find_all("span"):
                    cls_list = span.get("class") or []
                    if "card__price" in cls_list and "card__price--big" not in cls_list:
                        t = span.get_text(strip=True)
                        if t: prezzo = t; break
            if presale_date and prezzo: break
            node = node.parent
        results.append({"titolo": titolo, "link": link, "preordine": presale_date, "prezzo": prezzo})
    return results[:TARGET_ITEMS]

def _extract_all_pages(pages_html: list) -> list:
    all_items = []; seen: set = set()
    for html in pages_html:
        for item in _extract_catalog_page(html):
            lnk = item.get("link", "")
            if lnk and lnk in seen: continue
            seen.add(lnk); all_items.append(item)
    all_items.reverse(); return all_items

def _print_catalog_list(items: list) -> None:
    print(); print("  {:>4}    {:<50}  {}".format("N", "Titolo", "Prezzo")); print(_TSEP)
    for i, item in enumerate(items, 1):
        flag  = " \u25b6 " if item.get("preordine") else "   "
        full  = _format_title_with_preorder(item)
        title = _truncate_title_smart(full, max_title_len=50)
        print("  {:>4}.{}{:<50}  {}".format(i, flag, title, item.get("prezzo", "")))
    print(_TSEP)
    total = len(items); pre_n = sum(1 for it in items if it.get("preordine"))
    print("  Totale: {}  (disponibili: {}  |  preordini: {})".format(total, total - pre_n, pre_n))
    print("  Ordine: dal piu vecchio (in alto) al piu recente (in basso)")
    if pre_n: print("  \u25b6 = preordine")

def _select_entries(item_map: dict) -> list | None:
    if not item_map: print("  Nessun titolo disponibile."); return None
    max_n = max(item_map.keys())
    while True:
        print("\n" + _SEP)
        print(f"  Titoli disponibili: 1-{max_n}")
        print("  Selezione:  Singolo(5)  Multiplo(1,3,7)  Range(1-10)  Tutti(T)  Annulla(0)")
        print(_SEP); raw = input("  Selezione: ").strip()
        if raw == "0": return None
        if raw.upper() == "T": return list(item_map.values())
        selected = []; has_error = False
        for part in [p.strip() for p in raw.split(",") if p.strip()]:
            if "-" in part:
                try:
                    a_s, b_s = part.split("-", 1); a, b = int(a_s.strip()), int(b_s.strip())
                    if a > b: a, b = b, a
                    for n in range(a, b + 1):
                        if n in item_map:
                            if item_map[n] not in selected: selected.append(item_map[n])
                        else: print(f"  Numero {n} fuori range (1-{max_n}) \u2014 ignorato.")
                except ValueError: print(f"  Range non valido: '{part}' \u2014 ignorato."); has_error = True
            else:
                try:
                    n = int(part)
                    if n in item_map:
                        if item_map[n] not in selected: selected.append(item_map[n])
                    else: print(f"  Numero {n} fuori range (1-{max_n}) \u2014 ignorato.")
                except ValueError: print(f"  Valore non valido: '{part}' \u2014 ignorato."); has_error = True
        if has_error: input("  Premi invio per riprovare..."); continue
        if not selected: print("  Nessun titolo valido."); input("  Premi invio per riprovare..."); continue
        return selected

def _write_multi_items(folder: str, entries: list) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = "MCM_Uscite_" + ts
    fpath = str(Path(folder) / (base_name + ".txt"))
    if Path(fpath).exists():
        c = 1
        while (Path(folder) / f"{base_name}_{c}.txt").exists(): c += 1
        fpath = str(Path(folder) / f"{base_name}_{c}.txt")
    lines = [_EQ, "  USCITE E PREORDER \u2014 MangaComicsMarket.it", _EQ]
    for i, e in enumerate(entries, 1):
        lines.extend(["", "  [{:>3}]  {}".format(i, e.get("titolo", "")), "  " + _EQS])
        if e.get("prezzo"):    lines.append("  Prezzo:          " + e["prezzo"])
        if e.get("preordine"): lines.append("  Preordine:       " + e["preordine"])
        if e.get("link"):      lines.append("  (" + e["link"] + ")")
    lines.extend(["", _EQ])
    try:
        with open(fpath, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        print("  Salvato: " + fpath)
    except OSError as exc: print("  Errore salvataggio: " + str(exc))


# -- Entry point --------------------------------------------------------------

def handle_mcm_uscite() -> None:
    """Entry point chiamato da handlers.py."""
    clear_screen()
    print(_EQ); print("  ULTIME USCITE E PREORDER  \u2014  MangaComicsMarket.it")
    print("  (T.D.M. Fumetti)"); print(_EQ)
    print("\n  URL di default:\n  " + CATALOG_URL)
    raw_url = input("\n  Premi INVIO per usarlo, o incolla un URL diverso: ").strip()
    url_da_usare = raw_url if raw_url else CATALOG_URL
    print(f"\n  Caricamento catalogo ({MAX_PAGES} pagine x {TARGET_ITEMS} titoli/pagina)...")
    pages_html = _fetch_catalog_all_pages(url_da_usare)
    if not pages_html: print("\n  Errore: impossibile caricare il catalogo."); input("  Premi invio..."); return
    items = _extract_all_pages(pages_html)
    if not items: print("\n  Nessun titolo trovato."); input("  Premi invio..."); return
    print(f"\n  Totale titoli acquisiti: {len(items)}")
    item_map = {i: item for i, item in enumerate(items, 1)}

    def _show_list():
        clear_screen(); print(_EQ)
        print("  ULTIME USCITE E PREORDER  \u2014  MangaComicsMarket.it")
        print(f"  ({MAX_PAGES} pag.  *  {TARGET_ITEMS} titoli/pag.  *  max {MAX_PAGES * TARGET_ITEMS})")
        print(_EQ); print("  URL: " + url_da_usare); _print_catalog_list(items)

    _show_list()
    while True:
        selected = _select_entries(item_map)
        if selected is None: return
        n_sel = len(selected); clear_screen(); print(_EQ)
        print(f"  {n_sel} titolo/i selezionato/i"); print(_EQ); print()
        for i, e in enumerate(selected, 1):
            flag  = " \u25b6 " if e.get("preordine") else "   "
            title = _truncate_title_smart(_format_title_with_preorder(e), max_title_len=50)
            prezzo = e.get("prezzo", ""); pr_str = "  " + prezzo if prezzo else ""
            print(f"  {i:>3}.{flag}{title:<50}{pr_str}")
        print()
        if input("  Vuoi esportare in file .txt? (s/n): ").strip().lower() in ("s", "si", "y", "yes"):
            folder = _ensure_mcm_folder()
            if folder: _write_multi_items(folder, selected); print(f"\n  {n_sel} titolo/i in: {folder}")
            input("\n  Premi invio per continuare...")
        _show_list()


if __name__ == "__main__":
    handle_mcm_uscite()
