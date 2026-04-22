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
from scripts.core.url_manager import get as get_url

# ── [refactor] ora in manga_engine ────────────────────────────────────────
from manga_engine import (
    _click_next_page,
    _dismiss_cookie_mcm,
    _extract_all_pages,
    _extract_catalog_page,
    _extract_preorder_date,
    _format_title_with_preorder,
    _new_page_mcm,
    _normalise,
    _print_catalog_list,
    _scroll_to_load_all,
    _select_96_per_page,
    _select_entries,
    _wait_for_catalog_items,
)

BASE_URL    = get_url("download", "amazon")
_SEARCH_URL = get_url("download", "amazon_search")
CATALOG_URL = get_url("manga", "mangacomicsmarket_catalogo")
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