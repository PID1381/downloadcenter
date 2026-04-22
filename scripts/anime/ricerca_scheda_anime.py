#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_scheda_anime.py v3.8
Download Center - scripts/anime/ricerca_scheda_anime.py

NOVITA v3.8 (fix JSON response + estrazione titolo):
  [FIX CRITICO] La POST AJAX di AnimeClick risponde con JSON:
                {"ok":true,"data":{"html":"...HTML risultati..."}}
                Il parser precedente cercava .thumbnail direttamente
                nell'HTML grezzo → trovava 0 risultati perche il
                contenuto era annidato dentro data["data"]["html"].
  [NEW]         _unwrap_json(raw): se raw inizia con "{", lo parsa
                come JSON ed estrae data["data"]["html"] prima di
                passarlo a BeautifulSoup.
  [NEW]         _http_search(): ricerca HTTP pura (urllib + cookie)
                senza Playwright. Piu veloce e affidabile per step 1-3.
                Step 1: GET /ricerca/anime → CSRF token + cookie
                Step 2: POST AJAX → JSON → _unwrap_json → HTML
                Step 3: Playwright form interattivo classico (fallback)
  [FIX]         _parse_search(): il tag <a> nei .thumbnail e vuoto
                (contiene solo <img>). Il titolo e nel popover
                data-content -> <h5>. Nuovo ordine sorgenti:
                  1. data-content -> h5  (principale)
                  2. img[alt]            (fallback)
                  3. a.get_text()        (ultimo fallback)
  [MANTIENE]    Tutto il resto invariato (URL dinamici, parser 3
                livelli, get_anime_details, export, display menu).
