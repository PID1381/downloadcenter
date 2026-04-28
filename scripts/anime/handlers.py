#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers.py - ANIME HANDLERS CON MENU GERARCHICO
Repository: https://github.com/PID1381/downloadcenter
Data: 16 Aprile 2026
Patch AnimeUnity: 28 Aprile 2026
"""

from __future__ import annotations
import sys
import types
import traceback as _tb
from pathlib import Path

_THIS_DIR    = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()
_DL_DIR      = _SCRIPTS_DIR / "download"
_ROOT_DIR    = _SCRIPTS_DIR.parent.resolve()

_REQUIRED_PATHS = [str(_THIS_DIR), str(_SCRIPTS_DIR), str(_DL_DIR), str(_ROOT_DIR)]
for _p in reversed(_REQUIRED_PATHS):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)


def _load_module(name: str, file_path: Path):
    """Carica un file .py come modulo Python"""
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    file_dir = str(file_path.parent)
    if file_dir not in sys.path:
        sys.path.insert(0, file_dir)

    sys.modules.pop(name, None)

    mod = types.ModuleType(name)
    mod.__file__ = str(file_path)
    sys.modules[name] = mod

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            code = f.read()
        exec(code, mod.__dict__)
        return mod
    except BaseException as e:
        sys.modules.pop(name, None)
        print(f"Errore caricamento {name}: {e}")
        _tb.print_exc()
        input("Premi INVIO...")
        return None


def _safe_call(func, *args, **kwargs):
    """Chiama una funzione in modo sicuro"""
    try:
        if callable(func):
            return func(*args, **kwargs)
    except BaseException as e:
        print(f"Errore: {e}")
        _tb.print_exc()
        input("Premi INVIO per continuare...")


def _clear_screen():
    """Pulisce lo schermo"""
    import os
    os.system('cls' if sys.platform == 'win32' else 'clear')


class AnimeHandlers:
    """Gestore del menu Anime con sottomenu gerarchici"""

    def __init__(self):
        """Inizializza i moduli"""
        self.estrai_link_anime = _load_module(
            'estrai_link_anime',
            _THIS_DIR / 'estrai_link_anime.py'
        )
        self.ricerca_scheda_anime = _load_module(
            'ricerca_scheda_anime',
            _THIS_DIR / 'ricerca_scheda_anime.py'
        )
        self.watchlist = _load_module(
            'watchlist',
            _THIS_DIR / 'watchlist.py'
        )
        self.scan_local_series = _load_module(
            'scan_local_series',
            _THIS_DIR / 'scan_local_series.py'
        )
        # PATCH AnimeUnity: lazy load (caricato al primo utilizzo)
        self.animeunity_handler = None

    def show_anime_video_submenu(self):
        """Sottomenu Anime Video"""
        while True:
            _clear_screen()
            print("""
========================================================
  ANIME VIDEO
========================================================
  Anime e Manga > Anime > Anime video

  +--------------------------------------+
  |  1.  Animeworld (AW)                 |
  |  2.  Animeunity (AU)                 |
  |  0.  Torna al menu precedente        |
  +--------------------------------------+
""")
            choice = input("Scegli un'opzione (0-2): ").strip()

            if choice == "0":
                return

            elif choice == "1":
                # AnimeWorld - logica originale invariata
                if self.estrai_link_anime:
                    if hasattr(self.estrai_link_anime, 'estrai_singolo'):
                        _safe_call(self.estrai_link_anime.estrai_singolo)
                    else:
                        for attr_name in dir(self.estrai_link_anime):
                            if not attr_name.startswith('_'):
                                attr = getattr(self.estrai_link_anime, attr_name)
                                if callable(attr):
                                    _safe_call(attr)
                                    break
                else:
                    print("Modulo Animeworld non disponibile")
                    input("Premi INVIO per continuare...")

            elif choice == "2":
                # PATCH AnimeUnity
                if self.animeunity_handler is None:
                    self.animeunity_handler = _load_module(
                        'animeunity_handler',
                        _THIS_DIR / 'animeunity_handler.py'
                    )
                if self.animeunity_handler and hasattr(self.animeunity_handler, 'run'):
                    _safe_call(self.animeunity_handler.run)
                else:
                    print("Modulo AnimeUnity non disponibile.")
                    print("Verifica che animeunity_handler.py sia in scripts/anime/")
                    input("Premi INVIO per continuare...")

            else:
                print("Opzione non valida!")
                input("Premi INVIO per continuare...")

    def show_anime_card_submenu(self):
        """Sottomenu Schede Anime"""
        while True:
            _clear_screen()
            print("""
