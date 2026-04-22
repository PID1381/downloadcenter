#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_scheda_anime.py v3.6
Download Center - scripts/anime/ricerca_scheda_anime.py

NOVITA v3.6 (fix ricerca per titolo):
  [FIX]      BASE_URL / SEARCH_PAGE_URL non piu costanti statiche a livello modulo
             → ora lette dinamicamente via _get_base_url() / _get_search_url()
             → le modifiche da Impostazioni > Cambia URL vengono rispettate
  [FIX]      _build_search_url() usa urllib.parse.urlencode per costruire il
             parametro GET correttamente: la chiave "search_manga[title]" arriva
             al server decodificata, attivando il filtro titolo su AnimeClick
             (prima: "search_manga%5Btitle%5D=..." → chiave letterale, nessun filtro)
  [FIX]      _parse_search() aggiunto fallback a due livelli:
               1. selettori alternativi card/item/opera se .thumbnail non trovato
               2. link-scan su href=/anime/<id>/ se container assente
             → evita lista vuota per variazioni HTML di AnimeClick
  [FIX]      Tutti i riferimenti a BASE_URL nel codice sostituiti con _get_base_url()
  [MANTIENE] Tutto il resto invariato rispetto a v3.5
"""
from __future__ import annotations

import html as html_lib
import json
import re
import sys
import textwrap
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    sync_playwright = None  # type: ignore[assignment]

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from anime_engine import (
        clear_screen, show_header, show_success, show_error,
        show_info, show_warning, ask_yes_no, wait_enter,
        sanitize_filename, get_headless_mode,
        COOKIE_SEL, COOKIE_TEXTS,
    )
except ImportError as e:
    print(f"ERRORE: anime_engine non trovato: {e}")
    sys.exit(1)

_THIS_DIR   = Path(__file__).parent.resolve()
_TEMP_DIR   = _THIS_DIR.parent / "temp"
_ROOT_DIR   = _THIS_DIR.parent.parent
_EXPORT_DIR = _ROOT_DIR / "export" / "schede"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

from scripts.core.url_manager import get as get_url

# ── Costanti non legate all'URL base (invariate) ─────────────────────────────
SEARCH_INPUT_ID = "search_manga_title"
RESULTS_DIV_ID  = "row-elenco-opere"
_W              = 56
PAGE_TIMEOUT    = 20_000

# Anno corrente calcolato dinamicamente (fix v3.5: era hardcoded a 2025)
_YEAR_NOW = date.today().year


# ── Funzioni URL dinamiche (FIX v3.6) ────────────────────────────────────────
# BASE_URL e SEARCH_PAGE_URL non sono piu costanti statiche lette all'avvio.
# Vengono ricalcolate ad ogni chiamata cosi rispecchiano sempre le modifiche
# fatte dall'utente in Impostazioni > Cambia URL (scritte in site_urls.json).

def _get_base_url() -> str:
    """Legge BASE_URL fresco dall'url_manager ad ogni chiamata."""
    return get_url("anime", "animeclick") or "https://www.animeclick.it"


def _get_search_url() -> str:
    """URL pagina di ricerca anime (calcolato dinamicamente)."""
    return _get_base_url() + "/ricerca/anime"


def _build_search_url(query: str) -> str:
    """
    Costruisce l'URL di ricerca con parametro GET correttamente encodato.

    FIX v3.6: usa urlencode({"search_manga[title]": query}) invece di
    concatenare la stringa pre-encoded "search_manga%5Btitle%5D=<query>".

    Con il vecchio metodo il server riceveva la chiave come stringa letterale
    "search_manga%5Btitle%5D" (con %5B%5D come caratteri, non parentesi),
    quindi il filtro per titolo non si attivava e la ricerca restituiva
    risultati generici o non pertinenti.

    Con urlencode la chiave arriva decodificata come "search_manga[title]"
    e il filtro si attiva correttamente.
    """
    return _get_search_url() + "?" + urlencode({"search_manga[title]": query})


