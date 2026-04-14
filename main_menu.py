#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Center v2.0 - Main Menu
Entry point refactored con architettura core centralizzata.

NOVITA v2.1 FIX:
  [NEW]     Startup initialization sequence all'avvio:
            1. Verifica dipendenze (requests, beautifulsoup4, playwright)
            2. Svuotamento cache automatico
            3. Ricerca aggiornamenti nuovi episodi
            4. Controllo download pendenti
            5. Visualizzazione step a video + attesa invio
  [FIX]     sys.path configurato con TUTTI i percorsi necessari:
            - root/
            - root/scripts/
            - root/scripts/core/
            - root/scripts/anime/
            - root/scripts/manga/
            - root/scripts/download/
  [ROBUST]  Importazioni con try/except per gestire casi mancanti
  [MANTIENE] Tutta la struttura menu principale invariata
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

# ════════════════════════════════════════════════════════════════════════════
# PATH SETUP — CONFIGURAZIONE CORRETTA
# ════════════════════════════════════════════════════════════════════════════

_ROOT = Path(__file__).parent.resolve()
_SCRIPTS = _ROOT / "scripts"
_ANIME = _SCRIPTS / "anime"
_MANGA = _SCRIPTS / "manga"
_DOWNLOAD = _SCRIPTS / "download"
_CORE = _SCRIPTS / "core"

# Aggiungi TUTTI i percorsi necessari al sys.path in ordine di priorita
_REQUIRED_PATHS = [str(_ANIME), str(_CORE), str(_DOWNLOAD), str(_MANGA), str(_SCRIPTS), str(_ROOT)]
for p in reversed(_REQUIRED_PATHS):
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

# ════════════════════════════════════════════════════════════════════════════
# CORE IMPORTS
# ════════════════════════════════════════════════════════════════════════════

from core.config import config
from core.ui import ui
from core.logger import logger
from core.cache import cache_mgr
from core.backup import backup_mgr


# ════════════════════════════════════════════════════════════════════════════
# STARTUP INITIALIZATION SEQUENCE
# ════════════════════════════════════════════════════════════════════════════

def _check_dependencies() -> Dict[str, bool]:
    """
    Verifica tutte le dipendenze richieste.
    Ritorna dict con stato di ogni libreria.
    """
    deps = {
        'requests': False,
        'beautifulsoup4': False,
        'playwright': False,
    }
    
    # Verifica requests
    try:
        import requests
        deps['requests'] = True
    except ImportError:
        pass
    
    # Verifica beautifulsoup4
    try:
        from bs4 import BeautifulSoup
        deps['beautifulsoup4'] = True
    except ImportError:
        pass
    
    # Verifica playwright
    try:
        from playwright.sync_api import sync_playwright
        deps['playwright'] = True
    except ImportError:
        pass
    
    return deps


def _display_dependency_status(deps: Dict[str, bool]) -> None:
    """Visualizza lo stato delle dipendenze."""
    print()
    print("  VERIFICA DIPENDENZE:")
    print("  " + "-" * 52)
    
    for lib, installed in deps.items():
        status = "✓ OK" if installed else "✗ MANCANTE"
        symbol = "  [✓]" if installed else "  [✗]"
        print(f"{symbol} {lib:<25} {status}")
    
    print("  " + "-" * 52)
    
    # Se qualche dipendenza manca, mostra istruzioni
    missing = [lib for lib, ok in deps.items() if not ok]
    if missing:
        print()
        ui.show_warning("Alcune dipendenze mancano!")
        print()
        print("  Esegui i seguenti comandi per installarle:")
        print()
        if 'requests' in missing or 'beautifulsoup4' in missing:
            print("    pip install requests beautifulsoup4")
        if 'playwright' in missing:
            print("    pip install playwright")
            print("    playwright install chromium")
        print()


