#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_scheda_anime.py  v4.2
Download Center - scripts/anime/ricerca_scheda_anime.py

NOVITA v4.2 (rispetto a v4.1):
  [FIX 7+] _filter_by_relevance meno aggressiva:
           - mantiene score 1 (match parziale) oltre a score 2 (match esatto)
           - se risultati con match <= 3 restituisce TUTTA la lista
           - scarta solo veri falsi positivi (score 0) quando ci sono >3 match
           Prima: "naruto" -> 1 risultato su 28 (scartava spin-off/film)
           Ora:   "naruto" -> tutti i 28 risultati pertinenti

MANTIENE tutti i fix di v4.1:
  [FIX 1]  URL dinamici via _get_base_url() / _get_search_url()
  [FIX 2]  urlencode con chiave decodificata (non %5B%5D)
  [FIX 3]  Parser HTML a 3 livelli (thumbnail > card > link-scan)
  [FIX 4]  _unwrap_json(): estrae HTML da JSON wrapper AJAX
  [FIX 5]  _http_search(): fallback HTTP puro con CookieJar
  [FIX 6]  Titolo da data-content > h5 > img[alt] > caption > a
  [FIX 8]  Voto: regex solo decimali + validazione range 0 < v <= 10
  [RIMOSSO] page.on("response") + page.type(delay=150ms)
  [VELOCITA] GET diretto come strategia 1, form come fallback
  [VELOCITA] wait_until="domcontentloaded" + timeout ottimizzati
"""
from __future__ import annotations

import html as html_lib
import http.cookiejar
import json
import re
import sys
import textwrap
import urllib.parse
import urllib.request
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
    print("ERRORE: anime_engine non trovato:", e)
    sys.exit(1)

try:
    from scripts.core.url_manager import get as get_url
except ImportError:
    def get_url(*args, **kwargs):  # type: ignore[misc]
        return None

_THIS_DIR   = Path(__file__).parent.resolve()
_TEMP_DIR   = _THIS_DIR.parent / "temp"
_ROOT_DIR   = _THIS_DIR.parent.parent
_EXPORT_DIR = _ROOT_DIR / "export" / "schede"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# -- Costanti non-URL
SEARCH_INPUT_ID = "search_manga_title"
RESULTS_DIV_ID  = "row-elenco-opere"
_W              = 56
PAGE_TIMEOUT    = 20_000

# Anno corrente calcolato dinamicamente
_YEAR_NOW = date.today().year

# Header HTTP base per urllib
_BASE_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9",
}


# -- FIX 1: URL dinamici
def _get_base_url() -> str:
    """Restituisce BASE_URL fresco dall'url_manager ad ogni chiamata."""
    return get_url("anime", "animeclick") or "https://www.animeclick.it"


def _get_search_url() -> str:
    return _get_base_url() + "/ricerca/anime"


