#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers.py v2.5.5 - ANIME HANDLERS CON SCAN_LOCAL_SERIES INTEGRATO

NOVITÀ v2.5.5:
  - Integrazione scan_local_series.py nel menu Anime
  - Opzione 5 aggiunta: "Scan serie in locale"
  - _load_module con types.ModuleType (fix v2.5.4 confermato)
  - sys.path aggiornato con tutti i percorsi necessari
  - Traceback completo se il modulo crasha

STRUTTURA MENU:
  1. Ricerca anime video (AW) → estrai_link_anime.py
  2. Ricerca scheda anime (ACK) → ricerca_scheda_anime.py
  3. Download diretto → download_diretto_anime.py (download/)
  4. Watchlist → watchlist.py
  5. Scan serie in locale → scan_local_series.py
  0. Torna al menu precedente
"""
from __future__ import annotations
import sys
import types
import traceback as _tb
from pathlib import Path

_THIS_DIR    = Path(__file__).parent.resolve()    # scripts/anime/
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()         # scripts/
_DL_DIR      = _SCRIPTS_DIR / "download"
_ROOT_DIR    = _SCRIPTS_DIR.parent.resolve()      # root del progetto

# Aggiorna sys.path con TUTTI i percorsi necessari, in ordine di priorita
_REQUIRED_PATHS = [str(_THIS_DIR), str(_SCRIPTS_DIR), str(_DL_DIR), str(_ROOT_DIR)]
for _p in reversed(_REQUIRED_PATHS):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)


# ══════════════════════════════════════════════════════════════════════════════════════
# LOADER UNIVERSALE
# ══════════════════════════════════════════════════════════════════════════════════════

def _load_module(name: str, file_path: Path):
    """
    Carica un file .py come modulo Python usando types.ModuleType.

    Differenze rispetto alle versioni precedenti:
      - types.ModuleType garantisce __builtins__ corretto (no crash silenzioso)
      - sys.path aggiornato con tutti i percorsi PRIMA dell'exec
      - Registrato in sys.modules PRIMA di exec (standard Python)
      - utf-8-sig gestisce eventuali BOM
      - BaseException cattura qualsiasi tipo di errore
      - Traceback SEMPRE visibile se il file crasha
    """
    file_path = Path(file_path)
    if not file_path.exists():
        print()
        print(f"  [ERRORE] File '{file_path.name}' non trovato in: {file_path.parent}")
        print()
        input("  Premi INVIO...")
        return None

    # Assicura che la cartella del file sia in sys.path
    file_dir = str(file_path.parent)
    if file_dir not in sys.path:
        sys.path.insert(0, file_dir)

    # Rimuovi cache stale
    sys.modules.pop(name, None)

    # Crea modulo con types.ModuleType (ha __builtins__ corretto)
    mod             = types.ModuleType(name)
    mod.__file__    = str(file_path)
    mod.__package__ = ""
    mod.__loader__  = None
    mod.__spec__    = None

    # Registra PRIMA di exec (previene import circolari)
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
# ANIME HANDLERS
# ══════════════════════════════════════════════════════════════════════════════════════

class AnimeHandlers:
    """Gestione menu anime."""

    def show_menu(self) -> None:
        """Menu principale Anime."""
        while True:
            # Carica anime_engine per UI
            engine = _load_module("anime_engine", _THIS_DIR / "anime_engine.py")
            if engine is None:
                print("  [ERRORE] Impossibile caricare anime_engine.py")
                break
            
            engine.clear_screen()
            engine.show_header("ANIME", "Anime e Manga > Anime")
            
            print("  +--------------------------------------+")
            print("  |  1.  Ricerca anime video (AW)        |")
            print("  |  2.  Ricerca scheda anime (ACK)      |")
            print("  |  3.  Download diretto                |")
            print("  |  4.  Watchlist                       |")
            print("  |  5.  Scan serie in locale            |")
            print("  |  0.  Torna al menu precedente        |")
            print("  +--------------------------------------+")
            
            scelta = engine.get_valid_choice(
                "Scegli un'opzione (0-5): ", ["0","1","2","3","4","5"]
            )
            
            if   scelta == "0": return
            elif scelta == "1": self._handle_estrai_link()
            elif scelta == "2": self._handle_ricerca_scheda()
            elif scelta == "3": self._handle_download()
            elif scelta == "4": self._handle_watchlist()
            elif scelta == "5": self._handle_scan_local()

    # ──────────────────────────────────────────────────────────────────────────────────
    # 1: Ricerca anime video
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
    # 2: Ricerca scheda anime
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
    # 3: Download diretto
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_download(self) -> None:
        """Download diretto (download_diretto_anime.py)."""
        mod = _load_module("download_diretto_anime", _DL_DIR / "download_diretto_anime.py")
        if mod is None:
            return
        
        if hasattr(mod, "main"):
            mod.main()
        else:
            print("  [ERRORE] Funzione main() non trovata")
            input("  Premi INVIO...")

    # ──────────────────────────────────────────────────────────────────────────────────
    # 4: Watchlist
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
    # 5: Scan serie in locale (NUOVO)
    # ──────────────────────────────────────────────────────────────────────────────────

    def _handle_scan_local(self) -> None:
        """
        Scan serie in locale (scan_local_series.py).
        
        NOVITÀ v2.5.5:
          - Integrazione diretta nel menu Anime
          - Caricamento con _load_module
          - Gestione errori centralizzata
        """
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
    print("  ANIME HANDLERS v2.5.5")
    print("=" * 56)
    print()
    print("  ✓ Loader: types.ModuleType")
    print("  ✓ sys.path: Configurato correttamente")
    print("  ✓ Moduli: 5 opzioni nel menu")
    print("  ✓ Traceback: Completo in caso di errore")
    print()
    print("  Pronto per l'integrazione nel menu principale")
    print()
    
    # Test di caricamento anime_engine
    print("  [*] Test caricamento anime_engine.py...")
    engine = _load_module("anime_engine", _THIS_DIR / "anime_engine.py")
    if engine:
        print("  ✓ anime_engine.py caricato correttamente")
        print(f"  ✓ Funzioni disponibili: {len(engine.__all__)}")
    else:
        print("  ✗ Errore caricamento anime_engine.py")
    
    print()
