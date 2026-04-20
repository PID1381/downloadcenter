#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MANGA ENGINE v1.4 - CORE ENGINE CENTRALIZZATO + FIX v2.3
Download Center - scripts/manga/manga_engine.py

NOVITA v1.3 (FIX per la_mia_collezione.py v2.3):
  §9.5 Nuovi metodi in MangaPageSession:
        - fetch_animeclick_manga_search()  ->  ricerca Playwright AnimeClick
  §9.6 Nuova funzione helper:
        - extract_animeclick_manga_results()  ->  parsing robusto risultati
  §11  __all__ aggiornato: 66 -> 67 simboli pubblici

NOVITA v1.2:
  §7  Nuova funzione di configurazione:
        get_export_dir()  ->  legge "default_export_dir" da prefs.json
        (distinta da get_link_dir() che legge "default_link_dir")
  §11 __all__ aggiornato: 65 -> 66 simboli pubblici

NOVITA v1.1:
  §1  Costanti Vinted: BASE_URL_VINTED, VINTED_CATALOG_URL,
                       VINTED_SEARCH_INPUT_SEL, VINTED_EXPORT_FILENAME
  §8  search_vinted_manga()
  §9  extract_vinted_results(), _vinted_attr(), extract_vinted_item_details()
      MangaPageSession: fetch_vinted_search(), fetch_vinted_item()
  §10.5 save_vinted_export()

ESPORTAZIONI: 67 simboli pubblici (vedi __all__)
"""
from __future__ import annotations

import csv
import os
import re
import json
import time
import signal
import threading
from datetime import datetime

# ── Costanti globali (patch) ────────────────────────────────────────────────
_MESI_IT = {
    1: "gennaio",  2: "febbraio", 3: "marzo",    4: "aprile",
    5: "maggio",   6: "giugno",   7: "luglio",   8: "agosto",
    9: "settembre",10: "ottobre", 11: "novembre",12: "dicembre",
}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_cookie_dismissed: bool = False
_cookie_dismissed_mcm: bool = False
_WARNING_BEFORE_MS: int = 5_000
# ── Separatori UI ────────────────────────────────────────────
_EQ   = "=" * 72   # separatore titolo sezione
_SEP  = "-" * 72   # separatore generico
_TSEP = "-" * 72   # separatore tabella risultati

# ── Timeout / paginazione ────────────────────────────────────
_EXTEND_BY_MS: int = 10_000   # ms aggiuntivi se si vuole aspettare ancora

# ── Selettori Playwright (Amazon) ────────────────────────────
_PER_PAGE_SELECTOR  = "select[name='s-results-per-page']"

_COOKIE_SELECTORS: list[str] = [
    "input[id='sp-cc-accept']",
    "button[id='sp-cc-accept']",
    "[data-cel-widget='sp-cc'] button",
]

_COOKIE_TEXTS: list[str] = [
    "accetta",
    "accept",
    "acconsento",
    "consent",
]
# ────────────────────────────────────────────────────────────────────────────


from html import unescape
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, quote_plus


# ── Dipendenze opzionali ────────────────────────────────────────────────────

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    requests      = None  # type: ignore[assignment]
    BeautifulSoup = None  # type: ignore[assignment]
    HAS_REQUESTS  = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    HAS_PLAYWRIGHT  = False


# ════════════════════════════════════════════════════════════════════════════
# §1  COSTANTI GLOBALI MANGA
# ════════════════════════════════════════════════════════════════════════════

_TEMP_DIR   = Path(__file__).parent.parent / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)
_PREFS_FILE = _TEMP_DIR / "prefs.json"

WIDTH = 56

# URL base siti manga
from scripts.core.url_manager import get as get_url
BASE_URL_MCM = get_url("manga", "mangacomicsmarket")
BASE_URL_ACK = get_url("anime", "animeclick")
BASE_URL_AMZ = get_url("download", "amazon")
BASE_URL = BASE_URL_MCM  # alias generico

# ── Vinted ──────────────────────────────────────────────────────────────────
BASE_URL_VINTED        = get_url("manga", "vinted")
VINTED_CATALOG_URL     = get_url("manga", "vinted_catalog")
VINTED_SEARCH_INPUT_SEL = '[data-testid="search-text--input"]'
VINTED_EXPORT_FILENAME  = "Manga usati Vinted.txt"

# URL catalogo MCM e selettore campo ricerca
MCM_CATALOG_URL = get_url("manga", "mangacomicsmarket_catalogo")
MCM_SEARCH_INPUT_SEL = 'input[placeholder="Cosa stai cercando?"]'

# Dipartimento Amazon libri + template ricerca
MANGA_AMZ_DEPT  = "stripbooks"
MANGA_AMZ_QUERY = get_url("download", "amazon_search") + MANGA_AMZ_DEPT

# Numero di item attesi per pagina nel catalogo MCM
TARGET_ITEMS_MANUAL: int = 96   # modalità manuale (scroll interattivo)
TARGET_ITEMS:        int = 96   # modalità automatica

# Estensioni immagini copertine manga
IMAGE_EXT: Tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
)

# Estensioni file manga digitali
MANGA_EXT: Tuple[str, ...] = (
    ".cbz", ".cbr", ".pdf", ".epub",
)

# Estensioni da bloccare in Playwright
BLOCK_EXTS: Tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".css", ".woff", ".woff2", ".ttf", ".eot", ".otf",
)

# Selettori CSS banner cookie
COOKIE_SEL: List[str] = [
    "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#cookie-accept",
    ".cc-btn.cc-allow",
    "#onetrust-accept-btn-handler",
    "#sp-cc-accept",
    "input[name='accept']",
    "button[id*='accept']",
    "button[class*='accept']",
    "button[class*='cookie']",
    "a[id*='accept']",
    "#cookieConsentOK",
    ".accept-cookies",
]

# Testi pulsanti cookie da cliccare
COOKIE_TEXTS: List[str] = [
    "continua", "accetta", "accept", "ok", "agree",
    "accetto", "accetta tutto", "accetta i cookie",
    "allow all", "allow cookies", "got it",
]

# Stealth JS anti-bot
_STEALTH_JS: str = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins',   {get: () => [1, 2, 3]});
Object.defineProperty(navigator, 'languages', {get: () => ['it-IT','it','en-US','en']});
window.chrome = {runtime: {}};
"""

