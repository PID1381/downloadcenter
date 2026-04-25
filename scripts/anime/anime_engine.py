#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANIME ENGINE v2.0 - CORE ENGINE CENTRALIZZATO
PATCH v2.0.1: BASE_URL/SEARCH_URL letti da url_mgr centralizzato
Download Center - scripts/anime/anime_engine.py

NOVITA v2.0 rispetto a v1.5:
  §1  Costanti globali espanse:
        VIDEO_EXT, BLOCK_EXTS, COOKIE_SEL, COOKIE_TEXTS, HAS_PLAYWRIGHT
  §5  Utility aggiunte:
        is_video(), parse_episode_selection(), print_progress_eta(), save_links()
  §6  Interrupt handler:
        interrupted (threading.Event), setup_interrupt(), teardown_interrupt()
  §8  Browser / Playwright (migrato da estrai_link_anime):
        PageSession, extract_video_links(), extract_from_js(), extract_episode_links()

ESPORTAZIONI: 48 simboli pubblici (vedi __all__)

FUNZIONI CENTRALIZZATE:
  UI/Display   : clear_screen, show_header, show_success, show_error,
                 show_info, show_warning, print_separator, print_double_separator
  Input        : ask_yes_no, get_valid_choice, get_path_input, wait_enter
  File/Path    : sanitize_filename, clean_path, load_urls_from_file,
                 save_urls_to_file, get_safe_path, ensure_folder, save_links
  Utility      : sort_links_numerically, normalize_url, animate_progress,
                 is_video, parse_episode_selection, print_progress_eta
  Config       : load_prefs, save_prefs, get_link_dir, get_headless_mode
  Search       : search_animeworld, search_animeunity
  Interrupt    : interrupted, setup_interrupt, teardown_interrupt
  Browser      : PageSession, extract_video_links, extract_from_js,
                 extract_episode_links
  Classes      : VideoExtractor
  Costanti     : WIDTH, BASE_URL, SEARCH_URL, VIDEO_EXT, BLOCK_EXTS,
                 COOKIE_SEL, COOKIE_TEXTS
  Flags        : HAS_REQUESTS, HAS_PLAYWRIGHT

DESIGN:
  - Zero dipendenze da core.config (fallback autonomo su prefs.json)
  - Importazioni opzionali con try/except (requests, bs4, playwright)
  - Compatibile con: watchlist, estrai_link_anime, ricerca_scheda_anime,
                     scan_local_series, handlers
"""
from __future__ import annotations

import os
import re
import json
import time
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse


# ── Dipendenze opzionali ────────────────────────────────────────────────────

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
    HAS_BS4      = True
except ImportError:
    requests      = None  # type: ignore[assignment]
    BeautifulSoup = None  # type: ignore[assignment]
    HAS_REQUESTS  = False
    HAS_BS4       = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    HAS_PLAYWRIGHT  = False

# ── URL Manager centralizzato (opzionale — fallback su costanti locali) ──
try:
    from core.url_manager import url_mgr as _url_mgr
    _HAS_URL_MGR = True
except ImportError:
    try:
        from scripts.core.url_manager import url_mgr as _url_mgr
        _HAS_URL_MGR = True
    except ImportError:
        _url_mgr     = None  # type: ignore[assignment]
        _HAS_URL_MGR = False


# ════════════════════════════════════════════════════════════════════════════
# §1  COSTANTI GLOBALI
# ════════════════════════════════════════════════════════════════════════════

_TEMP_DIR   = Path(__file__).parent.parent / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)
_PREFS_FILE = _TEMP_DIR / "prefs.json"

WIDTH = 56

# BASE_URL / SEARCH_URL: letti da url_mgr se disponibile, altrimenti fallback
_BASE_URL_FALLBACK   = "https://www.animeworld.ac"
_SEARCH_URL_FALLBACK = _BASE_URL_FALLBACK + "/search"


def _get_base_url() -> str:
    """Ritorna BASE_URL da url_mgr centralizzato, o fallback hardcodato."""
    if _HAS_URL_MGR:
        try:
            url = _url_mgr.get("anime", "animeworld")
            if url:
                return url.rstrip("/")
        except Exception:
            pass
    return _BASE_URL_FALLBACK


def _get_search_url() -> str:
    """Ritorna SEARCH_URL da url_mgr centralizzato, o fallback hardcodato."""
    if _HAS_URL_MGR:
        try:
            url = _url_mgr.get("anime", "animeworld_search")
            if url:
                return url
        except Exception:
            pass
    return _get_base_url() + "/search"


# Costanti pubbliche — retrocompatibilità con moduli importatori
# Valutate UNA VOLTA all'import. Per URL sempre aggiornati
# usare _get_base_url() / _get_search_url().
BASE_URL   = _get_base_url()
SEARCH_URL = _get_search_url()

# Estensioni file video riconosciute (is_video, VideoExtractor, PageSession)
VIDEO_EXT: Tuple[str, ...] = (
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts",
    ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp", ".ogv", ".m3u8",
    ".vob", ".f4v", ".asf", ".rm", ".rmvb",
)

# Estensioni da bloccare in Playwright (velocizza caricamento pagine)
BLOCK_EXTS: Tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".css", ".woff", ".woff2", ".ttf", ".eot", ".otf",
)

# Selettori CSS banner cookie AnimeWorld / AnimeClick
COOKIE_SEL: List[str] = [
    "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#cookie-accept",
    ".cc-btn.cc-allow",
    "button[id*='accept']",
    "button[class*='accept']",
    "button[class*='cookie']",
    "a[id*='accept']",
    "#cookieConsentOK",
    ".cookieConsent__Button",
]

# Testi pulsanti cookie da cliccare (match case-insensitive, includes)
COOKIE_TEXTS: List[str] = [
    "continua", "accetta", "accept", "ok", "agree",
    "accetto", "allow all", "allow cookies", "got it",
]


# ════════════════════════════════════════════════════════════════════════════
# §2  UI / DISPLAY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def clear_screen() -> None:
    """Pulisce lo schermo (cross-platform)."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def show_header(title: str, breadcrumb: str = "") -> None:
    """Visualizza header formattato con titolo e breadcrumb opzionale."""
    clear_screen()
    print("=" * WIDTH)
    print(f"  {title}")
    print("=" * WIDTH)
    if breadcrumb:
        print(f"  {breadcrumb}")
    print()


