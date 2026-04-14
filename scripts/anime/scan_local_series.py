#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_local_series.py v2.5 - REFACTORING PERCORSI ROBUSTI
Download Center - scripts/anime/scan_local_series.py

NOVITA v2.5 (rispetto a v2.4):
  [REFACTOR] Path handling functions migrate in anime_engine v2.1
             - clean_unc_path: importato da engine
             - path_exists_safe: importato da engine
             - iterdir_safe: importato da engine
  [REFACTOR] Interrupt handling consolidato
             - setup_interrupt_global: importato da engine
             - teardown_interrupt_global: importato da engine
  [MAINT]    Tutta logica v2.4 invariata
             - scan_local_folder, complete_with_schema, etc
  [COMPAT]   100% backward-compatible con v2.4

BENEFICI:
  - DRY principle: niente duplicazione tra moduli
  - Manutenzione centralizzata: fix in anime_engine
  - Reuso in altri moduli: watchlist, estrai_link, etc
  - Codice piu leggibile: meno funzioni locali
"""

import csv
import json
import os
import re
import sys
import time
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── Import da anime_engine v2.1+ ────────────────────────────────────────────
try:
    from anime_engine import (
        clear_screen, show_header, show_success, show_error, show_info,
        show_warning, ask_yes_no, wait_enter, get_path_input,
        sanitize_filename, print_progress_eta,
        interrupted,
        # NEW v2.5 - da anime_engine v2.1+:
        clean_unc_path,
        path_exists_safe,
        iterdir_safe,
        setup_interrupt_global,
        teardown_interrupt_global,
    )
except ImportError as e:
    print(f"ERRORE: Impossibile importare anime_engine.py: {e}")
    sys.exit(1)


# ── Percorsi ─────────────────────────────────────────────────────────────────

_SCRIPTS_DIR  = Path(__file__).parent.parent.resolve()
_ROOT_DIR     = _SCRIPTS_DIR.parent.resolve()
_TEMP_DIR     = _SCRIPTS_DIR / "temp"
_EXPORT_DIR   = _ROOT_DIR / "export" / "scan"

_TEMP_DIR.mkdir(parents=True, exist_ok=True)
LAST_SCAN_FILE = _TEMP_DIR / "last_scan.json"


# ── Costanti ─────────────────────────────────────────────────────────────────

VIDEO_EXTENSIONS: tuple = (
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".m4v",
    ".mpg", ".mpeg", ".3gp", ".ogv", ".ts", ".m3u8", ".webm",
    ".vob", ".f4v", ".asf", ".rm", ".rmvb",
)

EXCLUDED_FOLDERS: set = {
    ".", "..", "__pycache__", ".git", ".github", "node_modules",
    ".vscode", ".idea", "temp", "tmp", ".cache",
}


# ════════════════════════════════════════════════════════════════════════════
# SCAN LOCALE
# ════════════════════════════════════════════════════════════════════════════

def count_videos(folder_path: Path) -> int:
    "Conta file video in una cartella (non ricorsivo)."
    try:
        return sum(
            1 for item in folder_path.iterdir()
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        )
    except (PermissionError, OSError):
        return 0
    except Exception:
        return 0


def scan_local_folder(base_path: str) -> List[Dict]:
    """
    Scansiona cartella cercando serie. Puo essere interrotta con Ctrl+C.
    
    NEW v2.5: Usa funzioni path handling da anime_engine v2.1+
    """
    series = []
    
    base_path = clean_unc_path(base_path)  # NEW v2.5: da anime_engine
    
    if not path_exists_safe(base_path):  # NEW v2.5: da anime_engine
        show_error(f"Percorso non esiste o non accessibile: {base_path}")
        return []

    base = Path(base_path)
    
    if not base.is_dir():
        show_error(f"Non e una cartella: {base_path}")
        return []

    items = iterdir_safe(str(base))  # NEW v2.5: da anime_engine
    if not items:
        return []
    
    has_subdirs = False
    for item in items:
        if interrupted.is_set():
            show_warning("Scansione interrotta - dati parziali salvati.")
            break
        
        if not item.is_dir() or item.name in EXCLUDED_FOLDERS:
            continue
        has_subdirs = True
        video_count = count_videos(item)
        if video_count > 0:
            series.append({
                "titolo":          item.name,
                "percorso":        str(item),
                "episodi_locali":  video_count,
                "episodi_totali":  "?",
                "stato":           "Sconosciuto",
                "link_ack":        None,
                "completezza":     "?",
                "data_scan":       datetime.now().isoformat(),
            })

    if not series and (not has_subdirs or len(items) == 0):
        video_count = count_videos(base)
        if video_count > 0:
            series.append({
                "titolo":          base.name,
                "percorso":        str(base),
                "episodi_locali":  video_count,
                "episodi_totali":  "?",
                "stato":           "Sconosciuto",
                "link_ack":        None,
                "completezza":     "?",
                "data_scan":       datetime.now().isoformat(),
            })

    return series


# ════════════════════════════════════════════════════════════════════════════
# PERSISTENZA
# ════════════════════════════════════════════════════════════════════════════

def save_scan(series: List[Dict]) -> bool:
    "Salva scan corrente in JSON."
    try:
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(LAST_SCAN_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"data_scan": datetime.now().isoformat(), "series": series},
                f, indent=2, ensure_ascii=False,
            )
        return True
    except Exception as e:
        show_error(f"Errore salvataggio scan: {e}")
        return False


def load_last_scan() -> Optional[List[Dict]]:
    "Carica l'ultimo scan da JSON."
    try:
        if LAST_SCAN_FILE.exists():
            with open(LAST_SCAN_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("series", [])
    except Exception as e:
        show_error(f"Errore caricamento scan: {e}")
    return None


def load_from_csv(file_path: str) -> Optional[List[Dict]]:
    "Carica serie da file CSV esportato."
    try:
        series = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ep_local = int(row.get("Episodi Locali", 0))
                except Exception:
                    ep_local = 0
                try:
                    ep_total = int(row.get("Episodi Totali", "?"))
                except Exception:
                    ep_total = "?"
                series.append({
                    "titolo":          row.get("Titolo", "Sconosciuto"),
                    "episodi_locali":  ep_local,
                    "episodi_totali":  ep_total,
                    "stato":           row.get("Stato", "Sconosciuto"),
                    "completezza":     row.get("Completezza", "?"),
                    "percorso":        "",
                    "link_ack":        None,
                    "data_scan":       datetime.now().isoformat(),
                })
        return series if series else None
    except Exception as e:
        show_error(f"Errore lettura CSV: {e}")
        return None


def load_from_txt(file_path: str) -> Optional[List[Dict]]:
    "Carica serie da file TXT esportato."
    try:
        series = []
        current = None
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if re.match(r"^\d+\.\s+", line):
                    if current and current.get("titolo"):
                        series.append(current)
                    m = re.match(r"^\d+\.\s+(.+)$", line)
                    if m:
                        current = {
                            "titolo": m.group(1), "episodi_locali": 0,
                            "episodi_totali": "?", "stato": "Sconosciuto",
                            "completezza": "?", "percorso": "",
                            "link_ack": None, "data_scan": datetime.now().isoformat(),
                        }
                elif "Episodi locali:" in line and current:
                    m = re.search(r"Episodi locali:\s*(\d+)", line)
                    if m:
                        current["episodi_locali"] = int(m.group(1))
                elif "Episodi totali:" in line and current:
                    m = re.search(r"Episodi totali:\s*(\d+|\?)", line)
                    if m:
                        val = m.group(1)
                        current["episodi_totali"] = int(val) if val.isdigit() else val
                elif "Stato:" in line and current:
                    m = re.search(r"Stato:\s*(.+)$", line)
                    if m:
                        current["stato"] = m.group(1).strip()
                elif "Completezza:" in line and current:
                    m = re.search(r"Completezza:\s*(.+)$", line)
                    if m:
                        current["completezza"] = m.group(1).strip()
        if current and current.get("titolo"):
            series.append(current)
        return series if series else None
    except Exception as e:
        show_error(f"Errore lettura TXT: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# DISPLAY & EXPORT
# ════════════════════════════════════════════════════════════════════════════

def print_series_table(series: List[Dict]) -> None:
    "Visualizza tabella serie."
    if not series:
        show_info("Nessuna serie trovata.")
        return
    print()
    print("  " + "-" * 80)
    print(f"  {'#':<4} {'Titolo':<40} {'Ep.Loc':<8} {'Ep.Tot':<8} {'Completezza'}")
    print("  " + "-" * 80)
    for i, s in enumerate(series, 1):
        titolo = s["titolo"]
        if len(titolo) > 40:
            titolo = titolo[:37] + "..."
        print(
            f"  {i:<4} {titolo:<40} "
            f"{str(s.get('episodi_locali', 0)):<8} "
            f"{str(s.get('episodi_totali', '?')):<8} "
            f"{s.get('completezza', '?')}"
        )
    print("  " + "-" * 80)
    print(f"  Totale: {len(series)} serie\n")


def export_to_csv(series: List[Dict], export_path: str) -> bool:
    "Esporta serie in CSV."
    if not series:
        show_error("Nessuna serie da esportare.")
        return False
    try:
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Titolo", "Episodi Locali", "Episodi Totali",
                "Stato", "Completezza", "Data Scan",
            ])
            writer.writeheader()
            for s in series:
                writer.writerow({
                    "Titolo":          s["titolo"],
                    "Episodi Locali":  s.get("episodi_locali", 0),
                    "Episodi Totali":  s.get("episodi_totali", "?"),
                    "Stato":           s.get("stato", "Sconosciuto"),
                    "Completezza":     s.get("completezza", "?"),
                    "Data Scan":       s.get("data_scan", "")[:10],
                })
        show_success(f"Esportato: {Path(export_path).name}")
        return True
    except Exception as e:
        show_error(f"Errore export: {e}")
        return False


def export_to_txt(series: List[Dict], export_path: str) -> bool:
    "Esporta serie in TXT."
    if not series:
        show_error("Nessuna serie da esportare.")
        return False
    try:
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("SCAN SERIE IN LOCALE\n")
            f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            for i, s in enumerate(series, 1):
                f.write(f"{i:3d}. {s['titolo']}\n")
                f.write(f"     Episodi locali: {s.get('episodi_locali', 0)}\n")
                f.write(f"     Episodi totali: {s.get('episodi_totali', '?')}\n")
                f.write(f"     Stato: {s.get('stato', 'Sconosciuto')}\n")
                f.write(f"     Completezza: {s.get('completezza', '?')}\n\n")
            f.write("=" * 80 + "\n")
            f.write(f"Totale serie: {len(series)}\n")
        show_success(f"Esportato: {Path(export_path).name}")
        return True
    except Exception as e:
        show_error(f"Errore export: {e}")
        return False


# ════════════════════════════════════════════════════════════════════════════
# FUNZIONALITA v2.4: COMPLETA CON SCHEDA
# ════════════════════════════════════════════════════════════════════════════

def complete_with_schema(series: List[Dict]) -> bool:
    """
    NEW v2.4: Per ogni serie trovata, ricerca su AnimeClick e salva scheda.
    
    Usa setup_interrupt_global/teardown_interrupt_global da anime_engine v2.1+
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ricerca_scheda_anime import AnimeTracker
    except ImportError:
        show_error("Modulo ricerca_scheda_anime non disponibile.")
        show_info("Assicurati che il file sia nella directory anime/")
        return False
    
    if not series:
        show_error("Nessuna serie da completare.")
        return False
    
    clear_screen()
    show_header("COMPLETA CON SCHEDA v2.4")
    show_info("Ricerca automatica su AnimeClick per ogni serie...")
    print()
    
    tracker = AnimeTracker()
    completati = 0
    falliti = 0
    totale = len(series)
    t0 = time.time()
    
    setup_interrupt_global()  # NEW v2.5: da anime_engine
    
    try:
        for i, s in enumerate(series, 1):
            if interrupted.is_set():
                show_warning(f"Completamento interrotto a {i-1}/{totale}")
                break
            
            titolo = s["titolo"]
            percorso = s.get("percorso", "")
            prefix = f"Ricerca     {titolo[:24]:<24}"
            print_progress_eta(i, totale, prefix=prefix, start_time=t0)
            
            try:
                results = tracker.search_anime(titolo, silent=True)
                if not results:
                    falliti += 1
                    continue
                
                best = results[0]
                details = tracker.get_anime_details(best["link"], silent=True)
                if not details or not details.get("titolo"):
                    falliti += 1
                    continue
                
                s["episodi_totali"] = details.get("episodes", "?")
                s["stato"] = details.get("stato", "Sconosciuto")
                s["link_ack"] = best["link"]
                
                ep_loc = s.get("episodi_locali", 0)
                ep_tot = details.get("episodes", 0)
                if ep_tot > 0:
                    if ep_loc >= ep_tot:
                        s["completezza"] = "100%"
                    else:
                        s["completezza"] = f"{int(ep_loc / ep_tot * 100)}%"
                
                if percorso and Path(percorso).is_dir():
                    success = _export_schema_to_series_folder(
                        details, percorso, titolo
                    )
                    if success:
                        completati += 1
                    else:
                        falliti += 1
                else:
                    falliti += 1
            
            except Exception:
                falliti += 1
        
        print("")
        print()
        show_success(f"Completamento: {completati}/{totale} serie")
        if falliti > 0:
            show_warning(f"{falliti} serie non completate")
        
        if completati > 0 or interrupted.is_set():
            save_scan(series)
            if interrupted.is_set():
                show_info("Dati parziali salvati in: scripts/temp/last_scan.json")
        
        return True
    
    finally:
        teardown_interrupt_global()  # NEW v2.5: da anime_engine


