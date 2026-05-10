# scripts/core/browser.py
# [MODIFICA run#1] path-guard posizionato PRIMA di ogni import interno
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)


def _import_error_msg(pkg: str) -> str:
    return (
        f"\n[ERRORE] Dipendenza mancante: '{pkg}'\n"
        f"Installa con:  pip install {pkg}\n"
        f"Per playwright aggiungi: playwright install chromium\n"
    )


_playwright_available = False
try:
    from playwright.sync_api import sync_playwright
    _playwright_available = True
except ImportError:
    pass

_instance = None


class BrowserManager:
    """Wrapper singleton per Playwright (opzionale)."""

    def __init__(self):
        self._available = _playwright_available

    def is_available(self) -> bool:
        return self._available

    def get_browser(self, headless: bool = True):
        if not self._available:
            print(_import_error_msg("playwright"))
            return None
        pw = sync_playwright().start()
        return pw.chromium.launch(headless=headless)


def get() -> BrowserManager:
    global _instance
    if _instance is None:
        _instance = BrowserManager()
    return _instance
