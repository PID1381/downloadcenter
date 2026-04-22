"""
Manga Handlers — PATCHATO
==========================
Versione corretta di scripts/manga/handlers.py

Patch applicata:
  - Rimossa _call_main() che cercava main()/run() inesistenti
  - Aggiunta _call() con entry point reali per ogni modulo
  - Entry point corrette:
      ultime_uscite_manga  → handle_manga_uscite()
      ricerca_mcm          → handle_ricerca_mcm()
      acquisti_manga_amazon→ handle_amazon_manga()
      la_mia_collezione    → handle_collezione()
      ricerca_automatica   → handle_ricerca_automatica()
      ricerca_vinted       → handle_vinted_ricerca()

Percorso: scripts/manga/handlers.py
"""

from scripts.core import ui
from . import (
    ultime_uscite_manga,
    ricerca_mcm,
    acquisti_manga_amazon,
    la_mia_collezione,
    ricerca_automatica_acquisti,
    ricerca_vinted,
)


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _call(module, entry_point: str):
    """
    Chiama la funzione entry point specificata del modulo.
    Se non esiste mostra un errore leggibile.
    """
    fn = getattr(module, entry_point, None)
    if callable(fn):
        fn()
    else:
        ui.show_error(
            f"Entry point '{entry_point}' non trovata in {module.__name__}. "
            "Controlla la versione del modulo."
        )
        ui.wait_enter()


# ---------------------------------------------------------------------------
# Sottomenu: Ricerca manga
# ---------------------------------------------------------------------------

def _show_ricerca_manga_submenu():
    while True:
        header = ui.show_header("RICERCA MANGA")
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices={
                "1": "Update manga Animeclick (ACK)",
                "2": "Update manga SocialAnime (SA)",
                "0": "Torna al menu precedente",
            },
            default="0",
        )
        if choice == "0":
            return
        elif choice == "1":
            # entry point reale: handle_manga_uscite()
            _call(ultime_uscite_manga, "handle_manga_uscite")
        elif choice == "2":
            ui.show_info("Update manga SocialAnime è in fase di sviluppo...")
            ui.wait_enter()


# ---------------------------------------------------------------------------
# Sottomenu: Acquisti manga
# ---------------------------------------------------------------------------

def _show_acquisti_manga_submenu():
    while True:
        header = ui.show_header("ACQUISTI MANGA")
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices={
                "1": "Confronto automatico acquisti",
                "2": "Acquisti Amazon",
                "3": "Acquisti Mangacomicsmarket (T.D.M.Fumett)",
                "4": "Acquisti usato Vinted",
                "0": "Torna al menu precedente",
            },
            default="0",
        )
        if choice == "0":
            return
        elif choice == "1":
            # entry point reale: handle_ricerca_automatica()
            _call(ricerca_automatica_acquisti, "handle_ricerca_automatica")
        elif choice == "2":
            # entry point reale: handle_amazon_manga()
            _call(acquisti_manga_amazon, "handle_amazon_manga")
        elif choice == "3":
            # entry point reale: handle_ricerca_mcm()
            _call(ricerca_mcm, "handle_ricerca_mcm")
        elif choice == "4":
            # entry point reale: handle_vinted_ricerca()
            _call(ricerca_vinted, "handle_vinted_ricerca")


# ---------------------------------------------------------------------------
# Sottomenu: Utilità
# ---------------------------------------------------------------------------

def _show_utility_submenu():
    while True:
        header = ui.show_header("UTILITÀ")
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices={
                "1": "La mia collezione",
                "0": "Torna al menu precedente",
            },
            default="0",
        )
        if choice == "0":
            return
        elif choice == "1":
            # entry point reale: handle_collezione()
            _call(la_mia_collezione, "handle_collezione")


# ---------------------------------------------------------------------------
# Menu principale MANGA
# ---------------------------------------------------------------------------

def show_menu():
    """Entry point chiamata da main_menu.py → _submenu_anime_manga()"""
    while True:
        header = ui.show_header("MANGA")
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices={
                "1": "Ricerca manga",
                "2": "Acquisti manga",
                "3": "Utilità",
                "0": "Torna al menu precedente",
            },
            default="0",
        )
        if choice == "0":
            return
        elif choice == "1":
            _show_ricerca_manga_submenu()
        elif choice == "2":
            _show_acquisti_manga_submenu()
        elif choice == "3":
            _show_utility_submenu()
