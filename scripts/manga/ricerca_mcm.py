#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_mcm.py v5.9 — 1 pagina x 96 risultati (AUTO e MANUAL)
# FIX v5.9: ottimizzazioni timing AUTO (stall 3000->1200ms, skip wait 300ms, skip wait 200ms cookie)
#            Evita blocco su titoli con risultati generici MCM
=========================================================
Modulo per la Ricerca articoli su MangaComicsMarket.it.
Percorso: scripts/manga/ricerca_mcm.py

NOVITA v5.0 (performance):
  P1 - URL con &term=titolo: goto() gia con risultati filtrati
       Elimina _perform_search() + attesa post-ricerca (~6-17s/manga)
  P2 - MAX_PAGES = 1 per entrambe le modalita
       96 risultati coprono teoricamente 96 mesi di uscite mensili
  P3 - TARGET_ITEMS = 96 per entrambe le modalita

  Risparmio stimato per ricerca automatica: -60/75% per manga

NOVITA v5.2 (fix):
       MCM restituisce i volumi in ordine crescente (v.1 ... v.74);
       il reverse li capovolgeva nascondendo i volumi piu recenti.

NOVITA v5.1:
  Unificato a 1 pagina x 96 risultati per AUTO e MANUAL

INVARIATO: parsing, UI manuale, _select_entries, _save_acquisti
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

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

# -- Costanti modulo ----------------------------------------------------------
BASE_URL = "https://www.mangacomicsmarket.it"

# URL base catalogo (senza termine di ricerca)
_CATALOG_BASE = (
    "https://www.mangacomicsmarket.it/catalogo/fumetti"
    "?genre=Manga-15&merchant=5"
)

# Mantenuto per compatibilita con moduli esterni
CATALOG_URL = _CATALOG_BASE

# P2: pagine massime per modalita
MAX_PAGES_AUTO   = 1   # ricerca automatica: 1 pagina basta
MAX_PAGES_MANUAL = 1   # ricerca manuale: 1 pagina (96 risultati sufficienti)
MAX_PAGES        = MAX_PAGES_MANUAL  # default (compatibilita)

# P3: target item per modalita
TARGET_ITEMS_AUTO   = 96   # ricerca automatica: 96 risultati (= MANUAL)
TARGET_ITEMS_MANUAL = 96   # ricerca manuale: 96 per pagina
TARGET_ITEMS        = TARGET_ITEMS_MANUAL  # default (compatibilita)

MAX_CARD_LEVELS = 8

_SEP  = "  " + "-" * (WIDTH - 2)
_EQ   = "=" * WIDTH
_EQS  = "-" * WIDTH
_TSEP = "  " + "-" * 70

_WARNING_BEFORE_MS = 5_000
_EXTEND_BY_MS      = 15_000
SEARCH_INPUT_SEL   = 'input[placeholder="Cosa stai cercando?"]' 
_PER_PAGE_SELECTOR = 'div[role="radio"][aria-label="96"]'

_MESI_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

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


# -- Helpers locali -----------------------------------------------------------

def _ensure_acquisti_folder() -> str | None:
    link_dir = get_link_dir()
    if not link_dir:
        print("\n  Percorso 'default_link_dir' non configurato.")
        alt = input("  Inserisci percorso base alternativo (invio = annulla): ").strip()
        if not alt: print("  Operazione annullata."); return None
        link_dir = alt
    folder = str(Path(link_dir) / "Acquisti online manga")
    try:
        Path(folder).mkdir(parents=True, exist_ok=True); return folder
    except OSError as exc: print("  Errore creazione cartella: " + str(exc)); return None

def _save_acquisti(folder: str, selected: list) -> None:
    now   = datetime.now()
    mese  = _MESI_IT[now.month]
    anno  = str(now.year)
    fname = f"Acquisti futuri - {mese} {anno}.txt"
    fpath = str(Path(folder) / fname)
    lines = []
    for e in selected:
        titolo    = e.get("titolo", "").strip()
        link      = e.get("link", "").strip()
        preordine = e.get("preordine", "").strip()
        if preordine: lines.append(f"{titolo} (preord. {preordine}) - {link}")
        else:         lines.append(f"{titolo} - {link}")
    mode = "a" if Path(fpath).exists() else "w"
    try:
        with open(fpath, mode, encoding="utf-8") as f:
            if mode == "a": f.write("\n")
            f.write("\n".join(lines) + "\n")
        print("  Salvato: " + fpath)
    except OSError as exc: print("  Errore salvataggio: " + str(exc))


# -- Browser helpers ----------------------------------------------------------

_cookie_dismissed_mcm: bool = False


