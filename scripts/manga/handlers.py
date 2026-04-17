"""
Manga Handlers v4.0 - MODIFICATO
=================================
Menu handlers per il dominio manga con struttura gerarchica.
Percorso: scripts/manga/handlers.py

MODIFICHE v4.0:
  - Menu principale con 3 categorie: Ricerca manga, Acquisti manga, Utilità
  - Sottomenu "Ricerca manga" con opzioni 1-2
  - Sottomenu "Acquisti manga" con opzioni 1-4
  - Sottomenu "Utilità" con opzione 1
  - Collegamento corretto a tutti i moduli
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


def _call_main(module):
    """Chiama la funzione main di un modulo"""
    if hasattr(module, "main"):
        return module.main()
    elif hasattr(module, "run"):
        return module.run()
    else:
        # Fallback: chiama la prima funzione non privata
        for attr_name in dir(module):
            if not attr_name.startswith("_"):
                attr = getattr(module, attr_name)
                if callable(attr):
                    return attr()


def _show_ricerca_manga_submenu():
    """Sottomenu: Ricerca manga"""
    while True:
        header = ui.show_header("RICERCA MANGA")
        
        choices = {
            "1": "Update manga Animeclick (ACK)",
            "2": "Update manga SocialAnime (SA)",
            "0": "Torna al menu precedente",
        }
        
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices=choices,
            default="0",
        )
        
        if choice == "0":
            return
        elif choice == "1":
            _call_main(ultime_uscite_manga)
        elif choice == "2":
            ui.show_info("Update manga SocialAnime è in fase di sviluppo...")
            input("Premi INVIO per continuare...")


def _show_acquisti_manga_submenu():
    """Sottomenu: Acquisti manga"""
    while True:
        header = ui.show_header("ACQUISTI MANGA")
        
        choices = {
            "1": "Confronto automatico acquisti",
            "2": "Acquisti Amazon",
            "3": "Acquisti Mangacomicsmarket (T.D.M.Fumett)",
            "4": "Acquisti usato Vinted",
            "0": "Torna al menu precedente",
        }
        
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices=choices,
            default="0",
        )
        
        if choice == "0":
            return
        elif choice == "1":
            _call_main(ricerca_automatica_acquisti)
        elif choice == "2":
            _call_main(acquisti_manga_amazon)
        elif choice == "3":
            _call_main(ricerca_mcm)
        elif choice == "4":
            _call_main(ricerca_vinted)


def _show_utility_submenu():
    """Sottomenu: Utilità"""
    while True:
        header = ui.show_header("UTILITÀ")
        
        choices = {
            "1": "La mia collezione",
            "0": "Torna al menu precedente",
        }
        
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices=choices,
            default="0",
        )
        
        if choice == "0":
            return
        elif choice == "1":
            _call_main(la_mia_collezione)


def show_menu():
    """Menu principale MANGA"""
    while True:
        header = ui.show_header("MANGA")
        
        choices = {
            "1": "Ricerca manga",
            "2": "Acquisti manga",
            "3": "Utilità",
            "0": "Torna al menu precedente",
        }
        
        choice = ui.ask_choice(
            header=header,
            message="Scegli un'opzione",
            choices=choices,
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
