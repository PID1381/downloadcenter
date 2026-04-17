#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
watchlist.py - Gestione Watchlist Anime
Branch: upgrade - VERSIONE CON SCRAPING REALE SU ANIMEWORLD
CORRETTA: Bug fix - list index out of range, parsing episodi robusto
"""

import os
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# FUNZIONI DI SUPPORTO - UTILITY
# ============================================================================

def clear_screen() -> None:
    """Pulisce lo schermo del terminale"""
    os.system('cls' if os.name == 'nt' else 'clear')


def show_header(title: str) -> None:
    """Mostra un header formattato"""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def show_warning(msg: str) -> None:
    """Mostra un messaggio di avviso"""
    print(f"\n  ⚠️  {msg}\n")


def show_error(msg: str) -> None:
    """Mostra un messaggio di errore"""
    print(f"\n  ❌ {msg}\n")


def show_success(msg: str) -> None:
    """Mostra un messaggio di successo"""
    print(f"\n  ✅ {msg}\n")


def wait_enter(msg: str = "Premi INVIO per continuare...") -> None:
    """Aspetta che l'utente prema INVIO"""
    input(f"\n  {msg}")


def get_watchlist_dir() -> Path:
    """
    Ritorna il percorso della directory watchlist (scripts/temp/)
    
    Struttura del progetto:
    DC 2 upgrade/
    ├── scripts/
    │   ├── anime/
    │   │   └── watchlist.py  (questo file)
    │   └── temp/             (dove sono i file JSON)
    │       ├── watchlist_in_corso.json
    │       └── watchlist_finiti_da_vedere.json
    """
    script_dir = Path(__file__).parent  # scripts/anime/
    
    # Risali di una directory e entra in temp/
    temp_dir = script_dir.parent / "temp"
    
    if temp_dir.exists():
        return temp_dir
    
    # Fallback per altre strutture
    possible_paths = [
        script_dir / "temp",
        script_dir / ".." / "temp",
        script_dir.parent.parent / "temp",
        Path.cwd() / "temp",
        Path.cwd() / "scripts" / "temp",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return temp_dir


def get_watchlist_file_path(category: str = "in_corso") -> Path:
    """
    Ritorna il percorso del file watchlist JSON
    """
    watchlist_dir = get_watchlist_dir()
    
    category_files = {
        "in_corso": watchlist_dir / "watchlist_in_corso.json",
        "finiti_da_vedere": watchlist_dir / "watchlist_finiti_da_vedere.json",
    }
    
    return category_files.get(category)


# ============================================================================
# FUNZIONI DI CARICAMENTO DATI
# ============================================================================

def load_watchlist_by_category(category: str = "in_corso") -> list:
    """Carica la watchlist per una categoria specifica"""
    try:
        watchlist_file = get_watchlist_file_path(category)
        
        if not watchlist_file.exists():
            print(f"  [!] File non trovato: {watchlist_file}")
            return []
        
        with open(watchlist_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Gestisci diverse strutture di dati
        if isinstance(data, dict):
            if "data" in data:
                return data.get("data", [])
            elif category in data:
                return data.get(category, [])
            else:
                return list(data.values()) if data else []
        elif isinstance(data, list):
            return data
        else:
            return []
    
    except json.JSONDecodeError as e:
        print(f"  [!] Errore nel parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"  [!] Errore nel caricamento: {e}")
        return []


def save_watchlist(anime_list: list, category: str = "in_corso") -> bool:
    """Salva la watchlist aggiornata"""
    try:
        watchlist_file = get_watchlist_file_path(category)
        
        watchlist_file.parent.mkdir(parents=True, exist_ok=True)
        
        if watchlist_file.exists():
            with open(watchlist_file, "r", encoding="utf-8") as f:
                original_data = json.load(f)
        else:
            original_data = {}
        
        # Aggiorna i dati
        if isinstance(original_data, dict):
            if "data" in original_data:
                original_data["data"] = anime_list
            else:
                original_data = anime_list
        else:
            original_data = anime_list
        
        with open(watchlist_file, "w", encoding="utf-8") as f:
            json.dump(original_data, f, ensure_ascii=False, indent=2)
        
        return True
    
    except Exception as e:
        print(f"  [!] Errore nel salvataggio: {e}")
        return False


# ============================================================================
# FUNZIONI DI SUPPORTO - PARSING EPISODI
# ============================================================================

def extract_episode_number_from_string(ep_str: str) -> int:
    """
    Estrae il numero di episodi da stringhe come:
    - "[2/26]" → 2
    - "[2/?]" → 2
    - "2" → 2
    """
    try:
        ep_str = str(ep_str).replace("[", "").replace("]", "")
        if "/" in ep_str:
            ep_str = ep_str.split("/")[0]
        return int(ep_str.strip())
    except:
        return 0


def extract_total_episodes_from_format(ep_str: str) -> str:
    """
    Estrae il totale da stringhe come:
    - "[2/26]" → "26"
    - "[2/?]" → "?"
    
    Ritorna il totale (numero o "?")
    """
    try:
        ep_str = str(ep_str).replace("[", "").replace("]", "")
        if "/" in ep_str:
            parts = ep_str.split("/")
            if len(parts) > 1:
                return parts[1].strip()
        return "?"
    except:
        return "?"


def format_episode_string(ep_attuali: int, ep_totali: int) -> str:
    """
    Formatta una stringa di episodi nel formato "[x/y]"
    """
    try:
        ep_totali = int(ep_totali) if isinstance(ep_totali, str) and ep_totali.isdigit() else ep_totali
        return f"[{ep_attuali}/{ep_totali}]"
    except:
        return f"[{ep_attuali}/?]"


# ============================================================================
# FUNZIONI DI SCRAPING - ANIMEWORLD
# ============================================================================

def check_nuovi_episodi_animeworld(anime: dict) -> dict:
    """
    SCRAPE REALE: Verifica nuovi episodi su AnimeWorld
    
    Scrape il div con classe "widget servers" e conta i <li class="episode">
    nel server attivo (AnimeWorld Server)
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        
    except ImportError:
        return {
            "titolo": anime.get("titolo", ""),
            "episodi_nuovi": False,
            "nuovi_episodi": 0,
            "errore": "Mancano dipendenze: requests, beautifulsoup4"
        }
    
    try:
        titolo = anime.get("titolo", "")
        link = anime.get("link", "")
        
        # Estrai episodi attuali dal formato "[2/26]"
        ep_str = anime.get("episodi", "[0/?]")
        ep_attuali = extract_episode_number_from_string(ep_str)
        
        # Estrai il totale attuale (per mantenerlo se non lo trovi)
        ep_totale_attuale = extract_total_episodes_from_format(ep_str)
        
        if not link:
            return {
                "titolo": titolo,
                "episodi_nuovi": False,
                "nuovi_episodi": 0,
                "ep_attuali": ep_attuali,
                "ep_totale": ep_totale_attuale
            }
        
        # Costruisci URL completo se necessario
        if not link.startswith("http"):
            link = "https://www.animeworld.so" + link
        
        print(f"    Scraping: {titolo[:40]:<40}", end=" ... ", flush=True)
        
        # Fai richiesta HTTP
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(link, timeout=10, headers=headers)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")
        
        # === CERCA IL WIDGET SERVERS ===
        widget = soup.find("div", class_="widget servers")
        if not widget:
            print("❌ Widget non trovato")
            return {
                "titolo": titolo,
                "episodi_nuovi": False,
                "nuovi_episodi": 0,
                "ep_attuali": ep_attuali,
                "ep_totale": ep_totale_attuale,
                "errore": "Widget servers non trovato"
            }
        
        # === CERCA IL SERVER ATTIVO ===
        server = widget.find("div", class_="server active")
        if not server:
            server = widget.find("div", class_="server")
        
        if not server:
            print("❌ Server non trovato")
            return {
                "titolo": titolo,
                "episodi_nuovi": False,
                "nuovi_episodi": 0,
                "ep_attuali": ep_attuali,
                "ep_totale": ep_totale_attuale,
                "errore": "Server non trovato"
            }
        
        # === CONTA GLI EPISODI ===
        episodes = server.find_all("li", class_="episode")
        ep_totali = len(episodes)
        
        if ep_totali == 0:
            print("❌ Nessun episodio trovato")
            return {
                "titolo": titolo,
                "episodi_nuovi": False,
                "nuovi_episodi": 0,
                "ep_attuali": ep_attuali,
                "ep_totale": ep_totale_attuale
            }
        
        # === CONFRONTA ===
        if ep_totali > ep_attuali:
            nuovi = ep_totali - ep_attuali
            print(f"✅ +{nuovi} ({ep_attuali}→{ep_totali})")
            return {
                "titolo": titolo,
                "episodi_nuovi": True,
                "nuovi_episodi": nuovi,
                "ep_attuali": ep_attuali,
                "ep_totale": ep_totali
            }
        else:
            print(f"✓ Nessuno ({ep_attuali}={ep_totali})")
            return {
                "titolo": titolo,
                "episodi_nuovi": False,
                "nuovi_episodi": 0,
                "ep_attuali": ep_attuali,
                "ep_totale": ep_totali
            }
    
    except requests.exceptions.Timeout:
        print("⏱️ Timeout")
        return {
            "titolo": anime.get("titolo", ""),
            "episodi_nuovi": False,
            "nuovi_episodi": 0,
            "errore": "Timeout"
        }
    except requests.exceptions.ConnectionError:
        print("🌐 Errore rete")
        return {
            "titolo": anime.get("titolo", ""),
            "episodi_nuovi": False,
            "nuovi_episodi": 0,
            "errore": "Errore di connessione"
        }
    except requests.exceptions.RequestException as e:
        print(f"❌ {type(e).__name__}")
        return {
            "titolo": anime.get("titolo", ""),
            "episodi_nuovi": False,
            "nuovi_episodi": 0,
            "errore": str(e)
        }
    except Exception as e:
        print(f"❌ Errore: {str(e)}")
        return {
            "titolo": anime.get("titolo", ""),
            "episodi_nuovi": False,
            "nuovi_episodi": 0,
            "errore": f"Errore generico: {str(e)}"
        }


# ============================================================================
# FUNZIONI DI AGGIORNAMENTO
# ============================================================================

def show_auto_update_in_corso() -> list:
    """
    Esegue l'aggiornamento automatico con SCRAPING REALE da AnimeWorld
    """
    clear_screen()
    show_header("AGGIORNAMENTO EPISODI - IN CORSO")
    
    print()
    print("  [i] Caricamento watchlist in corso...")
    print()
    
    try:
        # STEP 1: Carica la watchlist In Corso
        watchlist_in_corso = load_watchlist_by_category("in_corso")
        
        if not watchlist_in_corso:
            print("  [i] Nessun anime in corso da aggiornare.")
            print()
            wait_enter()
            return []
        
        # STEP 2: Aggiorna ogni anime
        anime_aggiornati = []
        total_anime = len(watchlist_in_corso)
        
        print(f"  Scansione di {total_anime} anime su AnimeWorld...\n")
        
        for idx, anime in enumerate(watchlist_in_corso, 1):
            try:
                # Mostra barra di progresso
                progress = int((idx / total_anime) * 40)
                bar = "█" * progress + "░" * (40 - progress)
                percentage = int((idx / total_anime) * 100)
                
                print(f"  [{bar}] {percentage:3d}%", flush=True)
                
                # Verifica se ci sono nuovi episodi (SCRAPE REALE)
                result = check_nuovi_episodi_animeworld(anime)
                
                if result.get("episodi_nuovi", False):
                    anime_aggiornati.append({
                        "titolo": result.get("titolo"),
                        "nuovi": result.get("nuovi_episodi", 0),
                        "da": result.get("ep_attuali"),
                        "a": result.get("ep_totale")
                    })
                    
                    # AGGIORNA l'anime con parsing robusto
                    try:
                        ep_totale = result.get("ep_totale", "?")
                        anime["episodi"] = format_episode_string(
                            result.get("ep_totale"),  # Usa il totale nuovo
                            result.get("ep_totale")
                        )
                    except Exception as parse_err:
                        print(f"  [⚠️] Errore parsing episodi per {anime.get('titolo')}: {parse_err}")
                
                # Pausa per non sovraccaricare il server
                time.sleep(0.5)
                
            except Exception as item_err:
                print(f"\n  [❌] Errore elaborando anime {idx}: {str(item_err)}")
                continue
        
        print()
        print()
        
        # STEP 3: Salva gli aggiornamenti
        if anime_aggiornati:
            save_watchlist(watchlist_in_corso, "in_corso")
        
        # STEP 4: Mostra risultati
        clear_screen()
        show_header("SERIE AGGIORNATE")
        print()
        
        if anime_aggiornati:
            print(f"  ✅ Aggiornate {len(anime_aggiornati)} serie:\n")
            for item in anime_aggiornati:
                nuovi = item.get("nuovi", 0)
                da = item.get("da", "?")
                a = item.get("a", "?")
                print(f"    • {item.get('titolo')} [{da}→{a}] (+{nuovi})")
            print()
        else:
            print("  [i] Nessun aggiornamento trovato.")
            print()
        
        wait_enter()
        return anime_aggiornati
        
    except Exception as e:
        show_error(f"Impossibile aggiornare: {str(e)}")
        import traceback
        traceback.print_exc()
        wait_enter()
        return []


# ============================================================================
# MENU PRINCIPALE
# ============================================================================

def _menu_in_corso() -> None:
    """Menu per la gestione della Watchlist - In Corso"""
    while True:
        clear_screen()
        show_header("WATCHLIST - IN CORSO")
        
        watchlist = load_watchlist_by_category("in_corso")
        
        print()
        print(f"  #    {'Titolo':<40} {'Ep':<10} {'Aggiunto':<15}")
        print("  " + "-" * 75)
        
        for idx, anime in enumerate(watchlist, 1):
            titolo = anime.get("titolo", "")[:40]
            ep = anime.get("episodi", "[?/?]")
            aggiunto = anime.get("aggiunto", "N/A")
            print(f"  {idx:<4} {titolo:<40} {ep:<10} {aggiunto:<15}")
        
        print("  " + "-" * 75)
        print(f"  Totale: {len(watchlist)} anime")
        print()
        
        print("  +--------------------------------------+")
        print("  |  1.  Aggiungi (manuale)              |")
        print("  |  2.  Aggiungi (cerca AnimeWorld)     |")
        print("  |  3.  Visualizza dettaglio            |")
        print("  |  4.  Sposta in FINITI                |")
        print("  |  5.  Elimina                         |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        print()
        
        scelta = input("  Scelta: ").strip()
        
        if scelta == "0":
            return
        elif scelta == "1":
            print("  [1] Aggiungi (manuale) - Non implementato")
            wait_enter()
        elif scelta == "2":
            print("  [2] Aggiungi (cerca AnimeWorld) - Non implementato")
            wait_enter()
        elif scelta == "3":
            print("  [3] Visualizza dettaglio - Non implementato")
            wait_enter()
        elif scelta == "4":
            print("  [4] Sposta in FINITI - Non implementato")
            wait_enter()
        elif scelta == "5":
            print("  [5] Elimina - Non implementato")
            wait_enter()
        else:
            show_warning("Opzione non valida!")
            wait_enter()


def _menu_finiti() -> None:
    """Menu per la gestione della Watchlist - Finiti da Vedere"""
    while True:
        clear_screen()
        show_header("WATCHLIST - FINITI DA VEDERE")
        
        watchlist = load_watchlist_by_category("finiti_da_vedere")
        
        print()
        print(f"  #    {'Titolo':<40} {'Ep':<10} {'Aggiunto':<15}")
        print("  " + "-" * 75)
        
        for idx, anime in enumerate(watchlist, 1):
            titolo = anime.get("titolo", "")[:40]
            ep = anime.get("episodi", "[?/?]")
            aggiunto = anime.get("aggiunto", "N/A")
            print(f"  {idx:<4} {titolo:<40} {ep:<10} {aggiunto:<15}")
        
        print("  " + "-" * 75)
        print(f"  Totale: {len(watchlist)} anime")
        print()
        
        print("  +--------------------------------------+")
        print("  |  1.  Visualizza dettaglio            |")
        print("  |  2.  Sposta in IN CORSO              |")
        print("  |  3.  Elimina                         |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        print()
        
        scelta = input("  Scelta: ").strip()
        
        if scelta == "0":
            return
        elif scelta == "1":
            print("  [1] Visualizza dettaglio - Non implementato")
            wait_enter()
        elif scelta == "2":
            print("  [2] Sposta in IN CORSO - Non implementato")
            wait_enter()
        elif scelta == "3":
            print("  [3] Elimina - Non implementato")
            wait_enter()
        else:
            show_warning("Opzione non valida!")
            wait_enter()


def handle_watchlist_menu(tracker=None) -> None:
    """
    Menu principale della Watchlist
    
    ESEGUE AUTOMATICAMENTE L'AGGIORNAMENTO DEGLI EPISODI
    con SCRAPING REALE da AnimeWorld appena accede alla watchlist
    """
    # AUTO-AGGIORNAMENTO ALL'INIZIO
    show_auto_update_in_corso()
    
    # ENTRARE NEL MENU PRINCIPALE
    while True:
        clear_screen()
        show_header("WATCHLIST - MENU PRINCIPALE")
        
        print()
        print("  +--------------------------------------+")
        print("  |  1.  Gestione - In Corso             |")
        print("  |  2.  Gestione - Finiti da Vedere     |")
        print("  |  0.  Torna al menu precedente         |")
        print("  +--------------------------------------+")
        print()
        
        scelta = input("  Scegli un'opzione (0-2): ").strip()
        
        if scelta == "0":
            return
        elif scelta == "1":
            _menu_in_corso()
        elif scelta == "2":
            _menu_finiti()
        else:
            show_warning("Opzione non valida!")
            wait_enter()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        handle_watchlist_menu()
    except KeyboardInterrupt:
        print("\n\n  Arrivederci!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ❌ Errore: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
