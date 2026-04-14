#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anime_engine.py v2.3 - COMPLETO CON URL MANAGER
Download Center - scripts/anime/anime_engine.py

VERSIONE: 2.3 (rispetto a v2.2)
  [NEW]      Integrazione URL Manager centralizzato
             - BASE_URL e SEARCH_URL letti dinamicamente da url_mgr
             - Fallback ai valori hardcoded se url_mgr non disponibile
  [MANTIENE] Tutta la struttura v2.2 invariata
  [COMPAT]   100% backward-compatible

COMPATIBILITÀ:
  ✓ estrai_link_anime.py v4.0+
  ✓ watchlist.py v7.4+
  ✓ ricerca_scheda_anime.py v3.5+
  ✓ scan_local_series.py v2.5+
  ✓ handlers.py v3.0+
  ✓ URL Manager centralizzato
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

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    requests = None
    BeautifulSoup = None
    HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    sync_playwright = None
    HAS_PLAYWRIGHT = False

# ════════════════════════════════════════════════════════════════════════════
# COSTANTI GLOBALI CON URL MANAGER
# ════════════════════════════════════════════════════════════════════════════

_TEMP_DIR = Path(__file__).parent.parent / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)
_PREFS_FILE = _TEMP_DIR / "prefs.json"

WIDTH = 56

# ── URL Base: Tenta di usare url_mgr, fallback a hardcoded ────────────────
try:
    from core.url_manager import url_mgr
    BASE_URL = url_mgr.get("animeworld", "https://www.animeworld.ac")
    SEARCH_URL = url_mgr.get("animeworld_search", BASE_URL + "/search")
except ImportError:
    # Fallback se url_mgr non disponibile
    BASE_URL = "https://www.animeworld.ac"
    SEARCH_URL = BASE_URL + "/search"

VIDEO_EXT: Tuple[str, ...] = (
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts",
    ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp", ".ogv", ".m3u8",
    ".vob", ".f4v", ".asf", ".rm", ".rmvb",
)

BLOCK_EXTS: Tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".css", ".woff", ".woff2", ".ttf", ".eot", ".otf",
)

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

COOKIE_TEXTS: List[str] = [
    "continua", "accetta", "accept", "ok", "agree",
    "accetto", "allow all", "allow cookies", "got it",
]

# ════════════════════════════════════════════════════════════════════════════
# UI / DISPLAY FUNCTIONS
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
# INPUT / INTERACTION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def ask_yes_no(question: str) -> bool:
    while True:
        response = input(f"  {question} (s/n): ").strip().lower()
        if response in ("s", "si", "y", "yes"):
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
# FILE / PATH FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", filename).strip()[:200]

def clean_path(path_str: str) -> str:
    return path_str.strip().strip('"').strip("'").strip()

def clean_unc_path(path_str: str) -> str:
    path_str = path_str.strip()
    if (path_str.startswith('"') and path_str.endswith('"')) or \
       (path_str.startswith("'") and path_str.endswith("'")):
        path_str = path_str[1:-1]
    return path_str.strip()

def path_exists_safe(path_str: str) -> bool:
    try:
        p = Path(path_str)
        return p.exists()
    except Exception:
        try:
            return os.path.exists(path_str) and os.path.isdir(path_str)
        except Exception:
            return False

def iterdir_safe(path_str: str) -> List[Path]:
    try:
        p = Path(path_str)
        if not p.is_dir():
            return []
        return sorted(p.iterdir())
    except PermissionError:
        show_error(f"Permesso negato: {path_str}")
        return []
    except OSError as e:
        show_error(f"Errore rete/accesso: {e}")
        return []
    except Exception as e:
        show_error(f"Errore iterazione: {e}")
        return []

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
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False

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
        else f"anime_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    fp = dest / f"{nome}.txt"
    cnt = 1
    while fp.exists():
        fp = dest / f"{nome}_{cnt}.txt"
        cnt += 1
    return fp if save_urls_to_file(links, str(fp)) else Path("")

