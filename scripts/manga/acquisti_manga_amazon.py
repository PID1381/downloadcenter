#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
acquisti_manga_amazon.py v2.2
==============================
Modulo per la ricerca manga su Amazon.it.
Percorso: scripts/manga/acquisti_manga_amazon.py

NOVITA v2.2:
  - Esportazione titoli in file di testo:
      {default_export_dir}/Acquisti manga Amazon/Lista Amazon - {Mese} {Anno}.txt
  - Formato riga: Titolo - URL Amazon
  - Append automatico: ricerche successive aggiungono in coda allo stesso file
  - Intestazione sessione: data + query(s) per leggibilita nel file
  - Conferma pre-salvataggio: anteprima titoli + percorso file
  - Opzione E (Esporta) nel menu principale risultati
"""
from __future__ import annotations

import json
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

# ── Import da manga_engine ────────────────────────────────────────────────────
try:
    from manga_engine import (
        load_prefs, get_headless_mode, get_page_timeout,
        clear_screen, sanitize_filename, WIDTH,
    )
    _ENGINE_OK = True
except ImportError:
    _ENGINE_OK = False
    WIDTH = 56

    def clear_screen():
        import os; os.system("cls" if os.name == "nt" else "clear")

    def sanitize_filename(n):
        return re.sub(r'[\\/:*?"<>|]', "_", n).strip()[:200]

    def load_prefs() -> dict:
        try:
            with open(_TEMP_DIR / "prefs.json", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get_headless_mode() -> bool:
        return bool(load_prefs().get("browser_headless", False))

    def get_page_timeout() -> int:
        try:
            return int(load_prefs().get("page_timeout", 15_000))
        except (ValueError, TypeError):
            return 15_000


# ── Costanti modulo ────────────────────────────────────────────────────────────
from scripts.core.url_manager import get as get_url
BASE_URL    = get_url("download", "amazon")
_SEARCH_URL = get_url("download", "amazon_search")
AMAZON_FOLDER = "Acquisti manga Amazon"
FILE_PREFIX   = "Lista Amazon - "

_SEP  = "  " + "-" * (WIDTH - 2)
_EQ   = "=" * WIDTH
_EQS  = "-" * WIDTH
_TSEP = "  " + "-" * 72

_MESI_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

# Stealth JS e selettori cookie Amazon-specific
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins',   {get: () => [1, 2, 3]});
Object.defineProperty(navigator, 'languages', {get: () => ['it-IT','it','en-US','en']});
window.chrome = {runtime: {}};
"""

