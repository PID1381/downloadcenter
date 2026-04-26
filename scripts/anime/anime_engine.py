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
# §8b  SEARCH FUNCTIONS — ANIMEUNITY (Playwright livesearch)
# ══════════════════════════════════════════════════════════

# Modalita debug: AU_DEBUG=1 -> headless=False + screenshot + dump DOM
_AU_DEBUG = os.environ.get("AU_DEBUG", "0").strip() == "1"


def _au_livesearch_js() -> str:
    # Snippet JS che legge .results .result dal DOM di AnimeUnity
    # Estrae: title, link, year, type, episodes
    return (
        "() => {"
        "  const results = [];"
        "  document.querySelectorAll('.results .result').forEach(r => {"
        "    const a = r.querySelector('a.livesearch-item');"
        "    if (!a) return;"
        "    const href  = a.href || a.getAttribute('href') || '';"
        "    const tEl   = r.querySelector('.livesearch-title');"
        "    const title = tEl ? tEl.innerText.trim() : '';"
        "    const infos = r.querySelectorAll('.livesearch-info');"
        "    const year  = infos[0] ? infos[0].innerText.trim() : '';"
        "    const type  = infos[1] ? infos[1].innerText.trim() : '';"
        "    const eps   = infos[2] ? infos[2].innerText.replace(/\u2022/g,\'\').trim() : \'\';"
        "    if (title && href) {"
        "      results.push({ title, link: href, year, type, episodes: eps });"
        "    }"
        "  });"
        "  return results;"
        "}"
    )


def _au_close_popups(ctx) -> None:
    """
    Chiude tutte le schede extra aperte da AnimeUnity
    (pubblicita, popup, redirect a YouTube, ecc.).
    Chiamata dopo ogni click che potrebbe aprire nuove schede.
    """
    try:
        pages = ctx.pages
        if len(pages) > 1:
            for extra in pages[1:]:
                try:
                    extra_url = ''
                    try:
                        extra_url = extra.url
                    except Exception as _dbg_ex_:
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                    extra.close()
                    if _AU_DEBUG:
                        print(f"  [AU_DEBUG] chiusa scheda extra: {extra_url}")
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
    except Exception as _dbg_ex_:
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')


