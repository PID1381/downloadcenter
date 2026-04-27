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
  Search       : search_animeworld
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
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
    return _BASE_URL_FALLBACK


def _get_search_url() -> str:
    """Ritorna SEARCH_URL da url_mgr centralizzato, o fallback hardcodato."""
    if _HAS_URL_MGR:
        try:
            url = _url_mgr.get("anime", "animeworld_search")
            if url:
                return url
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
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
    except Exception as _dbg_ex_:
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')


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
    except Exception as _dbg_ex_:
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')


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




# ══════════════════════════════════════════════════════════
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
    # §9 — Classes legacy (1)
    # "VideoExtractor",  # [FIX v2.3] RIMOSSO: classe non definita → ImportError
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