def _export_schema_to_series_folder(
    details: Dict, percorso_serie: str, titolo: str
) -> bool:
    "Esporta file .txt della scheda nella cartella della serie."
    try:
        folder = Path(percorso_serie)
        if not folder.is_dir():
            return False
        
        safe_name = sanitize_filename(titolo)
        txt_file = folder / f"{safe_name}.txt"
        
        sep = "=" * 56
        sep2 = "-" * 56
        generi_str = ", ".join(details.get("generi", [])) or "N/D"
        trama = details.get("trama", "N/D") or "N/D"
        
        if trama.lower().startswith("trama:"):
            trama = trama[6:].strip()
        
        lines = [
            sep,
            " SCHEDA ANIME - ANIMECLICK",
            sep,
            "",
            f"  Titolo  : {details.get('titolo', 'N/D')}",
            f"  Tipo    : {details.get('tipo', 'N/D') or 'N/D'}",
            f"  Anno    : {details.get('anno', 'N/D') or 'N/D'}",
            f"  Episodi : {details.get('episodes', '?') or '?'}",
            f"  Stato   : {details.get('stato', 'N/D') or 'N/D'}",
            f"  Voto    : {details.get('voto', 'N/D') or 'N/D'}",
            f"  Generi  : {generi_str}",
            "",
            sep2,
            " TRAMA",
            sep2,
            "",
        ]
        for line in textwrap.wrap(trama, width=72):
            lines.append(f"  {line}")
        lines += [
            "",
            sep2,
            " LINK E RISORSE",
            sep2,
            "",
            f"  Scheda   : {details.get('link', '')}",
            f"  Cover    : {details.get('copertina', '')}",
            "",
            f"  Data     : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            "",
            sep,
        ]
        
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return True
    
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════════════
# CONFRONTO ANIMECLICK
# ════════════════════════════════════════════════════════════════════════════

