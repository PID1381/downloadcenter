#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers.py v3.0 - MENU GERARCHICO ANIME

NOVITA v3.0:
  [RESTRUCTURE] Menu principale ristrutturato in 3 categorie:
                1. Ricerca anime video (sottomenu)
                2. Ricerca scheda anime (sottomenu)
                3. Utility anime (sottomenu)
  
  [NEW] Sottomenu "Ricerca anime video":
        1. Ricerca AnimeWorld (AW)
        2. Ricerca AnimeUnity (placeholder)
        0. Torna

  [NEW] Sottomenu "Ricerca scheda anime":
        1. Ricerca AnimeClick (ACK)
        2. Ricerca SocialAnime (placeholder)
        0. Torna

  [NEW] Sottomenu "Utility anime":
        1. Download diretto video
        2. Watchlist
        3. Scan locale cartelle video
        0. Torna

  [COMPAT] 100% backward-compatible: stessi flussi interni, solo UI ristrutturata
  [READY] Pronto per future aggiunte (AnimeUnity, SocialAnime, etc)
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


# ══════════════════════════════════════════════════════════════════════════════════════
# LOADER UNIVERSALE (v2.5.5 - invariato)
# ══════════════════════════════════════════════════════════════════════════════════════

def _load_module(name: str, file_path: Path):
    """Carica un file .py come modulo Python usando types.ModuleType."""
    file_path = Path(file_path)
    if not file_path.exists():
        print()
        print(f"  [ERRORE] File '{file_path.name}' non trovato in: {file_path.parent}")
        print()
        input("  Premi INVIO...")
        return None

    file_dir = str(file_path.parent)
    if file_dir not in sys.path:
        sys.path.insert(0, file_dir)

    sys.modules.pop(name, None)

    mod             = types.ModuleType(name)
    mod.__file__    = str(file_path)
    mod.__package__ = ""
    mod.__loader__  = None
    mod.__spec__    = None

    sys.modules[name] = mod

    try:
        source = file_path.read_text(encoding="utf-8-sig")
        code   = compile(source, str(file_path), "exec")
        exec(code, mod.__dict__)
        return mod
    except BaseException as e:
        sys.modules.pop(name, None)
        print()
        print(f"  [ERRORE] Caricamento '{file_path.name}':")
        print(f"    {type(e).__name__}: {e}")
        print()
        print("  ── Traceback completo ──────────────────────────────")
        for line in _tb.format_exc().splitlines():
            print(f"  {line}")
        print("  ────────────────────────────────────────────────────")
        print()
        input("  Premi INVIO...")
        return None


# ══════════════════════════════════════════════════════════════════════════════════════
# ANIME HANDLERS v3.0 - MENU GERARCHICO
# ══════════════════════════════════════════════════════════════════════════════════════

