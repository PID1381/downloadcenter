#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_local_series.py v2.1 — ALLINEATO A anime_engine v2.0
Download Center - scripts/anime/scan_local_series.py

NOVITA v2.1 (rispetto a v2.0):
  [FIX]     Export path hardcoded "export" sostituito con _EXPORT_DIR
              calcolato dal percorso del file (root/export/scan/)
  [ALIGN]   print_progress_eta() dall'engine sostituisce la barra
              manuale in compare_with_animeclick()
  [ALIGN]   import anime_engine espanso: aggiunto print_progress_eta,
              wait_enter
  +         import time aggiunto per start_time ETA

Invariato:
  scan_local_folder(), save_scan(), load_last_scan()
  load_from_csv(), load_from_txt(), print_series_table()
  export_to_csv(), export_to_txt(), compare_with_animeclick()
  handle_scan_menu() e handler privati
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── Import da anime_engine ────────────────────────────────────────────────────
try:
    from anime_engine import (
        clear_screen, show_header, show_success, show_error, show_info,
        show_warning, ask_yes_no, wait_enter, get_path_input,
        sanitize_filename, print_progress_eta,
    )
except ImportError as e:
    print(f"ERRORE: Impossibile importare anime_engine.py: {e}")
    sys.exit(1)


# ── Percorsi ─────────────────────────────────────────────────────────────────

_SCRIPTS_DIR  = Path(__file__).parent.parent.resolve()   # scripts/
_ROOT_DIR     = _SCRIPTS_DIR.parent.resolve()            # root/
_TEMP_DIR     = _SCRIPTS_DIR / "temp"
_EXPORT_DIR   = _ROOT_DIR / "export" / "scan"           # FIX v2.1

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
    """Conta file video in una cartella (non ricorsivo)."""
    try:
        return sum(
            1 for item in folder_path.iterdir()
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        )
    except Exception:
        return 0


def scan_local_folder(base_path: str) -> List[Dict]:
    """
    Scansiona cartella di primo livello cercando sottocartelle con video.

    Returns:
        Lista dict con dati serie (titolo, percorso, episodi_locali, ...)
    """
    series = []
    base   = Path(base_path)

    if not base.exists():
        show_error(f"Percorso non esiste: {base_path}")
        return []
    if not base.is_dir():
        show_error(f"Non e una cartella: {base_path}")
        return []

    try:
        for item in sorted(base.iterdir()):
            if not item.is_dir() or item.name in EXCLUDED_FOLDERS:
                continue
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
    except Exception as e:
        show_error(f"Errore scansione: {e}")

    return series


# ════════════════════════════════════════════════════════════════════════════
# PERSISTENZA
# ════════════════════════════════════════════════════════════════════════════