# -- FIX 4: Unwrap JSON AJAX
def _unwrap_json(raw: str) -> str:
    """
    Se raw e' un JSON wrapper AJAX {ok, data:{html:...}}, estrae l'HTML interno.
    Se raw e' gia' HTML diretto, lo restituisce invariato (funzione idempotente).
    """
    stripped = raw.strip() if raw else ""
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

    # -- Browser

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
        """Chiude banner cookie usando COOKIE_SEL e COOKIE_TEXTS dell'engine."""
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
                page.wait_for_timeout(400)
        except Exception:
            pass

    # -- Ricerca

    def search_anime(self, query: str, *, silent: bool = False) -> list:
        """
        Ricerca anime su AnimeClick.it. Ritorna lista dict result.

        Strategia:
          1. GET diretto con parametri URL (veloce, stabile)
          2. Fallback: form interattivo (fill + Enter)
          3. Fallback: HTTP puro senza Playwright
        """
        if not HAS_PLAYWRIGHT:
            if not silent:
                show_error("Playwright mancante. Esegui: pip install playwright && playwright install chromium")
            return self._http_search(query, silent=silent)
        if not HAS_BS4:
            if not silent:
                show_error("beautifulsoup4 mancante. Esegui: pip install beautifulsoup4")
            return []
        if not query or not query.strip():
            return []

        query = query.strip()
        risultati: list = []
        self._cookie_dismissed = False

        if not silent:
            print("\n  [*] Ricerca '" + query + "' su AnimeClick.it...")

        try:
            with sync_playwright() as pw:
                browser, page = self._new_page(pw)
                try:
                    base_url   = _get_base_url()
                    search_url = _get_search_url()

                    # -- Strategia 1: GET diretto
                    # FIX 2: urlencode con chiave decodificata (non %5B%5D)
                    params     = urllib.parse.urlencode({"search_manga[title]": query})
                    direct_url = search_url + "?" + params
                    if not silent:
                        print("  [->] GET: " + direct_url)
                    try:
                        page.goto(direct_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                        self._dismiss_cookies(page)
                        try:
                            page.wait_for_selector(
                                "#" + RESULTS_DIV_ID + ", #elenco-opere",
                                state="attached",
                                timeout=8_000,
                            )
                        except Exception:
                            pass
                        page.wait_for_timeout(800)
                        dom_html     = page.content()
                        html_content = _unwrap_json(dom_html)
                        if html_content:
                            parsed = self._parse_search(
                                BeautifulSoup(html_content, "html.parser")
                            )
                            if parsed:
                                risultati = self._filter_by_relevance(parsed, query)
                    except Exception as e1:
                        if not silent:
                            show_warning("Strategia GET fallita; provo form...")

                    # -- Strategia 2: form interattivo (fallback)
                    if not risultati:
                        if not silent:
                            print("  [->] Fallback: form interattivo...")
                        try:
                            page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                        except Exception:
                            page.goto(search_url, wait_until="load", timeout=PAGE_TIMEOUT)
                        page.wait_for_timeout(800)
                        self._dismiss_cookies(page)
                        page.wait_for_timeout(300)

                        INPUT_SELECTORS = [
                            "#" + SEARCH_INPUT_ID,
                            "input[name='search_manga[title]']",
                            "input.form-control.input-sm[type='text']",
                            "input[name*='title']",
                        ]
                        filled = False
                        for sel in INPUT_SELECTORS:
                            try:
                                page.wait_for_selector(sel, timeout=4_000)
                                page.fill(sel, query)
                                page.press(sel, "Enter")
                                filled = True
                                break
                            except Exception:
                                continue

                        if filled:
                            try:
                                page.wait_for_selector(
                                    "#" + RESULTS_DIV_ID + ", #elenco-opere",
                                    state="attached",
                                    timeout=10_000,
                                )
                            except Exception:
                                pass
                            page.wait_for_timeout(800)
                            dom_html     = page.content()
                            html_content = _unwrap_json(dom_html)
                            if html_content:
                                parsed = self._parse_search(
                                    BeautifulSoup(html_content, "html.parser")
                                )
                                if parsed:
                                    risultati = self._filter_by_relevance(parsed, query)
                        elif not silent:
                            show_warning("Impossibile trovare il campo di ricerca.")

                finally:
                    browser.close()

        except Exception as exc:
            if not silent:
                show_error("Errore Playwright. Provo HTTP puro...")
            fallback = self._http_search(query, silent=silent)
            if fallback:
                risultati = self._filter_by_relevance(fallback, query)

        if not silent:
            print("  [ok] Risultati finali: " + str(len(risultati)))
        return risultati

    # -- FIX 3+6: Parser HTML a 3 livelli

    def _parse_search(self, soup) -> list:
        """
        Parse HTML risultati ricerca AnimeClick.
        FIX 3: 3 livelli di fallback (thumbnail > card/item > link-scan).
        FIX 6: titolo estratto da data-content > h5 > img[alt] > caption > a.
        FIX 8: voto regex solo decimali con validazione range.
        """
        base_url = _get_base_url()

        # Livello 1: container classico + .thumbnail
        container = soup.find("div", id=RESULTS_DIV_ID)
        if not container:
            container = soup.find("div", id="elenco-opere")

        items = []
        if container:
            items = container.find_all("div", class_=re.compile(r"\bthumbnail\b"))
            if not items:
                # Livello 2: classi CSS alternative
                items = container.find_all(
                    "div",
                    class_=re.compile(r"\bcard\b|\bitem\b|\bopera\b", re.I),
                )

        # Livello 3: link-scan su tutta la pagina
        if not items:
            results = []
            seen = set()
            for a in soup.find_all("a", href=re.compile(r"/anime/\d+/", re.I)):
                href = a.get("href", "").strip()
                if not href or href in seen:
                    continue
                seen.add(href)
                title = a.get_text(strip=True)
                if not title:
                    img = a.find("img")
                    if img:
                        title = (img.get("alt", "") or "").strip()
                if not title:
                    continue
                full_url = href if href.startswith("http") else base_url + href
                results.append({
                    "title": title, "link": full_url,
                    "tipo": "", "anno": "", "voto": "", "generi": [], "desc": "",
                })
            return results

        # Parsing standard dei thumbnail
        results = []
        for thumb in items:
            a_el = thumb.find("a", href=True)
            if not a_el:
                continue
            href = a_el.get("href", "").strip()
            if not href:
                continue
            full_url = href if href.startswith("http") else base_url + href

            # FIX 6: titolo da data-content > h5 > img[alt] > caption > a
            title  = ""
            dc_raw = thumb.get("data-content", "")
            if dc_raw:
                dc_soup = BeautifulSoup(html_lib.unescape(dc_raw), "html.parser")
                h5 = dc_soup.find("h5")
                if h5:
                    title = h5.get_text(strip=True)

            if not title:
                img_el = thumb.find("img")
                if img_el:
                    title = (img_el.get("alt", "") or "").strip()

            if not title:
                caption = thumb.find("div", class_="caption")
                if caption:
                    ca = caption.find("a")
                    if ca:
                        title = ca.get_text(strip=True)

            if not title:
                title = a_el.get_text(strip=True)

            if not title:
                continue

            # Anno
            anno = ""
            info_extra = thumb.find("div", class_="info-extra")
            if info_extra:
                pr = info_extra.find("div", class_="pull-right")
                if pr:
                    anno = pr.get_text(strip=True)

            # FIX 8: voto solo decimali + validazione range
            voto = ""
            if info_extra:
                ie_text = info_extra.get_text().replace("\xa0", " ")
                m = re.search(r"(\d+[.,]\d+)", ie_text)
                if m:
                    candidate = m.group(1).replace(",", ".")
                    try:
                        v = float(candidate)
                        if 0 < v <= 10:
                            voto = m.group(1)
                    except ValueError:
                        pass

            # Tipo, generi, desc da data-content
            tipo = desc = ""
            generi: list = []
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

    # -- FIX 7+: Filtro rilevanza meno aggressivo

    def _filter_by_relevance(self, results: list, query: str) -> list:
        """
        Filtra falsi positivi mantenendo tutti i risultati correlati.
        FIX 7+: meno aggressivo rispetto a v4.1.
          - Score 2: match esatto query nel titolo
          - Score 1: match parziale (almeno una parola chiave nel titolo)
          - Score 0: scartato SOLO se ci sono >3 match
          - Safety: se nessun match -> restituisce lista originale
          - Se matched <= 3 -> restituisce TUTTA la lista

        Esempio: "naruto" -> tutti i 28 risultati (Shippuden, film, OAV)
                 passano perche' contengono "naruto" nel titolo.
        """
        if not results:
            return results

        q_lower = query.strip().lower()
        q_words = [w for w in q_lower.split() if len(w) >= 3]

        def _score(title: str) -> int:
            t      = title.lower()
            t_norm = t.replace("-", " ").replace("_", " ").replace(":", " ")
            if q_lower in t or q_lower in t_norm:
                return 2  # match esatto
            if q_words and any(w in t or w in t_norm for w in q_words):
                return 1  # match parziale
            return 0

        scored    = [(r, _score(r["title"])) for r in results]
        has_match = any(s > 0 for _, s in scored)

        # Safety: nessun titolo corrisponde -> restituisce tutto
        if not has_match:
            return results

        matched = [r for r, s in scored if s > 0]

        # Se i risultati con match sono pochi, restituisce tutta la lista
        if len(matched) <= 3:
            return results

        # Altrimenti filtra: mantieni score 1 E score 2, scarta solo score 0
        filtered = [r for r, s in scored if s > 0]
        filtered.sort(key=lambda r: _score(r["title"]), reverse=True)
        return filtered

    # -- FIX 5: Fallback HTTP puro con CookieJar

    def _http_search(self, query: str, *, silent: bool = False) -> list:
        """
        Ricerca HTTP pura senza Playwright (fallback).
        FIX 2: urlencode con chiave decodificata.
        FIX 4: _unwrap_json() per risposta AJAX.
        """
        if not HAS_BS4:
            return []

        search_url = _get_search_url()
        cj     = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj)
        )

        try:
            # Step 1: GET per CSRF token + cookie di sessione
            req_get = urllib.request.Request(search_url, headers=_BASE_HDR)
            with opener.open(req_get, timeout=15) as resp:
                html_get = resp.read().decode("utf-8", errors="replace")

            soup_get = BeautifulSoup(html_get, "html.parser")
            token_el = soup_get.find("input", {"name": "search_manga[_token]"})
            csrf     = token_el["value"] if token_el else ""

            # Step 2: FIX 2 - urlencode con chiave decodificata
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
                search_url, data=post_body, headers=post_hdr, method="POST"
            )
            with opener.open(req_post, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            html_content = _unwrap_json(raw)
            return self._parse_search(BeautifulSoup(html_content, "html.parser"))

        except Exception as e:
            if not silent:
                show_warning("HTTP fallback fallito: " + str(e))
            return []

    # -- Dettagli scheda

    def get_anime_details(self, url: str, *, silent: bool = False) -> dict:
        """Recupera e parsa la scheda dettaglio anime da AnimeClick."""
        if not HAS_PLAYWRIGHT or not HAS_BS4:
            if not silent:
                show_error("Playwright o beautifulsoup4 non installati.")
            return {}
        if not silent:
            print("\n  [*] Recupero scheda: " + url)
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
                            page.wait_for_selector(sel, timeout=4_000)
                            break
                        except Exception:
                            continue
                    page.wait_for_timeout(800)
                    html = page.content()
                    if html:
                        details = self._parse_details(
                            BeautifulSoup(html, "html.parser"), url
                        )
                finally:
                    browser.close()
        except Exception as e:
            if not silent:
                show_error("Errore recupero scheda: " + str(e))
        return details

    def _parse_details(self, soup, url: str) -> dict:
        """
        Estrae dati strutturati dalla scheda HTML di AnimeClick.
        FIX: anno range dinamico (1950-_YEAR_NOW).
        FIX 8: voto regex solo decimali + validazione range.
        FIX 1: URL copertina dinamico via _get_base_url().
        """
        base_url = _get_base_url()
        d = {
            "titolo": "", "link": url, "tipo": "", "episodes": 0, "stato": "",
            "anno":   "", "generi": [], "trama": "", "voto": "", "copertina": "",
        }
        full = soup.get_text(" ", strip=True)

        # Titolo
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

        # Anno (range dinamico 1950-_YEAR_NOW)
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

        # Episodi
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

        # Stato
        for stato in ["Completato", "In corso", "In produzione", "In pausa", "Abbandonato"]:
            if stato.lower() in full.lower():
                d["stato"] = stato
                break

        # Tipo
        for tipo_val in ["Serie TV", "Film", "Serie OAV", "OAV", "Special", "ONA"]:
            if tipo_val.lower() in full.lower():
                d["tipo"] = tipo_val
                break

        # Generi
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

        # Trama
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

        # FIX 8: Voto solo decimali + validazione range
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

        # Copertina (FIX 1: URL base dinamico)
        for kw in [
            {"class": re.compile(r"cover|copertina|poster|locandina", re.I)},
            {"id":    re.compile(r"cover|copertina|poster", re.I)},
        ]:
            img = soup.find("img", kw)
            if img:
                src = img.get("src", "") or img.get("data-src", "")
                if src:
                    if not src.startswith("http"):
                        src = base_url + ("" if src.startswith("/") else "/") + src
                    d["copertina"] = src
                    break

        return d

    # -- Export

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

            # Scarica cover
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
                        show_success("Cover salvata: " + cover_saved)
                except Exception as e:
                    if not silent:
                        show_warning("Impossibile scaricare la cover: " + str(e))
            else:
                if not silent:
                    show_warning("Nessuna URL cover disponibile.")

            # Crea file .txt
            txt_file   = folder / (safe + ".txt")
            sep        = "=" * 56
            sep2       = "-" * 56
            generi_str = ", ".join(details.get("generi", [])) or "N/D"
            trama      = details.get("trama", "N/D") or "N/D"
            if trama.lower().startswith("trama:"):
                trama = trama[6:].strip()

            lines_txt = [
                sep,
                " SCHEDA ANIME",
                sep,
                "",
                "  Titolo  : " + details.get("titolo", "N/D"),
                "  Tipo    : " + (details.get("tipo", "N/D") or "N/D"),
                "  Anno    : " + (details.get("anno", "N/D") or "N/D"),
                "  Episodi : " + str(details.get("episodes", "?") or "?"),
                "  Stato   : " + (details.get("stato", "N/D") or "N/D"),
                "  Voto    : " + (details.get("voto", "N/D") or "N/D"),
                "  Generi  : " + generi_str,
                "",
                sep2,
                " TRAMA",
                sep2,
                "",
            ]
            for line in textwrap.wrap(trama, width=72):
                lines_txt.append("  " + line)
            lines_txt += [
                "",
                sep2,
                " LINK E RISORSE",
                sep2,
                "",
                "  Scheda  : " + details.get("link", ""),
                "  Cover   : " + details.get("copertina", ""),
                "",
                sep,
            ]
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines_txt))
            if not silent:
                show_success("File dati salvato: " + txt_file.name)

            return str(folder)

        except Exception as e:
            if not silent:
                show_error("Errore esportazione: " + str(e))
            return ""


