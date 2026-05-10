# scripts/anime/moduli/handlers_anime_video.py
# [MODIFICA run#1] try/except ImportError isolato su playwright; aggiunto path-guard
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

from scripts.core.settings_core import colorize


def _import_error_msg(pkg: str) -> str:
    return (
        f"\n[ERRORE] Dipendenza mancante: '{pkg}'\n"
        f"Installa con: pip install {pkg}\n"
    )


_playwright_ok = False
try:
    import playwright  # noqa: F401
    _playwright_ok = True
except ImportError:
    pass


def run() -> None:
    """Sottomenu video anime: AnimeWorld / AnimeUnity."""
    while True:
        print(colorize("\n── Video Anime ──", "cyan"))
        print("  1) AnimeWorld")
        print("  2) AnimeUnity")
        print("  0) Indietro")

        choice = input("Scelta: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            if not _playwright_ok:
                print(_import_error_msg("playwright"))
                continue
            try:
                from scripts.anime.moduli.AnimeWorld import handlers_animeworld
                handlers_animeworld.run()
            except ImportError as exc:
                print(colorize(f"[ERRORE] {exc}", "red"))
        elif choice == "2":
            try:
                from scripts.anime.moduli.AnimeUnity import handlers_animeunity
                handlers_animeunity.run()
            except ImportError as exc:
                print(colorize(f"[ERRORE] {exc}", "red"))
        else:
            print(colorize("Scelta non valida.", "red"))
