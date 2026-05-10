# scripts/anime/moduli/AnimeWorld/handlers_animeworld.py
# [MODIFICA run#1] Aggiunto path-guard + try/except ImportError per 'requests'
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(
        _os.path.dirname(
            _os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__))
            )
        )
    )
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import re
from scripts.core.settings_core import colorize

try:
    import requests as _requests
    _requests_ok = True
except ImportError:
    _requests_ok = False

_BASE_URL = "https://www.animeworld.ac"


def _display_results(links: list) -> None:
    if not links:
        print(colorize("Nessun risultato trovato.", "yellow"))
        return
    for i, lnk in enumerate(links, 1):
        print(f"  {i}) {lnk}")


def search_anime(query: str) -> list:
    """Cerca anime su AnimeWorld. Restituisce lista di URL risultato."""
    if not _requests_ok:
        print("[ERRORE] 'requests' non installato. Esegui: pip install requests")
        return []
    try:
        url  = f"{_BASE_URL}/search?keyword={query}"
        resp = _requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return re.findall(r'href="(/play/[^"]+)"', resp.text)
    except Exception as exc:
        print(colorize(f"[ERRORE] search_anime: {exc}", "red"))
        return []


def latest_releases() -> list:
    """Recupera le ultime uscite da AnimeWorld."""
    if not _requests_ok:
        print("[ERRORE] 'requests' non installato. Esegui: pip install requests")
        return []
    try:
        resp = _requests.get(_BASE_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return re.findall(r'href="(/play/[^"]+)"', resp.text)
    except Exception as exc:
        print(colorize(f"[ERRORE] latest_releases: {exc}", "red"))
        return []


def run() -> None:
    """Entry point AnimeWorld."""
    while True:
        print(colorize("\n── AnimeWorld ──", "cyan"))
        print("  1) Cerca anime")
        print("  2) Ultime uscite")
        print("  0) Indietro")

        choice = input("Scelta: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            q = input("Titolo da cercare: ").strip()
            if q:
                _display_results(search_anime(q))
        elif choice == "2":
            _display_results(latest_releases())
        else:
            print(colorize("Scelta non valida.", "red"))