def _au_open_searchbar(page, ctx=None) -> bool:
    """
    Apre il campo di ricerca AnimeUnity cliccando il pulsante lente.

    Comportamento reale (Vue.js):
      - Click 1 NATIVO -> apre scheda pub (YouTube/ad)
      - ctx.on('page') chiude SUBITO la scheda pub
      - bring_to_front() riporta il focus sulla home
      - Click 2 NATIVO -> Vue apre il pannello con input.search-bar

    REGOLE:
      - I click devono essere NATIVI (el.click()), non JS dispatchEvent
        (Vue.js ignora gli eventi sintetici per il pannello ricerca)
      - scroll_into_view_if_needed() solo sul click 1 (l'elemento
        potrebbe essere not-visible tra i due click -> timeout)
      - ctx.on('page') deve essere attivo PRIMA del click 1
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

    def _input_visible():
        for sel in INPUT_SELS:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    return sel
            except Exception as _dbg_ex_:
                if _AU_DEBUG:
                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
        return None

    def _find_btn():
        """Trova il pulsante lente VISIBILE nel DOM.
        AnimeUnity ha due pulsanti identici: uno mobile (nascosto, d-md-none)
        e uno desktop (visibile). query_selector_all + is_visible() prende
        quello giusto evitando il timeout da elemento non visibile.
        """
        for sel in BTN_SELS:
            try:
                els = page.query_selector_all(sel)
                for el in els:
                    try:
                        if el.is_visible():
                            return el, sel
                    except Exception as _dbg_ex_:
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
            except Exception as _dbg_ex_:
                if _AU_DEBUG:
                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
        # fallback: icona fa-search -> risali al button visibile
        try:
            icos = page.query_selector_all("i.fa-search, .fas.fa-search")
            for ico in icos:
                try:
                    if ico.is_visible():
                        btn = ico.evaluate_handle("el => el.closest('button')")
                        if btn:
                            return btn, "via-icon"
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
        return None, None

    # Gia visibile?
    found = _input_visible()
    if found:
        if _AU_DEBUG:
            print(f"  [AU_DEBUG] input gia visibile: {found}")
        return True

    # ── 1. Route blocker per richieste ad note ───────────────────────────────
    AD_DOMAINS = [
        "youtube.com", "youtu.be", "doubleclick.net",
        "googlesyndication", "adservice", "pagead",
        "pubmatic.com", "rubiconproject.com", "openx.net",
        "taboola.com", "outbrain.com", "adsrvr.org",
    ]
    try:
        def _route_handler(route):
            if any(d in route.request.url for d in AD_DOMAINS):
                route.abort()
            else:
                route.continue_()
        page.route("**/*", _route_handler)
        if _AU_DEBUG:
            print("  [AU_DEBUG] route: blocco ad/popup attivo")
    except Exception as _dbg_ex_:
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

    # ── 2. ctx.on('page'): chiude OGNI nuova scheda automaticamente ──────────
    # Deve essere attivo PRIMA del click 1, cosi chiude il popup non appena
    # si apre, senza bisogno di expect_popup() che ha problemi di timing.
    if ctx:
        try:
            def _close_new_page(new_page):
                try:
                    _url = new_page.url
                except Exception:
                    _url = "?"
                try:
                    new_page.close()
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                if _AU_DEBUG:
                    print(f"  [AU_DEBUG] popup chiuso automaticamente: {_url}")
            ctx.on('page', _close_new_page)
            if _AU_DEBUG:
                print("  [AU_DEBUG] listener ctx.on('page') attivo")
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

    # ── 3. Trova pulsante lente ──────────────────────────────────────────────
    btn_el, btn_sel = _find_btn()
    if not btn_el:
        if _AU_DEBUG:
            print("  [AU_DEBUG] pulsante lente NON trovato nel DOM")
        return False
    if _AU_DEBUG:
        print(f"  [AU_DEBUG] pulsante lente trovato: {btn_sel}")

    # ── 4. Click 1 NATIVO ────────────────────────────────────────────────────
    # scroll_into_view solo sul click 1 (elemento visibile in questo momento)
    if _AU_DEBUG:
        print("  [AU_DEBUG] click 1 nativo...")
    try:
        try:
            btn_el.scroll_into_view_if_needed(timeout=3000)
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')  # non bloccare se gia visibile o timeout breve
        btn_el.click()
        if _AU_DEBUG:
            print(f"  [AU_DEBUG] click 1 eseguito su: {btn_sel}")
    except Exception as _ex:
        if _AU_DEBUG:
            print(f"  [AU_DEBUG] errore click 1: {_ex}")

    # Pausa: lascia tempo al popup di aprirsi e a ctx.on di chiuderlo
    page.wait_for_timeout(600)

    # Riporta il focus sulla pagina principale
    try:
        page.bring_to_front()
    except Exception as _dbg_ex_:
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
    page.wait_for_timeout(300)

    # Input apparso dopo click 1?
    found = _input_visible()
    if found:
        if _AU_DEBUG:
            print(f"  [AU_DEBUG] input visibile dopo click 1: {found}")
        return True

    # ── 5. Click 2 NATIVO ────────────────────────────────────────────────────
    # Ri-cerca il pulsante (Vue potrebbe aver aggiornato il DOM).
    # NON usare scroll_into_view_if_needed: tra i due click l'elemento
    # potrebbe risultare not-visible per Vue -> timeout 20s.
    if _AU_DEBUG:
        print("  [AU_DEBUG] click 2 nativo (atteso campo ricerca)...")
    btn_el2, btn_sel2 = _find_btn()
    if btn_el2:
        try:
            btn_el2.click()
            if _AU_DEBUG:
                print(f"  [AU_DEBUG] click 2 eseguito su: {btn_sel2}")
        except Exception as _ex:
            if _AU_DEBUG:
                print(f"  [AU_DEBUG] errore click 2 nativo: {_ex}")
            # Fallback JS per click 2
            try:
                page.evaluate(
                    "() => {"
                    "  const sels = ["
                    "    'button.input-group-text.btn-dark-gray2',"
                    "    'button.btn-dark-gray2',"
                    "  ];"
                    "  for (const s of sels) {"
                    "    const el = document.querySelector(s);"
                    "    if (el) { el.click(); return true; }"
                    "  }"
                    "  const ico = document.querySelector("
                    "    'i.fa-search, .fas.fa-search'"
                    "  );"
                    "  if (ico) {"
                    "    const btn = ico.closest('button');"
                    "    if (btn) { btn.click(); return true; }"
                    "  }"
                    "  return false;"
                    "}"
                )
                if _AU_DEBUG:
                    print("  [AU_DEBUG] fallback JS click 2 eseguito")
            except Exception as _ex2:
                if _AU_DEBUG:
                    print(f"  [AU_DEBUG] errore fallback JS click 2: {_ex2}")
    else:
        if _AU_DEBUG:
            print("  [AU_DEBUG] pulsante lente non trovato per click 2 -> fallback JS")
        try:
            page.evaluate(
                "() => {"
                "  const sels = ["
                "    'button.input-group-text.btn-dark-gray2',"
                "    'button.btn-dark-gray2',"
                "  ];"
                "  for (const s of sels) {"
                "    const el = document.querySelector(s);"
                "    if (el) { el.click(); return true; }"
                "  }"
                "  return false;"
                "}"
            )
            if _AU_DEBUG:
                print("  [AU_DEBUG] fallback JS click 2 eseguito")
        except Exception as _ex:
            if _AU_DEBUG:
                print(f"  [AU_DEBUG] errore fallback JS click 2: {_ex}")

    # Attendi che Vue mostri il campo
    page.wait_for_timeout(700)

    found = _input_visible()
    if found:
        if _AU_DEBUG:
            print(f"  [AU_DEBUG] input visibile dopo click 2: {found}")
        return True

    # Tentativo finale: wait_for_selector
    for sel in INPUT_SELS:
        try:
            page.wait_for_selector(sel, timeout=4000, state='visible')
            if _AU_DEBUG:
                print(f"  [AU_DEBUG] input visibile (wait): {sel}")
            return True
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

    # Debug finale: screenshot + dump DOM
    if _AU_DEBUG:
        try:
            page.screenshot(path="au_debug_screenshot.png")
            html = page.content()
            with open("au_debug_dom.html", "w", encoding="utf-8") as _f:
                _f.write(html)
            print("  [AU_DEBUG] screenshot -> au_debug_screenshot.png")
            print("  [AU_DEBUG] DOM        -> au_debug_dom.html")
            inputs = page.evaluate(
                "() => Array.from(document.querySelectorAll('input'))"
                ".map(el => ({cls: el.className, ph: el.placeholder,"
                "             vis: el.offsetParent !== null}))"
            )
            print(f"  [AU_DEBUG] Input nel DOM ({len(inputs)}):")
            for inp in inputs[:10]:
                print(f"    class='{inp['cls']}'  placeholder='{inp['ph']}'  visible={inp['vis']}")
            btns = page.evaluate(
                "() => Array.from(document.querySelectorAll('button'))"
                ".map(b => ({cls: b.className, type: b.type,"
                "           txt: b.innerText.trim().slice(0,40)}))"
            )
            print(f"  [AU_DEBUG] Button nel DOM ({len(btns)}):")
            for b in btns[:10]:
                print(f"    class='{b['cls']}'  type='{b['type']}'  text='{b['txt']}'")
        except Exception as _ex:
            print(f"  [AU_DEBUG] Errore dump: {_ex}")

    return False

_HDR_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}



def search_animeunity(query: str, silent: bool = False) -> List[Dict]:
    """
    Cerca anime su AnimeUnity per titolo.
    Fast-path: X-Inertia su /archivio (JSON, paginazione auto).
    Fallback:  Playwright su /archivio (XHR intercept + DOM scraping).
    """
    # [FIX] Recupera X-Inertia-Version reale dal body HTML (data-page JSON)
    _au_inertia_ver_ = "1"
    try:
        import urllib.request as _ur_fix_
        import re as _re_fix_
        import html as _html_fix_
        import json as _json_fix_
        _vreq_ = _ur_fix_.Request(
            "https://www.animeunity.so/archivio",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                     "Accept-Language": "it-IT,it;q=0.9"}
        )
        with _ur_fix_.urlopen(_vreq_, timeout=10) as _vr_:
            _vbody_ = _vr_.read().decode("utf-8", errors="replace")
        _vm_ = (_re_fix_.search(r'data-page="([^"]+)"', _vbody_)
                or _re_fix_.search(r"data-page='([^']+)'", _vbody_))
        if _vm_:
            _vdata_ = _json_fix_.loads(_html_fix_.unescape(_vm_.group(1)))
            _au_inertia_ver_ = str(_vdata_.get("version", "1") or "1")
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] X-Inertia-Version reale: {_au_inertia_ver_}')
    except Exception as _vex_:
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] version-fetch fallita ({_vex_}), uso default 1')

    _BASE_AU = "https://www.animeunity.so"

    if not silent:
        print()
        print(f"  [*] Ricerca '{query}' su AnimeUnity.so...")
        print()

    # ── Fast-path urllib: DISABILITATO ──────────────────────────────────────
    # AnimeUnity è protetto da Cloudflare (cf_clearance cookie).
    # urllib non supera il JS challenge → risposta sempre HTML.
    # Il JSON X-Inertia è accessibile SOLO tramite browser (Playwright).
    if _AU_DEBUG:
        print(f'  [AU_DEBUG] fast-path urllib: SKIP (CF protection — uso Playwright)')

    # ── Fallback: Playwright ─────────────────────────────────────────────────
    if not HAS_PLAYWRIGHT:
        if not silent:
            show_error("Playwright obbligatorio per la ricerca AnimeUnity (fallback).")
        return []

    results: List[Dict] = []
    try:
        from urllib.parse import urlencode as _urlencode
        import json as _json_fb
        import re   as _re
        import html as _html_lib

        _archivio_url = f"{_BASE_AU}/archivio?{_urlencode({'title': query})}"
        _PW_UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

        # ── helper ──────────────────────────────────────────────────────────
        def _pg_url(pg) -> str:
            try:    return pg.url or ""
            except: return ""

        def _pg_alive(pg) -> bool:
            try:    return not pg.is_closed()
            except: return False

        def _safe_w(pg, ms: int) -> None:
            try:
                if _pg_alive(pg): pg.wait_for_timeout(ms)
            except: pass

        def _extract_items(obj, depth=0):
            """Naviga ricorsivamente il JSON e restituisce la lista anime."""
            if depth > 12:
                return None
            if isinstance(obj, list) and obj:
                if any(isinstance(x, dict) and any(k in x for k in ("id","title","title_it","slug")) for x in obj):
                    return obj
            if isinstance(obj, dict):
                for k in ("data","records","anime","animes","results","items","list","collection"):
                    v = obj.get(k)
                    if v is not None:
                        found = _extract_items(v, depth + 1)
                        if found:
                            return found
                for k, v in obj.items():
                    if k in ("data","records","anime","animes","results","items","list","collection"):
                        continue
                    if isinstance(v, (dict, list)):
                        found = _extract_items(v, depth + 1)
                        if found:
                            return found
            return None

        def _build_result(anime_list):
            """Costruisce la lista risultati dal JSON AnimeUnity."""
            out = []
            seen_ids = set()
            for _a in anime_list:
                if not isinstance(_a, dict):
                    continue
                _t = (
                    (_a.get("title_it")  or "").strip()
                    or (_a.get("title")  or "").strip()
                    or (_a.get("title_eng") or "").strip()
                    or (_a.get("name")   or "").strip()
                )
                _id = str(_a.get("id", "")).strip()
                _sl = str(_a.get("slug", "")).strip()
                if not _t or not _id:
                    continue
                if _id in seen_ids:
                    continue
                seen_ids.add(_id)
                _lnk = f"{_BASE_AU}/anime/{_id}/{_sl}" if _sl else f"{_BASE_AU}/anime/{_id}"
                _at  = str(_a.get("type",           "") or "")
                _ay  = str(_a.get("date",           "") or "")
                _ae  = str(_a.get("episodes_count", "") or "")
                _lp  = [p for p in [_at, _ay] if p]
                _lb  = " | ".join(_lp)
                _dp  = f"{_t} [{_lb}]" if _lb else _t
                out.append({
                    "title":     _dp,
                    "link":      _lnk,
                    "raw_title": _t,
                    "year":      _ay,
                    "type":      _at,
                    "episodes":  _ae,
                })
            return out

        # JS DOM scraping (usa new RegExp — nessun backslash Python)
        _JS_CARDS = (
            "() => {"
            "var res=[]; var seen={};"
            "var cards=Array.from(document.querySelectorAll("
            "  'article,.anime-card,.card,[class*=card],[class*=anime-item]'"
            "));"
            "if(!cards.length){"
            "  var links=Array.from(document.querySelectorAll('a[href*=\"/anime/\"]'));"
            "  links.forEach(function(a){"
            "    var h=a.href||'';"
            "    if(!h||seen[h])return; var _ap_=h.split('/anime/'); if(_ap_.length<2||!/^[0-9]/.test(_ap_[1]))return; seen[h]=true;"
            "    var c=a; for(var j=0;j<6;j++){"
            "      var cn=c.className||'';"
            "      if(cn.indexOf('card')>-1||cn.indexOf('item')>-1||c.tagName==='ARTICLE')break;"
            "      c=c.parentElement||c;}"
            "    var te=c.querySelector('h3,h4,h5,.title,[class*=title]')||a;"
            "    var tt=(te.textContent||'').trim()||a.title||'';"
            "    var ct=(c.textContent||'').trim();"
            "    var ym=ct.match(new RegExp('(19|20)[0-9]{2}'));"
            "    var tm=ct.match(new RegExp('(TV|Movie|OVA|ONA|Special)','i'));"
            "    var em=ct.match(new RegExp('([0-9]+)[ ]*ep','i'));"
            "    res.push({title:tt,link:h,year:ym?ym[0]:'',type:tm?tm[1]:'',episodes:em?em[1]:''});"
            "  }); return res;}"
            "cards.forEach(function(c){"
            "  var a=c.querySelector('a[href*=\"/anime/\"]');"
            "  if(!a)return;"
            "  var h=a.href||'';"
            "  if(!h||seen[h])return; seen[h]=true;"
            "  var te=c.querySelector('h3,h4,h5,.title,[class*=title]')||a;"
            "  var tt=(te.textContent||'').trim()||a.title||'';"
            "  var ct=(c.textContent||'').trim();"
            "  var ym=ct.match(new RegExp('(19|20)[0-9]{2}'));"
            "  var tm=ct.match(new RegExp('(TV|Movie|OVA|ONA|Special)','i'));"
            "  var em=ct.match(new RegExp('([0-9]+)[ ]*ep','i'));"
            "  res.push({title:tt,link:h,year:ym?ym[0]:'',type:tm?tm[1]:'',episodes:em?em[1]:''});"
            "}); return res;}"
        )

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = browser.new_context(
                user_agent=_PW_UA, locale="it-IT",
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.set_default_timeout(30000)

            # _xhr_data inizializzato QUI, prima di page.on()
            _xhr_data: list = []

            def _on_response(resp):
                try:
                    _ru = resp.url or ""
                    _rh = resp.headers or {}
                    _ct = _rh.get("content-type", "")
                    _xi = _rh.get("x-inertia", "")
                    if "archivio" in _ru and ("application/json" in _ct or _xi == "true"):
                        try:
                            _xhr_data.append(resp.json())
                        except Exception as _dbg_ex_:
                            if _AU_DEBUG:
                                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

            # page.on() registrato al livello corretto
            page.on("response", _on_response)

            try:
                try:
                    # [FIX #7] Pre-navigazione HOME per cf_clearance
                    if _AU_DEBUG:
                        print('  [AU_DEBUG] CF pre-nav: goto HOME per cf_clearance')
                    try:
                        page.goto('https://www.animeunity.so',
                                  wait_until='domcontentloaded', timeout=30000)
                        page.wait_for_timeout(4000)
                        _cfht_ = ''
                        try: _cfht_ = (page.title() or '') if not page.is_closed() else ''
                        except: pass
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] HOME ok | title: {_cfht_[:60]}')
                        if any(k in _cfht_.lower() for k in
                               ('just a moment', 'checking your browser', 'challenge')):
                            if _AU_DEBUG:
                                print('  [AU_DEBUG] CF challenge rilevato — attendo 6s')
                            page.wait_for_timeout(6000)
                    except Exception as _cfhe_:
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] HOME nav err: {_cfhe_}')
                    page.goto(_archivio_url, wait_until="domcontentloaded", timeout=20000)
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

                _alive     = [p for p in list(ctx.pages) if _pg_alive(p)]
                _page_arch = next((p for p in _alive if "archivio" in _pg_url(p)), None)
                page       = _page_arch or (_alive[0] if _alive else page)

                # Metodo 1: XHR Inertia catturati durante goto
                if _xhr_data:
                    for _xd in _xhr_data:
                        _items = _extract_items(_xd)
                        if _items:
                            results = _build_result(_items)
                            break

                # Metodo 2: fetch() in-browser via page.evaluate()
                # MOTIVO: page.request.get() NON usa cf_clearance → risposta HTML
                #         fetch() nel browser USA tutti i cookies → risposta JSON
                if not results and _pg_alive(page):
                    try:
                        from urllib.parse import urlencode as _ue2
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] M2: fetch() in-browser url={_archivio_url}')
                        # JS: fetch con X-Inertia headers (browser usa cf_clearance automaticamente)
                        _m2_js = (
                            "async () => {"
                            "  try {"
                            "    // Leggi XSRF-TOKEN da document.cookie"
                            "    var xsrf = '';"
                            "    document.cookie.split(';').forEach(function(c){"
                            "      var p=c.trim().split('=');"
                            "      if(p[0].toLowerCase().indexOf('xsrf')>-1) xsrf=decodeURIComponent(p.slice(1).join('='));"
                            "    });"
                            "    var hdrs = {"
                            "      'X-Inertia': 'true',"
                            "      'X-Inertia-Version': '" + _au_inertia_ver_ + "',"
                            "      'Accept': 'application/json, text/plain, */*',"
                            "      'X-Requested-With': 'XMLHttpRequest'"
                            "    };"
                            "    if(xsrf) hdrs['X-XSRF-TOKEN'] = xsrf;"
                            "    var r = await fetch('" + _archivio_url + "', {"
                            "      headers: hdrs, credentials: 'include'"
                            "    });"
                            "    var ct = r.headers.get('content-type') || '';"
                            "    if (ct.indexOf('json') > -1) {"
                            "      return {ok: true, status: r.status, json: await r.json(), xsrf: xsrf};"
                            "    } else {"
                            "      var txt = await r.text();"
                            "      return {ok: false, status: r.status, preview: txt.substring(0,120), xsrf: xsrf};"
                            "    }"
                            "  } catch(e) { return {ok: false, err: e.toString()}; }"
                            "})()"
                        )
                        _m2_res = page.evaluate(_m2_js)
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] M2: ok={_m2_res.get("ok")} status={_m2_res.get("status")} xsrf={str(_m2_res.get("xsrf",""))[:20]!r} preview={str(_m2_res.get("preview",""))[:80]!r}')
                        if _m2_res.get("ok") and _m2_res.get("json"):
                            _j2 = _m2_res["json"]
                            _i2 = _extract_items(_j2)
                            if _i2:
                                results = _build_result(_i2)
                                # paginazione M2
                                # Calcola last_page da struttura JSON AnimeUnity (vari formati)
                                _m2_props = _j2.get("props", {}) if isinstance(_j2, dict) else {}
                                _m2_aob   = _m2_props.get("animes", {})
                                if isinstance(_m2_aob, dict):
                                    _m2_lp = int(_m2_aob.get("last_page", 1) or 1)
                                elif isinstance(_j2, dict):
                                    # Fallback: cerca last_page in tutto il JSON
                                    _m2_lp = int(_j2.get("last_page", 1) or 1)
                                else:
                                    _m2_lp = 1
                                if _AU_DEBUG:
                                    _m2_tot = (_m2_aob.get("total","?") if isinstance(_m2_aob,dict)
                                               else _j2.get("total","?") if isinstance(_j2,dict) else "?")
                                    print(f'  [AU_DEBUG] M2: last_page={_m2_lp} total={_m2_tot} items_p1={len(_i2)}')
                                for _m2p in range(2, _m2_lp + 1):
                                    if not _pg_alive(page):
                                        break
                                    _url_p = f"{_BASE_AU}/archivio?{_ue2({'title': query, 'page': _m2p})}"
                                    if _AU_DEBUG:
                                        print(f'  [AU_DEBUG] M2 pagina {_m2p}/{_m2_lp}')
                                    _m2_js_p = (
                                        "async () => {"
                                        "  try {"
                                        "    var r = await fetch('" + _url_p + "', {"
                                        "      headers: {"
                                        "        'X-Inertia': 'true',"
                                        "        'X-Inertia-Version': '" + _au_inertia_ver_ + "',"
                                        "        'Accept': 'application/json, text/plain, */*',"
                                        "        'X-Requested-With': 'XMLHttpRequest'"
                                        "      }, credentials: 'include'"
                                        "    });"
                                        "    var ct = r.headers.get('content-type') || '';"
                                        "    if (ct.indexOf('json') > -1) return {ok: true, json: await r.json()};"
                                        "    return {ok: false};"
                                        "  } catch(e) { return {ok: false, err: e.toString()}; }"
                                        "})()"
                                    )
                                    try:
                                        _rp = page.evaluate(_m2_js_p)
                                        if _rp.get("ok") and _rp.get("json"):
                                            _ip = _extract_items(_rp["json"])
                                            if _ip:
                                                results.extend(_build_result(_ip))
                                    except Exception as _dbg_ex_:
                                        if _AU_DEBUG:
                                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                    except Exception as _dbg_ex_:
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

                # Metodo 3: data-page nel DOM
                if not results and _pg_alive(page):
                    try:
                        _html = page.content()
                        _m_dp = (
                            _re.search(r'data-page="([^"]+)"', _html)
                            or _re.search(r"data-page='([^']+)'", _html)
                        )
                        if _m_dp:
                            _i3 = _extract_items(_json_fb.loads(_html_lib.unescape(_m_dp.group(1))))
                            if _i3:
                                results = _build_result(_i3)
                    except Exception as _dbg_ex_:
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

                # Metodo 4: DOM scraping card (last resort)
                if not results:
                    if not _pg_alive(page):
                        page = ctx.new_page()
                        try:
                            page.goto(_archivio_url, wait_until="domcontentloaded", timeout=20000)
                        except Exception as _dbg_ex_:
                            if _AU_DEBUG:
                                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                        _safe_w(page, 6000)

                    if _pg_alive(page):
                        for _sel in ["article.anime-card","div.anime-card",".card","a[href*='/anime/']"]:
                            try:
                                page.wait_for_selector(_sel, timeout=8000)
                                if _AU_DEBUG:
                                    print(f'  [AU_DEBUG] M4: selettore trovato: {_sel}')
                                break
                            except Exception as _dbg_ex_:
                                if _AU_DEBUG:
                                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                        _safe_w(page, 500)
                        # Scroll infinito per caricare tutti i risultati
                        # AnimeUnity: 15 anime per batch, scroll → carica batch successivo
                        if _pg_alive(page):
                            try:
                                _prev_h  = 0
                                _prev_ct = 0
                                _stable  = 0
                                for _sc in range(30):   # max 30 scroll = max ~450 risultati
                                    _cur_h  = page.evaluate("document.body.scrollHeight")
                                    _cur_ct = page.evaluate(
                                        "document.querySelectorAll('a[href*=\'/anime/\']').length"
                                    )
                                    if _AU_DEBUG:
                                        print(f'  [AU_DEBUG] M4: scroll {_sc+1} — h={_cur_h} items={_cur_ct}')
                                    # Stabile per 3 iterazioni consecutive → stop
                                    if _cur_h == _prev_h and _cur_ct == _prev_ct:
                                        _stable += 1
                                        if _stable >= 3:
                                            break
                                    else:
                                        _stable = 0
                                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                    _safe_w(page, 2500)   # attendi caricamento batch (lazy load)
                                    try:
                                        page.wait_for_load_state("networkidle", timeout=3000)
                                    except Exception as _dbg_ex_:
                                        if _AU_DEBUG:
                                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                                    _prev_h  = _cur_h
                                    _prev_ct = _cur_ct
                                if _AU_DEBUG:
                                    _final_ct = page.evaluate(
                                        "document.querySelectorAll('a[href*=\"/anime/\"]').length"
                                    )
                                    print(f'  [AU_DEBUG] M4: scroll completato ({_sc+1} iter) — {_final_ct} links totali')
                                # Retry M3 (data-page) dopo scroll: Vue potrebbe aver idratato il DOM
                                if not results and _pg_alive(page):
                                    try:
                                        _html_post = page.content()
                                        _m_dp2 = (
                                            _re.search(r'data-page="([^"]+)"', _html_post)
                                            or _re.search(r"data-page='([^']+)'", _html_post)
                                        )
                                        if _m_dp2:
                                            _i3b = _extract_items(_json_fb.loads(_html_lib.unescape(_m_dp2.group(1))))
                                            if _i3b:
                                                results = _build_result(_i3b)
                                                if _AU_DEBUG:
                                                    print(f'  [AU_DEBUG] M3b (post-scroll data-page): {len(results)} risultati')
                                    except Exception as _dbg_ex_:
                                        if _AU_DEBUG:
                                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
                            except Exception as _dbg_ex_:
                                if _AU_DEBUG:
                                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

                    if _pg_alive(page):
                        try:
                            for item in page.evaluate(_JS_CARDS):
                                t   = (item.get("title","") or "").strip()
                                lnk = (item.get("link", "") or "").strip()
                                if not t or not lnk:
                                    continue
                                if not lnk.startswith("http"):
                                    lnk = _BASE_AU + ("" if lnk.startswith("/") else "/") + lnk
                                _at = item.get("type","")
                                _ay = item.get("year","")
                                _lp = [p for p in [_at, _ay] if p]
                                _lb = " | ".join(_lp)
                                results.append({
                                    "title":     f"{t} [{_lb}]" if _lb else t,
                                    "link":      lnk,
                                    "raw_title": t,
                                    "year":      _ay,
                                    "type":      _at,
                                    "episodes":  item.get("episodes",""),
                                })
                        except Exception as _e4:
                            if not silent:
                                show_warning(f"Playwright DOM AU: {_e4}")

            except Exception as ex:
                if not silent:
                    show_warning(f"Playwright /archivio AU: {ex}")
            finally:
                try:
                    browser.close()
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

    except Exception as ex:
        if not silent:
            show_error(f"Playwright AU: {ex}")

    # Deduplicazione finale per link
    if results:
        _seen_links = set()
        _deduped    = []
        for _r in results:
            _rl = (_r.get("link") or "").strip().rstrip("/")
            if _rl and _rl not in _seen_links:
                _seen_links.add(_rl)
                _deduped.append(_r)
        results = _deduped
        if _AU_DEBUG:
            print(f'  [AU_DEBUG] risultati dopo dedup: {len(results)}')

    if results and not silent:
        print(f"  Trovati {len(results)} risultati")

    return results


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
            except Exception as _dbg_ex_:
                if _AU_DEBUG:
                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(12_000)

    def close(self) -> None:
        """Chiude browser e sessione Playwright."""
        for obj, method in [(self._browser, "close"), (self._pw, "stop")]:
            if obj:
                try:
                    getattr(obj, method)()
                except Exception as _dbg_ex_:
                    if _AU_DEBUG:
                        print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
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
            except Exception as _dbg_ex_:
                if _AU_DEBUG:
                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')
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
        except Exception as _dbg_ex_:
            if _AU_DEBUG:
                print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

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
            except Exception as _dbg_ex_:
                if _AU_DEBUG:
                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

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
                    except Exception as _dbg_ex_:
                        if _AU_DEBUG:
                            print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

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
            except Exception as _dbg_ex_:
                if _AU_DEBUG:
                    print(f'  [AU_DEBUG] Exception {type(_dbg_ex_).__name__}: {_dbg_ex_}')

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
