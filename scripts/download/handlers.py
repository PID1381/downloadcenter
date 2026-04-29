"""
Download Handlers v2.2 - yt-dlp integrato
Menu handlers per il dominio download.
Compatibile con i nomi file originali del progetto v1.x

NOVITÀ v2.1:
  - Aggiunta opzione 3: Riprendi download interrotto
NOVITÀ v2.2:
  - Aggiunta opzione 4: yt-dlp download (wrapper ytdlp_wrapper.py)
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
            print("  |  4.  yt-dlp download                 |")
            print("  |  0.  Torna                           |")
            print("  +--------------------------------------+")
            scelta = ui.ask_choice("Scegli un'opzione (0-4): ", ["0","1","2","3","4"])
            if scelta == "0":
                return

            if scelta in ("1", "2", "3"):
                try:
                    import download_diretto_anime as _mod
                except ImportError:
                    ui.show_error("File 'download_diretto_anime.py' non trovato in scripts/download/")
                    ui.show_info("Verifica che il file esista in: scripts/download/")
                    ui.wait_enter()
                    return

                prefs = config.prefs
                if scelta == "1":
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

            elif scelta == "4":
                self._show_ytdlp_menu()

    # ── Menu yt-dlp ───────────────────────────────────────────────────────────
    def _show_ytdlp_menu(self) -> None:
        """Sottomenu yt-dlp: verifica installazione + download da URL."""
        if str(_THIS_DIR) not in sys.path:
            sys.path.insert(0, str(_THIS_DIR))

        try:
            import ytdlp_wrapper as _w
        except ImportError:
            print("  \u2717 ytdlp_wrapper.py non trovato in scripts/download/")
            input("  Premi Invio...")
            return

        if not _w.check_installed():
            print()
            print("  yt-dlp NON \xe8 installato nel tuo ambiente Python.")
            print("  Installa con:   pip install yt-dlp")
            print()
            input("  Premi Invio...")
            return

        while True:
            print()
            ver = _w.get_version()
            print(f"  \u250c{'\u2500'*39}\u2510")
            print(f"  \u2502  yt-dlp  v{ver:<29}\u2502")
            print(f"  \u251c{'\u2500'*39}\u2524")
            print(f"  \u2502  1.  Download da URL  (best MP4)    \u2502")
            print(f"  \u2502  2.  Download stream  HLS / M3U8    \u2502")
            print(f"  \u2502  0.  Torna                          \u2502")
            print(f"  \u2514{'\u2500'*39}\u2518")
            scelta = input("  Scegli (0-2): ").strip()
            if scelta == "0":
                return
            if scelta not in ("1", "2"):
                continue

            url = input("  URL: ").strip()
            if not url:
                print("  \u26a0 URL vuoto.")
                continue

            fname = input("  Nome file (Invio = automatico): ").strip() or None

            print()
            print(f"  \u2b07  Avvio download\u2026  \u2192  {_w._get_download_dir()}")
            print()

            if scelta == "1":
                ok = _w.download_url(url, filename=fname)
            else:
                ok = _w.download_hls(url, filename=fname)

            print()
            if ok:
                print("  \u2705 Download completato.")
            else:
                print("  \u2717  Download fallito. Controlla URL e connessione.")
            input("  Premi Invio...")


download_handlers = DownloadHandlers()