# ════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
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
    filled = int(length * current // total)
    chars = ["◐", "◓", "◑", "◒"]
    anim = chars[int(time.time() * 4) % 4]
    bar = "█" * filled + "░" * (length - filled)
    print(f"\r  {prefix}: |{bar}| {percent:.1f}% {anim}", end="", flush=True)

def is_video(url: str) -> bool:
    clean = url.lower().split("?")[0].split("#")[0]
    return any(clean.endswith(ext) for ext in VIDEO_EXT)

def parse_episode_selection(text: str, max_ep: int) -> List[int]:
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
    if total <= 0:
        return
    pct = 100.0 * current / total
    filled = int(bar_length * current // total)
    bar = "█" * filled + "░" * (bar_length - filled)
    w = len(str(total))
    if start_time is not None and current > 0:
        elapsed = time.time() - start_time
        rem = elapsed * (total - current) / current
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

# ════════════════════════════════════════════════════════════════════════════
# INTERRUPT HANDLER
# ════════════════════════════════════════════════════════════════════════════

interrupted: threading.Event = threading.Event()
_original_sigint_handler = None

def setup_interrupt() -> None:
    global _original_sigint_handler
    interrupted.clear()
    def _handler(sig, frame):
        interrupted.set()
        print(
            "\n\n  [!] Interruzione ricevuta - "
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

def setup_interrupt_global() -> None:
    setup_interrupt()

def teardown_interrupt_global() -> None:
    teardown_interrupt()

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION FUNCTIONS
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

def get_headless_mode() -> bool:
    return load_prefs().get("browser_headless", False)

# ════════════════════════════════════════════════════════════════════════════
# SEARCH FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def search_animeworld(query: str, silent: bool = False) -> List[Dict]:
    if not HAS_REQUESTS:
        if not silent:
            show_error("'requests' non installato - ricerca non disponibile")
        return []
    try:
        if not silent:
            print()
            print(f"  [*] Ricerca '{query}' su AnimeWorld.ac...")
            print()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(
            SEARCH_URL, params={"keyword": query}, headers=headers, timeout=15
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
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
                link = urljoin(BASE_URL, link)
            category = "SUB-ITA"
            status_div = inner.find("div", class_="status")
            if status_div:
                cat_div = status_div.find("div", class_=re.compile(r"ova|movie|special"))
                if cat_div:
                    category = cat_div.get_text(strip=True).upper()
            results.append({
                "title": title + " - " + category,
                "link": link,
                "raw_title": title,
                "category": category,
            })
        return results
    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca: {e}")
        return []

# ════════════════════════════════════════════════════════════════════════════
# VIDEO EXTRACTOR CLASS (PLACEHOLDER)
# ════════════════════════════════════════════════════════════════════════════

class VideoExtractor:
    _HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    def __init__(self, url: str) -> None:
        self.url = url
        self.base_domain = urlparse(url).netloc
        self.visited: Set[str] = set()
        self.video_links: Set[str] = set()
        self.alt_links: Set[str] = set()
        self.related_links: Dict[str, str] = {}
        self.anime_title: Optional[str] = None
    def extract(self) -> bool:
        return bool(self.video_links)
    def get_all_links(self) -> List[str]:
        return sort_links_numerically(list(self.alt_links | self.video_links))

# ════════════════════════════════════════════════════════════════════════════
# BROWSER / PLAYWRIGHT FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

_HDR_BROWSER: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def extract_video_links(soup, base_url: str = BASE_URL) -> List[str]:
    """Estrae link video da BeautifulSoup."""
    found: Set[str] = set()
    a_alt = soup.find("a", id="alternativeDownloadLink")
    if a_alt:
        href = a_alt.get("href", "").strip()
        if href:
            found.add(href if href.startswith("http") else urljoin(base_url, href))
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href and href != "#":
            full = href if href.startswith("http") else urljoin(base_url, href)
            if is_video(full):
                found.add(full)
    for source in soup.find_all("source", src=True):
        src = source["src"].strip()
        if src:
            full = src if src.startswith("http") else urljoin(base_url, src)
            if is_video(full):
                found.add(full)
    for el in soup.find_all(attrs={"data-src": True}):
        data_src = el["data-src"].strip()
        if data_src:
            full = data_src if data_src.startswith("http") else urljoin(base_url, data_src)
            if is_video(full):
                found.add(full)
    return sort_links_numerically(list(found))

def extract_from_js(page) -> List[str]:
    """Fallback: esegue JavaScript sulla pagina per trovare link video."""
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

def extract_episode_links(soup, base_url: str = BASE_URL) -> List[str]:
    """Estrae URL episodi da pagina serie AnimeWorld."""
    links: Set[str] = set()
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
    if not links:
        for a in soup.find_all("a", href=re.compile(r"/play/.+/\w+")):
            h = a["href"]
            if "/play/" in h:
                links.add(h if h.startswith("http") else urljoin(base_url, h))
    return sort_links_numerically(list(links))

class PageSession:
    """Sessione Playwright ottimizzata per AnimeWorld."""
    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._cookie_dismissed = False
    def __enter__(self) -> "PageSession":
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
        headless = get_headless_mode()
        self._pw = sync_playwright().start()
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
        for ext in BLOCK_EXTS:
            try:
                self._ctx.route(f"**/*{ext}", lambda route, _e=ext: route.abort())
            except Exception:
                pass
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(12_000)
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
    def fetch_page_links(self, url: str) -> Tuple[str, List[str]]:
        if not self._page:
            raise RuntimeError("PageSession non aperta. Chiamare .open() prima.")
        titolo: str = ""
        video_links: List[str] = []
        if HAS_REQUESTS:
            try:
                resp = requests.get(url, headers=_HDR_BROWSER, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")
                for tag, kw in [("h1", {"class": "title"}), ("h1", {"id": "anime-title"})]:
                    el = soup.find(tag, kw)
                    if el:
                        titolo = el.get_text(strip=True)
                        break
                video_links = extract_video_links(soup, url)
                if video_links:
                    return titolo, video_links
            except Exception:
                pass
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.dismiss_cookies()
            self._page.wait_for_timeout(800)
            if HAS_REQUESTS:
                soup = BeautifulSoup(self._page.content(), "html.parser")
                for tag, kw in [("h1", {"class": "title"}), ("h1", {"id": "anime-title"})]:
                    el = soup.find(tag, kw)
                    if el:
                        titolo = el.get_text(strip=True)
                        break
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
        if not self._page:
            raise RuntimeError("PageSession non aperta. Chiamare .open() prima.")
        titolo: str = ""
        ep_links: List[str] = []
        if HAS_REQUESTS:
            try:
                resp = requests.get(url, headers=_HDR_BROWSER, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")
                for tag, kw in [("h1", {"class": "title"}), ("h1", {"id": "anime-title"})]:
                    el = soup.find(tag, kw)
                    if el:
                        titolo = el.get_text(strip=True)
                        break
                ep_links = extract_episode_links(soup, url)
                if ep_links:
                    return titolo, ep_links
            except Exception:
                pass
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
            if HAS_REQUESTS:
                soup = BeautifulSoup(self._page.content(), "html.parser")
                ep_links = extract_episode_links(soup, url)
                if not titolo:
                    for tag, kw in [("h1", {"class": "title"}), ("h1", {"id": "anime-title"})]:
                        el = soup.find(tag, kw)
                        if el:
                            titolo = el.get_text(strip=True)
                            break
        except Exception as ex:
            show_error(f"Errore fetch_all_episodes: {ex}")
        return titolo, ep_links

# ════════════════════════════════════════════════════════════════════════════
# EXPORT — PUBLIC API (60 SIMBOLI)
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    # UI / Display (8)
    "clear_screen", "show_header", "show_success", "show_error",
    "show_info", "show_warning", "print_separator", "print_double_separator",
    # Input (4)
    "ask_yes_no", "get_valid_choice", "get_path_input", "wait_enter",
    # File / Path (10)
    "sanitize_filename", "clean_path", "clean_unc_path",
    "path_exists_safe", "iterdir_safe",
    "load_urls_from_file", "save_urls_to_file", "get_safe_path",
    "ensure_folder", "save_links",
    # Utility (6)
    "sort_links_numerically", "normalize_url", "animate_progress",
    "is_video", "parse_episode_selection", "print_progress_eta",
    # Interrupt (5)
    "interrupted", "setup_interrupt", "teardown_interrupt",
    "setup_interrupt_global", "teardown_interrupt_global",
    # Config (4)
    "load_prefs", "save_prefs", "get_link_dir", "get_headless_mode",
    # Search (1)
    "search_animeworld",
    # Classes (2)
    "VideoExtractor", "PageSession",
    # Browser (3)
    "extract_video_links", "extract_from_js", "extract_episode_links",
    # Costanti (7)
    "WIDTH", "BASE_URL", "SEARCH_URL", "VIDEO_EXT", "BLOCK_EXTS",
    "COOKIE_SEL", "COOKIE_TEXTS",
    # Flags (2)
    "HAS_REQUESTS", "HAS_PLAYWRIGHT",
]

if __name__ == "__main__":
    print()
    print("=" * 56)
    print("  ANIME ENGINE v2.3 - URL MANAGER INTEGRATION")
    print("=" * 56)
    print()
    print(f"  BASE_URL: {BASE_URL}")
    print(f"  SEARCH_URL: {SEARCH_URL}")
    print()
    print(f"  Esportazioni __all__: {len(__all__)} simboli")
    print(f"  HAS_REQUESTS: {HAS_REQUESTS}")
    print(f"  HAS_PLAYWRIGHT: {HAS_PLAYWRIGHT}")
    print()