def show_success(msg: str) -> None:
    """Messaggio di successo [✓]."""
    print(f"  [\u2713] {msg}")


def show_error(msg: str) -> None:
    """Messaggio di errore [✗]."""
    print(f"  [\u2717] {msg}")


def show_info(msg: str) -> None:
    """Messaggio informativo [i]."""
    print(f"  [i] {msg}")


def show_warning(msg: str) -> None:
    """Messaggio di avvertimento [!]."""
    print(f"  [!] {msg}")


def print_separator(char: str = "-") -> None:
    """Stampa separatore orizzontale."""
    print(f"  {char * (WIDTH - 2)}")


def print_double_separator() -> None:
    """Stampa doppio separatore (=)."""
    print("=" * WIDTH)


# ════════════════════════════════════════════════════════════════════════════
# §3  INPUT / INTERACTION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def ask_yes_no(question: str) -> bool:
    """Chiede risposta si/no. Ritorna True per si."""
    while True:
        response = input(f"  {question} (s/n): ").strip().lower()
        if response in ("s", "si", "si\u0300", "y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            show_error("Inserisci 's' o 'n'.")


def get_valid_choice(prompt: str, options: List[str]) -> str:
    """Chiede una scelta valida dalla lista options. Loop fino a risposta corretta."""
    while True:
        choice = input(f"  {prompt}").strip().lower()
        if choice in options:
            return choice
        show_error(f"Opzioni valide: {', '.join(options)}")


def get_path_input(prompt: str) -> Optional[str]:
    """Chiede percorso file/cartella. Ritorna None se vuoto o '0'."""
    path = input(f"  {prompt}").strip().strip('"').strip("'")
    if not path or path == "0":
        return None
    return path


def wait_enter(msg: str = "Premi INVIO per continuare...") -> None:
    """Attende pressione INVIO."""
    input(f"  {msg}")


# ════════════════════════════════════════════════════════════════════════════
# §4  FILE / PATH FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def sanitize_filename(filename: str) -> str:
    """Sanifica nome file rimuovendo caratteri non validi per il filesystem."""
    return re.sub(r'[<>:"/\\|?*]', "", filename).strip()[:200]


def clean_path(path_str: str) -> str:
    """Pulisce stringa percorso (rimuove virgolette, spazi ridondanti)."""
    return path_str.strip().strip('"').strip("'").strip()


def load_urls_from_file(file_path: str) -> List[str]:
    """Carica lista URL da file .txt (una per riga, ignora righe con #)."""
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
    """Salva lista URL su file .txt (una per riga). Ritorna True se OK."""
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
    """
    Ottiene percorso sicuro. Se non esiste lo crea. Se esiste, chiede
    conferma o genera nome alternativo con suffisso numerico (_1, _2, ...).
    """
    if not Path(base_path).exists():
        try:
            Path(base_path).mkdir(parents=True, exist_ok=True)
            return base_path
        except Exception as e:
            show_error(f"Errore creazione cartella: {e}")
            return None

    if not ask_user:
        return base_path

    show_warning(f"'{Path(base_path).name}' esiste gia!")
    if ask_yes_no("Vuoi usarlo comunque?"):
        return base_path

    counter = 1
    while Path(f"{base_path}_{counter}").exists():
        counter += 1
    new_path = f"{base_path}_{counter}"
    show_success(f"Nuovo percorso: {Path(new_path).name}")
    return new_path


def ensure_folder(path: str) -> bool:
    """Assicura che una cartella esista (crea se necessario). Ritorna True se OK."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════════════
# §5  UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def sort_links_numerically(links: List[str]) -> List[str]:
    """
    Ordina lista URL in modo numerico (per numero episodio).
    URL con numeri: ordinati per sequenza numerica.
    URL senza numeri: in fondo, in ordine alfabetico.
    """
    def _key(url: str) -> Tuple:
        nums = re.findall(r'\d+', url)
        if nums:
            return (0, tuple(int(n) for n in nums), url.lower())
        return (1, (999999,), url.lower())

    return sorted(links, key=_key)


def normalize_url(url: str, base_url: str = "") -> str:
    """Normalizza URL relativo in assoluto usando base_url."""
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
    """
    Barra di progresso con spinner animato.
    Per operazioni con ETA preciso usare print_progress_eta().
    """
    if total <= 0:
        return
    percent = 100 * (current / float(total))
    filled  = int(length * current // total)
    chars   = ["\u25d0", "\u25d3", "\u25d1", "\u25d2"]
    anim    = chars[int(time.time() * 4) % 4]
    bar     = "\u2588" * filled + "\u2591" * (length - filled)
    print(f"\r  {prefix}: |{bar}| {percent:.1f}% {anim}", end="", flush=True)


def is_video(url: str) -> bool:
    """
    Ritorna True se l'URL termina con estensione video in VIDEO_EXT.
    Ignora query string (?...) e frammenti (#...).
    Usata da: estrai_link_anime, VideoExtractor, PageSession.
    """
    clean = url.lower().split("?")[0].split("#")[0]
    return any(clean.endswith(ext) for ext in VIDEO_EXT)


def parse_episode_selection(text: str, max_ep: int) -> List[int]:
    """
    Parser selezione episodi da stringa utente -> indici 0-based.

    Formati supportati:
      tutto / all / *      -> tutti [0 .. max_ep-1]
      1-5                  -> range [0,1,2,3,4]
      1,3,7                -> singoli [0,2,6]
      1-5,7,9              -> misto [0,1,2,3,4,6,8]
      numeri fuori range   -> ignorati silenziosamente

    Ritorna lista indici 0-based, ordinata, senza duplicati.
    Usata da: estrai_link_anime.
    """
    text = text.strip().lower()
    if not text or text in ("tutto", "all", "tutti", "*"):
        return list(range(max_ep))

    indices: Set[int] = set()
    for part in text.replace(" ", "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a_s, b_s = part.split("-", 1)
                a = max(0, int(a_s) - 1)
                b = min(max_ep - 1, int(b_s) - 1)
                if a <= b:
                    indices.update(range(a, b + 1))
            except (ValueError, TypeError):
                pass
        elif part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < max_ep:
                indices.add(idx)

    return sorted(indices)


def print_progress_eta(
    current: int,
    total: int,
    prefix: str = "Progresso",
    start_time: Optional[float] = None,
    bar_length: int = 40,
) -> None:
    """
    Barra di avanzamento con ETA calcolato e counter "3/12".
    Sovrascrive la riga corrente (\\r). Usare print("") per andare a capo.

    Args:
        current:    Elemento corrente (incluso)
        total:      Totale elementi
        prefix:     Etichetta della barra
        start_time: time.time() di inizio (per ETA). Se None: mostra --:--
        bar_length: Larghezza barra in caratteri (default 40)

    Usata da: estrai_link_anime, scan_local_series.
    """
    if total <= 0:
        return
    pct    = 100.0 * current / total
    filled = int(bar_length * current // total)
    bar    = "\u2588" * filled + "\u2591" * (bar_length - filled)
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


def save_links(links: List[str], titolo: str, link_dir: str = "") -> Path:
    """
    Salva lista URL in file .txt con nome sanitizzato dal titolo.
    Se il file esiste gia aggiunge suffisso numerico (_1, _2, ...).
    Se link_dir e vuoto: usa get_link_dir() o default link_estratti/.

    Args:
        links:    Lista URL da salvare
        titolo:   Titolo anime (usato come nome file)
        link_dir: Directory destinazione (stringa vuota = usa default)

    Ritorna Path del file creato, o Path("") in caso di errore.
    Usata da: estrai_link_anime.
    """
    if not link_dir:
        link_dir = get_link_dir()
    if not link_dir:
        link_dir = str(Path(__file__).parent.parent.parent / "link_estratti")

    dest = Path(link_dir)
    dest.mkdir(parents=True, exist_ok=True)

    nome = (
        sanitize_filename(titolo)
        if titolo
        else f"anime_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    fp  = dest / f"{nome}.txt"
    cnt = 1
    while fp.exists():
        fp  = dest / f"{nome}_{cnt}.txt"
        cnt += 1

    return fp if save_urls_to_file(links, str(fp)) else Path("")


# ════════════════════════════════════════════════════════════════════════════
# §6  INTERRUPT HANDLER
# ════════════════════════════════════════════════════════════════════════════

# Flag globale condiviso: settato quando l'utente preme Ctrl+C durante
# operazioni multi-episodio. I loop interni controllano interrupted.is_set().
interrupted: threading.Event = threading.Event()

_original_sigint_handler = None  # conserva handler SIGINT originale


def setup_interrupt() -> None:
    """
    Installa handler SIGINT personalizzato (Ctrl+C).

    Al Ctrl+C:
      - Setta interrupted (threading.Event) — NON termina il processo
      - Stampa avviso "Interruzione ricevuta..."
      - Permette salvataggio risultati parziali prima dell'uscita

    Chiamare teardown_interrupt() al termine per ripristinare l'handler.
    Usata da: estrai_link_anime (download multi-episodio interrompibile).
    """
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
    """
    Ripristina l'handler SIGINT originale (dopo setup_interrupt()).
    Usata da: estrai_link_anime.
    """
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
    """Carica preferenze da scripts/temp/prefs.json."""
    if not _PREFS_FILE.exists():
        return {}
    try:
        with open(_PREFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(prefs: Dict) -> None:
    """Salva preferenze in scripts/temp/prefs.json."""
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_link_dir() -> str:
    """Legge directory link_estratti dalle preferenze utente."""
    return load_prefs().get("default_link_dir", "")


def get_headless_mode() -> bool:
    """Legge modalita headless browser dalle preferenze utente."""
    return load_prefs().get("browser_headless", False)


# ════════════════════════════════════════════════════════════════════════════
# §8  SEARCH FUNCTIONS — ANIMEWORLD
# ════════════════════════════════════════════════════════════════════════════

def search_animeworld(query: str, silent: bool = False) -> List[Dict]:
    """
    Ricerca anime su AnimeWorld.ac tramite requests + BeautifulSoup.

    Args:
        query:  Titolo da cercare
        silent: Se True non stampa messaggi (usato da watchlist)

    Returns:
        Lista dict: {title, link, raw_title, category}
    """
    if not HAS_REQUESTS:
        if not silent:
            show_error("'requests' non installato — ricerca non disponibile")
        return []

    try:
        if not silent:
            print()
            print(f"  [*] Ricerca '{query}' su AnimeWorld.ac...")
            print()

        headers  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(
            _get_search_url(), params={"keyword": query}, headers=headers, timeout=15
        )
        response.raise_for_status()

        soup      = BeautifulSoup(response.content, "html.parser")
        film_list = soup.find("div", class_="film-list")
        if not film_list:
            return []

        results = []
        for item in film_list.find_all("div", class_="item"):
            inner = item.find("div", class_="inner")
            if not inner:
                continue

            name_link = inner.find("a", class_="name")
            if not name_link:
                continue

            title = name_link.get("data-jtitle", "") or name_link.get_text(strip=True)
            if not title or len(title.strip()) < 2:
                continue

            poster_link = inner.find("a", class_="poster")
            if not poster_link:
                continue

            link = poster_link.get("href", "")
            if not link:
                continue
            if not link.startswith("http"):
                link = urljoin(_get_base_url(), link)

            category   = "SUB-ITA"
            status_div = inner.find("div", class_="status")
            if status_div:
                cat_div = status_div.find("div", class_=re.compile(r"ova|movie|special"))
                if cat_div:
                    category = cat_div.get_text(strip=True).upper()

            results.append({
                "title":     title + " - " + category,
                "link":      link,
                "raw_title": title,
                "category":  category,
            })

        return results

    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca: {e}")
        return []




# ════════════════════════════════════════════════════════════════════════════
# §8b  SEARCH FUNCTIONS — ANIMEUNITY (Playwright livesearch)
# ════════════════════════════════════════════════════════════════════════════

# Modalita debug: AU_DEBUG=1 -> headless=False + screenshot + dump DOM
_AU_DEBUG = os.environ.get("AU_DEBUG", "0").strip() == "1"


def _au_livesearch_js() -> str:
    """
    Snippet JavaScript che legge i risultati della livesearch AnimeUnity.

    Struttura DOM attesa:
      <div class="results">
        <div class="result">
          <a class="livesearch-item" href="/anime/{id}-{slug}">
            <div class="livesearch-title">Naruto</div>
            <span class="livesearch-info">2002</span>
            <span class="livesearch-info info-2">TV</span>
            <span class="livesearch-info"> * 220/220 episodi</span>
    """
    return """() => {
        const results = [];
        document.querySelectorAll('.results .result').forEach(r => {
            const a = r.querySelector('a.livesearch-item');
            if (!a) return;
            const href  = a.href || a.getAttribute('href') || '';
            const tEl   = r.querySelector('.livesearch-title');
            const title = tEl ? tEl.innerText.trim() : '';
            const infos = r.querySelectorAll('.livesearch-info');
            const year  = infos[0] ? infos[0].innerText.trim() : '';
            const type  = infos[1] ? infos[1].innerText.trim() : '';
            const eps   = infos[2]
                ? infos[2].innerText.replace(/\u2022/g, '').trim()
                : '';
            if (title && href) {
                results.push({ title, link: href, year, type, episodes: eps });
            }
        });
        return results;
    }"""


def _au_open_searchbar(page) -> bool:
    """
    Apre il campo di ricerca AnimeUnity cliccando il pulsante lente.

    Flusso UI reale AnimeUnity:
      1. Clicca <button class="input-group-text btn-dark-gray2">
         (contiene <i class="fas fa-search text-white">)
      2. Il campo <input class="search-bar"> diventa visibile e attivo
      3. Si digita il titolo -> risultati in .results (live, senza submit)

    Returns:
        True se il campo e ora visibile, False altrimenti.
    """
    INPUT_SELS = [
        "input.search-bar",
        "input[placeholder*='Cerca']",
        "input[placeholder*='anime']",
    ]
    BTN_SELS = [
        "button.input-group-text.btn-dark-gray2",
        "button[type='submit'].input-group-text",
        "button.btn-dark-gray2",
        "button:has(i.fa-search)",
        "button:has(.fas.fa-search)",
        ".input-group-text.btn-dark-gray2",
    ]

    # Controlla se il campo e gia visibile
    for sel in INPUT_SELS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                if _AU_DEBUG:
                    print(f"  [AU_DEBUG] input gia visibile: {sel}")
                return True
        except Exception:
            pass

    # Clicca il pulsante lente
    clicked = False
    for sel in BTN_SELS:
        try:
            el = page.query_selector(sel)
            if el:
                el.scroll_into_view_if_needed()
                el.click()
                page.wait_for_timeout(700)
                clicked = True
                if _AU_DEBUG:
                    print(f"  [AU_DEBUG] click pulsante lente: {sel}")
                break
        except Exception:
            pass

    if not clicked:
        if _AU_DEBUG:
            print("  [AU_DEBUG] fallback JS click sul pulsante lente")
        try:
            page.evaluate("""() => {
                const sels = [
                    'button.input-group-text.btn-dark-gray2',
                    'button[type="submit"].input-group-text',
                    'button.btn-dark-gray2',
                ];
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el) { el.click(); return true; }
                }
                const ico = document.querySelector(
                    'i.fa-search, i.fas.fa-search, .fas.fa-search'
                );
                if (ico) {
                    const btn = ico.closest('button');
                    if (btn) { btn.click(); return true; }
                }
                return false;
            }""")
            page.wait_for_timeout(700)
        except Exception:
            pass

    # Verifica che il campo sia ora visibile (state="visible")
    for sel in INPUT_SELS:
        try:
            page.wait_for_selector(sel, timeout=5000, state="visible")
            if _AU_DEBUG:
                print(f"  [AU_DEBUG] input visibile dopo click: {sel}")
            return True
        except Exception:
            pass

    if _AU_DEBUG:
        try:
            html = page.content()
            with open("au_debug_dom.html", "w", encoding="utf-8") as _f:
                _f.write(html)
            page.screenshot(path="au_debug_screenshot.png")
            print("  [AU_DEBUG] DOM  -> au_debug_dom.html")
            print("  [AU_DEBUG] Shot -> au_debug_screenshot.png")
            btns = page.evaluate("""() => Array.from(
                document.querySelectorAll('button')
            ).map(b => ({cls: b.className, type: b.type,
                         txt: b.innerText.trim().slice(0,40)}))""")
            print(f"  [AU_DEBUG] Button nel DOM ({len(btns)}):")
            for b in btns[:15]:
                print(f"    class='{b['cls']}'  type='{b['type']}'  text='{b['txt']}'")
            inputs = page.evaluate("""() => Array.from(
                document.querySelectorAll('input')
            ).map(i => ({cls: i.className, ph: i.placeholder,
                          vis: i.offsetParent !== null}))""")
            print(f"  [AU_DEBUG] Input nel DOM ({len(inputs)}):")
            for inp in inputs[:10]:
                print(f"    class='{inp['cls']}'  placeholder='{inp['ph']}'  visible={inp['vis']}")
        except Exception as _ex:
            print(f"  [AU_DEBUG] Errore dump: {_ex}")

    return False


def search_animeunity(query: str, silent: bool = False) -> List[Dict]:
    """
    Ricerca anime su AnimeUnity tramite livesearch Playwright.

    Flusso UI reale AnimeUnity:
      1. Apre la homepage e attende caricamento Vue.js (2500ms)
      2. Clicca il pulsante lente  <button class="input-group-text btn-dark-gray2">
      3. Il campo <input class="search-bar"> diventa visibile
      4. Digita il titolo (delay 80ms per sembrare umano)
      5. I risultati appaiono in <div class="results"> senza premere invio
      6. Legge .results .result > a.livesearch-item via JS

    Fast-path (requests+BS4):
      Tenta prima /archivio?title= (Inertia.js JSON) piu veloce,
      non richiede browser. Se fallisce, usa Playwright.

    Debug (AU_DEBUG=1):
      Windows:  set AU_DEBUG=1 && python main.py
      Linux:    AU_DEBUG=1 python main.py
      Effetti:  headless=False, slow_mo=200ms, screenshot, dump DOM, log step

    Args:
        query:  Titolo da cercare
        silent: Se True non stampa messaggi (usato da watchlist)

    Returns:
        Lista dict: {title, link, raw_title, year, type, episodes}

    Usata da: estrai_link_anime_unity.py -> _ricerca_e_seleziona_au()
    """
    if not HAS_PLAYWRIGHT:
        if not silent:
            show_error("Playwright obbligatorio per la ricerca AnimeUnity.")
        return []

    _BASE_AU = "https://www.animeunity.so"

    if _AU_DEBUG and not silent:
        show_info("[AU_DEBUG] modalita debug attiva (headless=False, slow_mo=200ms)")

    # -- Fast-path: requests + BS4 (Inertia.js /archivio?title=) -----------
    if HAS_REQUESTS and HAS_BS4:
        try:
            import json as _json
            _hdr = {
                "User-Agent": _HDR_BROWSER["User-Agent"],
                "Accept":     "application/json, text/html, */*",
                "Referer":    _BASE_AU,
            }
            r = requests.get(
                _BASE_AU + "/archivio",
                params={"title": query},
                headers=_hdr,
                timeout=12,
            )
            r.raise_for_status()
            soup    = BeautifulSoup(r.content, "html.parser")
            app_div = soup.find("div", id="app")
            if app_div:
                data_page = app_div.get("data-page", "")
                if data_page:
                    page_data = _json.loads(data_page)
                    animes    = (
                        page_data.get("props", {})
                        .get("titles", {})
                        .get("data", [])
                    )
                    fast_results = []
                    for a_ in animes:
                        title    = a_.get("title_it") or a_.get("title") or ""
                        slug     = a_.get("slug", "")
                        anime_id = a_.get("id", "")
                        if title and slug and anime_id:
                            link = f"{_BASE_AU}/anime/{anime_id}-{slug}"
                            fast_results.append({
                                "title":     title,
                                "link":      link,
                                "raw_title": title,
                                "year":      str(a_.get("date", "")),
                                "type":      a_.get("type", ""),
                                "episodes":  str(a_.get("episodes_count", "")),
                            })
                    if fast_results:
                        if _AU_DEBUG and not silent:
                            show_info(f"[AU_DEBUG] fast-path OK -> {len(fast_results)} risultati")
                        return fast_results
                    elif _AU_DEBUG and not silent:
                        show_info("[AU_DEBUG] fast-path: data-page trovato ma 0 risultati")
                elif _AU_DEBUG and not silent:
                    show_info("[AU_DEBUG] fast-path: app_div senza data-page")
            elif _AU_DEBUG and not silent:
                show_info("[AU_DEBUG] fast-path: div#app non trovato")
        except Exception as _fp_ex:
            if _AU_DEBUG and not silent:
                show_info(f"[AU_DEBUG] fast-path eccezione: {_fp_ex}")

    # -- Fallback: Playwright livesearch -----------------------------------
    results: List[Dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=not _AU_DEBUG,
                slow_mo=200 if _AU_DEBUG else 0,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = browser.new_context(
                user_agent=_HDR_BROWSER["User-Agent"],
                locale="it-IT",
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.set_default_timeout(20000)

            try:
                # 1. Apri homepage e attendi caricamento Vue.js
                if _AU_DEBUG and not silent:
                    show_info(f"[AU_DEBUG] goto {_BASE_AU}")
                page.goto(_BASE_AU, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)

                # 2. Clicca il pulsante lente -> apre input.search-bar
                if _AU_DEBUG and not silent:
                    show_info("[AU_DEBUG] apertura campo ricerca...")
                bar_open = _au_open_searchbar(page)
                if not bar_open:
                    if not silent:
                        show_warning(
                            "Pulsante ricerca AnimeUnity non trovato.\n"
                            "  -> Riprova con AU_DEBUG=1 per diagnostica."
                        )
                    browser.close()
                    return []

                # 3. Trova il campo input (ora visibile dopo il click)
                search_input = None
                for sel in [
                    "input.search-bar",
                    "input[placeholder*='Cerca']",
                    "input[placeholder*='anime']",
                ]:
                    try:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            search_input = sel
                            break
                    except Exception:
                        pass

                if not search_input:
                    if not silent:
                        show_warning("input.search-bar non trovato dopo apertura.")
                    browser.close()
                    return []

                # 4. Clicca e digita (80ms delay = digitazione umana)
                page.click(search_input)
                page.wait_for_timeout(300)
                page.type(search_input, query, delay=80)
                if _AU_DEBUG and not silent:
                    show_info(f"[AU_DEBUG] digitato '{query}' in {search_input}")

                # 5. Attendi comparsa risultati (senza premere invio)
                for res_sel in [".results .result", "a.livesearch-item", ".results"]:
                    try:
                        page.wait_for_selector(res_sel, timeout=7000)
                        if _AU_DEBUG and not silent:
                            show_info(f"[AU_DEBUG] risultati visibili: {res_sel}")
                        break
                    except Exception:
                        pass

                page.wait_for_timeout(600)

                # 6. Leggi risultati via JS
                raw = page.evaluate(_au_livesearch_js())
                if _AU_DEBUG and not silent:
                    show_info(f"[AU_DEBUG] risultati JS: {len(raw)}")

                for item in raw:
                    t   = item.get("title", "").strip()
                    lnk = item.get("link",  "").strip()
                    if not t or not lnk:
                        continue
                    if not lnk.startswith("http"):
                        lnk = _BASE_AU + ("" if lnk.startswith("/") else "/") + lnk
                    results.append({
                        "title":     t,
                        "link":      lnk,
                        "raw_title": t,
                        "year":      item.get("year",     ""),
                        "type":      item.get("type",     ""),
                        "episodes":  item.get("episodes", ""),
                    })

            except Exception as ex:
                if not silent:
                    show_warning(f"Livesearch AU: {ex}")
                if _AU_DEBUG:
                    import traceback
                    traceback.print_exc()
            finally:
                if _AU_DEBUG:
                    page.wait_for_timeout(3000)
                browser.close()

    except Exception as ex:
        if not silent:
            show_error(f"Playwright AU: {ex}")

    return results


# ════════════════════════════════════════════════════════════════════════════
# §9  VIDEO EXTRACTOR CLASS (legacy — mantenuto per compatibilita)
# ════════════════════════════════════════════════════════════════════════════

class VideoExtractor:
    """
    Estrazione link video da pagine anime via requests + BeautifulSoup.
    Supporta crawling ricorsivo su AnimeWorld.ac.

    Nota: per estrazione parallela multi-episodio usare le funzioni in §10.
    """

    _HDR = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def __init__(self, url: str) -> None:
        self.url           = url
        self.base_domain   = urlparse(url).netloc
        self.visited       : Set[str]        = set()
        self.video_links   : Set[str]        = set()
        self.alt_links     : Set[str]        = set()
        self.related_links : Dict[str, str]  = {}
        self.anime_title   : Optional[str]   = None

    def _is_valid_domain(self, url: str) -> bool:
        try:
            return urlparse(url).netloc in (self.base_domain, "")
        except Exception:
            return False

    def _is_php(self, url: str) -> bool:
        return ".php" in url.lower()

    def _extract_title(self, soup) -> Optional[str]:
        for tag, attrs in [
            ("h1", {"class": "title"}),
            (None, {"id": "anime-title"}),
            ("h1", {}),
        ]:
            el = soup.find(tag, attrs) if tag else soup.find(attrs=attrs)
            if el:
                return el.get_text(strip=True)
        return None

    def _extract_from_sections(self, soup, page_url: str = "") -> None:
        page_url = page_url or self.url
        for cls in ["widget servers", "download"]:
            section = soup.find("div", class_=cls)
            if not section:
                continue
            for a in section.find_all("a"):
                href = a.get("href", "")
                if href:
                    full = urljoin(page_url, href)
                    if not self._is_php(full) and is_video(full):
                        self.video_links.add(full)
            for source in section.find_all("source"):
                src = source.get("src", "")
                if src:
                    full = urljoin(page_url, src)
                    if not self._is_php(full) and is_video(full):
                        self.video_links.add(full)
            for el in section.find_all(attrs={"data-src": True}):
                data_src = el.get("data-src", "")
                if data_src:
                    full = urljoin(page_url, data_src)
                    if not self._is_php(full) and is_video(full):
                        self.video_links.add(full)

    def _crawl(self, url: str, depth: int = 0, max_depth: int = 2) -> None:
        if depth > max_depth or url in self.visited or not HAS_REQUESTS:
            return
        self.visited.add(url)
        try:
            resp = requests.get(url, headers=self._HDR, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            self._extract_from_sections(soup, url)
            if depth < max_depth:
                servers = soup.find("div", class_="widget servers")
                if servers:
                    for link in servers.find_all("a", href=True):
                        link_url = urljoin(url, link["href"])
                        if (
                            self._is_valid_domain(link_url)
                            and not self._is_php(link_url)
                            and link_url not in self.visited
                        ):
                            self._crawl(link_url, depth + 1, max_depth)
        except Exception:
            pass

    def extract(self) -> bool:
        """Estrae link video. Ritorna True se riuscito."""
        if not HAS_REQUESTS:
            return False
        try:
            resp = requests.get(self.url, headers=self._HDR, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            self.anime_title = self._extract_title(soup)
            self._crawl(self.url)
            return True
        except Exception:
            return False

    def get_all_links(self) -> List[str]:
        """Ritorna tutti i link video ordinati numericamente."""
        return sort_links_numerically(list(self.alt_links | self.video_links))


# ════════════════════════════════════════════════════════════════════════════
# §10  BROWSER / PLAYWRIGHT
# ════════════════════════════════════════════════════════════════════════════

_HDR_BROWSER: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _extract_title_from_soup(soup) -> str:
    """Helper interno: estrae titolo pagina da BeautifulSoup."""
    for tag, attrs in [("h1", {"class": "title"}), ("h1", {"id": "anime-title"})]:
        el = soup.find(tag, attrs)
        if el:
            return el.get_text(strip=True)
    el = soup.find(id="anime-title")
    if el:
        return el.get_text(strip=True)
    t = soup.find("title")
    if t:
        text = t.get_text(strip=True)
        for sep in (" - AnimeWorld", " | AnimeWorld"):
            if sep in text:
                text = text[: text.index(sep)]
        return text.strip()
    return ""


def extract_video_links(soup, base_url: str = "") -> List[str]:
    base_url = base_url or _get_base_url()
    """
    Estrae link video da BeautifulSoup.
    Cerca in: <a href>, <source src>, [data-src], <a id="alternativeDownloadLink">.
    Filtra per estensioni VIDEO_EXT.

    Args:
        soup:     Oggetto BeautifulSoup della pagina
        base_url: URL base per link relativi

    Returns:
        Lista URL video deduplicati e ordinati numericamente.
    Usata da: PageSession, estrai_link_anime.
    """
    found: Set[str] = set()

    # Metodo primario AnimeWorld: <a id="alternativeDownloadLink">
    a_alt = soup.find("a", id="alternativeDownloadLink")
    if a_alt:
        href = a_alt.get("href", "").strip()
        if href:
            found.add(href if href.startswith("http") else urljoin(base_url, href))

    # <a href> filtrati per VIDEO_EXT
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href and href != "#":
            full = href if href.startswith("http") else urljoin(base_url, href)
            if is_video(full):
                found.add(full)

    # <source src>
    for source in soup.find_all("source", src=True):
        src = source["src"].strip()
        if src:
            full = src if src.startswith("http") else urljoin(base_url, src)
            if is_video(full):
                found.add(full)

    # [data-src]
    for el in soup.find_all(attrs={"data-src": True}):
        data_src = el["data-src"].strip()
        if data_src:
            full = data_src if data_src.startswith("http") else urljoin(base_url, data_src)
            if is_video(full):
                found.add(full)

    return sort_links_numerically(list(found))


def extract_from_js(page) -> List[str]:
    """
    Fallback: esegue JavaScript sulla pagina Playwright per trovare link video.
    Cerca URL con estensioni VIDEO_EXT in tutto il DOM.

    Args:
        page: Playwright Page object

    Returns:
        Lista URL video trovati via JS. Lista vuota in caso di errore.
    Usata da: PageSession.fetch_page_links() come fallback.
    """
    ext_list = list(VIDEO_EXT)
    js = """(exts) => {
        const found = new Set();
        document.querySelectorAll('a[href], source[src]').forEach(el => {
            const u = el.href || el.src || '';
            if (u && exts.some(e => u.toLowerCase().split('?')[0].endsWith(e))) {
                found.add(u);
            }
        });
        document.querySelectorAll('[data-src]').forEach(el => {
            const u = el.dataset.src || '';
            if (u && exts.some(e => u.toLowerCase().split('?')[0].endsWith(e))) {
                found.add(u);
            }
        });
        const alt = document.getElementById('alternativeDownloadLink');
        if (alt && alt.href) found.add(alt.href);
        return Array.from(found);
    }"""
    try:
        results = page.evaluate(js, ext_list)
        return sort_links_numerically([u for u in results if u])
    except Exception:
        return []


def extract_episode_links(soup, base_url: str = "") -> List[str]:
    base_url = base_url or _get_base_url()
    """
    Estrae URL episodi da pagina serie AnimeWorld.
    Cerca nelle sezioni episodi standard; fallback su qualsiasi <a /play/>.

    Args:
        soup:     BeautifulSoup della pagina serie
        base_url: URL base per link relativi

    Returns:
        Lista URL episodi deduplicati e ordinati numericamente.
    Usata da: PageSession.fetch_all_episodes(), estrai_link_anime.
    """
    links: Set[str] = set()

    # Sezioni episodi in ordine di priorita
    for cls in ["server active", "server", "episodes-sv-1", "episodes", "ep-list"]:
        sec = soup.find(class_=cls)
        if not sec:
            continue
        for a in sec.find_all("a", href=True):
            h = a["href"]
            if h and h != "#" and "/play/" in h:
                links.add(h if h.startswith("http") else urljoin(base_url, h))
        if links:
            break

    # Fallback globale su /play/
    if not links:
        for a in soup.find_all("a", href=re.compile(r"/play/.+/\w+")):
            h = a["href"]
            if "/play/" in h:
                links.add(h if h.startswith("http") else urljoin(base_url, h))

    return sort_links_numerically(list(links))


class PageSession:
    """
    Sessione Playwright ottimizzata per AnimeWorld.

    - Blocca risorse inutili (BLOCK_EXTS) per velocizzare il caricamento
    - Gestisce banner cookie con COOKIE_SEL / COOKIE_TEXTS
    - Supporta sia context manager che utilizzo esplicito open()/close()

    Utilizzo consigliato (context manager):
        with PageSession() as sess:
            titolo, ep_urls  = sess.fetch_all_episodes(serie_url)
            titolo, vid_urls = sess.fetch_page_links(ep_url)

    Utilizzo esplicito:
        sess = PageSession()
        sess.open()
        try:
            titolo, links = sess.fetch_all_episodes(url)
        finally:
            sess.close()

    Metodi pubblici:
        .open()                   -> apre browser e pagina interna
        .close()                  -> chiude browser
        .new_browser(playwright)  -> (browser, page) con playwright esterno
        .dismiss_cookies(page)    -> chiude banner cookie
        .fetch_page_links(url)    -> (titolo, [video_links])
        .fetch_all_episodes(url)  -> (titolo, [ep_links])
    """

    def __init__(self) -> None:
        self._pw               = None
        self._browser          = None
        self._ctx              = None
        self._page             = None
        self._cookie_dismissed = False

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self) -> "PageSession":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def open(self) -> None:
        """Apre browser Playwright e prepara la pagina interna."""
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
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--blink-settings=imagesEnabled=false",
            ],
        )
        self._ctx = self._browser.new_context(
            locale="it-IT",
            user_agent=_HDR_BROWSER["User-Agent"],
        )
        # Blocca risorse non necessarie per velocizzare
        for ext in BLOCK_EXTS:
            try:
                self._ctx.route(f"**/*{ext}", lambda route, _e=ext: route.abort())
            except Exception:
                pass
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(12_000)

    def close(self) -> None:
        """Chiude browser e sessione Playwright."""
        for obj, method in [(self._browser, "close"), (self._pw, "stop")]:
            if obj:
                try:
                    getattr(obj, method)()
                except Exception:
                    pass
        self._browser = self._pw = self._ctx = self._page = None

    # ── Factory con playwright esterno ───────────────────────────────────────

    def new_browser(self, playwright) -> Tuple:
        """
        Crea browser + pagina da istanza playwright esterna (gia avviata).
        Il chiamante e responsabile della chiusura del browser.

        Returns:
            (browser, page) tuple
        """
        headless = get_headless_mode()
        browser  = playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        ctx = browser.new_context(
            locale="it-IT",
            user_agent=_HDR_BROWSER["User-Agent"],
        )
        for ext in BLOCK_EXTS:
            try:
                ctx.route(f"**/*{ext}", lambda route, _e=ext: route.abort())
            except Exception:
                pass
        page = ctx.new_page()
        page.set_default_timeout(12_000)
        return browser, page

    # ── Cookie handling ──────────────────────────────────────────────────────

    def dismiss_cookies(self, page=None) -> None:
        """
        Chiude banner cookie usando COOKIE_SEL e COOKIE_TEXTS dell'engine.

        Args:
            page: Playwright Page. Se None usa la pagina interna della sessione.
        """
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
                const t = (e.innerText || e.value || e.textContent || '').trim().toLowerCase();
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

    # ── Fetch methods ────────────────────────────────────────────────────────

    def fetch_page_links(self, url: str) -> Tuple[str, List[str]]:
        """
        Carica URL episodio e restituisce (titolo, [video_links]).
        Fast path: requests+BS4. Fallback: browser Playwright.

        Args:
            url: URL pagina episodio AnimeWorld

        Returns:
            (titolo, lista_link_video)
        """
        if not self._page:
            raise RuntimeError("PageSession non aperta. Chiamare .open() prima.")

        titolo: str            = ""
        video_links: List[str] = []

        # Fast path: requests + BS4
        if HAS_REQUESTS and HAS_BS4:
            try:
                resp = requests.get(url, headers=_HDR_BROWSER, timeout=10)
                resp.raise_for_status()
                soup        = BeautifulSoup(resp.content, "html.parser")
                titolo      = _extract_title_from_soup(soup)
                video_links = extract_video_links(soup, url)
                if video_links:
                    return titolo, video_links
            except Exception:
                pass

        # Fallback: browser
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(800)

            if HAS_BS4:
                soup        = BeautifulSoup(self._page.content(), "html.parser")
                titolo      = _extract_title_from_soup(soup)
                video_links = extract_video_links(soup, url)

            if not video_links:
                video_links = extract_from_js(self._page)
                if not titolo:
                    try:
                        titolo = self._page.title().replace(" - AnimeWorld", "").strip()
                    except Exception:
                        pass

        except Exception as ex:
            show_error(f"Errore fetch_page_links: {ex}")

        return titolo, video_links

    def fetch_all_episodes(self, url: str) -> Tuple[str, List[str]]:
        """
        Carica pagina serie e restituisce (titolo, [ep_links]).
        Fast path: requests+BS4. Fallback: browser Playwright.

        Args:
            url: URL pagina serie AnimeWorld

        Returns:
            (titolo, lista_url_episodi)
        """
        if not self._page:
            raise RuntimeError("PageSession non aperta. Chiamare .open() prima.")

        titolo: str         = ""
        ep_links: List[str] = []

        # Fast path: requests + BS4
        if HAS_REQUESTS and HAS_BS4:
            try:
                resp = requests.get(url, headers=_HDR_BROWSER, timeout=10)
                resp.raise_for_status()
                soup     = BeautifulSoup(resp.content, "html.parser")
                titolo   = _extract_title_from_soup(soup)
                ep_links = extract_episode_links(soup, url)
                if ep_links:
                    return titolo, ep_links
            except Exception:
                pass

        # Fallback: browser
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.dismiss_cookies()
            for sel in [
                ".server.active .episodes",
                "#episodes-sv-1",
                ".episodes",
                "ul.episodes",
            ]:
                try:
                    self._page.wait_for_selector(sel, timeout=5_000)
                    break
                except Exception:
                    continue
            self._page.wait_for_timeout(800)

            if HAS_BS4:
                soup     = BeautifulSoup(self._page.content(), "html.parser")
                ep_links = extract_episode_links(soup, url)
                if not titolo:
                    titolo = _extract_title_from_soup(soup)

        except Exception as ex:
            show_error(f"Errore fetch_all_episodes: {ex}")

        return titolo, ep_links


# ════════════════════════════════════════════════════════════════════════════
# §11  EXPORT — PUBLIC API  (47 simboli)
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    # §2 — UI / Display (8)
    "clear_screen",
    "show_header",
    "show_success",
    "show_error",
    "show_info",
    "show_warning",
    "print_separator",
    "print_double_separator",
    # §3 — Input (4)
    "ask_yes_no",
    "get_valid_choice",
    "get_path_input",
    "wait_enter",
    # §4 — File / Path (7)
    "sanitize_filename",
    "clean_path",
    "load_urls_from_file",
    "save_urls_to_file",
    "get_safe_path",
    "ensure_folder",
    "save_links",
    # §5 — Utility (6)
    "sort_links_numerically",
    "normalize_url",
    "animate_progress",
    "is_video",
    "parse_episode_selection",
    "print_progress_eta",
    # §6 — Interrupt (3)
    "interrupted",
    "setup_interrupt",
    "teardown_interrupt",
    # §7 — Config (4)
    "load_prefs",
    "save_prefs",
    "get_link_dir",
    "get_headless_mode",
    # §8 — Search (2)
    "search_animeworld",
    "search_animeunity",
    # §9 — Classes legacy (1)
    "VideoExtractor",
    # §10 — Browser / Playwright (4)
    "PageSession",
    "extract_video_links",
    "extract_from_js",
    "extract_episode_links",
    # Costanti (7)
    "WIDTH",
    "BASE_URL",
    "SEARCH_URL",
    "VIDEO_EXT",
    "BLOCK_EXTS",
    "COOKIE_SEL",
    "COOKIE_TEXTS",
    # Flags (2)
    "HAS_REQUESTS",
    "HAS_PLAYWRIGHT",
]


# ════════════════════════════════════════════════════════════════════════════
# MAIN — selftest
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("=" * 56)
    print("  ANIME ENGINE v2.0 — selftest")
    print("=" * 56)
    print()
    print(f"  Esportazioni __all__  : {len(__all__)}")
    print(f"  HAS_REQUESTS          : {HAS_REQUESTS}")
    print(f"  HAS_PLAYWRIGHT        : {HAS_PLAYWRIGHT}")
    print()
    print("  Costanti:")
    print(f"    VIDEO_EXT  : {len(VIDEO_EXT)} estensioni")
    print(f"    BLOCK_EXTS : {len(BLOCK_EXTS)} estensioni")
    print(f"    COOKIE_SEL : {len(COOKIE_SEL)} selettori")
    print()
    print("  Test is_video():")
    cases = [
        ("https://srv.example.com/ep01.mp4",    True),
        ("https://srv.example.com/ep01.mkv?t=x", True),
        ("https://example.com/cover.jpg",        False),
        ("https://example.com/page",             False),
    ]
    for u, expected in cases:
        result = is_video(u)
        ok = "[OK]  " if result == expected else "[FAIL]"
        print(f"    {ok} is_video({u[-35:]!r}) -> {result}")
    print()
    print("  Test parse_episode_selection():")
    ep_cases = [
        ("1-3",    10, [0, 1, 2]),
        ("1,3,5",  10, [0, 2, 4]),
        ("1-3,7",  10, [0, 1, 2, 6]),
        ("tutto",   5, [0, 1, 2, 3, 4]),
        ("0,11",   10, []),
    ]
    for raw, mx, expected in ep_cases:
        result = parse_episode_selection(raw, mx)
        ok = "[OK]  " if result == expected else "[FAIL]"
        print(f"    {ok} parse({raw!r:8}, max={mx}) -> {result}")
    print()
    print("  Pronto per importazione in:")
    print("    watchlist.py, estrai_link_anime.py,")
    print("    ricerca_scheda_anime.py, scan_local_series.py")
    print()