_HDR_BROWSER: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ════════════════════════════════════════════════════════════════════════════
# §2  UI / DISPLAY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def clear_screen() -> None:
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def show_header(title: str, breadcrumb: str = "") -> None:
    clear_screen()
    print("=" * WIDTH)
    print(f"  {title}")
    print("=" * WIDTH)
    if breadcrumb:
        print(f"  {breadcrumb}")
    print()


def show_success(msg: str) -> None:
    print(f"  [✓] {msg}")


def show_error(msg: str) -> None:
    print(f"  [✗] {msg}")


def show_info(msg: str) -> None:
    print(f"  [i] {msg}")


def show_warning(msg: str) -> None:
    print(f"  [!] {msg}")


def print_separator(char: str = "-") -> None:
    print(f"  {char * (WIDTH - 2)}")


def print_double_separator() -> None:
    print("=" * WIDTH)


# ════════════════════════════════════════════════════════════════════════════
# §3  INPUT / INTERACTION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def ask_yes_no(question: str) -> bool:
    while True:
        response = input(f"  {question} (s/n): ").strip().lower()
        if response in ("s", "si", "sì", "y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            show_error("Inserisci 's' o 'n'.")


def get_valid_choice(prompt: str, options: List[str]) -> str:
    while True:
        choice = input(f"  {prompt}").strip().lower()
        if choice in options:
            return choice
        show_error(f"Opzioni valide: {', '.join(options)}")


def get_path_input(prompt: str) -> Optional[str]:
    path = input(f"  {prompt}").strip().strip('"').strip("'")
    if not path or path == "0":
        return None
    return path


def wait_enter(msg: str = "Premi INVIO per continuare...") -> None:
    input(f"  {msg}")


# ════════════════════════════════════════════════════════════════════════════
# §4  FILE / PATH FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\|?*]', "", filename).strip()[:200]


def clean_path(path_str: str) -> str:
    return path_str.strip().strip('"').strip("'").strip()


def load_urls_from_file(file_path: str) -> List[str]:
    urls: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith("#"):
                    urls.append(url)
    except FileNotFoundError:
        show_error(f"File non trovato: {file_path}")
    except Exception as e:
        show_error(f"Errore lettura file: {e}")
    return urls


def save_urls_to_file(urls: List[str], file_path: str) -> bool:
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")
        return True
    except Exception as e:
        show_error(f"Errore salvataggio: {e}")
        return False


def get_safe_path(base_path: str, ask_user: bool = True) -> Optional[str]:
    if not Path(base_path).exists():
        try:
            Path(base_path).mkdir(parents=True, exist_ok=True)
            return base_path
        except Exception as e:
            show_error(f"Errore creazione cartella: {e}")
            return None

    if not ask_user:
        return base_path

    show_warning(f"'{Path(base_path).name}' esiste già!")
    if ask_yes_no("Vuoi usarlo comunque?"):
        return base_path

    counter = 1
    while Path(f"{base_path}_{counter}").exists():
        counter += 1
    new_path = f"{base_path}_{counter}"
    show_success(f"Nuovo percorso: {Path(new_path).name}")
    return new_path


def ensure_folder(path: str) -> bool:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def get_collection_path() -> Path:
    return _TEMP_DIR / "lamiacollezione.json"


def save_links(links: List[str], titolo: str, link_dir: str = "") -> Path:
    if not link_dir:
        link_dir = get_link_dir()
    if not link_dir:
        link_dir = str(Path(__file__).parent.parent.parent / "link_estratti")

    dest = Path(link_dir)
    dest.mkdir(parents=True, exist_ok=True)

    nome = (
        sanitize_filename(titolo)
        if titolo
        else f"manga_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    fp  = dest / f"{nome}.txt"
    cnt = 1
    while fp.exists():
        fp  = dest / f"{nome}_{cnt}.txt"
        cnt += 1

    return fp if save_urls_to_file(links, str(fp)) else Path("")


# ════════════════════════════════════════════════════════════════════════════
# §5  UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def sort_links_numerically(links: List[str]) -> List[str]:
    def _key(url: str) -> Tuple:
        nums = re.findall(r'\d+', url)
        if nums:
            return (0, tuple(int(n) for n in nums), url.lower())
        return (1, (999999,), url.lower())
    return sorted(links, key=_key)


def normalize_url(url: str, base_url: str = "") -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if base_url:
        return base_url.rstrip("/") + "/" + url.lstrip("/")
    return url


def animate_progress(
    current: int,
    total: int,
    prefix: str = "Progresso",
    length: int = 40,
) -> None:
    if total <= 0:
        return
    percent = 100 * (current / float(total))
    filled  = int(length * current // total)
    chars   = ["◐", "◓", "◑", "◒"]
    anim    = chars[int(time.time() * 4) % 4]
    bar     = "█" * filled + "░" * (length - filled)
    print(f"\r  {prefix}: |{bar}| {percent:.1f}% {anim}", end="", flush=True)


def print_progress_eta(
    current: int,
    total: int,
    prefix: str = "Progresso",
    start_time: Optional[float] = None,
    bar_length: int = 40,
) -> None:
    if total <= 0:
        return
    pct    = 100.0 * current / total
    filled = int(bar_length * current // total)
    bar    = "█" * filled + "░" * (bar_length - filled)
    w      = len(str(total))

    if start_time is not None and current > 0:
        elapsed = time.time() - start_time
        rem     = elapsed * (total - current) / current
        eta_str = f"ETA {int(rem // 60):02d}:{int(rem % 60):02d}"
    else:
        eta_str = "ETA --:--"

    print(
        f"\r  {prefix}: |{bar}| {pct:5.1f}%"
        f"  [{str(current).rjust(w)}/{total}]"
        f"  {eta_str}   ",
        end="",
        flush=True,
    )


def parse_volume_range(text: str, max_vol: int) -> List[int]:
    text = text.strip().lower()
    if not text or text in ("tutto", "all", "tutti", "*"):
        return list(range(max_vol))

    indices: Set[int] = set()
    for part in text.replace(" ", "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a_s, b_s = part.split("-", 1)
                a = max(0, int(a_s) - 1)
                b = min(max_vol - 1, int(b_s) - 1)
                if a <= b:
                    indices.update(range(a, b + 1))
            except (ValueError, TypeError):
                pass
        elif part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < max_vol:
                indices.add(idx)

    return sorted(indices)


def format_price(value: str) -> str:
    if not value:
        return ""
    v = value.strip()
    v = re.sub(r'[€$£]', "", v).strip()
    if re.match(r'^\d+\.\d{2}$', v):
        v = v.replace(".", ",")
    v = re.sub(r'\s*EUR\s*$', "", v, flags=re.IGNORECASE).strip()
    return f"{v} EUR" if v else ""


def is_manga_file(path: str) -> bool:
    clean = path.lower().split("?")[0].split("#")[0]
    return any(clean.endswith(ext) for ext in MANGA_EXT)


# ════════════════════════════════════════════════════════════════════════════
# §6  INTERRUPT HANDLER
# ════════════════════════════════════════════════════════════════════════════

interrupted: threading.Event = threading.Event()
_original_sigint_handler = None


def setup_interrupt() -> None:
    global _original_sigint_handler
    interrupted.clear()

    def _handler(sig, frame):
        interrupted.set()
        print(
            "\n\n  [!] Interruzione ricevuta — "
            "attendo il completamento del batch corrente...\n",
            flush=True,
        )

    try:
        _original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _handler)
    except (OSError, ValueError):
        _original_sigint_handler = None


def teardown_interrupt() -> None:
    global _original_sigint_handler
    if _original_sigint_handler is None:
        return
    try:
        signal.signal(signal.SIGINT, _original_sigint_handler)
    except (OSError, ValueError):
        pass
    finally:
        _original_sigint_handler = None


# ════════════════════════════════════════════════════════════════════════════
# §7  CONFIGURATION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def load_prefs() -> Dict:
    if not _PREFS_FILE.exists():
        return {}
    try:
        with open(_PREFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(prefs: Dict) -> None:
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_link_dir() -> str:
    return load_prefs().get("default_link_dir", "")


def get_export_dir() -> str:
    return load_prefs().get("default_export_dir", "")


def get_headless_mode() -> bool:
    return load_prefs().get("browser_headless", False)


def get_page_timeout() -> int:
    try:
        return int(load_prefs().get("page_timeout", 15_000))
    except (ValueError, TypeError):
        return 15_000


# ════════════════════════════════════════════════════════════════════════════
# §8  SEARCH FUNCTIONS — MANGA SPECIFIC
# ════════════════════════════════════════════════════════════════════════════

def search_mangacollec(query: str, silent: bool = False) -> List[Dict]:
    if not HAS_PLAYWRIGHT:
        if not silent:
            show_error("'playwright' non installato — ricerca MCM non disponibile")
        return []
    if not silent:
        show_info(f"Ricerca '{query}' su MangaComicsMarket.it...")
    try:
        with MangaPageSession() as sess:
            return sess.fetch_mcm_search(query)
    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca MCM: {e}")
        return []


def search_animeclick_manga(query: str, silent: bool = False) -> List[Dict]:
    if not HAS_REQUESTS:
        if not silent:
            show_error("'requests' non installato — ricerca AnimeClick non disponibile")
        return []

    search_url = f"{BASE_URL_ACK}/search?q={quote_plus(query)}&type=manga"
    try:
        if not silent:
            show_info(f"Ricerca '{query}' su AnimeClick.it (manga)...")
        resp = requests.get(search_url, headers=_HDR_BROWSER, timeout=15)
        resp.raise_for_status()
        soup    = BeautifulSoup(resp.content, "html.parser")
        results: List[Dict] = []

        for item in soup.find_all("div", class_=re.compile(r"item|result|card", re.I)):
            a_tag = item.find("a", href=re.compile(r"/manga/\d+"))
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True) or a_tag.get("title", "")
            if not title:
                continue
            link = a_tag.get("href", "")
            if not link.startswith("http"):
                link = urljoin(BASE_URL_ACK, link)
            results.append({
                "title":  title,
                "link":   link,
                "tipo":   "Manga",
                "anno":   "",
                "generi": [],
            })

        return results

    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca AnimeClick: {e}")
        return []


def search_amazon_manga(
    query: str,
    n_results: int = 20,
    silent: bool = False,
) -> List[Dict]:
    if not HAS_PLAYWRIGHT:
        if not silent:
            show_error("'playwright' non installato — ricerca Amazon non disponibile")
        return []
    if not silent:
        show_info(f"Ricerca '{query}' su Amazon.it...")
    try:
        with MangaPageSession() as sess:
            results = sess.fetch_amazon_search(query)
            return results[:n_results]
    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca Amazon: {e}")
        return []


def search_vinted_manga(query: str, silent: bool = False) -> List[Dict]:
    if not HAS_PLAYWRIGHT:
        if not silent:
            show_error("'playwright' non installato — ricerca Vinted non disponibile")
        return []
    if not silent:
        show_info(f"Ricerca '{query}' su Vinted.it...")
    try:
        with MangaPageSession() as sess:
            return sess.fetch_vinted_search(query)
    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca Vinted: {e}")
        return []


# ════════════════════════════════════════════════════════════════════════════
# §9  BROWSER / PLAYWRIGHT MANGA
# ════════════════════════════════════════════════════════════════════════════

def extract_manga_volumes(soup, base_url: str = BASE_URL_MCM) -> List[Dict]:
    results: List[Dict] = []
    main_div = soup.find("div", class_="main") or soup
    counter  = 1

    for p_tag in main_div.find_all("p"):
        classes = p_tag.get("class") or []
        if "card__name" not in classes or "card__name--big" in classes:
            continue
        a_tag = p_tag.find("a", href=True)
        if not a_tag:
            continue
        titolo = a_tag.get_text(strip=True)
        href   = a_tag.get("href", "")
        link   = (
            href if href.startswith("http")
            else base_url + (href if href.startswith("/") else "/" + href)
        )
        if not titolo or not link:
            continue

        presale_date = ""
        prezzo       = ""
        node = p_tag.parent

        for _ in range(8):
            if node is None:
                break
            if not presale_date:
                pt = node.find("span", class_="presale-tag")
                if pt:
                    lead = pt.find("span", class_="leading-normal")
                    if lead:
                        txt = lead.get_text(strip=True)
                        m   = re.search(r'(\d{1,2}[/\-.]\ d{1,2}[/\-.]\ d{4})', txt)
                        if m:
                            presale_date = m.group(1)
            if not prezzo:
                for span in node.find_all("span"):
                    cls_list = span.get("class") or []
                    if (
                        "card__price" in cls_list
                        and "card__price--big" not in cls_list
                    ):
                        t = span.get_text(strip=True)
                        if t:
                            prezzo = t
                            break
            if presale_date and prezzo:
                break
            node = node.parent

        results.append({
            "numero":    counter,
            "titolo":    titolo,
            "link":      link,
            "prezzo":    prezzo,
            "preordine": presale_date,
        })
        counter += 1

    return results


def extract_amazon_results(soup) -> List[Dict]:
    results: List[Dict] = []
    seen:    Set[str]   = set()

    items = soup.find_all("div", attrs={"data-component-type": "s-search-result"})
    if not items:
        items = soup.find_all("div", class_=re.compile(r"s-result-item"))

    for item in items:
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

        a_tag = h2.find("a", href=True) if h2 else None
        if not a_tag:
            a_tag = item.find("a", class_=re.compile(r"a-link-normal"), href=True)
        href = a_tag.get("href", "") if a_tag else ""
        url  = (
            href if href.startswith("http") else BASE_URL_AMZ + href
        ) if href else ""
        if not url or url in seen:
            continue
        seen.add(url)

        autore = ""
        for row in item.find_all("div", class_="a-row"):
            for span in row.find_all("span", class_=re.compile(r"a-color-secondary")):
                t = span.get_text(" ", strip=True)
                if t and len(t) > 1 and not re.match(r"^[€\d]", t):
                    autore = t[:80]
                    break
            if autore:
                break

        prezzo = ""
        price_offscreen = item.find("span", class_="a-offscreen")
        if price_offscreen:
            prezzo = price_offscreen.get_text(strip=True)
        if not prezzo:
            whole = item.find("span", class_="a-price-whole")
            frac  = item.find("span", class_="a-price-fraction")
            if whole:
                prezzo = "€" + whole.get_text(strip=True)
                if frac:
                    prezzo += "," + frac.get_text(strip=True)

        disponibile = "Sconosciuta"
        if price_offscreen or prezzo:
            disponibile = "Disponibile" if prezzo else "Verifica"
        avail = item.find("span", class_=re.compile(r"a-color-success"))
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


# ── Funzioni di parsing Vinted ────────────────────────────────────────────────

def extract_vinted_results(soup) -> List[Dict]:
    results:   List[Dict] = []
    seen_urls: Set[str]   = set()

    item_divs = soup.find_all(
        "div",
        attrs={"data-testid": re.compile(r"^product-item-id-\d+$")},
    )
    if not item_divs:
        feed = soup.find("div", class_=re.compile(r"feed-grid"))
        if feed:
            item_divs = feed.find_all("div", class_="feed-grid__item-content")

    for item_div in item_divs:
        testid  = item_div.get("data-testid", "")
        m_id    = re.match(r"product-item-id-(\d+)", testid)
        item_id = m_id.group(1) if m_id else ""

        a_tag = item_div.find("a", href=re.compile(r"/items/"))
        if not a_tag and item_div.parent:
            a_tag = item_div.parent.find("a", href=re.compile(r"/items/"))
        if not a_tag:
            a_tag = item_div.find("a", href=True)

        url = ""
        if a_tag:
            href = a_tag.get("href", "")
            url  = href if href.startswith("http") else BASE_URL_VINTED + href

        if not url and item_id:
            node = item_div.parent
            for _ in range(4):
                if node is None:
                    break
                a = node.find("a", href=re.compile(r"/items/"))
                if a:
                    href = a.get("href", "")
                    url  = href if href.startswith("http") else BASE_URL_VINTED + href
                    break
                node = node.parent if hasattr(node, "parent") else None

        if url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        img      = item_div.find("img")
        alt_text = img.get("alt", "") if img else ""

        titolo = prezzo = condizioni = ""
        if alt_text:
            t_m        = re.match(r"^(.+?)(?:,\s*condizioni:|,\s*€\d)", alt_text, re.I)
            titolo     = t_m.group(1).strip() if t_m else alt_text.split(",")[0].strip()
            c_m        = re.search(r"condizioni:\s*([^,€]+)", alt_text, re.I)
            condizioni = c_m.group(1).strip() if c_m else ""
            p_m        = re.search(r"€([\d\.,]+)", alt_text)
            prezzo     = "€" + p_m.group(1) if p_m else ""

        if not titolo:
            titolo = f"Inserzione #{item_id}" if item_id else "Sconosciuto"

        results.append({
            "id":         item_id,
            "titolo":     titolo,
            "prezzo":     prezzo,
            "condizioni": condizioni,
            "url":        url,
        })

    return results


def _vinted_attr(soup, testid: str) -> str:
    div = soup.find("div", attrs={"data-testid": testid})
    if not div:
        return ""
    vals   = div.find_all("div", class_=re.compile(r"details-list__item-value"))
    target = vals[1] if len(vals) >= 2 else (vals[0] if vals else div)
    bold   = target.find("span", class_=lambda c: bool(c and "web_ui__Text__bold" in c))
    node   = bold or target
    text   = ""
    for child in node.children:
        if hasattr(child, "name") and child.name == "button":
            break
        text += child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
    return text.strip() or node.get_text(strip=True)


def extract_vinted_item_details(soup, url: str = "") -> Dict:
    details: Dict = {}

    summary = soup.find(attrs={"data-testid": "item-page-summary-plugin"})
    h1      = (summary.find("h1") if summary else None) or soup.find("h1")
    if h1:
        details["titolo"] = h1.get_text(strip=True)

    for testid, key in [
        ("item-attributes-status",        "condizioni"),
        ("item-attributes-language_book", "lingua"),
        ("item-attributes-author",        "autore"),
        ("item-attributes-upload_date",   "caricato"),
    ]:
        val = _vinted_attr(soup, testid)
        if val:
            details[key] = val

    price_el = soup.find(attrs={"data-testid": "item-price"})
    if price_el:
        p_tag = price_el.find("p")
        if p_tag:
            details["prezzo"] = p_tag.get_text(strip=True).replace("\xa0", " ")

    desc_el = soup.find(attrs={"itemprop": "description"})
    if desc_el:
        details["descrizione"] = desc_el.get_text(" ", strip=True)

    if url:
        details["url"] = url
    return details


def extract_animeclick_manga_results(soup) -> List[Dict]:
    """
    Estrae risultati ricerca manga da AnimeClick.
    Struttura: div#row-elenco-opere > div.thumbnail-opera-info-extra > a href="/manga/ID/titolo"
    FIX v1.3: Parsing robusto per trovare titoli come "Maison Ikkoku"
    """
    results: List[Dict] = []
    seen: Set[str] = set()
    
    row_elenco = soup.find("div", id="row-elenco-opere")
    if not row_elenco:
        return []
    
    for thumb in row_elenco.find_all("div", class_="thumbnail-opera-info-extra"):
        link_elem = thumb.find("a", href=re.compile(r"/manga/[0-9]+"))
        if not link_elem:
            continue
        
        href = link_elem.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL_ACK + (href if href.startswith("/") else "/" + href)
        
        title_elem = thumb.find("h5")
        if not title_elem:
            title_elem = link_elem
        titolo = title_elem.get_text(strip=True) or link_elem.get_text(strip=True)
        
        if not titolo or href in seen:
            continue
        
        seen.add(href)
        
        anno = ""
        info_extra = thumb.find("div", class_="info-extra")
        if info_extra:
            pull_right = info_extra.find("div", class_="pull-right")
            if pull_right:
                anno = pull_right.get_text(strip=True)
        
        voto = ""
        generi = []
        data_content = thumb.get("data-content", "")
        if data_content:
            decoded = unescape(data_content)
            soup_content = BeautifulSoup(decoded, "html.parser")
            generi_div = soup_content.find("div", class_="generi")
            if generi_div:
                generi = [li.get_text(strip=True) for li in generi_div.find_all("li")]
        
        results.append({
            "title": titolo,
            "titolo": titolo,
            "link": href,
            "url": href,
            "tipo": "Manga",
            "anno": anno,
            "voto": voto,
            "generi": generi,
        })
    
    return results


class MangaPageSession:
    """
    Sessione Playwright ottimizzata per siti manga (MCM, AnimeClick, Amazon, Vinted).
    """

    def __init__(self) -> None:
        self._pw               = None
        self._browser          = None
        self._ctx              = None
        self._page             = None
        self._cookie_dismissed = False

    def __enter__(self) -> "MangaPageSession":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def open(self) -> None:
        if not HAS_PLAYWRIGHT:
            raise RuntimeError(
                "Playwright non installato. "
                "Esegui: pip install playwright && playwright install chromium"
            )
        headless      = get_headless_mode()
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
            ],
        )
        self._ctx = self._browser.new_context(
            locale="it-IT",
            user_agent=_HDR_BROWSER["User-Agent"],
            viewport={"width": 1280, "height": 800},
        )
        self._ctx.add_init_script(_STEALTH_JS)
        for ext in BLOCK_EXTS:
            try:
                self._ctx.route(
                    f"**/*{ext}", lambda route, _e=ext: route.abort()
                )
            except Exception:
                pass
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(get_page_timeout())

    def close(self) -> None:
        for obj, method in [(self._browser, "close"), (self._pw, "stop")]:
            if obj:
                try:
                    getattr(obj, method)()
                except Exception:
                    pass
        self._browser = self._pw = self._ctx = self._page = None

    def dismiss_cookies(self, page=None) -> None:
        target = page or self._page
        if not target:
            return
        if self._cookie_dismissed and page is None:
            return

        js = """([selectors, texts]) => {
            for (const s of selectors) {
                try {
                    const e = document.querySelector(s);
                    if (e && e.offsetParent !== null) { e.click(); return true; }
                } catch (_) {}
            }
            const all = document.querySelectorAll(
                'button,a,input[type=button],input[type=submit],[role=button]'
            );
            for (const e of all) {
                const t=(e.innerText||e.value||e.textContent||"").trim().toLowerCase();
                if (texts.some(k => t.includes(k)) && e.offsetParent !== null) {
                    e.click();
                    return true;
                }
            }
            return false;
        }"""
        try:
            result = target.evaluate(js, [COOKIE_SEL, COOKIE_TEXTS])
            if result:
                if page is None:
                    self._cookie_dismissed = True
                target.wait_for_timeout(400)
        except Exception:
            pass

    def fetch_animeclick_manga_search(self, query: str) -> List[Dict]:
        """
        Ricerca manga su AnimeClick usando Playwright.
        URL: https://www.animeclick.it/ricerca/manga
        Campo ricerca: #search_manga_title
        Risultati: div#row-elenco-opere > div.thumbnail-opera-info-extra
        
        FIX v1.3 per la_mia_collezione.py: parsing robusto che trova "Maison Ikkoku"
        """
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        
        try:
            search_url = "https://www.animeclick.it/ricerca/manga"
            self._page.goto(search_url, wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(800)
            
            search_field = "#search_manga_title"
            self._page.wait_for_selector(search_field, timeout=10_000)
            self._page.click(search_field)
            self._page.wait_for_timeout(200)
            self._page.fill(search_field, "")
            self._page.wait_for_timeout(150)
            self._page.fill(search_field, query)
            self._page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                search_field,
            )
            self._page.wait_for_timeout(400)
            self._page.press(search_field, "Enter")
            
            for sel in ["#row-elenco-opere", "div.thumbnail-opera-info-extra"]:
                try:
                    self._page.wait_for_selector(sel, timeout=12_000)
                    self._page.wait_for_timeout(800)
                    break
                except Exception:
                    continue
            
            self.dismiss_cookies()
            
            prev_count = 0
            for _ in range(3):
                self._page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(600)
                count = self._page.evaluate(
                    "() => document.querySelectorAll('div.thumbnail-opera-info-extra').length"
                )
                if count == prev_count:
                    break
                prev_count = count
            
            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_animeclick_manga_results(soup)
        
        except Exception as exc:
            show_error(f"Errore fetch_animeclick_manga_search: {exc}")
        
        return []

    def fetch_animeclick_manga_search_staff(self, staff: str) -> List[Dict]:
        """
        Ricerca manga su AnimeClick per STAFF/AUTORE usando Playwright.
        URL: https://www.animeclick.it/ricerca/manga
        Campo compilato: #search_manga_staff  (titolo lasciato vuoto)
        NUOVO v1.4 — richiesto da la_mia_collezione.py v2.4
        """
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        try:
            self._page.goto("https://www.animeclick.it/ricerca/manga",
                            wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(800)

            # Assicura che il campo titolo sia vuoto
            try:
                self._page.wait_for_selector("#search_manga_title", timeout=8_000)
                self._page.fill("#search_manga_title", "")
            except Exception:
                pass

            # Compila il campo staff/autore
            self._page.wait_for_selector("#search_manga_staff", timeout=10_000)
            self._page.click("#search_manga_staff")
            self._page.wait_for_timeout(200)
            self._page.fill("#search_manga_staff", "")
            self._page.wait_for_timeout(150)
            self._page.fill("#search_manga_staff", staff)
            self._page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                "#search_manga_staff",
            )
            self._page.wait_for_timeout(400)
            self._page.press("#search_manga_staff", "Enter")

            for sel in ["#row-elenco-opere", "div.thumbnail-opera-info-extra"]:
                try:
                    self._page.wait_for_selector(sel, timeout=12_000)
                    self._page.wait_for_timeout(800)
                    break
                except Exception:
                    continue

            self.dismiss_cookies()
            prev_count = 0
            for _ in range(3):
                self._page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(600)
                count = self._page.evaluate(
                    "() => document.querySelectorAll('div.thumbnail-opera-info-extra').length"
                )
                if count == prev_count:
                    break
                prev_count = count

            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_animeclick_manga_results(soup)
        except Exception as exc:
            show_error(f"Errore fetch_animeclick_manga_search_staff: {exc}")
        return []

    def fetch_animeclick_manga_search_combined(self, title: str, staff: str) -> List[Dict]:
        """
        Ricerca manga su AnimeClick per TITOLO + STAFF/AUTORE usando Playwright.
        URL: https://www.animeclick.it/ricerca/manga
        Campi compilati: #search_manga_title  e  #search_manga_staff
        NUOVO v1.4 — richiesto da la_mia_collezione.py v2.4
        """
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        try:
            self._page.goto("https://www.animeclick.it/ricerca/manga",
                            wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(800)

            # Compila il campo titolo
            self._page.wait_for_selector("#search_manga_title", timeout=10_000)
            self._page.click("#search_manga_title")
            self._page.wait_for_timeout(200)
            self._page.fill("#search_manga_title", "")
            self._page.wait_for_timeout(150)
            self._page.fill("#search_manga_title", title)
            self._page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                "#search_manga_title",
            )
            self._page.wait_for_timeout(300)

            # Compila il campo staff/autore
            self._page.wait_for_selector("#search_manga_staff", timeout=8_000)
            self._page.click("#search_manga_staff")
            self._page.wait_for_timeout(200)
            self._page.fill("#search_manga_staff", "")
            self._page.wait_for_timeout(150)
            self._page.fill("#search_manga_staff", staff)
            self._page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                "#search_manga_staff",
            )
            self._page.wait_for_timeout(400)
            self._page.press("#search_manga_staff", "Enter")

            for sel in ["#row-elenco-opere", "div.thumbnail-opera-info-extra"]:
                try:
                    self._page.wait_for_selector(sel, timeout=12_000)
                    self._page.wait_for_timeout(800)
                    break
                except Exception:
                    continue

            self.dismiss_cookies()
            prev_count = 0
            for _ in range(3):
                self._page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(600)
                count = self._page.evaluate(
                    "() => document.querySelectorAll('div.thumbnail-opera-info-extra').length"
                )
                if count == prev_count:
                    break
                prev_count = count

            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_animeclick_manga_results(soup)
        except Exception as exc:
            show_error(f"Errore fetch_animeclick_manga_search_combined: {exc}")
        return []

    def fetch_mcm_search(self, query: str) -> List[Dict]:
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        try:
            self._page.goto(MCM_CATALOG_URL, wait_until="domcontentloaded")
            self.dismiss_cookies()
            for sel in ["p.card__name", ".card__name"]:
                try:
                    self._page.wait_for_selector(sel, timeout=8_000)
                    break
                except Exception:
                    continue
            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_manga_volumes(soup, BASE_URL_MCM)
        except Exception as exc:
            show_error(f"Errore fetch_mcm_search: {exc}")
        return []

    def fetch_amazon_search(self, query: str) -> List[Dict]:
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        encoded = quote_plus(query + " manga")
        url     = MANGA_AMZ_QUERY.format(query=encoded)

        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.dismiss_cookies()
            for sel in ["[data-component-type='s-search-result']", ".s-result-item"]:
                try:
                    self._page.wait_for_selector(sel, timeout=8_000)
                    break
                except Exception:
                    continue
            self.dismiss_cookies()
            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_amazon_results(soup)
        except Exception as exc:
            show_error(f"Errore fetch_amazon_search: {exc}")
        return []

    def fetch_vinted_search(self, query: str) -> List[Dict]:
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        try:
            self._page.goto(VINTED_CATALOG_URL, wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(1_000)
            for sel in [VINTED_SEARCH_INPUT_SEL, "input#search_text"]:
                try:
                    self._page.wait_for_selector(sel, timeout=8_000)
                    self._page.click(sel)
                    self._page.fill(sel, query)
                    self._page.press(sel, "Enter")
                    break
                except Exception:
                    continue
            for res_sel in ["div.feed-grid", "[data-testid^='product-item-id-']"]:
                try:
                    self._page.wait_for_selector(res_sel, timeout=12_000)
                    break
                except Exception:
                    continue
            self.dismiss_cookies()
            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_vinted_results(soup)
        except Exception as exc:
            show_error(f"Errore fetch_vinted_search: {exc}")
        return []

    def fetch_vinted_item(self, url: str) -> Dict:
        if not self._page:
            raise RuntimeError("MangaPageSession non aperta. Chiamare .open() prima.")
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(800)
            for sel in ["[data-testid='item-page-summary-plugin']", "h1"]:
                try:
                    self._page.wait_for_selector(sel, timeout=8_000)
                    break
                except Exception:
                    continue
            self._page.wait_for_timeout(400)
            html = self._page.content()
            if HAS_REQUESTS:
                soup = BeautifulSoup(html, "html.parser")
                return extract_vinted_item_details(soup, url)
        except Exception as exc:
            show_error(f"Errore fetch_vinted_item: {exc}")
        return {}


# ════════════════════════════════════════════════════════════════════════════
# §10 COLLECTION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def load_collection(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path) if path else get_collection_path()
    if not target.exists():
        return []
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        show_error(f"Errore lettura collezione: {e}")
        return []


def save_collection(
    collection: List[Dict],
    path: Optional[Path] = None,
) -> bool:
    target = Path(path) if path else get_collection_path()
    try:
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        show_error(f"Errore salvataggio collezione: {e}")
        return False


def export_collection_csv(
    collection: List[Dict],
    export_path: str,
) -> bool:
    if not collection:
        show_warning("Collezione vuota — nessun CSV creato.")
        return False

    fieldnames = ["titolo", "edizione", "variant", "stato_italia", "volumi"]
    try:
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in collection:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
        show_success(f"CSV esportato: {export_path}")
        return True
    except Exception as e:
        show_error(f"Errore export CSV: {e}")
        return False


def export_collection_txt(
    collection: List[Dict],
    export_path: str,
    separate: bool = False,
) -> bool:
    if not collection:
        show_warning("Collezione vuota — nessun TXT creato.")
        return False

    now        = datetime.now()
    sorted_col = sorted(
        collection, key=lambda r: r.get("titolo", "").lower()
    )

    lines: List[str] = [
        "=" * WIDTH,
        f"  La mia collezione manga al {now.day:02d}/{now.month:02d}/{now.year}",
        f"  Totale: {len(collection)} titoli",
        "=" * WIDTH,
    ]

    def _append_rows(rows: List[Dict]) -> None:
        for i, row in enumerate(rows, 1):
            t   = row.get("titolo", "")
            e   = row.get("edizione", "")
            v   = row.get("variant", "")
            s   = row.get("stato_italia", "")
            vol = row.get("volumi", "")
            lines.append(f"  {i:>3}.  {t}")
            parts = []
            if e:   parts.append(f"Ed.: {e}")
            if v:   parts.append(f"Variant: {v}")
            if s:   parts.append(f"Stato: {s}")
            if vol: parts.append(f"Vol.: {vol}")
            if parts:
                lines.append("        " + "  |  ".join(parts))

    if not separate:
        lines.append("")
        _append_rows(sorted_col)
        lines += ["", "=" * WIDTH]
    else:
        in_corso   = [r for r in sorted_col if "complet" not in r.get("stato_italia", "").lower()]
        completati = [r for r in sorted_col if "complet" in r.get("stato_italia", "").lower()]
        for name, rows in [("IN CORSO", in_corso), ("COMPLETATI", completati)]:
            lines += ["", f"  {name}  ({len(rows)} titoli)", ""]
            if rows:
                _append_rows(rows)
            else:
                lines.append("        (nessun titolo)")
        lines += ["", "=" * WIDTH]

    try:
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        show_success(f"TXT esportato: {export_path}")
        return True
    except Exception as e:
        show_error(f"Errore export TXT: {e}")
        return False


def save_vinted_export(items: List[Dict], export_dir: str) -> bool:
    try:
        Path(export_dir).mkdir(parents=True, exist_ok=True)
        fpath = Path(export_dir) / VINTED_EXPORT_FILENAME
        lines: List[str] = []
        for it in items:
            titolo = it.get("titolo", "").strip()
            url    = it.get("url",    "").strip()
            if titolo and url:
                lines.append(f"{titolo} - {url}")
            elif titolo:
                lines.append(titolo)
        if not lines:
            show_warning("Nessun dato da salvare.")
            return False
        mode = "a" if fpath.exists() else "w"
        with open(fpath, mode, encoding="utf-8") as fp:
            if mode == "a":
                fp.write("\n")
            fp.write("\n".join(lines) + "\n")
        return True
    except Exception as exc:
        show_error(f"Errore save_vinted_export: {exc}")
        return False


# ════════════════════════════════════════════════════════════════════════════
# §11  EXPORT — PUBLIC API  (67 simboli)
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    # §2 — UI / Display (8)
    "clear_screen", "show_header", "show_success", "show_error",
    "show_info", "show_warning", "print_separator", "print_double_separator",
    # §3 — Input (4)
    "ask_yes_no", "get_valid_choice", "get_path_input", "wait_enter",
    # §4 — File / Path (8)
    "sanitize_filename", "clean_path", "load_urls_from_file", "save_urls_to_file",
    "get_safe_path", "ensure_folder", "get_collection_path", "save_links",
    # §5 — Utility (7)
    "sort_links_numerically", "normalize_url", "animate_progress",
    "print_progress_eta", "parse_volume_range", "format_price", "is_manga_file",
    # §6 — Interrupt (3)
    "interrupted", "setup_interrupt", "teardown_interrupt",
    # §7 — Config (6)
    "load_prefs", "save_prefs", "get_link_dir", "get_export_dir",
    "get_headless_mode", "get_page_timeout",
    # §8 — Search (4)
    "search_mangacollec", "search_animeclick_manga", "search_amazon_manga",
    "search_vinted_manga",
    # §9 — Browser / Playwright (6)
    "MangaPageSession", "extract_manga_volumes", "extract_amazon_results",
    "extract_vinted_results", "extract_vinted_item_details",
    "extract_animeclick_manga_results",  # ← NUOVO v1.3
    # §10 — Collection (4)
    "load_collection", "save_collection", "export_collection_csv", "export_collection_txt",
    # §10.5 — Vinted export (1)
    "save_vinted_export",
    # Costanti MCM/ACK/AMZ (4)
    "WIDTH", "BASE_URL_MCM", "BASE_URL_ACK", "BASE_URL_AMZ",
    # Costanti Vinted (4)
    "BASE_URL_VINTED", "VINTED_CATALOG_URL",
    "VINTED_SEARCH_INPUT_SEL", "VINTED_EXPORT_FILENAME",
    # Altre costanti (5)
    "IMAGE_EXT", "MANGA_EXT", "BLOCK_EXTS", "COOKIE_SEL", "COOKIE_TEXTS",
    # Flags (2)
    "HAS_REQUESTS", "HAS_PLAYWRIGHT",
]


if __name__ == "__main__":
    print("=" * 56)
    print("  MANGA ENGINE v1.3 — FIX v2.3 per la_mia_collezione.py")
    print("=" * 56)
    print()
    print(f"  Esportazioni __all__  : {len(__all__)}")
    print(f"  HAS_REQUESTS          : {HAS_REQUESTS}")
    print(f"  HAS_PLAYWRIGHT        : {HAS_PLAYWRIGHT}")
    print()
    print("  Metodi aggiunti: fetch_animeclick_manga_search(), fetch_animeclick_manga_search_staff(), fetch_animeclick_manga_search_combined()")
    print("  Funzione helper: extract_animeclick_manga_results()")
    print()



# ══════════════════════════════════════════════════════════════════════
# FUNZIONI CONDIVISE — centralizzate dai moduli satellite
#   Eliminate duplicazioni in: ricerca_mcm.py, ultime_uscite_MCM.py,
#   acquisti_manga_amazon.py, ricerca_vinted.py
# ══════════════════════════════════════════════════════════════════════

def _normalise(href: str) -> str:
    if not href:
        return ""
    return href if href.startswith("http") else BASE_URL + (href if href.startswith("/") else "/" + href)

_engine_get_export_dir = get_export_dir  # alias interno per retrocompatibilità
def _get_export_dir() -> Optional[str]:
    """
    Restituisce il percorso export Vinted, creando la cartella se necessario.

    Priorità:
      1. manga_engine.get_export_dir()    (se disponibile)
      2. prefs.json["export_dir"]         (lettura diretta — fallback robusto)
      3. Input utente                     (ultimo resort)

    Percorso finale: export_dir / Vinted /
    """
    # Tentativo 1 — funzione engine
    base = ""
    if _engine_get_export_dir is not None:
        try:
            base = _engine_get_export_dir() or ""
        except Exception:
            base = ""

    # Tentativo 2 — prefs.json diretto
    if not base:
        base = _read_prefs_export_dir()

    # Tentativo 3 — input utente
    if not base:
        print('\n  Chiave "export_dir" non trovata in prefs.json.')
        base = input("  Inserisci percorso base alternativo (invio = annulla): ").strip()
        if not base:
            print("  Operazione annullata.")
            return None

    folder = str(Path(base) / VINTED_EXPORT_FOLDER)
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    except OSError as exc:
        show_error("Impossibile creare cartella export: " + str(exc))
        return None


# ── Display ───────────────────────────────────────────────────────────────────


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


def _print_item_detail(detail: Dict) -> None:
    print()
    print(_EQ)
    titolo = detail.get("titolo", "N/D")
    if len(titolo) > WIDTH - 4:
        titolo = titolo[:WIDTH - 7] + "..."
    print("  " + titolo)
    print(_EQ)
    for label, key in [
        ("Condizioni", "condizioni"),
        ("Lingua",     "lingua"),
        ("Autore",     "autore"),
        ("Caricato",   "caricato"),
        ("Prezzo",     "prezzo"),
    ]:
        val = detail.get(key, "")
        if val:
            print("  {:<16}  {}".format(label, val))
    descrizione = detail.get("descrizione", "")
    if descrizione:
        print()
        print("  Descrizione:")
        max_w = WIDTH - 6
        words = descrizione.split()
        line  = "    "
        for word in words:
            if len(line) + len(word) + 1 > max_w:
                print(line.rstrip())
                line = "    " + word
            else:
                line = line + word if line == "    " else line + " " + word
        if line.strip():
            print(line.rstrip())
    url = detail.get("url", "")
    if url:
        print()
        print("  URL inserzione:")
        print("  " + url)
    print(_EQ)


# ── Selezione multipla ────────────────────────────────────────────────────────


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


def _date_str() -> str:
    n = datetime.now()
    return f"{n.day:02d} {_MESI_IT[n.month]} {n.year}"


def _extract_preorder_date(span_elem) -> str:
    if not span_elem: return ""
    m = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})', span_elem.get_text(strip=True))
    return m.group(1) if m else ""


