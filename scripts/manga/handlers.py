"""
Manga Handlers v3.1
===================
Menu handlers per il dominio manga.
Percorso: scripts/manga/handlers.py

NOVITA v3.1:
  - Opzione 6: Ricerca usato su Vinted (ricerca_vinted.py)
  - ask_choice aggiornato a 0-6
"""
from __future__ import annotations
import sys
from pathlib import Path

_THIS_DIR    = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()

for _p in (_THIS_DIR, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.ui import ui


class MangaHandlers:

    def show_menu(self):
        while True:
            ui.show_header("MANGA", "Anime e Manga > Manga")
            print("  +------------------------------------------+")
            print("  |  1.  Ultime uscite manga (ACK)           |")
            print("  |  2.  Acquisti manga (MCM)                |")
            print("  |      (T.D.M.Fumett.)                     |")
            print("  |  3.  Acquisti manga (Amazon)             |")
            print("  |  4.  La mia collezione                   |")
            print("  |  5.  Ricerca automatica acquisti manga   |")
            print("  |  6.  Ricerca usato su Vinted             |")
            print("  |  0.  Torna al menu precedente            |")
            print("  +------------------------------------------+")
            scelta = ui.ask_choice(
                "Scegli un'opzione (0-6): ",
                ["0", "1", "2", "3", "4", "5", "6"],
            )
            if   scelta == "0": return
            elif scelta == "1": self._handle_ack()
            elif scelta == "2": self._handle_acquisti_mcm()
            elif scelta == "3": self._handle_amazon()
            elif scelta == "4": self._handle_collection()
            elif scelta == "5": self._handle_ricerca_automatica()
            elif scelta == "6": self._handle_vinted()

    def _handle_ack(self):
        try:
            import ultime_uscite_manga as _mod
        except ImportError:
            ui.show_error("File 'ultime_uscite_manga.py' non trovato in scripts/manga/")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_manga_uscite"):
            ui.show_error("Funzione handle_manga_uscite() non trovata.")
            ui.wait_enter(); return
        try:
            _mod.handle_manga_uscite()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()

    def _handle_acquisti_mcm(self):
        while True:
            ui.show_header("MANGA", "Anime e Manga > Manga > Acquisti manga (MCM)")
            print("  +------------------------------------------+")
            print("  |  1.  Ultime uscite/preorder (MCM)        |")
            print("  |      (T.D.M.Fumett.)                     |")
            print("  |  2.  Ricerca articoli (MCM)              |")
            print("  |      (T.D.M.Fumett.)                     |")
            print("  |  0.  Torna al menu precedente            |")
            print("  +------------------------------------------+")
            scelta = ui.ask_choice("Scegli un'opzione (0-2): ", ["0", "1", "2"])
            if   scelta == "0": return
            elif scelta == "1": self._handle_mcm()
            elif scelta == "2": self._handle_ricerca_mcm()

    def _handle_mcm(self):
        try:
            import ultime_uscite_MCM as _mod
        except ImportError:
            ui.show_error("File 'ultime_uscite_MCM.py' non trovato in scripts/manga/")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_mcm_uscite"):
            ui.show_error("Funzione handle_mcm_uscite() non trovata.")
            ui.wait_enter(); return
        try:
            _mod.handle_mcm_uscite()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()

    def _handle_ricerca_mcm(self):
        try:
            import ricerca_mcm as _mod
        except ImportError:
            ui.show_error("File 'ricerca_mcm.py' non trovato in scripts/manga/")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_ricerca_mcm"):
            ui.show_error("Funzione handle_ricerca_mcm() non trovata.")
            ui.wait_enter(); return
        try:
            _mod.handle_ricerca_mcm()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()

    def _handle_amazon(self):
        try:
            import acquisti_manga_amazon as _mod
        except ImportError:
            ui.show_error("File 'acquisti_manga_amazon.py' non trovato in scripts/manga/")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_amazon_manga"):
            ui.show_error("Funzione handle_amazon_manga() non trovata.")
            ui.wait_enter(); return
        try:
            _mod.handle_amazon_manga()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()

    def _handle_collection(self):
        try:
            import la_mia_collezione as _mod
        except ImportError:
            ui.show_info("Funzionalita 'La mia collezione' - In sviluppo.")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_collezione"):
            ui.show_info("Funzionalita 'La mia collezione' - In sviluppo.")
            ui.wait_enter(); return
        try:
            _mod.handle_collezione()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()

    def _handle_ricerca_automatica(self):
        try:
            import ricerca_automatica_acquisti as _mod
        except ImportError:
            ui.show_error("File 'ricerca_automatica_acquisti.py' non trovato in scripts/manga/")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_ricerca_automatica"):
            ui.show_error("Funzione handle_ricerca_automatica() non trovata.")
            ui.wait_enter(); return
        try:
            _mod.handle_ricerca_automatica()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()

    # -- Vinted (NUOVO v3.1) --------------------------------------------------
    def _handle_vinted(self):
        try:
            import ricerca_vinted as _mod
        except ImportError:
            ui.show_error("File 'ricerca_vinted.py' non trovato in scripts/manga/")
            ui.wait_enter(); return
        if not hasattr(_mod, "handle_vinted_ricerca"):
            ui.show_error("Funzione handle_vinted_ricerca() non trovata.")
            ui.wait_enter(); return
        try:
            _mod.handle_vinted_ricerca()
        except Exception as e:
            ui.show_error("Errore: " + str(e)); ui.wait_enter()


manga_handlers = MangaHandlers()