def _check_nuovi_episodi() -> int:
    """
    Controlla se ci sono nuovi episodi in watchlist.
    Ritorna il numero di anime aggiornati.
    Gestisce errori in modo robusto.
    """
    try:
        # Prova a importare check_nuovi_episodi da watchlist
        from anime.watchlist import check_nuovi_episodi
        n = check_nuovi_episodi(silent=True)
        return n if isinstance(n, int) else 0
    except ImportError as e:
        # watchlist.py non riesce a importare anime_engine
        # Proviamo un approccio alternativo: load anime_engine direttamente
        try:
            from anime_engine import search_animeworld
            # Se animd_engine carica OK, allora tentiamo di nuovo watchlist
            from anime.watchlist import check_nuovi_episodi
            n = check_nuovi_episodi(silent=True)
            return n if isinstance(n, int) else 0
        except Exception:
            # Se tutto fallisce, ritorniamo 0 in silenzio
            logger.warning("Impossibile verificare nuovi episodi", module="startup")
            return 0
    except Exception as e:
        # Qualsiasi altro errore
        logger.warning(f"Errore verifica episodi: {e}", module="startup")
        return 0


def _check_pending_downloads() -> Tuple[bool, int]:
    """
    Controlla se ci sono download pendenti.
    Ritorna (has_pending, count).
    """
    try:
        state_file = config.temp_dir / ".download_state.json"
        if not state_file.exists():
            return False, 0
        
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        files = state.get('files', {})
        if not files:
            return False, 0
        
        # Conta file non completati
        pending = sum(
            1 for f in files.values()
            if isinstance(f, dict) and f.get('status') != 'completed'
        )
        
        return pending > 0, pending
    except Exception as e:
        logger.warning(f"Errore lettura download state: {e}", module="startup")
        return False, 0


def _startup_initialization() -> None:
    """
    Sequence di inizializzazione all'avvio:
    1. Verifica dipendenze
    2. Svuota cache
    3. Ricerca nuovi episodi
    4. Controlla download pendenti
    5. Attesa invio per continuare
    """
    ui.show_header("DOWNLOAD CENTER v2.0 - STARTUP")
    
    # ── STEP 1: Verifica dipendenze ──────────────────────────────────────────
    print("  [STEP 1/4] Verifica dipendenze...")
    print()
    deps = _check_dependencies()
    _display_dependency_status(deps)
    
    # ── STEP 2: Svuotamento cache ────────────────────────────────────────────
    print()
    print("  [STEP 2/4] Pulizia cache...")
    print()
    
    try:
        temp_del, temp_err = cache_mgr.clear_temp_files()
        if temp_del > 0:
            ui.show_success(f"Cache pulita: {temp_del} file temporanei rimossi")
        else:
            ui.show_info("Cache già pulita")
        
        if temp_err > 0:
            ui.show_warning(f"Errori durante la pulizia: {temp_err}")
    except Exception as e:
        ui.show_error(f"Errore durante pulizia cache: {e}")
        logger.error(f"Errore cache cleanup: {e}", module="startup")
    
    # ── STEP 3: Ricerca nuovi episodi ────────────────────────────────────────
    print()
    print("  [STEP 3/4] Ricerca aggiornamenti episodi...")
    print()
    
    try:
        n = _check_nuovi_episodi()
        if n > 0:
            ui.show_success(f"{n} anime aggiornati con nuovi episodi")
        else:
            ui.show_info("Nessun nuovo episodio disponibile")
    except Exception as e:
        ui.show_warning(f"Impossibile verificare nuovi episodi")
        logger.warning(f"Errore verifica episodi: {e}", module="startup")
    
    # ── STEP 4: Controllo download pendenti ───────────────────────────────────
    print()
    print("  [STEP 4/4] Controllo download pendenti...")
    print()
    
    has_pending, count = _check_pending_downloads()
    if has_pending:
        ui.show_warning(f"⚠ {count} download in sospeso")
        print("  Accedi al menu 'Download Diretto' per riprenderli")
    else:
        ui.show_info("Nessun download pendente")
    
    # ── Attesa invio ─────────────────────────────────────────────────────────
    print()
    print("  " + "=" * 52)
    ui.wait_enter("Premi INVIO per continuare...")