def save_scan(series: List[Dict]) -> bool:
    """Salva scan corrente in JSON (scripts/temp/last_scan.json)."""
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
    """Carica l'ultimo scan da JSON."""
    try:
        if LAST_SCAN_FILE.exists():
            with open(LAST_SCAN_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("series", [])
    except Exception as e:
        show_error(f"Errore caricamento scan: {e}")
    return None


def load_from_csv(file_path: str) -> Optional[List[Dict]]:
    """Carica serie da file CSV esportato."""
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
    """Carica serie da file TXT esportato."""
    try:
        series  = []
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
    """Visualizza tabella serie."""
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
    """Esporta serie in CSV."""
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
    """Esporta serie in TXT."""
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
# CONFRONTO ANIMECLICK
# ════════════════════════════════════════════════════════════════════════════

def compare_with_animeclick(series: List[Dict]) -> bool:
    """
    Confronta ogni serie locale con AnimeClick per recuperare
    episodi totali, stato e completezza.
    Progresso mostrato con print_progress_eta() dall'engine (FIX v2.1).
    """
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

    tracker     = AnimeTracker()
    confrontati = 0
    totale      = len(series)
    t0          = time.time()

    for i, s in enumerate(series, 1):
        titolo  = s["titolo"]
        # FIX v2.1: print_progress_eta sostituisce la barra manuale
        prefix  = f"Confronto  {titolo[:24]:<24}"
        print_progress_eta(i, totale, prefix=prefix, start_time=t0)

        try:
            results = tracker.search_anime(titolo, silent=True)
            if results:
                best    = results[0]
                details = tracker.get_anime_details(best["link"], silent=True)
                if details:
                    ep_tot = details.get("episodes", 0)
                    if ep_tot > 0:
                        s["episodi_totali"] = ep_tot
                        s["link_ack"]       = best["link"]
                        ep_loc              = s.get("episodi_locali", 0)
                        if ep_loc >= ep_tot:
                            s["completezza"] = "100%"
                        else:
                            s["completezza"] = f"{int(ep_loc / ep_tot * 100)}%"
                        s["stato"]          = details.get("stato", "Sconosciuto")
                        confrontati        += 1
        except Exception:
            pass  # continua con la serie successiva

    print("")  # vai a capo dopo la progress bar
    print()
    show_success(f"Confronti completati: {confrontati}/{totale}")
    return True


# ════════════════════════════════════════════════════════════════════════════
# MENU PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════

def handle_scan_menu():
    """Menu principale Scan serie in locale."""
    while True:
        clear_screen()
        show_header("SCAN SERIE IN LOCALE")
        print("  +--------------------------------------+")
        print("  |  1.  Scansiona cartella              |")
        print("  |  2.  Visualizza ultimo scan          |")
        print("  |  3.  Confronta con AnimeClick        |")
        print("  |  4.  Esporta risultati               |")
        print("  |  0.  Torna al menu Anime             |")
        print("  +--------------------------------------+")
        scelta = input("  Scelta (0-4): ").strip()

        if   scelta == "0": return
        elif scelta == "1": _handle_scansione()
        elif scelta == "2": _handle_visualizza_ultimo()
        elif scelta == "3": _handle_confronto()
        elif scelta == "4": _handle_export()


def _handle_scansione():
    """Gestisce scansione cartella."""
    clear_screen()
    show_header("SCANSIONE CARTELLA")
    path = get_path_input("Percorso cartella (0 = annulla): ")
    if not path:
        return
    if not os.path.exists(path):
        show_error(f"Percorso non valido: {path}")
        wait_enter()
        return

    print()
    show_info("Scansione in corso...")
    series = scan_local_folder(path)

    if not series:
        show_warning("Nessuna serie trovata.")
        wait_enter()
        return

    save_scan(series)
    clear_screen()
    show_header(f"RISULTATI: {len(series)} serie trovate")
    print_series_table(series)

    while True:
        print("  1. Confronta con AnimeClick")
        print("  2. Esporta risultati")
        print("  3. Nuova scansione")
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
            _handle_export_menu(series)
            break
        elif opt == "3":
            break


def _handle_visualizza_ultimo():
    """Visualizza ultimo scan salvato."""
    clear_screen()
    show_header("ULTIMO SCAN SALVATO")
    series = load_last_scan()
    if not series:
        show_warning("Nessun scan precedente trovato.")
        wait_enter()
        return

    print_series_table(series)
    while True:
        print("  1. Confronta con AnimeClick")
        print("  2. Esporta risultati")
        print("  0. Torna al menu")
        print()
        opt = input("  Scelta (0-2): ").strip()
        if opt == "0":
            return
        elif opt == "1":
            compare_with_animeclick(series)
            wait_enter()
            clear_screen()
            show_header(f"RISULTATI: {len(series)} serie")
            print_series_table(series)
        elif opt == "2":
            _handle_export_menu(series)
            return


def _handle_confronto():
    """Gestisce confronto con AnimeClick da cartella o file esportato."""
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
        if not os.path.exists(path):
            show_error(f"Percorso non valido: {path}")
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


def _handle_export():
    """Avvia export dall'ultimo scan salvato."""
    series = load_last_scan()
    if not series:
        clear_screen()
        show_header("ESPORTA RISULTATI")
        show_warning("Nessun scan precedente trovato.")
        wait_enter()
        return
    _handle_export_menu(series)


def _handle_export_menu(series: List[Dict]):
    """
    Menu export risultati.
    FIX v2.1: usa _EXPORT_DIR (root/export/scan/) invece di 'export' relativo.
    """
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


if __name__ == "__main__":
    handle_scan_menu()