class AnimeTracker:

    def __init__(self):
        self._cookie_dismissed = False
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # ── Browser ──────────────────────────────────────────────────────────────

    def _new_page(self, playwright):
        """Crea browser + pagina Playwright per AnimeClick."""
        headless = get_headless_mode()
        browser  = playwright.chromium.launch(headless=headless)
        ctx = browser.new_context(
            locale="it-IT",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)
        return browser, page

    def _dismiss_cookies(self, page) -> None:
        """
        Chiude banner cookie usando COOKIE_SEL e COOKIE_TEXTS dell'engine.
        Compatibile con AnimeClick e AnimeWorld.
        """
        if self._cookie_dismissed:
            return
        js = """([selectors, texts]) => {
            for (const s of selectors) {
                try {
                    const e = document.querySelector(s);
                    if (e && e.offsetParent !== null) { e.click(); return 'ok'; }
                } catch (_) {}
            }
            const all = document.querySelectorAll(
                'button,a,input[type=button],input[type=submit],[role=button]');
            for (const e of all) {
                const t = (e.innerText||e.value||e.textContent||'').trim().toLowerCase();
                if (texts.some(k => t.includes(k)) && e.offsetParent !== null) {
                    e.click(); return 'ok';
                }
            }
            return null;
        }"""
        try:
            res = page.evaluate(js, [COOKIE_SEL, COOKIE_TEXTS])
            if res:
                self._cookie_dismissed = True
                page.wait_for_timeout(600)
        except Exception:
            pass

    # ── Ricerca ───────────────────────────────────────────────────────────────

    def search_anime(self, query: str, *, silent: bool = False) -> list:
        """Ricerca anime su AnimeClick.it. Ritorna lista dict result."""
        if not HAS_PLAYWRIGHT:
            if not silent:
                show_error("Playwright mancante. Esegui: pip install playwright && playwright install chromium")
            return []
        if not HAS_BS4:
            if not silent:
                show_error("beautifulsoup4 mancante. Esegui: pip install beautifulsoup4")
            return []
        if not silent:
            print(f"\n  [*] Ricerca '{query}' su AnimeClick.it...")

        results = []
        self._cookie_dismissed = False
        try:
            with sync_playwright() as pw:
                browser, page = self._new_page(pw)
                try:
                    # Strategia 1: GET diretto con URL correttamente encodato
                    # FIX v3.6: _build_search_url() usa urlencode, non stringa pre-encoded
                    direct_url = _build_search_url(query)
                    if not silent:
                        print(f"  [->] GET: {direct_url}")
                    try:
                        page.goto(direct_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                        self._dismiss_cookies(page)
                        try:
                            page.wait_for_selector(f"#{RESULTS_DIV_ID}", timeout=10_000)
                        except Exception:
                            pass
                        page.wait_for_timeout(1_000)
                        html = page.content()
                        if html:
                            results = self._parse_search(BeautifulSoup(html, "html.parser"))
                    except Exception as e1:
                        if not silent:
                            show_warning(f"Strategia 1 fallita ({e1}); provo form interattivo...")

                    # Strategia 2: form interattivo (fallback)
                    if not results:
                        if not silent:
                            print("  [->] Fallback: form interattivo...")
                        # FIX v3.6: usa _get_search_url() dinamico, non SEARCH_PAGE_URL statico
                        try:
                            page.goto(_get_search_url(), wait_until="networkidle", timeout=PAGE_TIMEOUT)
                        except Exception:
                            page.goto(_get_search_url(), wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                        page.wait_for_timeout(1_000)
                        self._dismiss_cookies(page)
                        page.wait_for_timeout(500)
                        INPUT_SELECTORS = [
                            f"#{SEARCH_INPUT_ID}",
                            "input[name='search_manga[title]']",
                            "input.form-control.input-sm[type='text']",
                            "input[name*='title']",
                        ]
                        filled = False
                        for sel in INPUT_SELECTORS:
                            try:
                                page.wait_for_selector(sel, timeout=5_000)
                                page.fill(sel, query)
                                page.press(sel, "Enter")
                                filled = True
                                break
                            except Exception:
                                continue
                        if filled:
                            try:
                                page.wait_for_selector(f"#{RESULTS_DIV_ID}", timeout=12_000)
                            except Exception:
                                pass
                            page.wait_for_timeout(1_200)
                            html = page.content()
                            if html:
                                results = self._parse_search(BeautifulSoup(html, "html.parser"))
                        elif not silent:
                            show_warning("Impossibile trovare il campo di ricerca.")
                finally:
                    browser.close()
        except Exception as e:
            if not silent:
                show_error(f"Errore ricerca: {e}")
        return results

    def _parse_search(self, soup) -> list:
        """
        Parse HTML risultati ricerca AnimeClick.

        FIX v3.6: parser a tre livelli per robustezza:
          Livello 1: selettore classico .thumbnail dentro #row-elenco-opere
          Livello 2: selettori alternativi .card / .item / .opera (variazioni HTML)
          Livello 3: link-scan su href=/anime/<id>/ (fallback totale)
        Tutti i riferimenti a BASE_URL sostituiti con _get_base_url() dinamico.
        """
        base = _get_base_url()
        results = []

        # ── Livello 1 & 2: container #row-elenco-opere ────────────────────────
        container = soup.find("div", id=RESULTS_DIV_ID)
        if container:
            # Livello 1: .thumbnail (struttura classica AnimeClick)
            items = container.find_all("div", class_=re.compile(r"\bthumbnail\b"))
            # Livello 2: fallback su .card / .item / .opera
            if not items:
                items = container.find_all(
                    "div",
                    class_=re.compile(r"\bcard\b|\bitem\b|\bopera\b", re.I),
                )
        else:
            items = []

        if items:
            for thumb in items:
                # Cerca caption con selettori alternativi
                caption = thumb.find(
                    "div",
                    class_=re.compile(r"\bcaption\b|\binfo\b|\bdetail\b", re.I),
                )
                a_el = caption.find("a", href=True) if caption else None
                # Fallback: link diretto /anime/<id>/
                if not a_el:
                    a_el = thumb.find("a", href=re.compile(r"/anime/\d+/", re.I))
                # Fallback finale: qualsiasi link nel thumb
                if not a_el:
                    a_el = thumb.find("a", href=True)
                if not a_el:
                    continue

                href  = a_el.get("href", "").strip()
                title = a_el.get_text(strip=True)
                if not href or not title:
                    continue
                # FIX v3.6: usa _get_base_url() dinamico
                full_url = href if href.startswith("http") else base + href

                anno = voto = ""
                info_extra = thumb.find("div", class_="info-extra")
                if info_extra:
                    pr = info_extra.find("div", class_="pull-right")
                    if pr:
                        anno = pr.get_text(strip=True)
                    ie_text = info_extra.get_text().replace("\xa0", " ")
                    m = re.search(r"(\d+[.,]\d+|\d+)", ie_text)
                    if m:
                        voto = m.group(1)

                tipo = desc = ""
                generi: list[str] = []
                dc_raw = thumb.get("data-content", "")
                if dc_raw:
                    dc_soup = BeautifulSoup(html_lib.unescape(dc_raw), "html.parser")
                    for cat_div in dc_soup.find_all("div", class_="categorie"):
                        strong = cat_div.find("strong")
                        if strong and "Categorie" in strong.get_text():
                            lis  = cat_div.find_all("li")
                            tipo = ", ".join(li.get_text(strip=True) for li in lis)
                            break
                    generi_div = dc_soup.find("div", class_="generi")
                    if generi_div:
                        generi = [
                            li.get_text(strip=True)
                            for li in generi_div.find_all("li")
                            if li.get_text(strip=True)
                        ]
                    for p in dc_soup.find_all("p"):
                        t = p.get_text(strip=True)
                        if t:
                            desc = t
                            break

                results.append({
                    "title":  title,
                    "link":   full_url,
                    "tipo":   tipo,
                    "anno":   anno,
                    "voto":   voto,
                    "generi": generi,
                    "desc":   desc,
                })
            return results

        # ── Livello 3: link-scan totale (fallback se container assente) ───────
        # Cerca tutti i link con pattern /anime/<id>/ nella pagina
        seen: set[str] = set()
        for a in soup.find_all("a", href=re.compile(r"/anime/\d+/", re.I)):
            href  = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if not href or not title or len(title) < 2:
                continue
            full_url = href if href.startswith("http") else base + href
            if full_url in seen:
                continue
            seen.add(full_url)
            results.append({
                "title":  title,
                "link":   full_url,
                "tipo":   "",
                "anno":   "",
                "voto":   "",
                "generi": [],
                "desc":   "",
            })
        return results

    # ── Dettagli scheda ───────────────────────────────────────────────────────

    def get_anime_details(self, url: str, *, silent: bool = False) -> dict:
        """Recupera e parsa la scheda dettaglio anime da AnimeClick."""
        if not HAS_PLAYWRIGHT or not HAS_BS4:
            if not silent:
                show_error("Playwright o beautifulsoup4 non installati.")
            return {}
        if not silent:
            print(f"\n  [*] Recupero scheda: {url}")
        details = {}
        self._cookie_dismissed = False
        try:
            with sync_playwright() as pw:
                browser, page = self._new_page(pw)
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    self._dismiss_cookies(page)
                    for sel in ["h1", ".titolo-opera", "#main", ".opera-title"]:
                        try:
                            page.wait_for_selector(sel, timeout=5_000)
                            break
                        except Exception:
                            continue
                    page.wait_for_timeout(1_500)
                    html = page.content()
                    if html:
                        details = self._parse_details(
                            BeautifulSoup(html, "html.parser"), url
                        )
                finally:
                    browser.close()
        except Exception as e:
            if not silent:
                show_error(f"Errore recupero scheda: {e}")
        return details

    def _parse_details(self, soup, url: str) -> dict:
        """
        Estrae dati strutturati dalla scheda HTML di AnimeClick.

        FIX v3.5: anno non piu hardcoded a 2025.
        FIX v3.6: BASE_URL sostituito con _get_base_url() dinamico.
        """
        d = {
            "titolo": "", "link": url, "tipo": "", "episodes": 0, "stato": "",
            "anno":   "", "generi": [], "trama": "", "voto": "", "copertina": "",
        }
        full = soup.get_text(" ", strip=True)

        # ── Titolo ────────────────────────────────────────────────────────────
        for tag, kw in [
            ("h1", {"class": re.compile(r"title|titolo|nome|opera", re.I)}),
            ("h1", {}),
            ("h2", {"class": re.compile(r"title|titolo", re.I)}),
        ]:
            el = soup.find(tag, kw)
            if el:
                raw = el.get_text(strip=True)
                for sep in [" - AnimeClick", " | AnimeClick", " AnimeClick"]:
                    if sep in raw:
                        raw = raw[:raw.index(sep)]
                d["titolo"] = raw.strip()
                break
        if not d["titolo"]:
            t_el = soup.find("title")
            if t_el:
                raw = t_el.get_text(strip=True)
                for sep in [" - AnimeClick", " | AnimeClick"]:
                    if sep in raw:
                        raw = raw[:raw.index(sep)]
                d["titolo"] = raw.strip()

        # ── Anno (range dinamico 1950-_YEAR_NOW) ─────────────────────────────
        def _valid_year(y: str) -> bool:
            try:
                return 1950 <= int(y) <= _YEAR_NOW
            except (ValueError, TypeError):
                return False

        anno_label = re.search(
            r"Anno\s*(?:di\s*(?:pubblicazione|trasmissione|uscita|produzione))?"
            r"[:\s]+(\b\d{4}\b)",
            full,
            re.I,
        )
        if anno_label and _valid_year(anno_label.group(1)):
            d["anno"] = anno_label.group(1)
        else:
            for m in re.finditer(r"\b(\d{4})\b", full):
                if _valid_year(m.group(1)):
                    d["anno"] = m.group(1)
                    break

        # ── Episodi ───────────────────────────────────────────────────────────
        for pat in [
            r"Episodi\s*[:\s]+(\d+)",
            r"(\d+)\s+episodi?\b",
            r"episodi?[:\s]+(\d+)",
            r"\bep(?:isodi?)?\s*[.:\s]+(\d+)",
            r"N\u00b0\s*ep\.?\s*[:\s]*(\d+)",
        ]:
            m = re.search(pat, full, re.I)
            if m:
                d["episodes"] = int(m.group(1))
                break

        # ── Stato ─────────────────────────────────────────────────────────────
        for stato in ["Completato", "In corso", "In produzione", "In pausa", "Abbandonato"]:
            if stato.lower() in full.lower():
                d["stato"] = stato
                break

        # ── Tipo ──────────────────────────────────────────────────────────────
        for tipo_val in ["Serie TV", "Film", "Serie OAV", "OAV", "Special", "ONA"]:
            if tipo_val.lower() in full.lower():
                d["tipo"] = tipo_val
                break

        # ── Generi ────────────────────────────────────────────────────────────
        for tag, kw in [
            ("a",    {"href": re.compile(r"/genere/|/genre/|/tag/", re.I)}),
            ("span", {"class": re.compile(r"genere|genre|tag|cat", re.I)}),
        ]:
            els = soup.find_all(tag, kw)
            if els:
                d["generi"] = list(dict.fromkeys(
                    e.get_text(strip=True) for e in els if e.get_text(strip=True)
                ))[:10]
                break

        # ── Trama ─────────────────────────────────────────────────────────────
        for tag, kw in [
            ("div", {"class": re.compile(r"trama|synopsis|sinossi|plot|desc", re.I)}),
            ("div", {"id":    re.compile(r"trama|synopsis|plot|desc", re.I)}),
            ("p",   {"class": re.compile(r"trama|synopsis|desc", re.I)}),
        ]:
            el = soup.find(tag, kw)
            if el:
                t = el.get_text(" ", strip=True)
                if len(t) > 30:
                    d["trama"] = t[:800]
                    break

        # ── Voto ──────────────────────────────────────────────────────────────
        for pat in [
            r"(\d+[.,]\d+)\s*/\s*10",
            r"Voto\s*[:\s]+(\d+[.,]\d+)",
            r"Media\s*[:\s]+(\d+[.,]\d+)",
            r"Punteggio\s*[:\s]+(\d+[.,]\d+)",
            r"class[^>]*voto[^>]*>\s*(\d+[.,]\d+)",
            r"\b([1-9]\d?[.,]\d{1,2})\s*(?:/10)?",
        ]:
            m = re.search(pat, full, re.I)
            if m:
                candidate = m.group(1).replace(",", ".")
                try:
                    v = float(candidate)
                    if 0 < v <= 10:
                        d["voto"] = candidate
                        break
                except ValueError:
                    continue

        # ── Copertina ─────────────────────────────────────────────────────────
        for kw in [
            {"class": re.compile(r"cover|copertina|poster|locandina", re.I)},
            {"id":    re.compile(r"cover|copertina|poster", re.I)},
        ]:
            img = soup.find("img", kw)
            if img:
                src = img.get("src", "") or img.get("data-src", "")
                if src:
                    # FIX v3.6: usa _get_base_url() dinamico
                    if not src.startswith("http"):
                        src = _get_base_url() + ("" if src.startswith("/") else "/") + src
                    d["copertina"] = src
                    break

        return d

    # ── Export ────────────────────────────────────────────────────────────────

    def export_scheda(self, details: dict, *, silent: bool = False) -> str:
        """
        Esporta la scheda in:
          _EXPORT_DIR / <titolo> /
              <titolo>.jpg   (cover scaricata)
              <titolo>.txt   (dati formattati)

        Ritorna il percorso della cartella oppure '' se errore.
        """
        if not details or not details.get("titolo"):
            return ""
        try:
            safe   = sanitize_filename(details["titolo"])
            folder = _EXPORT_DIR / safe
            folder.mkdir(parents=True, exist_ok=True)

            # 1. Scarica cover ────────────────────────────────────────────────
            cover_url   = details.get("copertina", "")
            cover_saved = ""
            if cover_url:
                raw_path = cover_url.split("?")[0]
                ext = Path(raw_path).suffix or ".jpg"
                if ext.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    ext = ".jpg"
                cover_file = folder / (safe + ext)
                try:
                    req = urllib.request.Request(
                        cover_url,
                        headers={"User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        )},
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        with open(cover_file, "wb") as f:
                            f.write(resp.read())
                    cover_saved = cover_file.name
                    if not silent:
                        show_success(f"Cover salvata: {cover_saved}")
                except Exception as e:
                    if not silent:
                        show_warning(f"Impossibile scaricare la cover: {e}")
            else:
                if not silent:
                    show_warning("Nessuna URL cover disponibile.")

            # 2. Crea file .txt ───────────────────────────────────────────────
            txt_file = folder / (safe + ".txt")
            sep      = "=" * 56
            sep2     = "-" * 56
            generi_str = ", ".join(details.get("generi", [])) or "N/D"
            trama = details.get("trama", "N/D") or "N/D"
            if trama.lower().startswith("trama:"):
                trama = trama[6:].strip()

            lines = [
                sep,
                " SCHEDA ANIME",
                sep,
                "",
                f"  Titolo  : {details.get('titolo', 'N/D')}",
                f"  Tipo    : {details.get('tipo', 'N/D') or 'N/D'}",
                f"  Anno    : {details.get('anno', 'N/D') or 'N/D'}",
                f"  Episodi : {details.get('episodes', '?') or '?'}",
                f"  Stato   : {details.get('stato', 'N/D') or 'N/D'}",
                f"  Voto    : {details.get('voto', 'N/D') or 'N/D'}",
                f"  Generi  : {generi_str}",
                "",
                sep2,
                " TRAMA",
                sep2,
                "",
            ]
            for line in textwrap.wrap(trama, width=72):
                lines.append(f"  {line}")
            lines += [
                "",
                sep2,
                " LINK E RISORSE",
                sep2,
                "",
                f"  Scheda  : {details.get('link', '')}",
                f"  Cover   : {details.get('copertina', '')}",
                "",
                sep,
            ]
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if not silent:
                show_success(f"File dati salvato: {txt_file.name}")

            return str(folder)

        except Exception as e:
            if not silent:
                show_error(f"Errore esportazione: {e}")
            return ""


# ── Helpers display ───────────────────────────────────────────────────────────

def _select_result(results: list):
    """Menu selezione da lista risultati ricerca. Ritorna il dict scelto o None."""
    if not results:
        show_warning("Nessun risultato trovato.")
        wait_enter()
        return None
    print()
    for i, r in enumerate(results, 1):
        tipo = f" [{r['tipo']}]"      if r.get("tipo") else ""
        anno = f" ({r['anno']})"      if r.get("anno") else ""
        voto = f" \u2605{r['voto']}" if r.get("voto") else ""
        print(f"  {i:>2}. {r['title']}{tipo}{anno}{voto}")
        if r.get("desc"):
            snippet = r["desc"]
            if len(snippet) > 72:
                snippet = snippet[:70] + "..."
            print(f"       \u2514 {snippet}")
    print()
    print("  0. Annulla")
    print()
    while True:
        sel = input("  Seleziona: ").strip()
        if sel == "0":
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(results):
            return results[int(sel) - 1]
        show_error("Selezione non valida.")


def _display_details(d: dict) -> None:
    """Stampa a video i dati scheda anime con box-drawing standard."""
    rows = [
        ("Titolo",  d.get("titolo",   "N/D") or "N/D"),
        ("Tipo",    d.get("tipo",     "N/D") or "N/D"),
        ("Episodi", str(d.get("episodes", "?"))),
        ("Stato",   d.get("stato",    "N/D") or "N/D"),
        ("Anno",    d.get("anno",     "N/D") or "N/D"),
        ("Voto",    d.get("voto",     "N/D") or "N/D"),
    ]
    if d.get("generi"):
        rows.append(("Generi", ", ".join(d["generi"][:6])))

    w0 = max(len(r[0]) for r in rows)
    w1 = min(max(len(r[1]) for r in rows), 50)

    def _cell(val, w):
        if len(val) > w: val = val[:w-2] + ".."
        return val.ljust(w)

    def _border(l, m, r, f):
        return "  " + l + f*(w0+2) + m + f*(w1+2) + r

    def _row(k, v):
        return f"  \u2502 {_cell(k,w0)} \u2502 {_cell(v,w1)} \u2502"

    print()
    print(_border("\u250c","\u252c","\u2510","\u2500"))
    for k, v in rows:
        print(_row(k, v))
    print(_border("\u2514","\u2534","\u2518","\u2500"))

    if d.get("trama"):
        t = d["trama"].lstrip("Trama:").strip()
        short = (t[:200] + "...") if len(t) > 200 else t
        print()
        print(f"  Trama: {short}")

    if d.get("link"):
        print()
        print(f"  Link: {d['link']}")
    print()


# ── Menu principale ───────────────────────────────────────────────────────────

def handle_ricerca_scheda_anime(tracker=None):
    """Menu principale ricerca scheda anime v3.6"""
    if tracker is None:
        tracker = AnimeTracker()

    if not HAS_PLAYWRIGHT:
        clear_screen()
        show_header("RICERCA SCHEDA ANIME v3.6")
        show_error("Playwright non installato.")
        show_info("Esegui: pip install playwright && playwright install chromium")
        wait_enter()
        return

    while True:
        clear_screen()
        print("  " + "=" * _W)
        print("  RICERCA SCHEDA ANIME v3.6")
        print("  " + "=" * _W)
        print()
        print("  1. Ricerca per titolo")
        print("  2. Ricerca per URL diretto")
        print("  0. Torna al menu Anime")
        print()
        scelta = input("  Scelta (0-2): ").strip()

        if scelta == "0":
            return

        elif scelta == "1":
            clear_screen()
            show_header("RICERCA PER TITOLO", "Anime > Ricerca Scheda")
            query = input("  Titolo da cercare (0 = annulla): ").strip()
            if not query or query == "0":
                continue
            results = tracker.search_anime(query)
            if not results:
                show_warning("Nessun risultato. Prova un titolo diverso o abbreviato.")
                wait_enter()
                continue
            clear_screen()
            show_header(f"RISULTATI: {len(results)} trovati")
            selected = _select_result(results)
            if not selected:
                continue
            print("\n  [*] Caricamento scheda in corso...")
            det = tracker.get_anime_details(selected["link"])
            if not det or not det.get("titolo"):
                show_error("Impossibile recuperare la scheda.")
                wait_enter()
                continue
            clear_screen()
            show_header("SCHEDA ANIME")
            _display_details(det)
            if ask_yes_no("Esportare la scheda (cover + file testo)?"):
                folder = tracker.export_scheda(det)
                if folder:
                    show_success("Esportazione completata!")
                    show_info(f"Cartella: {folder}")
                else:
                    show_error("Errore durante l'esportazione.")
            wait_enter()

        elif scelta == "2":
            clear_screen()
            show_header("RICERCA PER URL", "Anime > Ricerca Scheda")
            print("  Esempio: https://www.animeclick.it/anime/475/maison-ikkoku")
            print()
            url = input("  URL (0 = annulla): ").strip()
            if not url or url == "0":
                continue
            # FIX v3.6: usa _get_base_url() dinamico
            if not url.startswith("http"):
                url = _get_base_url() + ("" if url.startswith("/") else "/") + url
            print("\n  [*] Caricamento scheda in corso...")
            det = tracker.get_anime_details(url)
            if not det or not det.get("titolo"):
                show_error("Impossibile recuperare la scheda.")
                show_info("Verifica che l'URL sia corretto e raggiungibile.")
                wait_enter()
                continue
            clear_screen()
            show_header("SCHEDA ANIME")
            _display_details(det)
            if ask_yes_no("Esportare la scheda (cover + file testo)?"):
                folder = tracker.export_scheda(det)
                if folder:
                    show_success("Esportazione completata!")
                    show_info(f"Cartella: {folder}")
                else:
                    show_error("Errore durante l'esportazione.")
            wait_enter()

        else:
            show_error("Opzione non valida.")
            wait_enter()


if __name__ == "__main__":
    tracker = AnimeTracker()
    handle_ricerca_scheda_anime(tracker)