def compare_with_animeclick(series: List[Dict]) -> bool:
    "Confronta serie con AnimeClick."
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ricerca_scheda_anime import AnimeTracker
    except ImportError:
        show_error("Modulo ricerca_scheda_anime non disponibile.")
        show_info("Assicurati che il file sia nella directory anime/")
        return False

    if not series:
        show_error("Nessuna serie da confrontare.")
        return False

    clear_screen()
    show_header("CONFRONTO CON ANIMECLICK")

    tracker = AnimeTracker()
    confrontati = 0
    totale = len(series)
    t0 = time.time()
    
    setup_interrupt_global()  # NEW v2.5: da anime_engine
    
    try:
        for i, s in enumerate(series, 1):
            if interrupted.is_set():
                show_warning(f"Confronto interrotto a {i-1}/{totale}")
                break
            
            titolo = s["titolo"]
            prefix = f"Confronto  {titolo[:24]:<24}"
            print_progress_eta(i, totale, prefix=prefix, start_time=t0)

            try:
                results = tracker.search_anime(titolo, silent=True)
                if results:
                    best = results[0]
                    details = tracker.get_anime_details(best["link"], silent=True)
                    if details:
                        ep_tot = details.get("episodes", 0)
                        if ep_tot > 0:
                            s["episodi_totali"] = ep_tot
                            s["link_ack"] = best["link"]
                            ep_loc = s.get("episodi_locali", 0)
                            if ep_loc >= ep_tot:
                                s["completezza"] = "100%"
                            else:
                                s["completezza"] = f"{int(ep_loc / ep_tot * 100)}%"
                            s["stato"] = details.get("stato", "Sconosciuto")
                            confrontati += 1
            except Exception:
                pass

        print("")
        print()
        show_success(f"Confronti completati: {confrontati}/{totale}")
        
        if confrontati > 0 or interrupted.is_set():
            save_scan(series)
            if interrupted.is_set():
                show_info("Dati parziali salvati in: scripts/temp/last_scan.json")
        
        return True
    
    finally:
        teardown_interrupt_global()  # NEW v2.5: da anime_engine


