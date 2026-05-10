# scripts/core/startup_check.py
# [MODIFICA run#1] Aggiunto path-guard; stub check_pending_downloads dichiarato
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import json
import time
import os

from scripts.core.settings_core import PREFS_FILE, colorize


def _check_dependencies() -> list:
    """Verifica dipendenze opzionali; restituisce lista di quelle mancanti."""
    missing = []
    for pkg in ("requests", "playwright", "yt_dlp"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing


def _check_pending_downloads() -> None:
    """
    [STUB] – Aggiunta minima per consentire compilazione/testing.
    Implementazione reale da definire nel layer download.
    """
    pass


def _cleanup_cache() -> None:
    """Rimuove file temporanei più vecchi di 7 giorni."""
    temp_dir = os.path.join(_PROJECT_ROOT, "scripts", "temp")
    if not os.path.isdir(temp_dir):
        return
    cutoff = time.time() - 7 * 86400
    for fname in os.listdir(temp_dir):
        fpath = os.path.join(temp_dir, fname)
        if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
            try:
                os.remove(fpath)
            except OSError:
                pass


def run_startup_check() -> None:
    """Esegue il controllo periodico (ogni 24 h) all'avvio."""
    prefs = {}
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as fh:
                prefs = json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass

    last = prefs.get("last_startup_check", 0)
    now  = time.time()

    if now - last < 86400:
        return

    missing = _check_dependencies()
    if missing:
        print(colorize(f"[AVVISO] Dipendenze mancanti: {', '.join(missing)}", "yellow"))

    _check_pending_downloads()
    _cleanup_cache()

    prefs["last_startup_check"] = now
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass
