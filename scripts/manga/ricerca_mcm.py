#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_mcm.py v5.2 — 1 pagina x 96 risultati (AUTO e MANUAL)
=========================================================
Modulo per la Ricerca articoli su MangaComicsMarket.it.
Percorso: scripts/manga/ricerca_mcm.py

NOVITA v5.0 (performance):
  P1 - URL con ?q=titolo: goto() gia con risultati filtrati
       Elimina _perform_search() + attesa post-ricerca (~6-17s/manga)
  P2 - MAX_PAGES = 1 per entrambe le modalita
       96 risultati coprono teoricamente 96 mesi di uscite mensili
  P3 - TARGET_ITEMS = 96 per entrambe le modalita

  Risparmio stimato per ricerca automatica: -60/75% per manga

NOVITA v5.2 (fix):
  F1 - Rimosso all_items.reverse() in _extract_all_pages
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
    "https://www.mangacomicsmarket.it/catalogo"
    "?genre=Manga-15&merchant=5&availability=1"
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


# -- Cartella acquisti --------------------------------------------------------

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


def _new_page_mcm(playwright, extra_timeout_ms: int = 0):
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
            """() => { const btn=document.querySelector('div[role="radio"][aria-label="96"]');
                return btn ? btn.getAttribute('aria-checked')=== 'true' : false; }"""
        )
        if not already: page.click(_PER_PAGE_SELECTOR); page.wait_for_timeout(2_000)
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
        if clicked: page.wait_for_timeout(2_000); _wait_for_catalog_items(page); return True
    except Exception: pass
    return False

def _scroll_to_load_all(
    page,
    expected: int = TARGET_ITEMS_MANUAL,
    extra_timeout_ms: int = 0,
    interactive: bool = True,
) -> None:
    """
    P3: expected = 96 in entrambe le modalita.
    interactive=False disabilita il prompt di estensione (usato in auto).
    """
    timeout_ms = get_page_timeout() + extra_timeout_ms
    step_ms = 600; elapsed = 0; stall_ms = 0; last_count = 0; _warned = False
    while elapsed < timeout_ms:
        count = page.evaluate("""() => {
            const tags = document.querySelectorAll('p.card__name');
            return Array.from(tags).filter(p => {
                const cls = Array.from(p.classList);
                return cls.includes('card__name') && !cls.includes('card__name--big');
            }).length;
        }""")
        if count >= expected: break
        if count == last_count:
            stall_ms += step_ms
            if stall_ms >= 3_000: break
        else: stall_ms = 0
        last_count = count
        remaining = timeout_ms - elapsed
        if interactive and not _warned and remaining <= _WARNING_BEFORE_MS:
            _warned = True
            print(f"\n\n  Timeout tra circa {max(0, remaining // 1000)} secondi ({count}/{expected} elementi).")
            ans = input(f"  Attendere altri {_EXTEND_BY_MS // 1000} sec? (s=aspetta / n=esci): ").strip().lower()
            if ans in ("s", "si", "y", "yes"):
                timeout_ms += _EXTEND_BY_MS; _warned = False
                print(f"  Attesa estesa di {_EXTEND_BY_MS // 1000} secondi.")
            else: raise _TimeoutAbort("Utente ha scelto di interrompere.")
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(step_ms); elapsed += step_ms

def _wait_for_catalog_items(page) -> None:
    for sel in ["p.card__name", ".card__name", "[class*='card__name']"]:
        try: page.wait_for_selector(sel, timeout=12_000); page.wait_for_timeout(800); return
        except Exception: continue
    page.wait_for_timeout(3_000)

def _perform_search(page, search_term: str) -> bool:
    """Fallback: digita nel campo ricerca. Usato solo se ?q= non funziona."""
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


# -- P1: costruisce URL con ?q= -----------------------------------------------

def _build_search_url(search_term: str) -> str:
    """
    P1: Aggiunge &q=<termine_codificato> all'URL base.
    Esempio: /catalogo?genre=Manga-15&merchant=5&availability=1&q=kingdom
    """
    encoded = quote_plus(search_term)
    return f"{_CATALOG_BASE}&q={encoded}"


# -- Fetch principale ---------------------------------------------------------