# ════════════════════════════════════════════════════════════════════════════
# MENU PRINCIPALE (v2.5)
# ════════════════════════════════════════════════════════════════════════════

def handle_scan_menu():
    "Menu principale Scan serie in locale."
    setup_interrupt_global()  # NEW v2.5: da anime_engine
    
    try:
        while True:
            if interrupted.is_set():
                show_warning("Uscita richiesta.")
                break
            
            try:
                clear_screen()
                show_header("SCAN SERIE IN LOCALE")
                print("  +--------------------------------------+")
                print("  |  1.  Scansiona cartella              |")
                print("  |  2.  Visualizza ultimo scan          |")
                print("  |  3.  Confronta con AnimeClick        |")
                print("  |  4.  Esporta risultati               |")
                print("  |  5.  Completa con scheda      [NEW]  |")
                print("  |  0.  Torna al menu Anime             |")
                print("  +--------------------------------------+")
                scelta = input("  Scelta (0-5): ").strip()

                if scelta == "0":
                    break
                elif scelta == "1":
                    _handle_scansione()
                elif scelta == "2":
                    _handle_visualizza_ultimo()
                elif scelta == "3":
                    _handle_confronto()
                elif scelta == "4":
                    _handle_export()
                elif scelta == "5":
                    _handle_completa()
            
            except KeyboardInterrupt:
                interrupted.set()
                show_warning("Uscita richiesta.")
                break
    
    finally:
        teardown_interrupt_global()  # NEW v2.5: da anime_engine


def _handle_scansione():
    "Gestisce scansione cartella."
    try:
        clear_screen()
        show_header("SCANSIONE CARTELLA")
        path = get_path_input("Percorso cartella (0 = annulla): ")
        if not path:
            return
        if not path_exists_safe(path):  # NEW v2.5: da anime_engine
            show_error(f"Percorso non valido o non accessibile: {path}")
            wait_enter()
            return

        print()
        show_info("Scansione in corso...")
        series = scan_local_folder(path)

        if not series:
            show_warning("Nessuna serie trovata.")
            show_info("Assicurati che la cartella contenga video o sottocartelle con video.")
            wait_enter()
            return

        save_scan(series)
        clear_screen()
        show_header(f"RISULTATI: {len(series)} serie trovate")
        print_series_table(series)

        while True:
            if interrupted.is_set():
                break
            
            try:
                print("  1. Confronta con AnimeClick")
                print("  2. Completa con scheda")
                print("  3. Esporta risultati")
                print("  4. Nuova scansione")
                print("  0. Torna al menu")
                print()
                opt = input("  Scelta (0-4): ").strip()
                if opt == "0":
                    return
                elif opt == "1":
                    compare_with_animeclick(series)
                    wait_enter()
                    clear_screen()
                    show_header(f"RISULTATI: {len(series)} serie")
                    print_series_table(series)
                elif opt == "2":
                    complete_with_schema(series)
                    wait_enter()
                    clear_screen()
                    show_header(f"RISULTATI: {len(series)} serie")
                    print_series_table(series)
                elif opt == "3":
                    _handle_export_menu(series)
                    break
                elif opt == "4":
                    break
            except KeyboardInterrupt:
                interrupted.set()
                show_warning("Operazione annullata.")
                break
    
    except KeyboardInterrupt:
        interrupted.set()
        show_warning("Scansione annullata.")


def _handle_visualizza_ultimo():
    "Visualizza ultimo scan salvato."
    try:
        clear_screen()
        show_header("ULTIMO SCAN SALVATO")
        series = load_last_scan()
        if not series:
            show_warning("Nessun scan precedente trovato.")
            wait_enter()
            return

        print_series_table(series)
        while True:
            if interrupted.is_set():
                break
            
            try:
                print("  1. Confronta con AnimeClick")
                print("  2. Completa con scheda")
                print("  3. Esporta risultati")
                print("  0. Torna al menu")
                print()
                opt = input("  Scelta (0-3): ").strip()
                if opt == "0":
                    return
                elif opt == "1":
                    compare_with_animeclick(series)
                    wait_enter()
                    clear_screen()
                    show_header(f"RISULTATI: {len(series)} serie")
                    print_series_table(series)
                elif opt == "2":
                    complete_with_schema(series)
                    wait_enter()
                    clear_screen()
                    show_header(f"RISULTATI: {len(series)} serie")
                    print_series_table(series)
                elif opt == "3":
                    _handle_export_menu(series)
                    return
            except KeyboardInterrupt:
                interrupted.set()
                show_warning("Operazione annullata.")
                break
    
    except KeyboardInterrupt:
        interrupted.set()
        show_warning("Visualizzazione annullata.")


def _handle_confronto():
    "Gestisce confronto."
    try:
        clear_screen()
        show_header("CONFRONTO CON ANIMECLICK")
        print("  +--------------------------------------+")
        print("  |  1.  Cartella locale                 |")
        print("  |  2.  Carica da file esportato        |")
        print("  |  0.  Torna al menu                   |")
        print("  +--------------------------------------+")
        opt = input("  Scelta (0-2): ").strip()
        if opt == "0":
            return

        series = None

        if opt == "1":
            path = get_path_input("\nPercorso cartella (0 = annulla): ")
            if not path:
                return
            if not path_exists_safe(path):  # NEW v2.5: da anime_engine
                show_error(f"Percorso non valido o non accessibile: {path}")
                wait_enter()
                return
            show_info("Scansione in corso...")
            series = scan_local_folder(path)
            if not series:
                show_warning("Nessuna serie trovata.")
                wait_enter()
                return

        elif opt == "2":
            print()
            show_info("Formati supportati: CSV, TXT")
            file_path = get_path_input("Percorso file (0 = annulla): ")
            if not file_path:
                return
            if not os.path.exists(file_path):
                show_error(f"File non trovato: {file_path}")
                wait_enter()
                return
            ext = Path(file_path).suffix.lower()
            if ext == ".csv":
                series = load_from_csv(file_path)
            elif ext == ".txt":
                series = load_from_txt(file_path)
            else:
                show_error(f"Formato non supportato: {ext}")
                wait_enter()
                return
            if not series:
                show_error("Impossibile caricare file.")
                wait_enter()
                return

        if series:
            compare_with_animeclick(series)
            clear_screen()
            show_header(f"RISULTATI CONFRONTO: {len(series)} serie")
            print_series_table(series)
            wait_enter()
    
    except KeyboardInterrupt:
        interrupted.set()
        show_warning("Confronto annullato.")


