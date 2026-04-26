#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers.py - ANIME HANDLERS CON MENU GERARCHICO
Repository: https://github.com/PID1381/downloadcenter
Data: 16 Aprile 2026

PATCH v2.2:
  [NEW] Caricamento modulo estrai_link_anime_unity
  [NEW] Routing voce "2" (AnimeUnity) in show_anime_video_submenu()
  [FIX] Rimossa voce [In sviluppo] da AnimeUnity
"""

from __future__ import annotations
import sys
import types
import traceback as _tb
from pathlib import Path
try:
    from core.ui import ui
except ImportError:
    from scripts.core.ui import ui

try:
    from core.ui import ui
except ImportError:
    try:
        from scripts.core.ui import ui
    except ImportError:
        from core.ui import ui

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
        # [FIX v2.3] input("Premi INVIO...") rimosso: consumava l'INVIO in buffer
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
        # [NEW] Modulo AnimeUnity
        self.estrai_link_anime_unity = _load_module(
            'estrai_link_anime_unity',
            _THIS_DIR / 'estrai_link_anime_unity.py'
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

    def show_anime_video_submenu(self):
        while True:
            ui.show_header("🎬  ANIME VIDEO", "Anime e Manga > Anime > Anime video")
            choice = ui.ask_choice(
                message="Scegli un'opzione",
                choices={
                    "1": "🌐  Animeworld (AW)",
                    "2": "🌐  Animeunity (AU)",
                    "0": "🔙  Torna al menu precedente",
                },
            )
            if choice == "0":
                return
            elif choice == "1":
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
                    ui.show_error("Modulo Animeworld non disponibile")
                    ui.wait_enter()
            elif choice == "2":
                # [NEW] AnimeUnity
                if self.estrai_link_anime_unity:
                    if hasattr(self.estrai_link_anime_unity, 'estrai_singolo_au'):
                        _safe_call(self.estrai_link_anime_unity.estrai_singolo_au)
                    else:
                        for attr_name in dir(self.estrai_link_anime_unity):
                            if not attr_name.startswith('_'):
                                attr = getattr(self.estrai_link_anime_unity, attr_name)
                                if callable(attr):
                                    _safe_call(attr)
                                    break
                else:
                    ui.show_error("Modulo AnimeUnity non disponibile")
                    ui.wait_enter()

    def show_anime_card_submenu(self):
        while True:
            ui.show_header("🗂️   SCHEDE ANIME", "Anime e Manga > Anime > Schede anime")
            choice = ui.ask_choice(
                message="Scegli un'opzione",
                choices={
                    "1": "🔍  Animeclick (ACK)",
                    "2": "🔍  Animesocial (AS)  [In sviluppo]",
                    "0": "🔙  Torna al menu precedente",
                },
            )
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
                    ui.show_error("Modulo Animeclick non disponibile")
                    ui.wait_enter()
            elif choice == "2":
                ui.show_info("Animesocial è in fase di sviluppo...")
                ui.wait_enter()

    def show_utility_submenu(self):
        while True:
            ui.show_header("🛠️   UTILITÀ", "Anime e Manga > Anime > Utilità")
            choice = ui.ask_choice(
                message="Scegli un'opzione",
                choices={
                    "1": "📋  Watchlist",
                    "2": "⬇️  Download diretto",
                    "3": "🔍  Scan serie in locale",
                    "0": "🔙  Torna al menu precedente",
                },
            )
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
                    ui.show_error("Modulo Watchlist non disponibile")
                    ui.wait_enter()
            elif choice == "2":
                try:
                    from download_diretto_anime import main as download_main
                    download_main()
                except ImportError:
                    try:
                        from pathlib import Path
                        _DL_DIR = Path(__file__).parent.parent / "download"
                        if str(_DL_DIR) not in sys.path:
                            sys.path.insert(0, str(_DL_DIR))
                        from download_diretto_anime import main as download_main
                        download_main()
                    except Exception as e:
                        ui.show_error(f"Errore caricamento modulo: {e}")
                        ui.wait_enter()
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
                    ui.show_error("Modulo Scan serie in locale non disponibile")
                    ui.wait_enter()

    def show_menu(self):
        while True:
            ui.show_header("📺  ANIME", "Anime e Manga > Anime")
            choice = ui.ask_choice(
                message="Scegli un'opzione",
                choices={
                    "1": "🎬  Anime video",
                    "2": "🗂️  Schede anime",
                    "3": "🛠️  Utilità",
                    "0": "🔙  Torna al menu precedente",
                },
            )
            if choice == "0":
                return
            elif choice == "1":
                self.show_anime_video_submenu()
            elif choice == "2":
                self.show_anime_card_submenu()
            elif choice == "3":
                self.show_utility_submenu()


# ── PATCH FIX v2.3 ────────────────────────────────────────────────────────────
# Lazy singleton: AnimeHandlers NON viene istanziato all'import del modulo.
# main_menu.py accede a _anime_mod.anime_handlers → proxy trasparente.
# ──────────────────────────────────────────────────────────────────────────────
_anime_handlers_instance = None


def get_anime_handlers():
    """Lazy singleton — crea AnimeHandlers solo al primo utilizzo."""
    global _anime_handlers_instance
    if _anime_handlers_instance is None:
        try:
            _anime_handlers_instance = AnimeHandlers()
        except Exception as e:
            import traceback
            print(f"\n[ERRORE] Impossibile inizializzare AnimeHandlers: {e}")
            traceback.print_exc()
            input("Premi INVIO per continuare...")
            return None
    return _anime_handlers_instance


class _AnimeHandlersProxy:
    """Proxy trasparente: delega tutti gli accessi all'istanza lazy."""
    def __getattr__(self, name):
        instance = get_anime_handlers()
        if instance is None:
            raise AttributeError(
                f"AnimeHandlers non disponibile (errore di inizializzazione)"
            )
        return getattr(instance, name)


# Compatibilità con main_menu.py: _anime_mod.anime_handlers.show_menu()
# Il proxy crea l'istanza reale solo al primo accesso effettivo.
anime_handlers = _AnimeHandlersProxy()