def _perform_search(page, search_term: str) -> bool:
    """Fallback: digita nel campo ricerca. Usato solo se &term= non funziona."""
    try: page.wait_for_selector(SEARCH_INPUT_SEL, timeout=10_000)
    except Exception as exc: print("\n  Campo ricerca non trovato: " + str(exc)); return False
    for attempt in range(3):
        try:
            if attempt == 0:
                page.fill(SEARCH_INPUT_SEL, ""); page.wait_for_timeout(150)
                page.fill(SEARCH_INPUT_SEL, search_term)
                page.evaluate("""(sel) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""", SEARCH_INPUT_SEL)
                page.wait_for_timeout(500); page.press(SEARCH_INPUT_SEL, "Enter")
            elif attempt == 1:
                page.click(SEARCH_INPUT_SEL, click_count=3); page.wait_for_timeout(200)
                page.keyboard.type(search_term, delay=50); page.press(SEARCH_INPUT_SEL, "Enter")
            else:
                page.focus(SEARCH_INPUT_SEL); page.keyboard.press("Control+a")
                page.wait_for_timeout(150); page.keyboard.type(search_term, delay=50)
                page.keyboard.press("Enter")
            page.wait_for_timeout(2_500); _wait_for_catalog_items(page); return True
        except Exception: continue
    print("\n  Ricerca non riuscita.")
    return False


# -- P1: costruisce URL con &term= -----------------------------------------------

def _build_search_url(search_term: str) -> str:
    """
    P1: Aggiunge &term=<termine_codificato> all'URL base.
    Esempio: /catalogo?genre=Manga-15&merchant=5&term=kingdom
    """
    encoded = quote_plus(search_term)
    return f"{_CATALOG_BASE}&term={encoded}"


# -- Fetch principale ---------------------------------------------------------


def _fetch_search_pages(
    search_term: str,
    mode: str = "manual",
) -> list:
    """
    Carica risultati ricerca MCM.

    Logica:
      1. goto(URL con &term=titolo)
      2. Aspetta che MCM risponda: cards trovate  OPPURE  div 'Nessun prodotto trovato'
      3a. Se compare il div 'Nessun prodotto trovato' -> return []  (zero attese extra)
      3b. Se compaiono cards -> prosegui con scroll e parsing
      3c. Se timeout (MCM non risponde) -> in AUTO return [], in MANUAL fallback _perform_search

    mode = 'auto'   -> no prompt interattivi, timeout breve (4 s)
    mode = 'manual' -> prompt interattivi, timeout lungo (12 s),
                       fallback _perform_search se &term= non funziona
    """
    global _cookie_dismissed_mcm

    is_auto   = (mode == "auto")
    max_pages = MAX_PAGES_AUTO   if is_auto else MAX_PAGES_MANUAL
    target    = TARGET_ITEMS_AUTO if is_auto else TARGET_ITEMS_MANUAL
    extra_ms  = 0

    # JS: restituisce "empty" | "found" | "none"
    _RACE_JS = """() => {
        const empty = Array.from(document.querySelectorAll('.text-grey-strong'))
            .some(el => el.textContent.includes('Nessun prodotto trovato'));
        if (empty) return 'empty';
        const cards = Array.from(document.querySelectorAll('p.card__name'))
            .filter(p => {
                const cls = Array.from(p.classList);
                return cls.includes('card__name') && !cls.includes('card__name--big');
            });
        if (cards.length > 0) return 'found';
        return 'none';
    }"""

    search_url = _build_search_url(search_term)

    while True:
        _cookie_dismissed_mcm = False
        pages_html: list = []

        try:
            with sync_playwright() as pw:
                browser, pg = _new_page_mcm(pw, extra_timeout_ms=extra_ms)
                try:
                    # ── 1. Naviga all'URL con il termine gia incluso ──────────────
                    pg.goto(search_url, wait_until="domcontentloaded")
                    _dismiss_cookie_mcm(pg)

                    # ── 2. Race: aspetta cards OPPURE div 'Nessun prodotto trovato'
                    _race_timeout = 4_000 if is_auto else 12_000
                    try:
                        pg.wait_for_function(
                            """() => {
                                const empty = Array.from(document.querySelectorAll('.text-grey-strong'))
                                    .some(el => el.textContent.includes('Nessun prodotto trovato'));
                                if (empty) return true;
                                const cards = Array.from(document.querySelectorAll('p.card__name'))
                                    .filter(p => {
                                        const cls = Array.from(p.classList);
                                        return cls.includes('card__name') && !cls.includes('card__name--big');
                                    });
                                return cards.length > 0;
                            }""",
                            timeout=_race_timeout,
                        )
                    except Exception:
                        pass  # timeout: valutiamo comunque lo stato DOM

                    # ── 3. Leggi lo stato attuale del DOM ─────────────────────────
                    _state = pg.evaluate(_RACE_JS)

                    if _state == "empty":
                        # MCM ha risposto: nessun risultato -> esci subito
                        return []

                    if _state == "none":
                        # Nessuna risposta dal DOM (MCM lento o &term= non funziona)
                        if is_auto:
                            return []
                        # MANUAL: fallback con _perform_search
                        pg.goto(_CATALOG_BASE, wait_until="domcontentloaded")
                        _dismiss_cookie_mcm(pg)
                        _wait_for_catalog_items(pg, auto_timeout_ms=None)
                        ok = _perform_search(pg, search_term)
                        if not ok:
                            return []
                        # Dopo fallback: ricontrolla lo stato
                        _state = pg.evaluate(_RACE_JS)
                        if _state in ("empty", "none"):
                            return []
                        # _state == "found": prosegui

                    # ── 4. Cards trovate: scroll + parsing ────────────────────────
                    if not is_auto:
                        _select_96_per_page(pg)

                    for pg_num in range(1, max_pages + 1):
                        if pg_num > 1:
                            if not is_auto:
                                _select_96_per_page(pg)
                            _wait_for_catalog_items(
                                pg,
                                auto_timeout_ms=4_000 if is_auto else None,
                            )

                        _scroll_to_load_all(
                            pg,
                            expected=target,
                            extra_timeout_ms=extra_ms,
                            interactive=not is_auto,
                        )
                        _dismiss_cookie_mcm(pg)
                        if not is_auto: pg.wait_for_timeout(300)  # FIX v5.8: skip in AUTO
                        html = pg.content()
                        pages_html.append(html)

                        if not is_auto:
                            dbg = str(_TEMP_DIR / f"debug_ricerca_p{pg_num}.html")
                            with open(dbg, "w", encoding="utf-8") as f:
                                f.write(html)

                        if pg_num < max_pages and not is_auto:
                            if not _click_next_page(pg):
                                break

                except _TimeoutAbort:
                    if not is_auto:
                        print("\n  Caricamento interrotto dall'utente.")
                finally:
                    browser.close()

        except PWTimeout:
            if is_auto:
                return []
            print("\n  Timeout durante il caricamento.")
            ans = input(f"\n  Riprovare con +{_EXTEND_BY_MS // 1000} s? (s/n): ").strip().lower()
            if ans in ("s", "si", "y", "yes"):
                extra_ms += _EXTEND_BY_MS
                print(f"  Riprovo con {_EXTEND_BY_MS // 1000} s in piu...")
                continue
            return []
        except Exception as exc:
            print("\n  Errore: " + str(exc))
            return []

        return pages_html

