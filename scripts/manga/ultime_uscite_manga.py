#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ultime_uscite_manga.py v2.1-fixed
===================================
Modulo per le Ultime uscite manga di AnimeClick.it.
Percorso: scripts/manga/ultime_uscite_manga.py

FIX v2.1:
  - _extract_news_list: legge titolo da img[alt] e a[title] dentro .thumbnail-news-img
  - _extract_article_groups: pattern body aggiornato per article-body/article-body-wrapper
  - Import manga_engine: rimosso doppio import orfano che causava SyntaxError
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

# ── Percorsi ──────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).parent.resolve()    # scripts/manga/
_TEMP_DIR = _THIS_DIR.parent / "temp"          # scripts/temp/
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

for _p in [str(_THIS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Import da manga_engine ────────────────────────────────────────────────────
try:
    from manga_engine import (
        clear_screen, show_error, show_success, show_info,
        sanitize_filename, get_link_dir, get_headless_mode, get_page_timeout,
        load_prefs, save_prefs, WIDTH, COOKIE_SEL, COOKIE_TEXTS,
    )
    _ENGINE_OK = True
except ImportError:
    _ENGINE_OK = False
    WIDTH = 56
    import json

    def clear_screen():
        import os; os.system("cls" if os.name == "nt" else "clear")
    def show_error(m):   print(f"  [\u2717] {m}")
    def show_success(m): print(f"  [\u2713] {m}")
    def show_info(m):    print(f"  [i] {m}")
    def sanitize_filename(n): return re.sub(r'[<>:"/\\|?*]', "", n).strip()[:200]
    def load_prefs():
        p = _TEMP_DIR / "prefs.json"
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    def save_prefs(d):
        try:
            with open(_TEMP_DIR / "prefs.json", "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        except Exception: pass
    def get_link_dir(): return load_prefs().get("default_link_dir", "")
    def get_headless_mode(): return bool(load_prefs().get("browser_headless", False))
    def get_page_timeout():
        try: return int(load_prefs().get("page_timeout", 15_000))
        except Exception: return 15_000
    COOKIE_SEL = [
        "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "#cookie-accept", ".cc-btn.cc-allow",
        "button[id*='accept']", "button[class*='cookie']",
    ]
    COOKIE_TEXTS = ["continua", "accetta", "accept", "ok", "agree", "accetto"]

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Costanti modulo ────────────────────────────────────────────────────────────
BASE_URL         = "https://www.animeclick.it"
MANGA_USCITE_URL = "https://www.animeclick.it/news/rubrica/6/uscite-manga-del-mese"

_SEP = "  " + "-" * (WIDTH - 2)
_EQ  = "=" * WIDTH
_EQS = "-" * WIDTH

_MANGA_GROUPS_ORDER = ["Uscite ufficiali", "Data non pervenuta", "Lost in action"]

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins',   {get: () => [1, 2, 3]});
Object.defineProperty(navigator, 'languages', {get: () => ['it-IT','it','en-US','en']});
window.chrome = {runtime: {}};
"""

# ── Preferenze manga-specifiche ────────────────────────────────────────────────

def _get_manga_last_first() -> dict | None:
    return load_prefs().get("manga_last_first")

def _set_manga_last_first(article: dict) -> None:
    prefs = load_prefs()
    prefs["manga_last_first"] = {"titolo": article.get("titolo",""), "link": article.get("link","")}
    save_prefs(prefs)

# ── Helpers locali ─────────────────────────────────────────────────────────────

def _normalise(href: str) -> str:
    if not href: return ""
    return href if href.startswith("http") else BASE_URL + href

def _hyperlink(text: str, url: str) -> str:
    if not url: return text
    return "\033]8;;" + url + "\007" + text + "\033]8;;\007"

# ── Export folder ─────────────────────────────────────────────────────────────

def _ensure_uscite_manga_folder() -> str | None:
    link_dir = get_link_dir()
    if not link_dir:
        print("\n  Percorso 'default_link_dir' non configurato nelle Impostazioni.")
        alt = input("  Inserisci percorso base alternativo (invio = annulla): ").strip()
        if not alt: print("  Operazione annullata."); return None
        link_dir = alt
    folder = str(Path(link_dir) / "Ultime uscite manga")
    try:
        Path(folder).mkdir(parents=True, exist_ok=True); return folder
    except OSError as exc:
        print("  Errore creazione cartella: " + str(exc)); return None

def _write_single_entry(folder: str, entry: dict) -> None:
    fname = sanitize_filename(entry["titolo"] + " [Manga].txt")
    fpath = str(Path(folder) / fname)
    lines = [_EQ, "  " + entry["titolo"], _EQS]
    if entry.get("data"):          lines.append("  Data uscita:    " + entry["data"])
    if entry.get("casa_editrice"): lines.append("  Casa editrice:  " + entry["casa_editrice"])
    if entry.get("prezzo"):        lines.append("  Prezzo:         " + entry["prezzo"])
    if entry.get("gruppo"):        lines.append("  Gruppo:         " + entry["gruppo"])
    link = entry.get("link","")
    if link: lines.extend([_EQS, "  (" + link + ")"])
    lines.append(_EQ)
    try:
        with open(fpath, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        print("  Salvato: " + fpath)
    except OSError as exc: print("  Errore salvataggio: " + str(exc))

def _write_article_file(folder: str, entries: list, article_title: str) -> None:
    base_name = sanitize_filename(article_title)
    fpath = str(Path(folder) / (base_name + ".txt"))
    if Path(fpath).exists():
        c = 1
        while (Path(folder) / f"{base_name}_{c}.txt").exists(): c += 1
        fpath = str(Path(folder) / f"{base_name}_{c}.txt")
    lines = [_EQ, "  USCITE MANGA \u2014 " + article_title, _EQ]
    for i, e in enumerate(entries, 1):
        lines.extend(["", "  [{:>3}]  {}".format(i, e["titolo"]), "  " + _EQS])
        if e.get("data"):          lines.append("  Data uscita:    " + e["data"])
        if e.get("casa_editrice"): lines.append("  Casa editrice:  " + e["casa_editrice"])
        if e.get("prezzo"):        lines.append("  Prezzo:         " + e["prezzo"])
        if e.get("gruppo"):        lines.append("  Gruppo:         " + e["gruppo"])
        if e.get("link"):          lines.append("  (" + e["link"] + ")")
    lines.extend(["", _EQ])
    try:
        with open(fpath, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        print("  Salvato: " + fpath)
    except OSError as exc: print("  Errore salvataggio: " + str(exc))

# ── Browser helpers ────────────────────────────────────────────────────────────

_cookie_dismissed: bool = False

def _new_page(playwright):
    browser = playwright.chromium.launch(
        headless=get_headless_mode(),
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
    )
    ctx = browser.new_context(locale="it-IT", user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ))
    ctx.add_init_script(_STEALTH_JS)
    page = ctx.new_page()
    page.set_default_timeout(get_page_timeout())
    return browser, page

def _handle_intro_redirect(page, original_url: str) -> None:
    timeout_ms = get_page_timeout()
    step = 500; elapsed = 0
    while elapsed < timeout_ms:
        if "/video-intro" not in page.url: return
        try:
            clicked = page.evaluate("""() => {
                const kw = ['skip','salta','continua','continue','entra','vai','accedi'];
                const all = document.querySelectorAll('button, a, input[type="button"], [role="button"]');
                for (const el of all) {
                    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (kw.some(k => t.includes(k)) && el.offsetParent !== null) { el.click(); return true; }
                }
                return false;
            }""")
            if clicked:
                page.wait_for_timeout(800)
                if "/video-intro" not in page.url: return
        except Exception: pass
        page.wait_for_timeout(step); elapsed += step
    if "/video-intro" in page.url:
        try: page.goto(original_url, wait_until="domcontentloaded"); page.wait_for_timeout(1_000)
        except Exception: pass

def _dismiss_cookie(page) -> None:
    global _cookie_dismissed
    if _cookie_dismissed: return
    clicked = page.evaluate(
        """([selectors, textCandidates]) => {
            for (const sel of selectors) {
                try { const el = document.querySelector(sel); if (el && el.offsetParent !== null) { el.click(); return 'css:' + sel; } } catch(e) {}
            }
            const all = document.querySelectorAll('button, a, input[type="button"], input[type="submit"], [role="button"]');
            for (const el of all) {
                const txt = (el.innerText || el.value || '').trim().toLowerCase();
                if (textCandidates.includes(txt) && el.offsetParent !== null) { el.click(); return 'text:' + txt; }
            }
            return null;
        }""", [COOKIE_SEL, COOKIE_TEXTS],
    )
    if clicked:
        _cookie_dismissed = True; page.wait_for_timeout(300); return
    for sel in COOKIE_SEL:
        try: page.click(sel, timeout=600); _cookie_dismissed = True; page.wait_for_timeout(300); return
        except Exception: continue

def _wait_for_manga_list(page) -> None:
    for sel in ["#news-div .col-news", "#news-div", ".col-news", ".thumbnail-news"]:
        try: page.wait_for_selector(sel, timeout=8000); page.wait_for_timeout(800); return
        except Exception: continue
    for _ in range(10):
        page.wait_for_timeout(700)
        if page.evaluate("() => document.querySelectorAll('#news-div .col-news').length") >= 1:
            page.wait_for_timeout(500); return
    try: page.wait_for_load_state("networkidle", timeout=8000)
    except Exception: pass
    page.wait_for_timeout(2000)

def _wait_for_manga_article(page) -> None:
    for sel in ["table.tab-edizioni", "div.tab-edizioni-wrap", ".tab-edizioni", "table"]:
        try: page.wait_for_selector(sel, timeout=8000); page.wait_for_timeout(800); return
        except Exception: continue
    for _ in range(10):
        page.wait_for_timeout(700)
        if page.evaluate("() => document.querySelectorAll('table tr').length") >= 3:
            page.wait_for_timeout(500); return
    try: page.wait_for_load_state("networkidle", timeout=8000)
    except Exception: pass
    page.wait_for_timeout(2000)

# ── Fetch HTML ─────────────────────────────────────────────────────────────────

def _fetch_news_list_html(url: str = MANGA_USCITE_URL) -> str:
    global _cookie_dismissed; _cookie_dismissed = False; html = ""
    try:
        with sync_playwright() as pw:
            browser, page = _new_page(pw)
            try:
                page.goto(url, wait_until="domcontentloaded")
                _handle_intro_redirect(page, url)
                _dismiss_cookie(page); _wait_for_manga_list(page); _dismiss_cookie(page)
                html = page.content()
                with open(str(_TEMP_DIR / "debug_manga_news.html"), "w", encoding="utf-8") as f: f.write(html)
            finally: browser.close()
    except PWTimeout: print("  Timeout durante il caricamento della lista.")
    except Exception as exc: print("  Errore: " + str(exc))
    return html

def _fetch_article_html(url: str) -> str:
    global _cookie_dismissed; _cookie_dismissed = False; html = ""
    try:
        with sync_playwright() as pw:
            browser, page = _new_page(pw)
            try:
                page.goto(url, wait_until="domcontentloaded")
                _handle_intro_redirect(page, url)
                _dismiss_cookie(page); _wait_for_manga_article(page); _dismiss_cookie(page)
                html = page.content()
                with open(str(_TEMP_DIR / "debug_manga_article.html"), "w", encoding="utf-8") as f: f.write(html)
            finally: browser.close()
    except PWTimeout: print("  Timeout durante il caricamento dell'articolo.")
    except Exception as exc: print("  Errore: " + str(exc))
    return html

# ── Parsing lista news ─────────────────────────────────────────────────────────
# FIX: AnimeClick mette il titolo in img[alt] e a[title] dentro .thumbnail-news-img
# NON nel caption. La strategia 1 ora cerca lì per prima cosa.

def _extract_news_list(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    news_div = soup.find("div", id="news-div")
    if not news_div:
        nd = soup.find("div", class_=re.compile(r"col-news"))
        news_div = nd.parent if nd else soup

    for col in news_div.find_all("div", class_="col-news")[:10]:
        thumb = (col.find("div", class_=lambda c: c and "thumbnail-news" in c)
                 or col.find("div", class_=lambda c: c and "thumbnail" in c)
                 or col)

        titolo = ""
        link_href = ""
        data = ""

        # ── STRATEGIA 1: .thumbnail-news-img > a > img[alt] (struttura reale AnimeClick) ──
        img_wrap = thumb.find("div", class_="thumbnail-news-img")
        if img_wrap:
            a_tag = img_wrap.find("a", href=True)
            if a_tag:
                link_href = a_tag.get("href", "")
                # Titolo da title="" del <a>
                t = a_tag.get("title", "").strip()
                if t and len(t) > 2:
                    titolo = t
                # Titolo da alt="" dell'<img>
                if not titolo:
                    img = a_tag.find("img")
                    if img:
                        t = img.get("alt", "").strip()
                        if t and len(t) > 2:
                            titolo = t

        # ── STRATEGIA 2: caption > h4/h3/h2/h5/p > a ──
        if not titolo:
            caption = thumb.find("div", class_="caption")
            if caption:
                for tag in ["h4", "h3", "h2", "h5", "p"]:
                    h = caption.find(tag)
                    if h:
                        a = h.find("a", href=True)
                        if a:
                            titolo = a.get_text(strip=True)
                            link_href = link_href or a.get("href", "")
                        else:
                            titolo = h.get_text(strip=True)
                        break
                if not titolo:
                    for a in caption.find_all("a", href=True):
                        t = a.get_text(strip=True)
                        if t and len(t) > 2:
                            titolo = t
                            link_href = link_href or a.get("href", "")
                            break

        # ── STRATEGIA 3: qualsiasi h* nel thumb ──
        if not titolo:
            for tag in ["h4", "h3", "h2", "h5"]:
                h = thumb.find(tag)
                if h:
                    a = h.find("a", href=True)
                    if a:
                        titolo = a.get_text(strip=True)
                        link_href = link_href or a.get("href", "")
                    else:
                        titolo = h.get_text(strip=True)
                    break

        # ── STRATEGIA 4: primo <a> con testo nel col ──
        if not titolo:
            for a in col.find_all("a", href=True):
                t = a.get_text(strip=True)
                if t and len(t) > 3:
                    titolo = t
                    link_href = link_href or a.get("href", "")
                    break

        if not titolo:
            continue

        # ── Data: span.data-pubblicazione (struttura AnimeClick) ──
        span_data = thumb.find("span", class_="data-pubblicazione")
        if span_data:
            data = span_data.get_text(strip=True)
        if not data:
            tt = thumb.find("time")
            if tt:
                data = tt.get("datetime", "") or tt.get_text(strip=True)
        if not data:
            for tag in thumb.find_all(["small", "span", "em", "abbr", "p"]):
                txt = tag.get_text(strip=True)
                if re.search(r"\d{1,2}[/\-\.]\d{1,2}", txt):
                    data = txt
                    break

        results.append({
            "titolo": titolo,
            "data":   data,
            "link":   _normalise(link_href),
        })

    return results

# ── Parsing articolo ───────────────────────────────────────────────────────────

def _parse_tab_edizioni(table) -> list:
    entries = []; rows = table.find_all("tr")
    if len(rows) < 2: return entries
    hdr = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th","td"])]
    N = len(hdr)
    col = {"data": None, "titolo": None, "editore": None, "prezzo": None}
    for i, h in enumerate(hdr):
        if col["data"]    is None and re.search(r"data|uscita",                     h): col["data"]    = i
        if col["titolo"]  is None and re.search(r"titolo|opera|manga|serie|nome",   h): col["titolo"]  = i
        if col["editore"] is None and re.search(r"editore|casa|edizioni|publisher", h): col["editore"] = i
        if col["prezzo"]  is None and re.search(r"prezzo|costo|euro|price",         h): col["prezzo"]  = i
    if col["titolo"] is None:
        if N >= 4:
            col["data"]    = col["data"]    if col["data"]    is not None else 0
            col["titolo"]  = 1
            col["editore"] = col["editore"] if col["editore"] is not None else 2
            col["prezzo"]  = col["prezzo"]  if col["prezzo"]  is not None else 3
        elif N == 3: col["data"], col["titolo"], col["editore"] = 0, 1, 2
        elif N == 2: col["titolo"], col["editore"] = 0, 1
        elif N == 1: col["titolo"] = 0

    def _gc(cells, key):
        idx = col.get(key)
        return cells[idx].get_text(" ", strip=True) if idx is not None and idx < len(cells) else ""

    def _gl(cells):
        idx = col.get("titolo")
        if idx is not None and idx < len(cells):
            for a in cells[idx].find_all("a", href=True):
                h = a.get("href", "")
                if h and not h.startswith("#"): return _normalise(h)
        for cell in cells:
            for a in cell.find_all("a", href=True):
                h = a.get("href", "")
                if h and re.search(r"/(manga|anime|novel|liveaction|serietv)/\d+", h): return _normalise(h)
        return ""

    SKIP = {"titolo","opera","manga","serie","data","editore","prezzo","casa editrice"}
    for row in rows[1:]:
        cells = row.find_all(["td","th"])
        if not cells: continue
        t = _gc(cells, "titolo")
        if not t or len(t) < 2 or t.lower().strip() in SKIP: continue
        entries.append({
            "titolo":        t,
            "data":          _gc(cells, "data"),
            "prezzo":        _gc(cells, "prezzo"),
            "casa_editrice": _gc(cells, "editore"),
            "link":          _gl(cells),
        })
    return entries

# FIX: pattern body aggiornato per article-body / article-body-wrapper di AnimeClick
def _extract_article_groups(html: str) -> dict:
    groups = {g: [] for g in _MANGA_GROUPS_ORDER}
    soup = BeautifulSoup(html, "html.parser")

    # Cerca il corpo articolo con pattern aggiornato che copre article-body-wrapper
    body = (
        soup.find("div", class_=re.compile(r"article.?body", re.I))
        or soup.find("div", class_=re.compile(r"news.?body|corpo.?news|news.?content|contenuto", re.I))
        or soup.find("article")
        or soup.find("div", class_="corpo")
        or soup.find("div", class_=re.compile(r"^content$|^corpo$", re.I))
        or soup
    )

    current_group = "Uscite ufficiali"
    seen: set = set()

    for el in body.descendants:
        if not hasattr(el, "name") or not el.name:
            continue
        if el.name in ("strong", "b", "h2", "h3", "h4"):
            txt = el.get_text(strip=True).lower()
            if "lost in action" in txt:
                current_group = "Lost in action"
            elif re.search(r"data non pervenuta|data n\.p\.|senza data", txt):
                current_group = "Data non pervenuta"
            elif re.search(r"uscite ufficiali|uscite del mese|uscite confermate", txt):
                current_group = "Uscite ufficiali"
        if el.name == "div" and "tab-edizioni-wrap" in " ".join(el.get("class") or []):
            table = el.find("table", class_="tab-edizioni")
            if table and id(table) not in seen:
                seen.add(id(table))
                for e in _parse_tab_edizioni(table):
                    e["gruppo"] = current_group
                    groups[current_group].append(e)
        if el.name == "table":
            cls = " ".join(el.get("class") or [])
            if ("tab-edizioni" in cls or el.find("th") or el.find("td")) and id(el) not in seen:
                seen.add(id(el))
                for e in _parse_tab_edizioni(el):
                    e["gruppo"] = current_group
                    groups[current_group].append(e)
    return groups

# ── Visualizzazione ────────────────────────────────────────────────────────────

def _print_news_list(news: list) -> None:
    print("\n  {:<4} {}".format("N", "Titolo")); print(_SEP)
    for i, art in enumerate(news, 1):
        print("  {:<4} {}{}".format(
            i, art["titolo"],
            "  [" + art["data"] + "]" if art.get("data") else ""
        ))
    print(_SEP)

def _print_groups_summary(groups: dict) -> dict:
    item_map = {}; counter = 1
    for gn in _MANGA_GROUPS_ORDER:
        entries = groups.get(gn, [])
        if not entries: continue
        print("\n  [{}]  ({} titoli)".format(gn, len(entries))); print(_SEP)
        for entry in entries:
            parts = []
            if entry.get("data"): parts.append(entry["data"])
            lnk = entry.get("link", "")
            title_str = _hyperlink(entry["titolo"], lnk) if lnk else entry["titolo"]
            parts.append(title_str)
            if entry.get("casa_editrice"): parts.append(entry["casa_editrice"])
            if entry.get("prezzo"):        parts.append(entry["prezzo"])
            print("  {:>3}.  ".format(counter) + "  |  ".join(parts))
            item_map[counter] = entry; counter += 1
        print(_SEP)
    return item_map

def _print_entry_detail(entry: dict) -> None:
    link = entry.get("link", ""); print("\n" + _EQ)
    print("  " + (_hyperlink(entry["titolo"], link) if link else entry["titolo"])); print(_EQS)
    if entry.get("data"):          print("  {:<22} {}".format("Data uscita",   entry["data"]))
    if entry.get("casa_editrice"): print("  {:<22} {}".format("Casa editrice", entry["casa_editrice"]))
    if entry.get("prezzo"):        print("  {:<22} {}".format("Prezzo",        entry["prezzo"]))
    if entry.get("gruppo"):        print("  {:<22} {}".format("Gruppo",        entry["gruppo"]))
    if link: print(_EQS); print("  " + link)
    print(_EQ)

def _select_entries(item_map: dict) -> list | None:
    if not item_map: print("  Nessun titolo disponibile."); return None
    max_n = max(item_map.keys())
    while True:
        print("\n" + _SEP)
        print("  Titoli: 1-{}  |  Singolo  Multiplo(1,3,7)  Range(1-10)  Tutti(T)  Annulla(0)".format(max_n))
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
                        else: print("  Numero {} fuori range (1-{}) \u2014 ignorato.".format(n, max_n))
                except ValueError:
                    print("  Range non valido: '{}' \u2014 ignorato.".format(part)); has_error = True
            else:
                try:
                    n = int(part)
                    if n in item_map:
                        if item_map[n] not in selected: selected.append(item_map[n])
                    else: print("  Numero {} fuori range (1-{}) \u2014 ignorato.".format(n, max_n))
                except ValueError:
                    print("  Valore non valido: '{}' \u2014 ignorato.".format(part)); has_error = True
        if has_error: input("  Premi invio per riprovare..."); continue
        if not selected: print("  Nessun titolo selezionato valido."); input("  Premi invio per riprovare..."); continue
        return selected

# ── Flusso articolo ────────────────────────────────────────────────────────────

def _handle_article(article: dict) -> None:
    clear_screen(); print(_EQ); print("  " + article["titolo"]); print(_EQ)
    print("\n  Caricamento uscite in corso...")
    html = _fetch_article_html(article["link"])
    if not html: input("\n  Premi invio per tornare..."); return
    groups = _extract_article_groups(html)
    total = sum(len(v) for v in groups.values())
    if total == 0:
        print("\n  Nessuna uscita trovata.")
        input("\n  Premi invio per tornare...")
        return

    def _reprint():
        clear_screen(); print(_EQ); print("  " + article["titolo"]); print(_EQ)
        return _print_groups_summary(groups)

    item_map = _reprint()
    while True:
        print("\n" + _SEP); print("  S  Seleziona titoli  |  0  Torna indietro"); print(_SEP)
        scelta = input("  Scelta: ").strip().upper()
        if scelta == "0": return
        if scelta != "S": print("  Opzione non valida."); continue
        selected = _select_entries(item_map)
        if not selected: item_map = _reprint(); continue
        n_sel = len(selected)
        if n_sel == 1:
            e = selected[0]
            clear_screen(); print(_EQ); print("  " + e["titolo"]); print(_EQ)
            print("\n  1. Visualizza a video  2. Esporta .txt  3. Torna")
            azione = input("\n  Scelta (1-3): ").strip()
            if azione == "1":
                _print_entry_detail(e); input("\n  Premi invio..."); item_map = _reprint()
            elif azione == "2":
                folder = _ensure_uscite_manga_folder()
                if folder: _write_single_entry(folder, e); print("  Cartella: " + folder)
                input("\n  Premi invio..."); item_map = _reprint()
            elif azione == "3":
                item_map = _reprint()
            else:
                print("  Opzione non valida.")
        else:
            clear_screen(); print(_EQ); print("  {} titoli selezionati".format(n_sel)); print(_EQ); print()
            for i, e in enumerate(selected, 1):
                print("  {:>3}.  {}{}".format(
                    i, e["titolo"],
                    "  [{}]".format(e["data"]) if e.get("data") else ""
                ))
            print()
            print("  1. Visualizza a video (uno per uno)  2. Esporta .txt  3. Torna")
            azione = input("\n  Scelta (1-3): ").strip()
            if azione == "1":
                for e in selected:
                    clear_screen(); _print_entry_detail(e)
                    if input("\n  Invio = prossimo  (0=ferma): ").strip() == "0": break
                input("\n  Premi invio..."); item_map = _reprint()
            elif azione == "2":
                folder = _ensure_uscite_manga_folder()
                if folder:
                    _write_article_file(folder, selected, article["titolo"])
                    print("\n  {} titoli in: {}".format(n_sel, folder))
                input("\n  Premi invio..."); item_map = _reprint()
            elif azione == "3":
                item_map = _reprint()
            else:
                print("  Opzione non valida.")

# ── Controllo novita ───────────────────────────────────────────────────────────

def check_manga_news_update() -> None:
    last = _get_manga_last_first()
    print("\n" + _SEP); print("  Controllo aggiornamenti uscite manga...")
    html = _fetch_news_list_html()
    if not html: print("  Impossibile verificare."); input("  Premi invio..."); return
    news = _extract_news_list(html)
    if not news: print("  Nessun articolo trovato."); input("  Premi invio..."); return
    first = news[0]; _set_manga_last_first(first)
    if not last:
        print("  Primo avvio: memorizzato.\n  " + first["titolo"])
        input("  Premi invio..."); return
    if last.get("link","") == first.get("link","") and last.get("titolo","") == first.get("titolo",""):
        print("  Nessuna novita."); input("  Premi invio..."); return
    print("\n  NUOVA USCITA MANGA RILEVATA!\n" + _EQ)
    print("  " + first["titolo"])
    if first.get("data"): print("  Data: " + first["data"])
    if first.get("link"): print("  " + first["link"])
    print(_EQ)
    if input("\n  Vuoi aprire questo articolo ora? (s/n): ").strip().lower() in ("s","si","y","yes"):
        _handle_article(first)

# ── Entry point ────────────────────────────────────────────────────────────────

def handle_manga_uscite() -> None:
    """Entry point chiamato da handlers.py."""
    clear_screen()
    print(_EQ); print("  ULTIME USCITE MANGA  AnimeClick.it"); print(_EQ)
    print("\n  URL di default:\n  " + MANGA_USCITE_URL)
    raw = input("\n  Premi INVIO per usarlo, o incolla un URL diverso: ").strip()
    url = raw if raw else MANGA_USCITE_URL
    print("\n  Caricamento lista articoli...")
    html = _fetch_news_list_html(url)
    if not html:
        print("\n  Errore: impossibile caricare la pagina.")
        input("  Premi invio per tornare..."); return
    news = _extract_news_list(html)
    if not news:
        print("\n  Nessun articolo trovato.")
        input("  Premi invio per tornare..."); return

    def _show_list():
        clear_screen()
        print(_EQ); print("  ULTIME USCITE MANGA  AnimeClick.it"); print(_EQ)
        print("  URL: " + url)
        _print_news_list(news)

    _show_list()
    while True:
        print(_SEP); print("  Numero articolo da aprire  |  0 Torna al menu"); print(_SEP)
        scelta = input("  Scelta: ").strip()
        if scelta == "0": return
        if scelta.isdigit() and 1 <= int(scelta) <= len(news):
            _handle_article(news[int(scelta) - 1]); _show_list()
        else:
            print("  Selezione non valida.")


if __name__ == "__main__":
    handle_manga_uscite()
