# scripts/anime/handlers_anime.py
# [MODIFICA run#1] Aggiunto path-guard
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import importlib

from scripts.anime.core_anime   import get_main_menu, get_handler_path
from scripts.core.settings_core import colorize


def run_anime_menu() -> None:
    """Loop principale del menu anime."""
    while True:
        menu = get_main_menu()
        print(colorize("\n── Menu Anime ──", "cyan"))
        for key, label in menu.items():
            print(f"  {key}) {label}")
        print("  0) Indietro")

        choice = input("Scelta: ").strip()
        if choice == "0":
            break

        handler_path = get_handler_path(choice)
        if not handler_path:
            print(colorize("Scelta non valida.", "red"))
            continue

        try:
            module_name = (
                handler_path
                .replace("/", ".")
                .replace("\\", ".")
                .removesuffix(".py")
            )
            mod = importlib.import_module(module_name)
            mod.run()
        except ImportError as exc:
            print(colorize(f"[ERRORE] Impossibile caricare il modulo: {exc}", "red"))
        except AttributeError:
            print(colorize("[ERRORE] Il modulo non espone run().", "red"))