def _handle_completa():
    "Gestisce completamento con scheda."
    try:
        clear_screen()
        show_header("COMPLETA CON SCHEDA")
        print("  +--------------------------------------+")
        print("  |  1.  Cartella locale                 |")
        print("  |  2.  Carica da file esportato        |")
        print("  |  0.  Torna al menu                   |")
        print("  +--------------------------------------+")
        opt = input("  Scelta (0-2): ").strip()
        if opt == "0":
            return

        series = None

        if opt == "1":
            path = get_path_input("\nPercorso cartella (0 = annulla): ")
            if not path:
                return
            if not path_exists_safe(path):  # NEW v2.5: da anime_engine
                show_error(f"Percorso non valido o non accessibile: {path}")
                wait_enter()
                return
            show_info("Scansione in corso...")
            series = scan_local_folder(path)
            if not series:
                show_warning("Nessuna serie trovata.")
                wait_enter()
                return

        elif opt == "2":
            print()
            show_info("Formati supportati: CSV, TXT")
            file_path = get_path_input("Percorso file (0 = annulla): ")
            if not file_path:
                return
            if not os.path.exists(file_path):
                show_error(f"File non trovato: {file_path}")
                wait_enter()
                return
            ext = Path(file_path).suffix.lower()
            if ext == ".csv":
                series = load_from_csv(file_path)
            elif ext == ".txt":
                series = load_from_txt(file_path)
            else:
                show_error(f"Formato non supportato: {ext}")
                wait_enter()
                return
            if not series:
                show_error("Impossibile caricare file.")
                wait_enter()
                return

        if series:
            complete_with_schema(series)
            clear_screen()
            show_header(f"RISULTATI: {len(series)} serie")
            print_series_table(series)
            wait_enter()
    
    except KeyboardInterrupt:
        interrupted.set()
        show_warning("Completamento annullato.")


def _handle_export():
    "Avvia export."
    try:
        series = load_last_scan()
        if not series:
            clear_screen()
            show_header("ESPORTA RISULTATI")
            show_warning("Nessun scan precedente trovato.")
            wait_enter()
            return
        _handle_export_menu(series)
    except KeyboardInterrupt:
        interrupted.set()
        show_warning("Export annullato.")


def _handle_export_menu(series: List[Dict]):
    "Menu export."
    try:
        clear_screen()
        show_header("ESPORTA RISULTATI")
        print("  +--------------------------------------+")
        print("  |  1.  Salva in CSV                    |")
        print("  |  2.  Salva in TXT                    |")
        print("  |  0.  Torna indietro                  |")
        print("  +--------------------------------------+")
        scelta = input("  Scelta (0-2): ").strip()
        if scelta == "0":
            return

        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if scelta == "1":
            output = _EXPORT_DIR / f"scan_series_{timestamp}.csv"
            if export_to_csv(series, str(output)):
                show_info(f"Percorso: {output}")
        elif scelta == "2":
            output = _EXPORT_DIR / f"scan_series_{timestamp}.txt"
            if export_to_txt(series, str(output)):
                show_info(f"Percorso: {output}")

        wait_enter()
    
    except KeyboardInterrupt:
        interrupted.set()
        show_warning("Export annullato.")


if __name__ == "__main__":
    try:
        handle_scan_menu()
    except KeyboardInterrupt:
        print("\n\n  [!] Uscita - alla prossima!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  [!] Errore: {e}\n")
        sys.exit(1)