_COOKIE_SELECTORS = [
    "#sp-cc-accept",
    "input[name='accept']",
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
    "button[data-action*='accept']",
]
_COOKIE_TEXTS = ["accetta", "accept", "ok", "accetta tutto", "accetto", "continua"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalise(href: str) -> str:
    if not href:
        return ""
    return href if href.startswith("http") else BASE_URL + (href if href.startswith("/") else "/" + href)


def _get_export_dir() -> str:
    """
    Legge 'default_export_dir' da prefs.json.
    Chiave separata da 'default_link_dir': percorso dedicato all'export file.
    """
    return load_prefs().get("default_export_dir", "")


# ── Cartella export ────────────────────────────────────────────────────────────

def _get_folder() -> str | None:
    """
    Restituisce il percorso della cartella di export:
        {default_export_dir}/Acquisti manga Amazon/
    Usa la chiave 'default_export_dir' da prefs.json.
    La crea se non esiste.
    """
    base = _get_export_dir()
    if not base:
        print("\n  Percorso 'default_export_dir' non configurato nelle Impostazioni.")
        base = input("  Inserisci percorso base alternativo (invio = annulla): ").strip()
        if not base:
            print("  Operazione annullata.")
            return None
    folder = str(Path(base) / AMAZON_FOLDER)
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    except OSError as exc:
        print(f"  Errore creazione cartella: {exc}")
        return None


# ── Browser (sync_playwright diretto, senza BLOCK_EXTS) ──────────────────────
# NOTA: NON usare MangaPageSession qui.
#   MangaPageSession.open() registra ctx.route() per BLOCK_EXTS (include .css).
#   Amazon e una React SPA: senza CSS i componenti non si montano,
#   wait_for_selector va in timeout su tutti i selettori -> 0 risultati.

_cookie_dismissed: bool = False


def _new_page(playwright):
    """Browser senza blocco CSS/font/immagini — necessario per Amazon React SPA."""
    browser = playwright.chromium.launch(
        headless=get_headless_mode(),
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    ctx = browser.new_context(
        locale="it-IT",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        # nessun ctx.route() -> nessun blocco CSS/JS
    )
    ctx.add_init_script(_STEALTH_JS)
    page = ctx.new_page()
    page.set_default_timeout(get_page_timeout())
    return browser, page


def _dismiss_cookie(page) -> None:
    global _cookie_dismissed
    if _cookie_dismissed:
        return
    try:
        clicked = page.evaluate(
            """([selectors, texts]) => {
                for (const sel of selectors) {
                    try {
                        const el = document.querySelector(sel);
                        if (el && el.offsetParent !== null) { el.click(); return true; }
                    } catch(e) {}
                }
                const all = document.querySelectorAll(
                    'button, a, input[type="button"], input[type="submit"]'
                );
                for (const el of all) {
                    const txt = (el.innerText || el.value || '').trim().toLowerCase();
                    if (texts.includes(txt) && el.offsetParent !== null) {
                        el.click(); return true;
                    }
                }
                return false;
            }""",
            [_COOKIE_SELECTORS, _COOKIE_TEXTS],
        )
        if clicked:
            _cookie_dismissed = True
            page.wait_for_timeout(500)
    except Exception:
        pass


def _is_captcha_page(html: str) -> bool:
    lower = html.lower()
    return (
        "captcha" in lower
        or "robot check" in lower
        or "enter the characters" in lower
        or "automated access" in lower
    )


def _wait_for_results(page) -> bool:
    """Attende il primo selettore disponibile nei risultati Amazon."""
    for sel in [
        "[data-component-type='s-search-result']",
        ".s-result-item",
        ".s-search-results",
        "#search",
    ]:
        try:
            page.wait_for_selector(sel, timeout=10_000)
            page.wait_for_timeout(800)
            return True
        except Exception:
            continue
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        pass
    page.wait_for_timeout(2_000)
    return False


# ── Fetch HTML ─────────────────────────────────────────────────────────────────

def _fetch_amazon_search(query: str) -> list[dict]:
    """
    Apre Amazon.it, esegue la ricerca e restituisce i risultati.
    Usata anche da ricerca_automatica_acquisti.py.
    """
    global _cookie_dismissed
    _cookie_dismissed = False
    encoded = quote_plus(query)  # FIX-A: rimosso " manga" ridondante
    url     = _SEARCH_URL.format(query=encoded)
    html    = ""

    try:
        with sync_playwright() as pw:
            browser, page = _new_page(pw)
            try:
                page.goto(url, wait_until="domcontentloaded")
                _dismiss_cookie(page)
                _wait_for_results(page)
                _dismiss_cookie(page)
                html = page.content()
                with open(str(_TEMP_DIR / "debug_amazon.html"), "w", encoding="utf-8") as f:
                    f.write(html)
            finally:
                browser.close()
    except PWTimeout:
        print("  Timeout durante il caricamento di Amazon.it.")
        return []
    except Exception as exc:
        print(f"  Errore: {exc}")
        return []

    if _is_captcha_page(html):
        print("  Amazon ha mostrato una pagina CAPTCHA.")
        print("  Imposta 'browser_headless': false nelle Impostazioni.")
        return []

    return _extract_results(html)


# ── Parsing risultati ──────────────────────────────────────────────────────────


def _fetch_amazon_search_sorted(query: str) -> list[dict]:
    """FIX-C: Ricerca Amazon con sort=date-desc-rank per trovare volumi nuovi."""
    global _cookie_dismissed
    _cookie_dismissed = False
    encoded = quote_plus(query)
    url     = _SEARCH_URL.format(query=encoded) + "&s=date-desc-rank"
    driver  = _get_driver()
    try:
        driver.get(url)
        _dismiss_cookie_banner(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-component-type='s-search-result']"))
        )
        soup  = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select("[data-component-type='s-search-result']")
        return [r for c in cards if (r := _parse_card(c))]
    except Exception:
        return []
    finally:
        driver.quit()

def _extract_results(html: str) -> list[dict]:
    soup    = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen:    set[str]   = set()

    items = soup.find_all("div", attrs={"data-component-type": "s-search-result"})
    if not items:
        items = soup.find_all("div", class_=re.compile(r"s-result-item"))

    for item in items:
        # ── Titolo ──────────────────────────────────────────────────────────
        titolo = ""
        h2 = item.find("h2")
        if h2:
            span = (
                h2.find("span", class_="a-size-base-plus")
                or h2.find("span", class_="a-size-medium")
                or h2.find("span")
            )
            titolo = (span or h2).get_text(" ", strip=True)
        if not titolo or len(titolo) < 2:
            continue

        # ── URL ───────────────────────────────────────────────────────────────
        a_tag = h2.find("a", href=True) if h2 else None
        if not a_tag:
            a_tag = item.find("a", class_=re.compile(r"a-link-normal"), href=True)
        url = _normalise(a_tag.get("href", "")) if a_tag else ""
        if not url or url in seen:
            continue
        seen.add(url)

        # ── Autore ────────────────────────────────────────────────────────────
        autore = ""
        for row in item.find_all("div", class_="a-row"):
            for span in row.find_all("span", class_=re.compile(r"a-color-secondary")):
                t = span.get_text(" ", strip=True)
                if t and len(t) > 1 and not re.match(r"^[€\d]", t):
                    autore = t[:80]
                    break
            if autore:
                break
        if not autore:
            for a_auth in item.find_all("a", class_=re.compile(r"a-size-base")):
                t = a_auth.get_text(strip=True)
                if t and len(t) > 1:
                    autore = t[:80]
                    break

        # ── Prezzo ────────────────────────────────────────────────────────────
        prezzo = ""
        price_span = item.find("span", class_="a-offscreen")
        if price_span:
            prezzo = price_span.get_text(strip=True)
        if not prezzo:
            whole = item.find("span", class_="a-price-whole")
            frac  = item.find("span", class_="a-price-fraction")
            if whole:
                prezzo = "€" + whole.get_text(strip=True)
                if frac:
                    prezzo += "," + frac.get_text(strip=True)

        # ── Disponibilita ─────────────────────────────────────────────────────
        disponibile = "Sconosciuta"
        avail = (
            item.find("span", class_=re.compile(r"a-color-success"))
            or item.find("span", class_=re.compile(r"a-color-price"))
        )
        if price_span or prezzo:
            disponibile = "Disponibile" if prezzo else "Verifica"
        if avail:
            txt = avail.get_text(strip=True).lower()
            if "disponib" in txt or "stock" in txt:
                disponibile = "Disponibile"
            elif "esaurit" in txt or "non disponib" in txt:
                disponibile = "Non disponibile"

        results.append({
            "titolo":      titolo,
            "autore":      autore,
            "prezzo":      prezzo,
            "disponibile": disponibile,
            "url":         url,
        })

    return results[:20]


# ── Visualizzazione ────────────────────────────────────────────────────────────

def _print_results(items: list[dict]) -> None:
    print()
    print("  {:>3}   {:<44}  {:>8}".format("N", "Titolo", "Prezzo"))
    print(_TSEP)
    for i, it in enumerate(items, 1):
        t = it["titolo"]
        if len(t) > 44:
            t = t[:41] + "..."
        p = it.get("prezzo", "\u2014") or "\u2014"
        d = " *" if it.get("disponibile") == "Non disponibile" else ""
        print("  {:>3}.  {:<44}  {:>8}{}".format(i, t, p, d))
    print(_TSEP)
    print(f"  * = Non disponibile   |   Totale risultati: {len(items)}")
    print()


def _print_item_detail(it: dict) -> None:
    print("\n" + _EQ)
    print("  " + it.get("titolo", "N/D"))
    print(_EQS)
    if it.get("autore"):      print(f"  {'Autore':<22} {it['autore']}")
    if it.get("prezzo"):      print(f"  {'Prezzo':<22} {it['prezzo']}")
    if it.get("disponibile"): print(f"  {'Disponibilita':<22} {it['disponibile']}")
    if it.get("url"):
        print(_EQS)
        print("  " + it["url"])
    print(_EQ)


# ── Selezione titoli ───────────────────────────────────────────────────────────

def _select_entries(item_map: dict[int, dict]) -> list[dict] | None:
    if not item_map:
        print("  Nessun risultato disponibile.")
        return None
    max_n = max(item_map.keys())
    while True:
        print("\n" + _SEP)
        print(f"  Titoli: 1-{max_n}  |  Singolo (3)  Multiplo (1,3,5)  Range (1-5)  Tutti (T)  Annulla (0)")
        print(_SEP)
        raw = input("  Selezione: ").strip()
        if raw == "0":
            return None
        if raw.upper() == "T":
            return list(item_map.values())
        selected: list[dict] = []
        error = False
        for part in [p.strip() for p in raw.split(",") if p.strip()]:
            if "-" in part:
                try:
                    a, b = [int(x.strip()) for x in part.split("-", 1)]
                    if a > b: a, b = b, a
                    for n in range(a, b + 1):
                        if n in item_map:
                            if item_map[n] not in selected:
                                selected.append(item_map[n])
                        else:
                            print(f"  {n} fuori range (1-{max_n}) \u2014 ignorato.")
                except ValueError:
                    print(f"  Range non valido: '{part}' \u2014 ignorato.")
                    error = True
            else:
                try:
                    n = int(part)
                    if n in item_map:
                        if item_map[n] not in selected:
                            selected.append(item_map[n])
                    else:
                        print(f"  {n} fuori range (1-{max_n}) \u2014 ignorato.")
                except ValueError:
                    print(f"  Valore non valido: '{part}' \u2014 ignorato.")
                    error = True
        if error:
            input("  Premi INVIO per riprovare...")
            continue
        if not selected:
            print("  Nessun titolo valido selezionato.")
            input("  Premi INVIO per riprovare...")
            continue
        return selected


# ── Salvataggio lista ─────────────────────────────────────────────────────────

def _get_lista_path(folder: str) -> str:
    """Percorso completo del file Lista Amazon - {Mese} {Anno}.txt"""
    now  = datetime.now()
    mese = _MESI_IT[now.month]
    return str(Path(folder) / f"{FILE_PREFIX}{mese} {now.year}.txt")


def _save_lista(folder: str, selected: list[dict], queries: list[str]) -> None:
    """
    Salva i titoli selezionati in 'Lista Amazon - {Mese} {Anno}.txt'.

    Formato file:
        === {Data}  -  Ricerca: {query} ===
        Titolo Vol. X - https://www.amazon.it/...
        Titolo Vol. Y - https://www.amazon.it/...

    Se il file esiste aggiunge in coda (append) con intestazione sessione.
    Anno dinamico: datetime.now().year — mai hardcoded.
    """
    fpath    = _get_lista_path(folder)
    exists   = Path(fpath).exists()
    now      = datetime.now()
    data_str = f"{now.day} {_MESI_IT[now.month]} {now.year}"
    q_str    = ", ".join(queries) if queries else "ricerca"
    header   = f"=== {data_str}  -  Ricerca: {q_str} ==="

    lines = []
    for it in selected:
        titolo = it.get("titolo", "").strip()
        url    = it.get("url",    "").strip()
        if titolo:
            lines.append(f"{titolo} - {url}" if url else titolo)

    if not lines:
        print("  Nessun titolo da salvare.")
        return

    try:
        with open(fpath, "a" if exists else "w", encoding="utf-8") as f:
            if exists:
                f.write("\n")          # riga vuota tra sessioni
            f.write(header + "\n")
            f.write("\n".join(lines) + "\n")

        print(f"\n  \u2713 Salvato: {fpath}")
        print(f"  {len(lines)} titolo/i aggiunto/i")
        print(f"  Modalita: {'aggiunto in coda' if exists else 'file creato'}")
    except OSError as exc:
        print(f"  Errore salvataggio: {exc}")


def _preview_and_export(
    selected: list[dict],
    queries:  list[str],
    folder:   str,
) -> None:
    """
    Mostra anteprima dei titoli da esportare, con percorso file,
    e chiede conferma prima di salvare.
    """
    fpath  = _get_lista_path(folder)
    exists = Path(fpath).exists()

    clear_screen()
    print(_EQ)
    print(f"  ESPORTA  \u2014  {len(selected)} titolo/i selezionato/i")
    print(_EQS)
    print()
    for i, it in enumerate(selected, 1):
        t = it.get("titolo", "")
        if len(t) > 52:
            t = t[:49] + "..."
        print(f"  {i:>3}.  {t}")
    print()
    print(_EQS)
    print(f"  File   : {fpath}")
    print(f"  Azione : {'aggiunta in coda' if exists else 'creazione nuovo file'}")
    print(_EQS)
    print()
    ans = input("  Confermi esportazione? (s/n): ").strip().lower()
    if ans in ("s", "si", "y", "yes"):
        _save_lista(folder, selected, queries)
    else:
        print("  Esportazione annullata.")


# ── Entry point ────────────────────────────────────────────────────────────────

def handle_amazon_manga() -> None:
    """Entry point chiamato da handlers.py."""
    while True:
        clear_screen()
        print(_EQ)
        print("  ACQUISTI MANGA  \u2014  Amazon.it")
        print(_EQ)
        print()
        print("  Inserisci uno o piu titoli manga separati da virgola,")
        print("  oppure un titolo singolo.")
        print("  es.  berserk,  vinland saga,  oyasumi punpun")
        print()
        raw = input("  Titoli (0 = esci): ").strip()
        if raw == "0" or not raw:
            return

        queries = [q.strip() for q in raw.split(",") if q.strip()]
        if not queries:
            continue

        all_items: list[dict] = []
        seen_urls: set[str]   = set()

        for i, q in enumerate(queries, 1):
            clear_screen()
            print(_EQ)
            print("  ACQUISTI MANGA  \u2014  Amazon.it")
            print(_EQ)
            print(f"\n  [{i}/{len(queries)}]  Ricerca: '{q}'...")
            results = _fetch_amazon_search(q)
            for it in results:
                u = it.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    all_items.append(it)

        if not all_items:
            print("\n  Nessun risultato trovato.")
            print("  Possibili cause: CAPTCHA Amazon / connessione / titolo non trovato.")
            input("  Premi INVIO per riprovare...")
            continue

        item_map: dict[int, dict] = {i: it for i, it in enumerate(all_items, 1)}

        def _reprint() -> None:
            clear_screen()
            print(_EQ)
            print("  ACQUISTI MANGA  \u2014  Amazon.it")
            print(_EQ)
            if len(queries) == 1:
                print(f"  Ricerca: '{queries[0]}'  |  {len(all_items)} risultati")
            else:
                print(f"  Ricerca multipla: {len(queries)} titoli  |  {len(all_items)} risultati totali")
            _print_results(all_items)

        _reprint()

        while True:
            print(_SEP)
            print("  E  Esporta titoli in lista")
            print("  D  Visualizza dettaglio (es. D3)")
            print("  N  Nuova ricerca")
            print("  0  Torna al menu")
            print(_SEP)
            sc = input("  Scelta: ").strip().upper()

            if sc == "0":
                return

            elif sc == "N":
                break

            elif sc.startswith("D") and sc[1:].isdigit():
                n = int(sc[1:])
                if n in item_map:
                    clear_screen()
                    _print_item_detail(item_map[n])
                    input("\n  Premi INVIO per tornare...")
                    _reprint()
                else:
                    print(f"  Numero {n} non valido.")

            elif sc == "E":
                selected = _select_entries(item_map)
                if not selected:
                    _reprint()
                    continue
                folder = _get_folder()
                if not folder:
                    _reprint()
                    continue
                _preview_and_export(selected, queries, folder)
                input("\n  Premi INVIO per continuare...")
                _reprint()

            else:
                print("  Opzione non valida.")


if __name__ == "__main__":
    handle_amazon_manga()