def _fetch_search_pages(
    search_term: str,
    mode: str = "manual",
) -> list:
    """
    Carica risultati ricerca MCM.

    mode = "auto"   -> MAX_PAGES_AUTO=1, TARGET_ITEMS_AUTO=96,
                       URL diretta ?q=, no prompt interattivi
    mode = "manual" -> MAX_PAGES_MANUAL=1, TARGET_ITEMS_MANUAL=96,
                       URL diretta ?q= con fallback _perform_search,
                       prompt interattivi attivi

    P1: Tenta sempre prima l'URL diretta con ?q=.
        Se dopo 3s ci sono 0 risultati E siamo in modalita manual,
        fa fallback a _perform_search() (SPA pura).
    P2: max_pages dipende da mode.
    P3: target_items dipende da mode.
    """
    global _cookie_dismissed_mcm

    is_auto    = (mode == "auto")
    max_pages  = MAX_PAGES_AUTO   if is_auto else MAX_PAGES_MANUAL
    target     = TARGET_ITEMS_AUTO if is_auto else TARGET_ITEMS_MANUAL
    extra_ms   = 0

    # P1: URL con ?q= diretta
    search_url = _build_search_url(search_term)

    while True:
        _cookie_dismissed_mcm = False
        pages_html: list = []

        try:
            with sync_playwright() as pw:
                browser, pg = _new_page_mcm(pw, extra_timeout_ms=extra_ms)
                try:
                    # P1: goto con ?q= gia nell'URL
                    pg.goto(search_url, wait_until="domcontentloaded")
                    _dismiss_cookie_mcm(pg)

                    pg.wait_for_timeout(800)
                    quick_count = pg.evaluate("""() => {
                        const tags = document.querySelectorAll('p.card__name');
                        return Array.from(tags).filter(p => {
                            const cls = Array.from(p.classList);
                            return cls.includes('card__name') && !cls.includes('card__name--big');
                        }).length;
                    }""")

                    # Fallback a _perform_search solo in modalita manual
                    if quick_count == 0 and not is_auto:
                        pg.goto(_CATALOG_BASE, wait_until="domcontentloaded")
                        _dismiss_cookie_mcm(pg)
                        _wait_for_catalog_items(pg)
                        _perform_search(pg, search_term)

                    pg.wait_for_timeout(500)
                    final_quick = pg.evaluate("""() => {
                        const tags = document.querySelectorAll('p.card__name');
                        return Array.from(tags).filter(p => {
                            const cls = Array.from(p.classList);
                            return cls.includes('card__name') && !cls.includes('card__name--big');
                        }).length;
                    }""")
                    if final_quick == 0:
                        pages_html.append(pg.content())
                        browser.close()
                        return pages_html

                    _wait_for_catalog_items(pg)

                    if not is_auto:
                        _select_96_per_page(pg)

                    for pg_num in range(1, max_pages + 1):
                        if pg_num > 1:
                            if not is_auto:
                                _select_96_per_page(pg)
                            _wait_for_catalog_items(pg)

                        # P3: target = 96 in entrambe le modalita; no prompt in auto
                        _scroll_to_load_all(
                            pg,
                            expected=target,
                            extra_timeout_ms=extra_ms,
                            interactive=not is_auto,
                        )
                        _dismiss_cookie_mcm(pg)
                        pg.wait_for_timeout(300)
                        html = pg.content()
                        pages_html.append(html)

                        if not is_auto:
                            dbg = str(_TEMP_DIR / f"debug_ricerca_p{pg_num}.html")
                            with open(dbg, "w", encoding="utf-8") as f: f.write(html)

                        # P2: max_pages=1 in entrambe le modalita
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
        container = _find_card_container(p_tag)
        presale_date = ""; prezzo = ""
        pt_tag = container.find("span", class_="presale-tag")
        if pt_tag:
            lead = pt_tag.find("span", class_="leading-normal")
            presale_date = _extract_preorder_date(lead) if lead else ""
        for span in container.find_all("span"):
            cls = span.get("class") or []
            if "card__price" in cls and "card__price--big" not in cls:
                t = span.get_text(strip=True)
                if t and re.search(r"\d", t): prezzo = t; break
        results.append({"titolo": titolo, "link": link, "preordine": presale_date, "prezzo": prezzo})
    return results[:TARGET_ITEMS_MANUAL]

def _extract_all_pages(pages_html: list) -> list:
    all_items = []; seen: set = set()
    for html in pages_html:
        for item in _extract_catalog_page(html):
            lnk = item.get("link", "")
            if lnk and lnk in seen: continue
            seen.add(lnk); all_items.append(item)
    return all_items

def _print_catalog_list(items: list) -> None:
    print(); print("  {:>4}     {:<46}  {}".format("N", "Titolo", "Prezzo")); print(_TSEP)
    for i, item in enumerate(items, 1):
        flag  = " > " if item.get("preordine") else "   "
        title = _format_title_with_preorder(item)
        if len(title) > 46: title = title[:43] + "..."
        print("  {:>4}.{}{:<46}  {}".format(i, flag, title, item.get("prezzo", "")))
    print(_TSEP)
    total = len(items); pre_n = sum(1 for it in items if it.get("preordine"))
    print("  Totale: {}  (disponibili: {}  |  preordini: {})".format(total, total - pre_n, pre_n))
    if pre_n: print("  > = preordine")

def _select_entries(item_map: dict) -> list | None:
    if not item_map: print("  Nessun titolo disponibile."); return None
    max_n = max(item_map.keys())
    while True:
        print("\n" + _SEP)
        print("  Aggiungi alla lista acquisti:")
        print(f"  Titoli: 1-{max_n}  |  Singolo  Multiplo(1,3,7)  Range(1-10)  Tutti(T)  Annulla(0)")
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
                        else: print(f"  Numero {n} fuori range (1-{max_n}) - ignorato.")
                except ValueError: print(f"  Range non valido: '{part}' - ignorato."); has_error = True
            else:
                try:
                    n = int(part)
                    if n in item_map:
                        if item_map[n] not in selected: selected.append(item_map[n])
                    else: print(f"  Numero {n} fuori range (1-{max_n}) - ignorato.")
                except ValueError: print(f"  Valore non valido: '{part}' - ignorato."); has_error = True
        if has_error: input("  Premi invio per riprovare..."); continue
        if not selected: print("  Nessun titolo valido."); input("  Premi invio per riprovare..."); continue
        return selected


# -- Entry point --------------------------------------------------------------

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