class AnimeHandlers:
    """Gestione menu anime gerarchico v3.0."""

    def show_menu(self) -> None:
        """Menu principale Anime - RISTRUTTURATO v3.0."""
        while True:
            engine = _load_module("anime_engine", _THIS_DIR / "anime_engine.py")
            if engine is None:
                print("  [ERRORE] Impossibile caricare anime_engine.py")
                break
            
            engine.clear_screen()
            engine.show_header("ANIME", "Anime e Manga > Anime")
            
            print("  +--------------------------------------+")
            print("  |  1.  Ricerca anime video            |")
            print("  |  2.  Ricerca scheda anime           |")
            print("  |  3.  Utility anime                  |")
            print("  |  0.  Torna al menu precedente       |")
            print("  +--------------------------------------+")
            
            scelta = engine.get_valid_choice(
                "Scegli un'opzione (0-3): ", ["0","1","2","3"]
            )
            
            if   scelta == "0": return
            elif scelta == "1": self._menu_ricerca_anime_video(engine)
            elif scelta == "2": self._menu_ricerca_scheda_anime(engine)
            elif scelta == "3": self._menu_utility_anime(engine)

    # ──────────────────────────────────────────────────────────────────────────────────
    # MENU 1: RICERCA ANIME VIDEO (SOTTOMENU)
    # ──────────────────────────────────────────────────────────────────────────────────

    def _menu_ricerca_anime_video(self, engine) -> None:
        """Sottomenu Ricerca anime video."""
        while True:
            engine.clear_screen()
            engine.show_header("RICERCA ANIME VIDEO", "Anime > Ricerca anime video")
            
            print("  +--------------------------------------+")
            print("  |  1.  Ricerca AnimeWorld (AW)        |")
            print("  |  2.  Ricerca AnimeUnity      [TODO] |")
            print("  |  0.  Torna                          |")
            print("  +--------------------------------------+")
            
            scelta = engine.get_valid_choice("Scegli (0-2): ", ["0","1","2"])
            
            if scelta == "0":
                return
            elif scelta == "1":
                self._handle_estrai_link()
            elif scelta == "2":
                engine.clear_screen()
                engine.show_header("RICERCA ANIMEUNITY", "Anime > Ricerca anime video > AnimeUnity")
                engine.show_warning("Funzionalita in sviluppo - coming soon!")
                engine.wait_enter()

    # ──────────────────────────────────────────────────────────────────────────────────
    # MENU 2: RICERCA SCHEDA ANIME (SOTTOMENU)
    # ──────────────────────────────────────────────────────────────────────────────────

    def _menu_ricerca_scheda_anime(self, engine) -> None:
        """Sottomenu Ricerca scheda anime."""
        while True:
            engine.clear_screen()
            engine.show_header("RICERCA SCHEDA ANIME", "Anime > Ricerca scheda anime")
            
            print("  +--------------------------------------+")
            print("  |  1.  Ricerca AnimeClick (ACK)       |")
            print("  |  2.  Ricerca SocialAnime     [TODO] |")
            print("  |  0.  Torna                          |")
            print("  +--------------------------------------+")
            
            scelta = engine.get_valid_choice("Scegli (0-2): ", ["0","1","2"])
            
            if scelta == "0":
                return
            elif scelta == "1":
                self._handle_ricerca_scheda()
            elif scelta == "2":
                engine.clear_screen()
                engine.show_header("RICERCA SOCIALANIME", "Anime > Ricerca scheda anime > SocialAnime")
                engine.show_warning("Funzionalita in sviluppo - coming soon!")
                engine.wait_enter()

    # ──────────────────────────────────────────────────────────────────────────────────
    # MENU 3: UTILITY ANIME (SOTTOMENU)
    # ──────────────────────────────────────────────────────────────────────────────────

    def _menu_utility_anime(self, engine) -> None:
        """Sottomenu Utility anime."""
        while True:
            engine.clear_screen()
            engine.show_header("UTILITY ANIME", "Anime > Utility anime")
            
            print("  +--------------------------------------+")
            print("  |  1.  Download diretto video         |")
            print("  |  2.  Watchlist                      |")
            print("  |  3.  Scan locale cartelle video     |")
            print("  |  0.  Torna                          |")
            print("  +--------------------------------------+")
            
            scelta = engine.get_valid_choice("Scegli (0-3): ", ["0","1","2","3"])
            
            if   scelta == "0": return
            elif scelta == "1": self._handle_download()
            elif scelta == "2": self._handle_watchlist()
            elif scelta == "3": self._handle_scan_local()

    # ──────────────────────────────────────────────────────────────────────────────────
    # HANDLER 1: Ricerca anime video (estrai_link)
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_estrai_link(self) -> None:
        """Ricerca anime video su AnimeWorld (estrai_link_anime.py)."""
        mod = _load_module("estrai_link_anime", _THIS_DIR / "estrai_link_anime.py")
        if mod is None:
            return
        
        if hasattr(mod, "estrai_singolo"):
            mod.estrai_singolo()
        else:
            print("  [ERRORE] Funzione estrai_singolo() non trovata")
            input("  Premi INVIO...")

    # ──────────────────────────────────────────────────────────────────────────────────
    # HANDLER 2: Ricerca scheda anime (ricerca_scheda_anime)
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_ricerca_scheda(self) -> None:
        """Ricerca scheda anime su AnimeClick (ricerca_scheda_anime.py)."""
        mod = _load_module("ricerca_scheda_anime", _THIS_DIR / "ricerca_scheda_anime.py")
        if mod is None:
            return
        
        if not hasattr(mod, "AnimeTracker") or not hasattr(mod, "handle_ricerca_scheda_anime"):
            print("  [ERRORE] Funzioni AnimeTracker/handle_ricerca_scheda_anime non trovate")
            input("  Premi INVIO...")
            return
        
        try:
            tracker = mod.AnimeTracker()
            mod.handle_ricerca_scheda_anime(tracker)
        except Exception as e:
            print(f"  [ERRORE] {e}")
            input("  Premi INVIO...")

    # ──────────────────────────────────────────────────────────────────────────────────
    # HANDLER 3: Download diretto
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_download(self) -> None:
        """Download diretto video (download_diretto_anime.py)."""
        mod = _load_module("download_diretto_anime", _DL_DIR / "download_diretto_anime.py")
        if mod is None:
            return
        
        if hasattr(mod, "main"):
            mod.main()
        else:
            print("  [ERRORE] Funzione main() non trovata")
            input("  Premi INVIO...")

    # ──────────────────────────────────────────────────────────────────────────────────
    # HANDLER 4: Watchlist
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_watchlist(self) -> None:
        """Watchlist (watchlist.py)."""
        mod = _load_module("watchlist_dc", _THIS_DIR / "watchlist.py")
        if mod is None:
            return

        fn = getattr(mod, "handle_watchlist_menu", None)

        if fn is None or not callable(fn):
            print("  [ERRORE] handle_watchlist_menu() non trovata in watchlist.py")
            input("  Premi INVIO...")
            return

        try:
            fn(tracker=None)
        except BaseException as e:
            print(f"  [ERRORE] {type(e).__name__}: {e}")
            input("  Premi INVIO...")

    # ──────────────────────────────────────────────────────────────────────────────────
    # HANDLER 5: Scan serie in locale
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_scan_local(self) -> None:
        """Scan locale cartelle video (scan_local_series.py)."""
        mod = _load_module("scan_local_series", _THIS_DIR / "scan_local_series.py")
        if mod is None:
            return

        fn = getattr(mod, "handle_scan_menu", None)

        if fn is None or not callable(fn):
            print("  [ERRORE] handle_scan_menu() non trovata in scan_local_series.py")
            input("  Premi INVIO...")
            return

        try:
            fn()
        except BaseException as e:
            print(f"  [ERRORE] {type(e).__name__}: {e}")
            input("  Premi INVIO...")


# ══════════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════════════

anime_handlers = AnimeHandlers()


# ══════════════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("=" * 56)
    print("  ANIME HANDLERS v3.0")
    print("=" * 56)
    print()
    print("  ✓ Menu gerarchico a 3 livelli")
    print("  ✓ Ricerca anime video (AW + AnimeUnity TODO)")
    print("  ✓ Ricerca scheda anime (ACK + SocialAnime TODO)")
    print("  ✓ Utility anime (Download + Watchlist + Scan)")
    print("  ✓ Loader: types.ModuleType")
    print("  ✓ sys.path: Configurato correttamente")
    print("  ✓ Traceback: Completo in caso di errore")
    print()
    print("  Pronto per l'integrazione nel menu principale")
    print()
    
    engine = _load_module("anime_engine", Path(__file__).parent / "anime_engine.py")
    if engine:
        print("  [*] Test caricamento anime_engine.py...")
        print("  ✓ anime_engine.py caricato correttamente")
    else:
        print("  ✗ Errore caricamento anime_engine.py")
    
    print()