"""
from __future__ import annotations

import html as html_lib
import http.cookiejar
import json
import re
import sys
import textwrap
import urllib.request
import urllib.parse
from datetime import date
from pathlib import Path

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

# ── Costanti ──────────────────────────────────────────────────────────────────
SEARCH_INPUT_ID = "search_manga_title"
SEARCH_FORM_ID  = "form-ricerca-opera"
RESULTS_DIV_ID  = "row-elenco-opere"
RESULTS_CONT_ID = "elenco-opere"
_W              = 56
PAGE_TIMEOUT    = 20_000

_YEAR_NOW = date.today().year

_BASE_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Referer":         "https://www.animeclick.it/",
}


# ── URL dinamici ──────────────────────────────────────────────────────────────
def _get_base_url() -> str:
    return get_url("anime", "animeclick") or "https://www.animeclick.it"


def _get_search_url() -> str:
    return _get_base_url() + "/ricerca/anime"


# ── Utility: scarta wrapper JSON restituito dalla POST AJAX ───────────────────
def _unwrap_json(raw: str) -> str:
    """
    AnimeClick risponde alla POST AJAX con:
        {"ok": true, "data": {"html": "...HTML risultati..."}}
    Questa funzione estrae l'HTML interno da data["data"]["html"].
    Se raw non e JSON (risposta HTML diretta) lo restituisce invariato.
    """
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return raw
    try:
        obj = json.loads(stripped)
        data_node = obj.get("data", {})
        if isinstance(data_node, dict) and "html" in data_node:
            return data_node["html"]
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return raw


class AnimeTracker:

    def __init__(self):
        self._cookie_dismissed = False
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # ── Browser Playwright ────────────────────────────────────────────────────

    def _new_page(self, playwright):
        headless = get_headless_mode()
        browser  = playwright.chromium.launch(headless=headless)
        ctx = browser.new_context(
            locale="it-IT",
            user_agent=_BASE_HDR["User-Agent"],
        )
        page = ctx.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)
        return browser, page

    def _dismiss_cookies(self, page) -> None:
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

    # ── Step 1-2: HTTP puro (urllib + cookie jar) ─────────────────────────────

    def _http_search(self, query: str, *, silent: bool = False) -> list:
        """
        Ricerca HTTP pura senza Playwright.

        Step 1: GET /ricerca/anime
                → ottieni CSRF token (input[name='search_manga[_token]'])
                  e cookie di sessione tramite CookieJar.

        Step 2: POST /ricerca/anime con header X-Requested-With: XMLHttpRequest
                → risposta JSON {"ok":true,"data":{"html":"..."}}
                → _unwrap_json() estrae l'HTML interno
                → _parse_search() restituisce la lista risultati.
        """
        if not HAS_BS4:
            return []

        search_url = _get_search_url()
        cj         = http.cookiejar.CookieJar()
        opener     = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj)
        )

        try:
            # ── Step 1: GET ───────────────────────────────────────────────────
            if not silent:
                print(f"  [->] HTTP GET {search_url} (CSRF token)...")
            req_get = urllib.request.Request(search_url, headers=_BASE_HDR)
            with opener.open(req_get, timeout=15) as resp:
                html_get = resp.read().decode("utf-8", errors="replace")

            soup_get = BeautifulSoup(html_get, "html.parser")
            token_el = soup_get.find("input", {"name": "search_manga[_token]"})
            csrf     = token_el["value"] if token_el else ""

            if not silent:
                print(f"  [{'✓' if csrf else '!'}] CSRF token: "
                      f"{'OK ' + csrf[:16] + '...' if csrf else 'non trovato'}")

            # ── Step 2: POST AJAX ─────────────────────────────────────────────
            if not silent:
                print(f"  [->] HTTP POST AJAX (query='{query}')...")

            post_body = urllib.parse.urlencode({
                "search_manga[title]":        query,
                "search_manga[staff]":        "",
                "search_manga[annoStagione]": "",
                "search_manga[tagsGenerali]": "",
                "search_manga[_token]":       csrf,
            }).encode("utf-8")

            post_hdr = {
                **_BASE_HDR,
                "Content-Type":     "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Referer":          search_url,
            }
            req_post = urllib.request.Request(
                search_url, data=post_body, headers=post_hdr
            )
            with opener.open(req_post, timeout=15) as resp:
                raw_response = resp.read().decode("utf-8", errors="replace")

            # Estrae HTML dal wrapper JSON
            html_results = _unwrap_json(raw_response)
            if not silent:
                has_q = query.lower() in html_results.lower()
                print(f"  [{'✓' if has_q else '!'}] Risposta: "
                      f"{len(html_results)} chars | "
                      f"query trovata: {'si' if has_q else 'no'}")

            results = self._parse_search(BeautifulSoup(html_results, "html.parser"))
            if not silent:
                print(f"  [{'✓' if results else '!'}] "
                      f"Risultati HTTP: {len(results)}")
            return results

        except Exception as e:
            if not silent:
                show_warning(f"HTTP search fallito ({e})")
            return []

    # ── Ricerca principale ────────────────────────────────────────────────────

    def search_anime(self, query: str, *, silent: bool = False) -> list:
        """
        Ricerca anime su AnimeClick.it.

        Flusso v3.8:
          Step 1+2: _http_search() — HTTP puro (urllib + CookieJar)
                    GET /ricerca/anime  → CSRF token + cookie sessione
                    POST AJAX           → JSON → _unwrap_json → HTML
                    _parse_search()     → lista risultati
          Step 3:   Playwright form interattivo classico (fallback se
                    _http_search restituisce lista vuota)
        """
        if not HAS_BS4:
            if not silent:
                show_error("beautifulsoup4 mancante. Esegui: pip install beautifulsoup4")
            return []
        if not silent:
            print(f"\n  [*] Ricerca '{query}' su AnimeClick.it...")

        # ── Step 1+2: HTTP puro ───────────────────────────────────────────────
        results = self._http_search(query, silent=silent)
        if results:
            return results

        # ── Step 3: Playwright form interattivo (fallback) ────────────────────
        if not HAS_PLAYWRIGHT:
            if not silent:
                show_warning("Playwright non disponibile. Installa: pip install playwright && playwright install chromium")
            return []

        if not silent:
            print("  [->] Fallback Step 3: Playwright form interattivo...")

        self._cookie_dismissed = False
        search_url = _get_search_url()

        try:
            with sync_playwright() as pw:
                browser, page = self._new_page(pw)
                try:
                    try:
                        page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                    except Exception:
                        page.goto(search_url, wait_until="load", timeout=PAGE_TIMEOUT)
                    self._dismiss_cookies(page)
                    page.wait_for_timeout(800)

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
                            page.wait_for_selector(
                                f"#{RESULTS_DIV_ID} .thumbnail",
                                timeout=12_000,
                            )
                        except Exception:
                            pass
                        page.wait_for_timeout(1_200)
                        raw_pw = page.content()
                        html_pw = _unwrap_json(raw_pw)
                        results = self._parse_search(
                            BeautifulSoup(html_pw, "html.parser")
                        )
                        if not silent:
                            print(f"  [{'✓' if results else '!'}] "
                                  f"Playwright risultati: {len(results)}")
                    else:
                        if not silent:
                            show_warning("Step 3: campo di ricerca non trovato.")
                finally:
                    browser.close()
        except Exception as e:
            if not silent:
                show_error(f"Step 3 Playwright fallito ({e})")

        if not results and not silent:
            show_warning("Nessun risultato trovato. Prova un titolo diverso o abbreviato.")
        return results

    # ── Parser risultati ──────────────────────────────────────────────────────

    def _parse_search(self, soup) -> list:
        """
        Parse HTML risultati ricerca AnimeClick.

        FIX v3.8 — estrazione titolo corretta:
          Il tag <a> nei .thumbnail e VUOTO (contiene solo <img>).
          Il titolo e nel popover data-content -> <h5>.
          Ordine sorgenti titolo:
            1. data-content -> h5  (principale)
            2. img[alt]            (fallback)
            3. a.get_text()        (ultimo fallback)

        Parser a tre livelli:
          Livello 1: .thumbnail dentro #row-elenco-opere
          Livello 2: .card / .item / .opera
          Livello 3: link-scan su href=/anime/<id>/ (fallback totale)
        """
        base    = _get_base_url()
        results = []

        # ── Livello 1 & 2 ─────────────────────────────────────────────────────
        container = soup.find("div", id=RESULTS_DIV_ID)
        if not container:
            container = soup.find("div", id=RESULTS_CONT_ID)

        if container:
            items = container.find_all("div", class_=re.compile(r"\bthumbnail\b"))
            if not items:
                items = container.find_all(
                    "div",
                    class_=re.compile(r"\bcard\b|\bitem\b|\bopera\b", re.I),
                )
        else:
            items = []

        if items:
            for thumb in items:
                # ── Link ──────────────────────────────────────────────────────
                a_el = thumb.find("a", href=re.compile(r"/anime/\d+/", re.I))
                if not a_el:
                    a_el = thumb.find("a", href=True)
                if not a_el:
                    continue

                href = a_el.get("href", "").strip()
                if not href:
                    continue
                full_url = href if href.startswith("http") else base + href

                # ── Titolo (FIX v3.8) ─────────────────────────────────────────
                title = ""

                # Fonte 1: data-content → <h5>
                dc_raw = thumb.get("data-content", "")
                if dc_raw and not title:
                    try:
                        dc_soup = BeautifulSoup(
                            html_lib.unescape(dc_raw), "html.parser"
                        )
                        h5 = dc_soup.find("h5")
                        if h5:
                            title = h5.get_text(strip=True)
                    except Exception:
                        pass

                # Fonte 2: img[alt]
                if not title:
                    img_el = thumb.find("img")
                    if img_el:
                        title = (img_el.get("alt", "") or "").strip()

                # Fonte 3: a.get_text()
                if not title:
                    title = a_el.get_text(strip=True)

                if not title:
                    continue

                # ── Anno, Voto ────────────────────────────────────────────────
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

                # ── Tipo, Generi, Desc da data-content ───────────────────────
                tipo = desc = ""
                generi: list[str] = []
                if dc_raw:
                    try:
                        dc_soup = BeautifulSoup(
                            html_lib.unescape(dc_raw), "html.parser"
                        )
                        for cat_div in dc_soup.find_all("div", class_="categorie"):
                            strong = cat_div.find("strong")
                            if strong and "Categorie" in strong.get_text():
                                lis  = cat_div.find_all("li")
                                tipo = ", ".join(
                                    li.get_text(strip=True) for li in lis
                                )
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
                    except Exception:
                        pass

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

        # ── Livello 3: link-scan totale ───────────────────────────────────────
        seen: set[str] = set()
        for a in soup.find_all("a", href=re.compile(r"/anime/\d+/", re.I)):
            href  = a.get("href", "").strip()
            title = a.get_text(strip=True)

            # Fallback titolo da img[alt]
            if not title:
                img_el = a.find("img")
                if img_el:
                    title = (img_el.get("alt", "") or "").strip()

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
        """Estrae dati strutturati dalla scheda HTML di AnimeClick."""
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

        # ── Anno ──────────────────────────────────────────────────────────────
        def _valid_year(y: str) -> bool:
            try:
                return 1950 <= int(y) <= _YEAR_NOW
            except (ValueError, TypeError):
                return False

        anno_label = re.search(
            r"Anno\s*(?:di\s*(?:pubblicazione|trasmissione|uscita|produzione))?"
            r"[:\s]+(\b\d{4}\b)",
            full, re.I,
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
                    if not src.startswith("http"):
                        src = _get_base_url() + ("" if src.startswith("/") else "/") + src
                    d["copertina"] = src
                    break

        return d

    # ── Export ────────────────────────────────────────────────────────────────

    def export_scheda(self, details: dict, *, silent: bool = False) -> str:
        """
        Esporta scheda in _EXPORT_DIR/<titolo>/:
          <titolo>.jpg  (cover)
          <titolo>.txt  (dati formattati)
        Ritorna il percorso cartella o '' se errore.
        """
        if not details or not details.get("titolo"):
            return ""
        try:
            safe   = sanitize_filename(details["titolo"])
            folder = _EXPORT_DIR / safe
            folder.mkdir(parents=True, exist_ok=True)

            # Cover ────────────────────────────────────────────────────────────
            cover_url = details.get("copertina", "")
            if cover_url:
                raw_path = cover_url.split("?")[0]
                ext = Path(raw_path).suffix or ".jpg"
                if ext.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    ext = ".jpg"
                cover_file = folder / (safe + ext)
                try:
                    req = urllib.request.Request(
                        cover_url, headers={"User-Agent": _BASE_HDR["User-Agent"]}
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        with open(cover_file, "wb") as f:
                            f.write(resp.read())
                    if not silent:
                        show_success(f"Cover salvata: {cover_file.name}")
                except Exception as e:
                    if not silent:
                        show_warning(f"Impossibile scaricare la cover: {e}")
            else:
                if not silent:
                    show_warning("Nessuna URL cover disponibile.")

            # File .txt ────────────────────────────────────────────────────────
            txt_file   = folder / (safe + ".txt")
            sep        = "=" * 56
            sep2       = "-" * 56
            generi_str = ", ".join(details.get("generi", [])) or "N/D"
            trama      = details.get("trama", "N/D") or "N/D"
            if trama.lower().startswith("trama:"):
                trama = trama[6:].strip()

            lines = [
                sep, " SCHEDA ANIME", sep, "",
                f"  Titolo  : {details.get('titolo', 'N/D')}",
                f"  Tipo    : {details.get('tipo',   'N/D') or 'N/D'}",
                f"  Anno    : {details.get('anno',   'N/D') or 'N/D'}",
                f"  Episodi : {details.get('episodes', '?') or '?'}",
                f"  Stato   : {details.get('stato',  'N/D') or 'N/D'}",
                f"  Voto    : {details.get('voto',   'N/D') or 'N/D'}",
                f"  Generi  : {generi_str}",
                "", sep2, " TRAMA", sep2, "",
            ]
            for line in textwrap.wrap(trama, width=72):
                lines.append(f"  {line}")
            lines += [
                "", sep2, " LINK E RISORSE", sep2, "",
                f"  Scheda  : {details.get('link', '')}",
                f"  Cover   : {details.get('copertina', '')}",
                "", sep,
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
    """Menu selezione da lista risultati."""
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
    """Stampa scheda con box-drawing."""
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
        if len(val) > w:
            val = val[:w-2] + ".."
        return val.ljust(w)

    def _border(l, m, r, f):
        return "  " + l + f*(w0+2) + m + f*(w1+2) + r

    def _row(k, v):
        return f"  \u2502 {_cell(k,w0)} \u2502 {_cell(v,w1)} \u2502"

    print()
    print(_border("\u250c", "\u252c", "\u2510", "\u2500"))
    for k, v in rows:
        print(_row(k, v))
    print(_border("\u2514", "\u2534", "\u2518", "\u2500"))

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
    """Menu principale ricerca scheda anime v3.8"""
    if tracker is None:
        tracker = AnimeTracker()

    while True:
        clear_screen()
        print("  " + "=" * _W)
        print("  RICERCA SCHEDA ANIME v3.8")
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
                    show_error("Errore durante l\'esportazione.")
            wait_enter()

        elif scelta == "2":
            clear_screen()
            show_header("RICERCA PER URL", "Anime > Ricerca Scheda")
            print("  Esempio: https://www.animeclick.it/anime/475/maison-ikkoku")
            print()
            url = input("  URL (0 = annulla): ").strip()
            if not url or url == "0":
                continue
            if not url.startswith("http"):
                url = _get_base_url() + ("" if url.startswith("/") else "/") + url
            print("\n  [*] Caricamento scheda in corso...")
            det = tracker.get_anime_details(url)
            if not det or not det.get("titolo"):
                show_error("Impossibile recuperare la scheda.")
                show_info("Verifica che l\'URL sia corretto e raggiungibile.")
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
                    show_error("Errore durante l\'esportazione.")
            wait_enter()

        else:
            show_error("Opzione non valida.")
            wait_enter()


if __name__ == "__main__":
    tracker = AnimeTracker()
    handle_ricerca_scheda_anime(tracker)
