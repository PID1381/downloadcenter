# scripts/core/link_extractor.py
# [MODIFICA run#1] Aggiunto path-guard + gestione OSError in save_links()
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import re
import os

try:
    import requests as _requests
    _requests_available = True
except ImportError:
    _requests_available = False


def extract_links(url: str, pattern: str = r'https?://[^\s"\'<>]+') -> list:
    """Scarica la pagina e restituisce i link che corrispondono al pattern."""
    if not _requests_available:
        print("[ERRORE] 'requests' non installato. Esegui: pip install requests")
        return []
    try:
        resp = _requests.get(url, timeout=15)
        resp.raise_for_status()
        return re.findall(pattern, resp.text)
    except Exception as exc:
        print(f"[ERRORE] extract_links: {exc}")
        return []


def filter_links(links: list, keyword: str) -> list:
    """Filtra i link che contengono la keyword (case-insensitive)."""
    kw = keyword.lower()
    return [lnk for lnk in links if kw in lnk.lower()]


def save_links(links: list, output_path: str) -> bool:
    """
    Salva i link in un file di testo, uno per riga.
    [MODIFICA run#1] Aggiunta gestione OSError/PermissionError.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(links))
        return True
    except OSError as exc:
        print(f"[ERRORE] save_links – impossibile scrivere '{output_path}': {exc}")
        return False
