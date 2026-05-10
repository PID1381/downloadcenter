# scripts/core/settings_core.py
# [MODIFICA run#1] Aggiunto path-guard block + resolve() su tutti i path derivati da __file__
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import os

# ── Colori ANSI ─────────────────────────────────────────────────────────────
COLORS = {
    "red":     "\033[91m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "blue":    "\033[94m",
    "magenta": "\033[95m",
    "cyan":    "\033[96m",
    "white":   "\033[97m",
    "reset":   "\033[0m",
    "bold":    "\033[1m",
}

def colorize(text: str, color: str) -> str:
    """Restituisce la stringa colorata con codici ANSI."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"

# ── Path globali ─────────────────────────────────────────────────────────────
# [MODIFICA run#1] Uso di os.path.realpath per risolvere symlink
BASE_DIR     = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.realpath(os.path.dirname(os.path.dirname(BASE_DIR)))
TEMP_DIR     = os.path.join(PROJECT_ROOT, "scripts", "temp")
LOG_FILE     = os.path.join(TEMP_DIR, "app.log")
PREFS_FILE   = os.path.join(TEMP_DIR, "prefs.json")
URLS_CONFIG  = os.path.join(TEMP_DIR, "urls_config.json")

# Crea TEMP_DIR se non esiste
os.makedirs(TEMP_DIR, exist_ok=True)
