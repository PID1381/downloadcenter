"""
Download Handlers v2.1 - AGGIORNATO
Menu handlers per il dominio download.
Compatibile con i nomi file originali del progetto v1.x

NOVITÀ v2.1:
  - Aggiunta opzione 3: Riprendi download interrotto
  - Integrazione con la nuova funzione resume_interrupted_downloads()
"""
from __future__ import annotations
import sys
from pathlib import Path

_THIS_DIR    = Path(__file__).parent.resolve()   # scripts/download/
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()        # scripts/

for _p in (_THIS_DIR, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.config import config
from core.ui     import ui


class DownloadHandlers:
    """Gestione menu download."""

    def show_menu(self) -> None:
        while True:
            ui.show_header("DOWNLOAD DIRETTO")
            print("  +--------------------------------------+")
            print("  |  1.  Scarica singolo file            |")
            print("  |  2.  Da cartella di file .txt        |")
            print("  |  3.  Riprendi download interrotto    |")
            print("  |  0.  Torna                           |")
            print("  +--------------------------------------+")
            scelta = ui.ask_choice("Scegli un'opzione (0-3): ", ["0","1","2","3"])
            if scelta == "0":
                return

            try:
                # Nome file REALE: download_diretto_anime.py
                import download_diretto_anime as _mod
            except ImportError:
                ui.show_error("File 'download_diretto_anime.py' non trovato in scripts/download/")
                ui.show_info("Verifica che il file esista in: scripts/download/")
                ui.wait_enter()
                return

            prefs = config.prefs
            if   scelta == "1":
                if hasattr(_mod, "scarica_singolo"):
                    _mod.scarica_singolo(prefs)
                else:
                    ui.show_error("Funzione scarica_singolo() non trovata.")
                    ui.wait_enter()
            elif scelta == "2":
                if hasattr(_mod, "scarica_da_cartella"):
                    _mod.scarica_da_cartella(prefs)
                else:
                    ui.show_error("Funzione scarica_da_cartella() non trovata.")
                    ui.wait_enter()
            elif scelta == "3":
                if hasattr(_mod, "resume_interrupted_downloads"):
                    _mod.resume_interrupted_downloads()
                else:
                    ui.show_error("Funzione resume_interrupted_downloads() non trovata.")
                    ui.wait_enter()


download_handlers = DownloadHandlers()