def _show_main_menu() -> None:
    """Menu principale Download Center v2.0."""
    while True:
        ui.show_header(f"DOWNLOAD CENTER v{config.version}")
        print("  +--------------------------------------+")
        print("  |  1.  Anime e Manga                   |")
        print("  |  2.  Download Diretto                |")
        print("  |  3.  Impostazioni                    |")
        print("  |  4.  Utilita                         |")
        print("  |  0.  Esci                            |")
        print("  +--------------------------------------+")
        scelta = ui.ask_choice("Scegli un'opzione (0-4): ", ["0","1","2","3","4"])

        if scelta == "0":
            ui.show_info("Uscita. Ciao!")
            break
        elif scelta == "1":
            _submenu_anime_manga()
        elif scelta == "2":
            _submenu_download()
        elif scelta == "3":
            _submenu_impostazioni()
        elif scelta == "4":
            _submenu_utilita()


def _submenu_anime_manga() -> None:
    while True:
        ui.show_header("ANIME E MANGA")
        print("  +--------------------------------------+")
        print("  |  1.  Anime                           |")
        print("  |  2.  Manga                           |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        scelta = ui.ask_choice("Scegli un'opzione (0-2): ", ["0","1","2"])
        if scelta == "0": return
        elif scelta == "1":
            try:
                from anime.handlers import anime_handlers
                anime_handlers.show_menu()
            except ImportError as e:
                ui.show_error(f"Modulo anime non disponibile: {e}")
                ui.wait_enter()
        elif scelta == "2":
            try:
                from manga.handlers import manga_handlers
                manga_handlers.show_menu()
            except ImportError as e:
                ui.show_error(f"Modulo manga non disponibile: {e}")
                ui.wait_enter()


def _submenu_download() -> None:
    try:
        from download.handlers import download_handlers
        download_handlers.show_menu()
    except ImportError as e:
        ui.show_error(f"Modulo download non disponibile: {e}")
        ui.wait_enter()


def _submenu_impostazioni() -> None:
    while True:
        ui.show_header("IMPOSTAZIONI")
        print(f"  Versione:          {config.version}")
        print(f"  Download dir:      {config.get_download_dir()}")
        print(f"  Link dir:          {config.get_link_dir()}")
        print(f"  Export dir:        {config.get_export_dir()}")
        print(f"  Browser headless:  {config.is_headless()}")
        print(f"  Debug mode:        {config.is_debug()}")
        print(f"  Timeout (s):       {config.get_timeout()}")
        print()
        print("  +--------------------------------------+")
        print("  |  1.  Cambia download dir             |")
        print("  |  2.  Toggle headless browser         |")
        print("  |  3.  Toggle debug mode               |")
        print("  |  4.  Reset impostazioni default      |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        scelta = ui.ask_choice("Scegli un'opzione (0-4): ", ["0","1","2","3","4"])
        if scelta == "0": return
        elif scelta == "1":
            new_dir = input("  Nuovo percorso download: ").strip()
            if new_dir:
                config.set("default_download_dir", new_dir)
                ui.show_success(f"Download dir aggiornata: {new_dir}")
        elif scelta == "2":
            config.set("browser_headless", not config.is_headless())
            ui.show_success(f"Headless: {config.is_headless()}")
        elif scelta == "3":
            config.set("debug_mode", not config.is_debug())
            ui.show_success(f"Debug mode: {config.is_debug()}")
        elif scelta == "4":
            if ui.ask_yes_no("Confermi reset impostazioni?"):
                config.reset_to_defaults()
                ui.show_success("Impostazioni ripristinate.")
        ui.wait_enter()


def _submenu_utilita() -> None:
    """Menu Utilita: Clear cache e Backup."""
    while True:
        ui.show_header("UTILITA")
        print("  +--------------------------------------+")
        print("  |  1.  Clear cache                     |")
        print("  |  2.  Backup file sensibili           |")
        print("  |  3.  Ripristina backup               |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        scelta = ui.ask_choice("Scegli un'opzione (0-3): ", ["0","1","2","3"])
        
        if scelta == "0":
            return
        elif scelta == "1":
            _handle_clear_cache()
        elif scelta == "2":
            _handle_create_backup()
        elif scelta == "3":
            _handle_restore_backup()
        ui.wait_enter()


def _handle_clear_cache() -> None:
    """Cancella cache e file temporanei."""
    ui.show_header("CLEAR CACHE")
    
    cache_size_before = cache_mgr.get_cache_size()
    print(f"  Cache attuale: {cache_mgr.format_size(cache_size_before)}")
    print()
    
    if not ui.ask_yes_no("Cancellare la cache?"):
        return
    
    print()
    print("  Cancellazione in corso...")
    result = cache_mgr.clear_all_cache()
    
    print()
    print(f"  File temporanei cancellati: {result['temp_files_deleted']}")
    print(f"  Log cancellati:             {result['logs_deleted']}")
    if result['temp_errors'] > 0:
        ui.show_warning(f"Errori durante la cancellazione: {result['temp_errors']}")
    
    print()
    print(f"  Cache prima: {cache_mgr.format_size(result['cache_size_before'])}")
    print(f"  Cache dopo:  {cache_mgr.format_size(result['cache_size_after'])}")
    
    if result['cache_size_before'] > result['cache_size_after']:
        saved = result['cache_size_before'] - result['cache_size_after']
        ui.show_success(f"Spazio liberato: {cache_mgr.format_size(saved)}")
    else:
        ui.show_info("Cache gia pulita.")


def _handle_create_backup() -> None:
    """Crea un backup dei file sensibili."""
    ui.show_header("BACKUP FILE SENSIBILI")
    
    if not ui.ask_yes_no("Creare un backup?"):
        return
    
    print()
    print("  Backup in corso...")
    result = backup_mgr.create_backup()
    
    print()
    print(f"  Timestamp: {result['timestamp']}")
    print(f"  Percorso:  {result['backup_path']}")
    print(f"  File con backup: {result['files_backed_up']}")
    
    if result['files_failed'] > 0:
        ui.show_warning(f"Errori: {result['files_failed']}")
        for err in result['errors'][:3]:
            print(f"    - {err}")
    else:
        ui.show_success("Backup completato con successo!")


def _handle_restore_backup() -> None:
    """Ripristina un backup."""
    ui.show_header("RIPRISTINA BACKUP")
    
    backups = backup_mgr.list_backups()
    
    if not backups:
        ui.show_info("Nessun backup disponibile.")
        return
    
    print()
    print("  Backup disponibili:")
    print()
    for i, backup in enumerate(backups, 1):
        timestamp_display = backup['timestamp'] if backup['timestamp'] else backup['name']
        print(f"  {i}.  {timestamp_display}  ({backup['files_count']} file)")
    
    print()
    print("  0.  Annulla")
    print()
    
    scelta = input("  Scegli un backup da ripristinare (0 = annulla): ").strip()
    
    if scelta == "0":
        return
    
    if not scelta.isdigit() or not (1 <= int(scelta) <= len(backups)):
        ui.show_error("Selezione non valida.")
        return
    
    backup = backups[int(scelta) - 1]
    
    if not ui.ask_yes_no(f"Ripristinare {backup['name']}?"):
        return
    
    print()
    print("  Ripristino in corso...")
    result = backup_mgr.restore_backup(backup['name'])
    
    if result['success']:
        ui.show_success(f"Backup ripristinato: {result['files_restored']} file")
        if result['files_failed'] > 0:
            ui.show_warning(f"Con {result['files_failed']} errori")
    else:
        ui.show_error("Ripristino fallito.")
        for err in result['errors'][:3]:
            print(f"  - {err}")


def main() -> None:
    """Entry point principale."""
    logger.info("Download Center v2.0 avviato", module="main")
    config.ensure_directories()
    
    # Verifica se è la prima esecuzione
    if config.is_first_run():
        ui.show_header("BENVENUTO - DOWNLOAD CENTER v2.0")
        ui.show_info("Prima esecuzione — directory create automaticamente.")
        ui.show_info(f"Download: {config.get_download_dir()}")
        ui.show_info(f"Link:     {config.get_link_dir()}")
        ui.show_info(f"Export:   {config.get_export_dir()}")
        config.set("first_run", False)
        ui.wait_enter()
    
    # Esegui startup initialization
    _startup_initialization()
    
    # Mostra menu principale
    _show_main_menu()
    
    logger.info("Download Center terminato", module="main")


if __name__ == "__main__":
    main()