def _format_title_with_preorder(item: dict) -> str:
    t = item["titolo"]
    return f"{t} (preord. {item['preordine']})" if item.get("preordine") else t


# -- Cartella acquisti --------------------------------------------------------


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
        # FIX v5.8: skip wait cookie in AUTO — il banner è già sparito dopo il click
        if not _cookie_dismissed_mcm: page.wait_for_timeout(200)
        return
    for sel in COOKIE_SEL:
        try:
            page.click(sel, timeout=600)
            _cookie_dismissed_mcm = True
            # FIX v5.8: skip wait cookie in AUTO — il banner è già sparito dopo il click
            if not _cookie_dismissed_mcm: page.wait_for_timeout(200)
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
            _stall_limit = 1_200 if not interactive else 3_000  # FIX v5.9: usa 'interactive' (già disponibile)
            if stall_ms >= _stall_limit: break
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


def _wait_for_catalog_items(page, auto_timeout_ms: int | None = None) -> None:
    # FIX v5.7: timeout ridotto in AUTO (4 s invece di 12 s)
    sel_timeout = auto_timeout_ms if auto_timeout_ms is not None else 12_000
    wait_after  = 800 if auto_timeout_ms is None else 300
    for sel in ["p.card__name", ".card__name", "[class*='card__name']"]:
        try: page.wait_for_selector(sel, timeout=sel_timeout); page.wait_for_timeout(wait_after); return
        except Exception: continue
    page.wait_for_timeout(3_000)


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
    
def _truncate_title_smart(text: str, max_title_len: int = 50) -> str:
    """Tronca il titolo a max_title_len caratteri preservando le parole."""
    if len(text) <= max_title_len:
        return text
    truncated = text[:max_title_len - 1].rsplit(" ", 1)[0]
    return truncated + "…"


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