# -- Parsing ------------------------------------------------------------------

def _find_card_container(p_tag):
    node = p_tag.parent
    for _ in range(MAX_CARD_LEVELS):
        if node is None: return p_tag.parent
        parent = node.parent
        if parent is None: return node
        names_in_parent = [
            n for n in parent.find_all("p")
            if "card__name" in (n.get("class") or [])
            and "card__name--big" not in (n.get("class") or [])
        ]
        if len(names_in_parent) > 1: return node
        node = parent
    return node

def handle_ricerca_mcm() -> None:
    """Entry point chiamato da handlers.py. Usa sempre mode='manual'."""
    while True:
        clear_screen(); print(_EQ)
        print("  RICERCA ARTICOLI  - MangaComicsMarket.it")
        print("  (T.D.M. Fumetti)"); print(_EQ)
        print(f"  Ricerca titoli nel catalogo MCM  (1 pagina x {TARGET_ITEMS_MANUAL} titoli)")
        search_term = input("\n  Inserisci il titolo da cercare (0 = esci): ").strip()
        if search_term == "0": return
        if not search_term: continue
        print("\n  Caricamento risultati in corso...\n")
        pages_html = _fetch_search_pages(search_term, mode="manual")
        if not pages_html:
            print("\n  Errore: impossibile caricare i risultati.")
            input("  Premi invio per riprovare..."); continue
        items = _extract_all_pages(pages_html)
        if not items:
            print(f"\n  Nessun risultato per: '{search_term}'.")
            input("  Premi invio per riprovare..."); continue
        item_map = {i: item for i, item in enumerate(items, 1)}

        def _reprint():
            clear_screen(); print(_EQ)
            print(f"  RISULTATI RICERCA: '{search_term}'")
            print(f"  MangaComicsMarket.it  (1 pag. | {TARGET_ITEMS_MANUAL} tit./pag.)")
            print(_EQ); _print_catalog_list(items)

        _reprint()
        selected = _select_entries(item_map)
        if selected:
            folder = _ensure_acquisti_folder()
            if folder:
                _save_acquisti(folder, selected)
                n_sel = len(selected); print()
                print(f"  {n_sel} titolo/i aggiunto/i alla lista acquisti:")
                for e in selected:
                    title = _format_title_with_preorder(e)
                    if len(title) > 52: title = title[:49] + "..."
                    print("  * " + title)
                print("  Cartella: " + folder)
        input("\n  Premi invio per una nuova ricerca  (0 nel campo = esci)...")


if __name__ == "__main__":
    handle_ricerca_mcm()