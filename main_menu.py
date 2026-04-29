#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Center v2.1 - Main Menu UPGRADE
Entry point refactored con architettura core centralizzata.

UPGRADE v2.1:
  [NEW]     Timer 24h per startup initialization
  [NEW]     Menu cambio URL per moduli anime/manga/vinted/download
  [MANTIENE] Tutta la struttura menu principale invariata
  [MANTIENE] Startup initialization sequence all'avvio
  [MANTIENE] Importazioni corrette e robust

PATCH v2.1.1:
  [FIX] _show_cambio_url_menu() — aggiunta opzione Vinted (opz. 3),
        Reset spostato a opzione 5. Propagazione URL a ricerca_vinted.
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

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
from download.handlers import download_handlers


# ════════════════════════════════════════════════════════════════════════════
# TIMER 24 ORE - IMPLEMENTAZIONE CORRETTA
# ════════════════════════════════════════════════════════════════════════════

_TIMER_FILE = _SCRIPTS / "temp" / ".startup_timer.json"

def _save_timer_timestamp() -> None:
    """Salva il timestamp attuale per il timer 24h."""
    try:
        _TIMER_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_startup": datetime.now().isoformat(),
            "version": "2.1"
        }
        with open(_TIMER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Timer 24h salvato", module="timer")
    except Exception as e:
        logger.error(f"Errore salvataggio timer: {e}", module="timer")


def _check_timer_24h() -> bool:
    """
    Verifica se sono passate 24 ore dall'ultimo startup.
    Ritorna True se deve eseguire startup, False altrimenti.
    """
    try:
        if not _TIMER_FILE.exists():
            logger.info("Primo avvio - esegui startup", module="timer")
            return True
        
        with open(_TIMER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        last_startup_str = data.get("last_startup", "")
        if not last_startup_str:
            logger.info("Timer non valido - esegui startup", module="timer")
            return True
        
        last_startup = datetime.fromisoformat(last_startup_str)
        now = datetime.now()
        elapsed = now - last_startup
        
        # 24 ore = 86400 secondi
        if elapsed.total_seconds() >= 86400:
            logger.info(f"Timer scaduto ({elapsed.days}d {elapsed.seconds//3600}h) - esegui startup", module="timer")
            return True
        else:
            remaining = timedelta(seconds=86400) - elapsed
            total_sec = int(remaining.total_seconds())  # [FIX] include anche i giorni
            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60
            logger.info(f"Timer attivo: {hours}h {minutes}m rimanenti", module="timer")
            print(f"\n  ⏱  Timer attivo: {hours}h {minutes}m rimanenti\n")
        # [FIX] Aggiungi pausa per visualizzare il timer
            import time
            time.sleep(2)
            input("  Premi INVIO per continuare...")
            return False
    
    except Exception as e:
        logger.error(f"Errore verifica timer: {e}", module="timer")
        return True


# ════════════════════════════════════════════════════════════════════════════
# GESTIONE URL MODULI - NUOVO
# ════════════════════════════════════════════════════════════════════════════


def _show_cambio_url_menu() -> None:
    """
    Menu per cambiare gli URL dei moduli — usa url_mgr centralizzato.

    PATCH v2.1.1:
      - Aggiunta opzione 3 Vinted (manga/vinted in url_mgr).
      - La modifica viene propagata a ricerca_vinted.py che legge
        da url_mgr al momento dell'import (fallback block aggiornato).
      - Reset spostato a opzione 5.
    """
    try:
        from core.url_manager import url_mgr
    except ImportError:
        try:
            from scripts.core.url_manager import url_mgr
        except ImportError:
            ui.show_error("Impossibile caricare url_manager.")
            ui.wait_enter()
            return

    # Mappa: (Label, categoria, chiave)
    _CATS = [
        ("Anime",    "anime",    "animeworld"),
        ("Manga",    "manga",    "mangacomicsmarket"),
        ("Vinted",   "manga",    "vinted"),
        ("Download", "download", "amazon"),
    ]

    while True:
        ui.show_header("CAMBIO URL MODULI")
        print()
        print("  URL Attuali:")
        for i, (label, cat, key) in enumerate(_CATS, 1):
            url = url_mgr.urls.get(cat, {}).get(key, "N/D")
            print(f"  {i}. {label:<10} {url}")
        print()
        print("  +--------------------------------------+")
        print("  |  1.  Cambia URL Anime               |")
        print("  |  2.  Cambia URL Manga               |")
        print("  |  3.  Cambia URL Vinted              |")
        print("  |  4.  Cambia URL Download            |")
        print("  |  5.  Reset URL di default           |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")

        scelta = ui.ask_choice("Scegli un'opzione (0-5): ", ["0","1","2","3","4","5"])

        if scelta == "0":
            return

        elif scelta in ("1", "2", "3", "4"):
            label, cat, key = _CATS[int(scelta) - 1]
            old_url = url_mgr.urls.get(cat, {}).get(key, "N/D")
            print()
            print(f"  URL attuale ({label}): {old_url}")
            new_url = input(f"  Nuovo URL {label} (INVIO per annullare): ").strip()
            if new_url:
                if not new_url.startswith(("http://", "https://")):
                    ui.show_error("URL non valido — deve iniziare con http:// o https://")
                else:
                    url_mgr.set(cat, key, new_url)
                    ui.show_success(f"URL {label} aggiornato: {new_url}")
            else:
                ui.show_info("Operazione annullata.")

        elif scelta == "5":
            if ui.ask_yes_no("Ripristinare URL di default?"):
                url_mgr.reset()
                ui.show_success("URL ripristinati ai valori di default")

        ui.wait_enter()

def _check_dependencies() -> Dict[str, bool]:
    """
    Verifica tutte le dipendenze richieste.
    Ritorna dict con stato di ogni libreria.
    """
    deps = {
        'requests': False,
        'beautifulsoup4': False,
        'playwright': False,
        'yt-dlp': False,
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
    
    # Verifica yt-dlp
    try:
        import yt_dlp  # noqa: F401
        deps['yt-dlp'] = True
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


def _check_nuovi_episodi() -> list:
    """
    Scraping silenzioso degli aggiornamenti episodi.
    Ritorna lista di dict: [{"titolo":..., "nuovi":..., "da":..., "a":...}]
    """
    try:
        from anime.watchlist import check_aggiornamenti_silenzioso
        return check_aggiornamenti_silenzioso()
    except Exception as e:
        logger.warning(f"Impossibile verificare nuovi episodi: {e}", module="startup")
        return []


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
    ui.show_header("DOWNLOAD CENTER v2.1 - STARTUP")
    
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
        aggiornati = _check_nuovi_episodi()
        if aggiornati:
            print(f"  ✅ {len(aggiornati)} serie aggiornate:")
            print()
            for item in aggiornati:
                nuovi = item.get("nuovi", 0)
                da    = item.get("da", "?")
                a     = item.get("a", "?")
                print(f"    • {item.get('titolo')} +{nuovi} [{da}→{a}]")
            print()
        else:
            ui.show_info("Nessun nuovo episodio disponibile")
    except Exception as e:
        ui.show_warning("Impossibile verificare nuovi episodi")
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
    # [FIX] Salva il timestamp timer 24h PRIMA di attendere INVIO
    _save_timer_timestamp()  # [FIX] salvato prima dell'attesa INVIO
    
    # Salva il timestamp per il timer
    ui.wait_enter("Premi INVIO per continuare...")


def _show_main_menu() -> None:
    """Menu principale Download Center v2.1."""
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
                from anime import handlers as _anime_mod
                _anime_mod.anime_handlers.show_menu()   # ← usa l'istanza della classe
            except (ImportError, AttributeError) as e:
                ui.show_error(f"Modulo anime non disponibile: {e}")
                ui.wait_enter()
        elif scelta == "2":
            try:
                from manga.handlers import show_menu as manga_show_menu
                manga_show_menu()   # ← funzione libera, non metodo di classe
            except (ImportError, AttributeError) as e:
                ui.show_error(f"Modulo manga non disponibile: {e}")
                ui.wait_enter()


def _submenu_download() -> None:
    try:
        from download.handlers import download_handlers
        download_handlers.show_menu()
    except (ImportError, AttributeError) as e:
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
        print("  |  4.  Cambio URL moduli               |")
        print("  |  5.  Reset impostazioni default      |")
        print("  |  6.  Impostazioni yt-dlp             |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        scelta = ui.ask_choice("Scegli un'opzione (0-6): ", ["0","1","2","3","4","5","6"])
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
            _show_cambio_url_menu()
        elif scelta == "5":
            if ui.ask_yes_no("Confermi reset impostazioni?"):
                config.reset_to_defaults()
                ui.show_success("Impostazioni ripristinate.")
        elif scelta == "6":
            _submenu_ytdlp_settings()
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



def _submenu_ytdlp_settings() -> None:
    """
    Submenu impostazioni yt-dlp.
    Legge/scrive le opzioni in prefs.json sotto la chiave "ytdlp".

    Opzioni gestite:
      format              — Formato video (es. best, bestvideo+bestaudio, 1080p)
      merge_output_format — Contenitore output (mp4, mkv, webm)
      audio_only          — Estrai solo audio (True/False)
      audio_format        — Formato audio (mp3, aac, flac, m4a, opus, wav)
      audio_quality       — Qualità audio 0-9 (0=migliore)
      write_subs          — Scarica sottotitoli (True/False)
      write_auto_subs     — Sottotitoli automatici (True/False)
      sub_langs           — Lingue sottotitoli (es. it,en)
      sub_format          — Formato sottotitoli (srt, ass, vtt)
      proxy               — URL proxy (es. socks5://127.0.0.1:1080)
      cookies_from_browser— Browser da cui leggere i cookie (chrome, firefox…)
      cookies_file        — Percorso file cookie Netscape
      rate_limit          — Limite velocità download (es. 2M, 500K)
      concurrent_frags    — Frammenti paralleli HLS (1-16)
      no_check_certs      — Disabilita verifica certificati SSL (True/False)
      prefer_free_formats — Preferisce formati liberi (True/False)
      embed_thumbnail     — Incorpora thumbnail nel file (True/False)
      embed_metadata      — Incorpora metadati nel file (True/False)
      sleep_interval      — Pausa tra download in secondi (0=nessuna)
    """
    import json as _json
    from pathlib import Path as _Path

    _SCRIPTS_DIR = _Path(__file__).parent / "scripts"
    _PREFS_FILE  = _SCRIPTS_DIR / "temp" / "prefs.json"

    # ── Helpers prefs ─────────────────────────────────────────────────────────
    def _load_prefs() -> dict:
        try:
            with open(_PREFS_FILE, "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return {}

    def _save_prefs(data: dict) -> None:
        _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_PREFS_FILE, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_ytdlp_cfg(prefs: dict) -> dict:
        return prefs.setdefault("ytdlp", {})

    # Defaults
    DEFAULTS = {
        "format":               "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format":  "mp4",
        "audio_only":           False,
        "audio_format":         "mp3",
        "audio_quality":        0,
        "write_subs":           False,
        "write_auto_subs":      False,
        "sub_langs":            "it,en",
        "sub_format":           "srt",
        "proxy":                "",
        "cookies_from_browser": "",
        "cookies_file":         "",
        "rate_limit":           "",
        "concurrent_frags":     1,
        "no_check_certs":       False,
        "prefer_free_formats":  False,
        "embed_thumbnail":      False,
        "embed_metadata":       True,
        "sleep_interval":       0,
    }

    # ── Verifica yt-dlp installato ────────────────────────────────────────────
    try:
        import yt_dlp
        _ytdlp_ver = getattr(yt_dlp.version, "__version__", "?")
        _ytdlp_ok  = True
    except ImportError:
        _ytdlp_ver = "NON INSTALLATO"
        _ytdlp_ok  = False

    while True:
        prefs  = _load_prefs()
        cfg    = _get_ytdlp_cfg(prefs)

        # Applica defaults per chiavi mancanti
        for k, v in DEFAULTS.items():
            cfg.setdefault(k, v)

        ui.show_header(f"IMPOSTAZIONI yt-dlp  [{_ytdlp_ver}]")

        if not _ytdlp_ok:
            print("  ⚠  yt-dlp non installato — installa con: pip install yt-dlp")
            print()

        # ── Visualizza impostazioni correnti ──────────────────────────────────
        print("  ┌─── FORMATO ─────────────────────────────────────────────────┐")
        print(f"  │  1.  Formato video      : {cfg['format'][:50]}")
        print(f"  │  2.  Contenitore output : {cfg['merge_output_format']}")
        print(f"  │  3.  Solo audio         : {cfg['audio_only']}")
        print(f"  │  4.  Formato audio      : {cfg['audio_format']}")
        print(f"  │  5.  Qualità audio (0=↑): {cfg['audio_quality']}")
        print("  ├─── SOTTOTITOLI ─────────────────────────────────────────────┤")
        print(f"  │  6.  Scarica sottotitoli: {cfg['write_subs']}")
        print(f"  │  7.  Sottotitoli auto   : {cfg['write_auto_subs']}")
        print(f"  │  8.  Lingue             : {cfg['sub_langs']}")
        print(f"  │  9.  Formato sub        : {cfg['sub_format']}")
        print("  ├─── RETE ────────────────────────────────────────────────────┤")
        print(f"  │  10. Proxy              : {cfg['proxy'] or '(nessuno)'}")
        print(f"  │  11. Cookie da browser  : {cfg['cookies_from_browser'] or '(nessuno)'}")
        print(f"  │  12. File cookie        : {cfg['cookies_file'] or '(nessuno)'}")
        print(f"  │  13. Limite velocità    : {cfg['rate_limit'] or '(illimitata)'}")
        print(f"  │  14. Frammenti paralleli: {cfg['concurrent_frags']}")
        print(f"  │  15. Disabilita SSL     : {cfg['no_check_certs']}")
        print("  ├─── AVANZATE ────────────────────────────────────────────────┤")
        print(f"  │  16. Preferisci formati liberi: {cfg['prefer_free_formats']}")
        print(f"  │  17. Incorpora thumbnail      : {cfg['embed_thumbnail']}")
        print(f"  │  18. Incorpora metadati       : {cfg['embed_metadata']}")
        print(f"  │  19. Pausa tra download (s)   : {cfg['sleep_interval']}")
        print("  ├─────────────────────────────────────────────────────────────┤")
        print("  │  20. Preset rapidi                                          │")
        print("  │  21. Reset valori default                                   │")
        print("  │   0. Torna                                                  │")
        print("  └─────────────────────────────────────────────────────────────┘")

        valid = [str(i) for i in range(22)] + ["0"]
        scelta = ui.ask_choice("Scegli impostazione (0-21): ",
                               [str(i) for i in range(22)])

        if scelta == "0":
            return

        # ── Formato video ─────────────────────────────────────────────────────
        elif scelta == "1":
            print()
            print("  Preset formato:")
            print("    a) Best MP4 (default)")
            print("    b) Best qualità disponibile")
            print("    c) Max 1080p MP4")
            print("    d) Max 720p MP4")
            print("    e) Max 480p MP4")
            print("    f) Inserisci manualmente")
            ch = input("  Scelta (a-f): ").strip().lower()
            presets = {
                "a": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "b": "bestvideo+bestaudio/best",
                "c": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
                "d": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
                "e": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
            }
            if ch in presets:
                cfg["format"] = presets[ch]
                ui.show_success(f"Formato impostato: {cfg['format'][:60]}")
            elif ch == "f":
                val = input("  Formato yt-dlp: ").strip()
                if val:
                    cfg["format"] = val
                    ui.show_success("Formato aggiornato.")

        # ── Contenitore output ────────────────────────────────────────────────
        elif scelta == "2":
            print()
            print("  Contenitori disponibili: mp4, mkv, webm, mov, avi, flv")
            val = input(f"  Contenitore [{cfg['merge_output_format']}]: ").strip().lower()
            if val in ("mp4","mkv","webm","mov","avi","flv"):
                cfg["merge_output_format"] = val
                ui.show_success(f"Contenitore: {val}")
            elif val:
                ui.show_error("Contenitore non valido.")

        # ── Solo audio ────────────────────────────────────────────────────────
        elif scelta == "3":
            cfg["audio_only"] = not cfg["audio_only"]
            ui.show_success(f"Solo audio: {cfg['audio_only']}")

        # ── Formato audio ─────────────────────────────────────────────────────
        elif scelta == "4":
            print()
            print("  Formati: mp3, aac, flac, m4a, opus, vorbis, wav, best")
            val = input(f"  Formato audio [{cfg['audio_format']}]: ").strip().lower()
            if val in ("mp3","aac","flac","m4a","opus","vorbis","wav","best"):
                cfg["audio_format"] = val
                ui.show_success(f"Formato audio: {val}")
            elif val:
                ui.show_error("Formato non valido.")

        # ── Qualità audio ─────────────────────────────────────────────────────
        elif scelta == "5":
            print()
            print("  Qualità audio: 0 (migliore) → 9 (peggiore), 5 = medio")
            val = input(f"  Qualità [{cfg['audio_quality']}]: ").strip()
            if val.isdigit() and 0 <= int(val) <= 9:
                cfg["audio_quality"] = int(val)
                ui.show_success(f"Qualità audio: {val}")
            elif val:
                ui.show_error("Inserisci un numero da 0 a 9.")

        # ── Sottotitoli ───────────────────────────────────────────────────────
        elif scelta == "6":
            cfg["write_subs"] = not cfg["write_subs"]
            ui.show_success(f"Scarica sottotitoli: {cfg['write_subs']}")

        elif scelta == "7":
            cfg["write_auto_subs"] = not cfg["write_auto_subs"]
            ui.show_success(f"Sottotitoli automatici: {cfg['write_auto_subs']}")

        elif scelta == "8":
            print()
            print("  Inserisci codici lingua separati da virgola (es: it,en,ja)")
            val = input(f"  Lingue [{cfg['sub_langs']}]: ").strip()
            if val:
                cfg["sub_langs"] = val
                ui.show_success(f"Lingue sottotitoli: {val}")

        elif scelta == "9":
            print()
            print("  Formati: srt, ass, vtt, lrc, best")
            val = input(f"  Formato sub [{cfg['sub_format']}]: ").strip().lower()
            if val in ("srt","ass","vtt","lrc","best"):
                cfg["sub_format"] = val
                ui.show_success(f"Formato sub: {val}")
            elif val:
                ui.show_error("Formato non valido.")

        # ── Rete ──────────────────────────────────────────────────────────────
        elif scelta == "10":
            print()
            print("  Esempi: socks5://127.0.0.1:1080  |  http://proxy:8080")
            print("  (lascia vuoto per nessun proxy)")
            val = input(f"  Proxy [{cfg['proxy'] or 'nessuno'}]: ").strip()
            cfg["proxy"] = val
            ui.show_success(f"Proxy: {val or 'rimosso'}")

        elif scelta == "11":
            print()
            print("  Browser: chrome, firefox, edge, safari, opera, brave, vivaldi")
            print("  (lascia vuoto per disabilitare)")
            val = input(f"  Browser [{cfg['cookies_from_browser'] or 'nessuno'}]: ").strip().lower()
            if val in ("chrome","firefox","edge","safari","opera","brave","vivaldi","chromium",""):
                cfg["cookies_from_browser"] = val
                ui.show_success(f"Cookie da browser: {val or 'disabilitato'}")
            elif val:
                ui.show_error("Browser non riconosciuto.")

        elif scelta == "12":
            print()
            print("  Percorso file cookie in formato Netscape (lascia vuoto per nessuno)")
            val = input(f"  File cookie [{cfg['cookies_file'] or 'nessuno'}]: ").strip()
            cfg["cookies_file"] = val
            ui.show_success(f"File cookie: {val or 'rimosso'}")

        elif scelta == "13":
            print()
            print("  Esempi: 2M (2 MB/s), 500K (500 KB/s). Lascia vuoto = illimitata.")
            val = input(f"  Limite velocità [{cfg['rate_limit'] or 'illimitata'}]: ").strip().upper()
            cfg["rate_limit"] = val
            ui.show_success(f"Limite: {val or 'rimosso'}")

        elif scelta == "14":
            print()
            print("  Frammenti paralleli per HLS: 1-16 (default 1)")
            val = input(f"  Frammenti [{cfg['concurrent_frags']}]: ").strip()
            if val.isdigit() and 1 <= int(val) <= 16:
                cfg["concurrent_frags"] = int(val)
                ui.show_success(f"Frammenti paralleli: {val}")
            elif val:
                ui.show_error("Inserisci un numero da 1 a 16.")

        elif scelta == "15":
            cfg["no_check_certs"] = not cfg["no_check_certs"]
            ui.show_success(f"Disabilita SSL: {cfg['no_check_certs']}")

        # ── Avanzate ──────────────────────────────────────────────────────────
        elif scelta == "16":
            cfg["prefer_free_formats"] = not cfg["prefer_free_formats"]
            ui.show_success(f"Preferisci formati liberi: {cfg['prefer_free_formats']}")

        elif scelta == "17":
            cfg["embed_thumbnail"] = not cfg["embed_thumbnail"]
            ui.show_success(f"Incorpora thumbnail: {cfg['embed_thumbnail']}")

        elif scelta == "18":
            cfg["embed_metadata"] = not cfg["embed_metadata"]
            ui.show_success(f"Incorpora metadati: {cfg['embed_metadata']}")

        elif scelta == "19":
            print()
            print("  Secondi di pausa tra download consecutivi (0 = nessuna)")
            val = input(f"  Pausa [{cfg['sleep_interval']}]: ").strip()
            if val.isdigit():
                cfg["sleep_interval"] = int(val)
                ui.show_success(f"Pausa: {val}s")
            elif val:
                ui.show_error("Inserisci un numero intero >= 0.")

        # ── Preset rapidi ─────────────────────────────────────────────────────
        elif scelta == "20":
            print()
            print("  PRESET RAPIDI:")
            print("  a) Streaming video — best MP4, metadati, no subs")
            print("  b) Podcast / Audio — solo MP3 qualità massima")
            print("  c) Archivio HD     — MKV best, subs IT+EN, metadati+thumb")
            print("  d) Mobile          — MP4 max 720p, leggero")
            print("  e) Anonimo         — best, no cookie, no metadati")
            ch = input("  Preset (a-e, Invio=annulla): ").strip().lower()
            presets_map = {
                "a": {
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "merge_output_format": "mp4",
                    "audio_only": False,
                    "write_subs": False,
                    "embed_metadata": True,
                    "embed_thumbnail": False,
                },
                "b": {
                    "format": "bestaudio/best",
                    "merge_output_format": "mp4",
                    "audio_only": True,
                    "audio_format": "mp3",
                    "audio_quality": 0,
                    "embed_metadata": True,
                    "embed_thumbnail": True,
                },
                "c": {
                    "format": "bestvideo+bestaudio/best",
                    "merge_output_format": "mkv",
                    "audio_only": False,
                    "write_subs": True,
                    "write_auto_subs": True,
                    "sub_langs": "it,en",
                    "sub_format": "srt",
                    "embed_metadata": True,
                    "embed_thumbnail": True,
                },
                "d": {
                    "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
                    "merge_output_format": "mp4",
                    "audio_only": False,
                    "write_subs": False,
                    "embed_metadata": False,
                },
                "e": {
                    "format": "bestvideo+bestaudio/best",
                    "merge_output_format": "mp4",
                    "cookies_from_browser": "",
                    "cookies_file": "",
                    "embed_metadata": False,
                    "embed_thumbnail": False,
                    "no_check_certs": False,
                },
            }
            if ch in presets_map:
                cfg.update(presets_map[ch])
                ui.show_success(f"Preset '{ch.upper()}' applicato.")
            elif ch:
                ui.show_error("Preset non valido.")

        # ── Reset ─────────────────────────────────────────────────────────────
        elif scelta == "21":
            if ui.ask_yes_no("Ripristinare tutti i valori default yt-dlp?"):
                cfg.clear()
                cfg.update(DEFAULTS)
                ui.show_success("Impostazioni yt-dlp ripristinate.")

        # ── Salva sempre ──────────────────────────────────────────────────────
        prefs["ytdlp"] = cfg
        _save_prefs(prefs)
        ui.wait_enter()


def main() -> None:
    """Entry point principale."""
    logger.info("Download Center v2.1 avviato", module="main")
    config.ensure_directories()
    
    # Verifica se è la prima esecuzione
    if config.is_first_run():
        ui.show_header("BENVENUTO - DOWNLOAD CENTER v2.1")
        ui.show_info("Prima esecuzione — directory create automaticamente.")
        ui.show_info(f"Download: {config.get_download_dir()}")
        ui.show_info(f"Link:     {config.get_link_dir()}")
        ui.show_info(f"Export:   {config.get_export_dir()}")
        config.set("first_run", False)
        ui.wait_enter()
    
    # Verifica timer 24h
    if _check_timer_24h():
        # Esegui startup initialization
        try:
            _startup_initialization()
        except Exception as e:
            logger.error(f"Errore durante startup: {e}", module="main")  # [FIX]
        finally:
            _save_timer_timestamp()  # [FIX] garantisce salvataggio timer anche in caso di errore
    
    # Mostra menu principale
    _show_main_menu()
    
    logger.info("Download Center terminato", module="main")


if __name__ == "__main__":
    main()