========================================================
  SCHEDE ANIME
========================================================
  Anime e Manga > Anime > Schede anime

  +--------------------------------------+
  |  1.  Animeclick (ACK)                |
  |  2.  Animesocial (AS) [In sviluppo]  |
  |  0.  Torna al menu precedente        |
  +--------------------------------------+
""")
            choice = input("Scegli un'opzione (0-2): ").strip()

            if choice == "0":
                return
            elif choice == "1":
                if self.ricerca_scheda_anime:
                    if hasattr(self.ricerca_scheda_anime, 'handle_ricerca_scheda_anime'):
                        _safe_call(self.ricerca_scheda_anime.handle_ricerca_scheda_anime)
                    else:
                        for attr_name in dir(self.ricerca_scheda_anime):
                            if not attr_name.startswith('_'):
                                attr = getattr(self.ricerca_scheda_anime, attr_name)
                                if callable(attr):
                                    _safe_call(attr)
                                    break
                else:
                    print("Modulo Animeclick non disponibile")
                    input("Premi INVIO per continuare...")
            elif choice == "2":
                print("Animesocial e' in fase di sviluppo...")
                input("Premi INVIO per continuare...")
            else:
                print("Opzione non valida!")
                input("Premi INVIO per continuare...")

    def show_utility_submenu(self):
        """Sottomenu Utilita'"""
        while True:
            _clear_screen()
            print("""
========================================================
  UTILITA'
========================================================
  Anime e Manga > Anime > Utilita'

  +--------------------------------------+
  |  1.  Watchlist                       |
  |  2.  Download diretto                |
  |  3.  Scan serie in locale            |
  |  0.  Torna al menu precedente        |
  +--------------------------------------+
""")
            choice = input("Scegli un'opzione (0-3): ").strip()

            if choice == "0":
                return
            elif choice == "1":
                if self.watchlist:
                    if hasattr(self.watchlist, 'handle_watchlist_menu'):
                        _safe_call(self.watchlist.handle_watchlist_menu)
                    else:
                        for attr_name in dir(self.watchlist):
                            if not attr_name.startswith('_'):
                                attr = getattr(self.watchlist, attr_name)
                                if callable(attr):
                                    _safe_call(attr)
                                    break
                else:
                    print("Modulo Watchlist non disponibile")
                    input("Premi INVIO per continuare...")
            elif choice == "2":
                try:
                    from download_diretto_anime import main as download_main
                    download_main()
                except ImportError:
                    try:
                        import sys
                        from pathlib import Path
                        _DL_DIR = Path(__file__).parent.parent / "download"
                        if str(_DL_DIR) not in sys.path:
                            sys.path.insert(0, str(_DL_DIR))
                        from download_diretto_anime import main as download_main
                        download_main()
                    except Exception as e:
                        print(f"Errore caricamento modulo: {e}")
                        input("Premi INVIO per continuare...")
            elif choice == "3":
                if self.scan_local_series:
                    if hasattr(self.scan_local_series, 'handle_scan_menu'):
                        _safe_call(self.scan_local_series.handle_scan_menu)
                    else:
                        for attr_name in dir(self.scan_local_series):
                            if not attr_name.startswith('_'):
                                attr = getattr(self.scan_local_series, attr_name)
                                if callable(attr):
                                    _safe_call(attr)
                                    break
                else:
                    print("Modulo Scan serie in locale non disponibile")
                    input("Premi INVIO per continuare...")
            else:
                print("Opzione non valida!")
                input("Premi INVIO per continuare...")

    def show_menu(self):
        """Menu principale Anime con sottomenu"""
        while True:
            _clear_screen()
            print("""
========================================================
  ANIME
========================================================
  Anime e Manga > Anime

  +--------------------------------------+
  |  1.  Anime video                     |
  |  2.  Schede anime                    |
  |  3.  Utilita'                        |
  |  0.  Torna al menu precedente        |
  +--------------------------------------+
""")
            choice = input("Scegli un'opzione (0-3): ").strip()

            if choice == "0":
                return
            elif choice == "1":
                self.show_anime_video_submenu()
            elif choice == "2":
                self.show_anime_card_submenu()
            elif choice == "3":
                self.show_utility_submenu()
            else:
                print("Opzione non valida!")
                input("Premi INVIO per continuare...")


anime_handlers = AnimeHandlers()