# -- Helpers display

def _select_result(results: list):
    """Menu selezione da lista risultati ricerca. Ritorna il dict scelto o None."""
    if not results:
        show_warning("Nessun risultato trovato.")
        wait_enter()
        return None
    print()
    for i, r in enumerate(results, 1):
        tipo = " [" + r["tipo"] + "]"        if r.get("tipo") else ""
        anno = " (" + r["anno"] + ")"        if r.get("anno") else ""
        voto = " \u2605" + r["voto"]         if r.get("voto") else ""
        print("  " + str(i).rjust(2) + ". " + r["title"] + tipo + anno + voto)
        if r.get("desc"):
            snippet = r["desc"]
            if len(snippet) > 72:
                snippet = snippet[:70] + "..."
            print("       \u2514 " + snippet)
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
    """Stampa a video i dati scheda anime formattati."""
    print()
    print("  Titolo  : " + d.get("titolo", "N/D"))
    print("  Tipo    : " + (d.get("tipo", "N/D") or "N/D"))
    print("  Episodi : " + str(d.get("episodes", "?")))
    print("  Stato   : " + d.get("stato", "N/D"))
    print("  Anno    : " + d.get("anno", "N/D"))
    print("  Voto    : " + (d.get("voto", "N/D") or "N/D"))
    if d.get("generi"):
        print("  Generi  : " + ", ".join(d["generi"][:6]))
    if d.get("trama"):
        t = d["trama"].lstrip("Trama:").strip()
        print("  Trama   : " + ((t[:157] + "...") if len(t) > 160 else t))
    if d.get("copertina"):
        print("  Cover   : " + d["copertina"][:70])
    print("  Link    : " + d.get("link", ""))
    print()


# -- Menu principale

def handle_ricerca_scheda_anime(tracker=None):
    """Menu principale ricerca scheda anime v4.2"""
    if tracker is None:
        tracker = AnimeTracker()

    if not HAS_PLAYWRIGHT:
        clear_screen()
        show_header("RICERCA SCHEDA ANIME v4.2")
        show_error("Playwright non installato.")
        show_info("Esegui: pip install playwright && playwright install chromium")
        wait_enter()
        return

    while True:
        clear_screen()
        print("  " + "=" * _W)
        print("  RICERCA SCHEDA ANIME v4.2")
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
            show_header("RISULTATI: " + str(len(results)) + " trovati")
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
                    show_info("Cartella: " + folder)
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
            base_url = _get_base_url()
            if not url.startswith("http"):
                url = base_url + ("" if url.startswith("/") else "/") + url
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
                    show_info("Cartella: " + folder)
                else:
                    show_error("Errore durante l'esportazione.")
            wait_enter()

        else:
            show_error("Opzione non valida.")
            wait_enter()


if __name__ == "__main__":
    tracker = AnimeTracker()
    handle_ricerca_scheda_anime(tracker)
