# main_menu.py  – Entry point principale DC3
# [MODIFICA run#1] Aggiunto path-guard; import lazy per layer handlers
import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.core.settings_core import colorize
from scripts.core.startup_check import run_startup_check


def main() -> None:
    """CLI entry point: menu principale DC3."""
    run_startup_check()

    while True:
        print(colorize("\n╔══════════════════════════╗", "cyan"))
        print(colorize("║   Download Center 3.0    ║", "cyan"))
        print(colorize("╚══════════════════════════╝", "cyan"))
        print("  1) Anime")
        print("  2) Manga")
        print("  3) Download")
        print("  4) Impostazioni")
        print("  0) Esci")

        choice = input("Scelta: ").strip()

        if choice == "0":
            print(colorize("Arrivederci.", "green"))
            break
        elif choice == "1":
            try:
                from scripts.anime.handlers_anime import run_anime_menu
                run_anime_menu()
            except ImportError as exc:
                print(colorize(f"[ERRORE] Layer Anime: {exc}", "red"))
        elif choice == "2":
            try:
                from scripts.manga.handlers_manga import run_manga_menu
                run_manga_menu()
            except ImportError as exc:
                print(colorize(f"[ERRORE] Layer Manga: {exc}", "red"))
        elif choice == "3":
            try:
                from scripts.download.handlers_download import run_download_menu
                run_download_menu()
            except ImportError as exc:
                print(colorize(f"[ERRORE] Layer Download: {exc}", "red"))
        elif choice == "4":
            try:
                from scripts.core.settings_handler import run_settings_menu
                run_settings_menu()
            except ImportError as exc:
                print(colorize(f"[ERRORE] Impostazioni: {exc}", "red"))
        else:
            print(colorize("Scelta non valida.", "red"))


if __name__ == "__main__":
    main()
