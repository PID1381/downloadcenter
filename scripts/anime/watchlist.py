#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
watchlist.py - Gestione Watchlist Anime
Branch: upgrade - VERSIONE CON SCRAPING REALE SU ANIMEWORLD
"""

import os
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================================
# UTILITY
# ============================================================================

def clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')

def show_header(title: str) -> None:
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)

def show_warning(msg: str) -> None:
    print(f"\n  ⚠️  {msg}\n")

def show_error(msg: str) -> None:
    print(f"\n  ❌ {msg}\n")

def show_success(msg: str) -> None:
    print(f"\n  ✅ {msg}\n")

def wait_enter(msg: str = "Premi INVIO per continuare...") -> None:
    input(f"\n  {msg}")

def get_watchlist_dir() -> Path:
    script_dir = Path(__file__).parent   # scripts/anime/
    temp_dir   = script_dir.parent / "temp"
    if temp_dir.exists():
        return temp_dir
    for path in [
        script_dir / "temp",
        script_dir / ".." / "temp",
        script_dir.parent.parent / "temp",
        Path.cwd() / "temp",
        Path.cwd() / "scripts" / "temp",
    ]:
        if path.exists():
            return path
    return temp_dir

def get_watchlist_file_path(category: str = "in_corso") -> Path:
    d = get_watchlist_dir()
    return {
        "in_corso":         d / "watchlist_in_corso.json",
        "finiti_da_vedere": d / "watchlist_finiti_da_vedere.json",
    }.get(category)

# ============================================================================
# CARICAMENTO / SALVATAGGIO
# ============================================================================

def load_watchlist_by_category(category: str = "in_corso") -> list:
    try:
        f = get_watchlist_file_path(category)
        if not f or not f.exists():
            return []
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data.get("data", data.get(category, list(data.values())))
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  [!] Errore caricamento: {e}")
        return []

def save_watchlist(anime_list: list, category: str = "in_corso") -> bool:
    try:
        f = get_watchlist_file_path(category)
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists():
            with open(f, "r", encoding="utf-8") as fh:
                original = json.load(fh)
        else:
            original = {}
        if isinstance(original, dict) and "data" in original:
            original["data"] = anime_list
            payload = original
        else:
            payload = anime_list
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"  [!] Errore salvataggio: {e}")
        return False

# ============================================================================
# EPISODI - HELPERS
# ============================================================================

def _get_ep_display(anime: dict) -> str:
    """Legge episodi_usciti e episodi_totali dal JSON → '[x/y]'"""
    usciti = anime.get("episodi_usciti", "?")
    totali = anime.get("episodi_totali", "?")
    return f"[{usciti}/{totali}]"

# ============================================================================
# SCRAPING - ANIMEWORLD
# ============================================================================

def _scrape_ep_count(link: str) -> Optional[int]:
    """Ritorna il numero di episodi trovati su AW, o None in caso di errore."""
    import requests
    from bs4 import BeautifulSoup
    if not link.startswith("http"):
        link = "https://www.animeworld.so" + link
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(link, timeout=10, headers=headers)
    r.raise_for_status()
    soup   = BeautifulSoup(r.content, "html.parser")
    widget = soup.find("div", class_="widget servers")
    if not widget:
        return None
    server = widget.find("div", class_="server active") or widget.find("div", class_="server")
    if not server:
        return None
    count = len(server.find_all("li", class_="episode"))
    return count if count > 0 else None


def check_nuovi_episodi_animeworld(anime: dict) -> dict:
    """Scraping con output visivo (barra progresso)."""
    titolo     = anime.get("titolo", "")
    link       = anime.get("link", "")
    ep_attuali = int(anime.get("episodi_usciti", 0))
    ep_totali_serie = anime.get("episodi_totali", "?")

    print(f"    Scraping: {titolo[:50]:<50}", end=" ... ", flush=True)

    if not link:
        print("⚠ Nessun link")
        return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                "ep_attuali": ep_attuali, "ep_totale": ep_attuali, "ep_totali_serie": ep_totali_serie}
    try:
        ep_online = _scrape_ep_count(link)
        if ep_online is None:
            print("❌ Nessun episodio trovato")
            return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                    "ep_attuali": ep_attuali, "ep_totale": ep_attuali, "ep_totali_serie": ep_totali_serie}
        if ep_online > ep_attuali:
            nuovi = ep_online - ep_attuali
            print(f"✅ +{nuovi} ({ep_attuali}→{ep_online})")
            return {"titolo": titolo, "episodi_nuovi": True, "nuovi_episodi": nuovi,
                    "ep_attuali": ep_attuali, "ep_totale": ep_online, "ep_totali_serie": ep_totali_serie}
        print(f"✓ Nessuno ({ep_attuali}={ep_online})")
        return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                "ep_attuali": ep_attuali, "ep_totale": ep_online, "ep_totali_serie": ep_totali_serie}
    except Exception as e:
        print(f"❌ {e}")
        return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                "ep_attuali": ep_attuali, "ep_totale": ep_attuali, "ep_totali_serie": ep_totali_serie}


def check_nuovi_episodi_animeworld_silent(anime: dict) -> dict:
    """Scraping silenzioso (nessun print)."""
    titolo     = anime.get("titolo", "")
    link       = anime.get("link", "")
    ep_attuali = int(anime.get("episodi_usciti", 0))
    ep_totali_serie = anime.get("episodi_totali", "?")

    if not link:
        return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                "ep_attuali": ep_attuali, "ep_totale": ep_attuali, "ep_totali_serie": ep_totali_serie}
    try:
        ep_online = _scrape_ep_count(link)
        if ep_online and ep_online > ep_attuali:
            return {"titolo": titolo, "episodi_nuovi": True,
                    "nuovi_episodi": ep_online - ep_attuali,
                    "ep_attuali": ep_attuali, "ep_totale": ep_online, "ep_totali_serie": ep_totali_serie}
        return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                "ep_attuali": ep_attuali, "ep_totale": ep_online or ep_attuali, "ep_totali_serie": ep_totali_serie}
    except Exception:
        return {"titolo": titolo, "episodi_nuovi": False, "nuovi_episodi": 0,
                "ep_attuali": ep_attuali, "ep_totale": ep_attuali, "ep_totali_serie": ep_totali_serie}


def check_aggiornamenti_silenzioso() -> list:
    """
    Usato da main_menu.py [STEP 3].
    Ritorna lista aggiornamenti senza output visivo.
    """
    try:
        watchlist = load_watchlist_by_category("in_corso")
        if not watchlist:
            return []
        aggiornati = []
        for anime in watchlist:
            try:
                res = check_nuovi_episodi_animeworld_silent(anime)
                if res.get("episodi_nuovi"):
                    aggiornati.append({
                        "titolo": res["titolo"],
                        "nuovi":  res["nuovi_episodi"],
                        "da":     res["ep_attuali"],
                        "a":      res["ep_totale"],
                    })
                    # ✅ aggiorna solo episodi_usciti, NON tocca episodi_totali
                    anime["episodi_usciti"]  = res["ep_totale"]
                    anime["data_ep_usciti"]  = datetime.now().strftime("%Y-%m-%d")
                time.sleep(0.5)
            except Exception:
                continue
        if aggiornati:
            save_watchlist(watchlist, "in_corso")
        return aggiornati
    except Exception:
        return []


def show_auto_update_in_corso() -> list:
    """Aggiornamento interattivo con barra progresso."""
    clear_screen()
    show_header("AGGIORNAMENTO EPISODI - IN CORSO")
    print()
    print("  [i] Caricamento watchlist in corso...")
    print()
    try:
        watchlist = load_watchlist_by_category("in_corso")
        if not watchlist:
            print("  [i] Nessun anime in corso da aggiornare.")
            wait_enter()
            return []

        aggiornati = []
        total      = len(watchlist)
        print(f"  Scansione di {total} anime su AnimeWorld...\n")

        for idx, anime in enumerate(watchlist, 1):
            progress = int((idx / total) * 40)
            bar      = "█" * progress + "░" * (40 - progress)
            pct      = int((idx / total) * 100)
            print(f"  [{bar}] {pct:3d}%", flush=True)
            try:
                res = check_nuovi_episodi_animeworld(anime)
                if res.get("episodi_nuovi"):
                    aggiornati.append({
                        "titolo": res["titolo"],
                        "nuovi":  res["nuovi_episodi"],
                        "da":     res["ep_attuali"],
                        "a":      res["ep_totale"],
                    })
                    # ✅ aggiorna solo episodi_usciti, NON tocca episodi_totali
                    anime["episodi_usciti"] = res["ep_totale"]
                    anime["data_ep_usciti"] = datetime.now().strftime("%Y-%m-%d")
                time.sleep(0.5)
            except Exception as e:
                print(f"\n  [❌] Errore anime {idx}: {e}")
                continue

        print()
        if aggiornati:
            save_watchlist(watchlist, "in_corso")

        clear_screen()
        show_header("SERIE AGGIORNATE")
        print()
        if aggiornati:
            print(f"  ✅ Aggiornate {len(aggiornati)} serie:\n")
            for it in aggiornati:
                print(f"    • {it['titolo']} [{it['da']}→{it['a']}] (+{it['nuovi']})")
            print()
        else:
            print("  [i] Nessun aggiornamento trovato.")
            print()
        wait_enter()
        return aggiornati
    except Exception as e:
        show_error(f"Impossibile aggiornare: {e}")
        import traceback; traceback.print_exc()
        wait_enter()
        return []

# ============================================================================
# AZIONI - IN CORSO
# ============================================================================

def _aggiungi_manuale(watchlist: list) -> None:
    clear_screen()
    show_header("AGGIUNGI ANIME - MANUALE")
    print()
    titolo = input("  Titolo: ").strip()
    if not titolo:
        show_warning("Titolo non inserito.")
        wait_enter()
        return
    link = input("  Link AnimeWorld (lascia vuoto se non hai): ").strip()
    ep_usciti_raw = input("  Episodi usciti [0]: ").strip()
    ep_totali_raw = input("  Episodi totali (numero o '?') [?]: ").strip()

    ep_usciti = int(ep_usciti_raw) if ep_usciti_raw.isdigit() else 0
    ep_totali = int(ep_totali_raw) if ep_totali_raw.isdigit() else (ep_totali_raw if ep_totali_raw else "?")

    nuovo = {
        "titolo":          titolo,
        "link":            link,
        "episodi_visti":   0,
        "episodi_usciti":  ep_usciti,
        "episodi_totali":  ep_totali,
        "stato":           "In corso",
        "data_aggiunta":   datetime.now().strftime("%Y-%m-%d"),
        "note":            "",
    }
    watchlist.append(nuovo)
    save_watchlist(watchlist, "in_corso")
    show_success(f"'{titolo}' aggiunto alla watchlist!")
    wait_enter()


def _aggiungi_cerca_aw(watchlist: list) -> None:
    """Cerca un anime su AnimeWorld e lo aggiunge alla watchlist."""
    clear_screen()
    show_header("AGGIUNGI ANIME - CERCA SU ANIMEWORLD")
    print()
    query = input("  Titolo da cercare: ").strip()
    if not query:
        show_warning("Query vuota.")
        wait_enter()
        return

    print(f"\n  🔍 Ricerca '{query}' su AnimeWorld...\n")
    try:
        import requests
        from bs4 import BeautifulSoup

        search_url = f"https://www.animeworld.ac/search?keyword={requests.utils.quote(query)}"
        headers    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r          = requests.get(search_url, timeout=10, headers=headers)
        r.raise_for_status()
        soup       = BeautifulSoup(r.content, "html.parser")

        # Risultati: div.film-list > div.item > a.name
        results = []
        for item in soup.select("div.film-list div.item")[:10]:
            name_tag = item.select_one("a.name")
            if not name_tag:
                continue
            titolo_r = name_tag.get_text(strip=True)
            href     = name_tag.get("href", "")
            link_r   = href if href.startswith("http") else "https://www.animeworld.ac" + href
            results.append({"titolo": titolo_r, "link": link_r})

        if not results:
            show_warning("Nessun risultato trovato.")
            wait_enter()
            return

        print(f"  Trovati {len(results)} risultati:\n")
        for i, res in enumerate(results, 1):
            print(f"  {i:>2}.  {res['titolo']}")
        print(f"  {'0':>2}.  Annulla")
        print()

        scelta = input("  Seleziona: ").strip()
        if not scelta.isdigit() or int(scelta) == 0:
            return
        idx = int(scelta) - 1
        if idx < 0 or idx >= len(results):
            show_warning("Selezione non valida.")
            wait_enter()
            return

        scelto = results[idx]
        # Scraping pagina anime per ep_totali
        ep_usciti_online = None
        ep_totali_serie  = "?"
        try:
            ep_usciti_online = _scrape_ep_count(scelto["link"])
        except Exception:
            pass

        nuovo = {
            "titolo":         scelto["titolo"],
            "link":           scelto["link"],
            "episodi_visti":  0,
            "episodi_usciti": ep_usciti_online or 0,
            "episodi_totali": ep_totali_serie,
            "stato":          "In corso",
            "data_aggiunta":  datetime.now().strftime("%Y-%m-%d"),
            "note":           "",
        }
        watchlist.append(nuovo)
        save_watchlist(watchlist, "in_corso")
        show_success(f"'{scelto['titolo']}' aggiunto! ({ep_usciti_online or 0}/{ep_totali_serie})")
        wait_enter()

    except ImportError:
        show_error("Mancano requests / beautifulsoup4.")
        wait_enter()
    except Exception as e:
        show_error(f"Errore ricerca: {e}")
        wait_enter()


def _visualizza_dettaglio(watchlist: list) -> None:
    clear_screen()
    show_header("VISUALIZZA DETTAGLIO")
    print()
    if not watchlist:
        show_warning("Watchlist vuota.")
        wait_enter()
        return

    for i, a in enumerate(watchlist, 1):
        print(f"  {i:>2}.  {a.get('titolo','')}")
    print(f"  {'0':>2}.  Annulla")
    print()
    scelta = input("  Seleziona: ").strip()
    if not scelta.isdigit() or int(scelta) == 0:
        return
    idx = int(scelta) - 1
    if idx < 0 or idx >= len(watchlist):
        show_warning("Selezione non valida.")
        wait_enter()
        return

    a = watchlist[idx]
    clear_screen()
    show_header(f"DETTAGLIO - {a.get('titolo','')}")
    print()
    print(f"  Titolo:          {a.get('titolo','N/A')}")
    print(f"  Stato:           {a.get('stato','N/A')}")
    print(f"  Episodi usciti:  {a.get('episodi_usciti','?')}")
    print(f"  Episodi totali:  {a.get('episodi_totali','?')}")
    print(f"  Episodi visti:   {a.get('episodi_visti','?')}")
    print(f"  Data aggiunta:   {a.get('data_aggiunta','N/A')}")
    print(f"  Data uscita:     {a.get('data_uscita','N/A')}")
    print(f"  Genere:          {a.get('genere','N/A')}")
    print(f"  Link:            {a.get('link','N/A')}")
    print(f"  Note:            {a.get('note','')}")
    print()
    wait_enter()


def _sposta_in_finiti(watchlist: list) -> None:
    clear_screen()
    show_header("SPOSTA IN FINITI DA VEDERE")
    print()
    if not watchlist:
        show_warning("Watchlist vuota.")
        wait_enter()
        return

    for i, a in enumerate(watchlist, 1):
        print(f"  {i:>2}.  {a.get('titolo','')}")
    print(f"  {'0':>2}.  Annulla")
    print()
    scelta = input("  Seleziona: ").strip()
    if not scelta.isdigit() or int(scelta) == 0:
        return
    idx = int(scelta) - 1
    if idx < 0 or idx >= len(watchlist):
        show_warning("Selezione non valida.")
        wait_enter()
        return

    anime = watchlist.pop(idx)
    anime["stato"]         = "Finito da vedere"
    anime["data_spostato"] = datetime.now().strftime("%Y-%m-%d")

    finiti = load_watchlist_by_category("finiti_da_vedere")
    finiti.append(anime)

    save_watchlist(watchlist, "in_corso")
    save_watchlist(finiti, "finiti_da_vedere")
    show_success(f"'{anime.get('titolo')}' spostato in Finiti da Vedere!")
    wait_enter()


def _elimina_anime(watchlist: list) -> None:
    clear_screen()
    show_header("ELIMINA ANIME")
    print()
    if not watchlist:
        show_warning("Watchlist vuota.")
        wait_enter()
        return

    for i, a in enumerate(watchlist, 1):
        print(f"  {i:>2}.  {a.get('titolo','')}")
    print(f"  {'0':>2}.  Annulla")
    print()
    scelta = input("  Seleziona: ").strip()
    if not scelta.isdigit() or int(scelta) == 0:
        return
    idx = int(scelta) - 1
    if idx < 0 or idx >= len(watchlist):
        show_warning("Selezione non valida.")
        wait_enter()
        return

    anime  = watchlist[idx]
    titolo = anime.get("titolo", "")
    print(f"\n  ⚠️  Sei sicuro di voler eliminare '{titolo}'? [s/N]: ", end="")
    conf = input().strip().lower()
    if conf == "s":
        watchlist.pop(idx)
        save_watchlist(watchlist, "in_corso")
        show_success(f"'{titolo}' eliminato!")
    else:
        print("  Operazione annullata.")
    wait_enter()

# ============================================================================
# AZIONI - FINITI DA VEDERE
# ============================================================================

def _visualizza_dettaglio_finiti(watchlist: list) -> None:
    _visualizza_dettaglio(watchlist)   # stessa logica


def _sposta_in_corso(watchlist: list) -> None:
    clear_screen()
    show_header("SPOSTA IN IN CORSO")
    print()
    if not watchlist:
        show_warning("Lista vuota.")
        wait_enter()
        return

    for i, a in enumerate(watchlist, 1):
        print(f"  {i:>2}.  {a.get('titolo','')}")
    print(f"  {'0':>2}.  Annulla")
    print()
    scelta = input("  Seleziona: ").strip()
    if not scelta.isdigit() or int(scelta) == 0:
        return
    idx = int(scelta) - 1
    if idx < 0 or idx >= len(watchlist):
        show_warning("Selezione non valida.")
        wait_enter()
        return

    anime = watchlist.pop(idx)
    anime["stato"]         = "In corso"
    anime["data_spostato"] = datetime.now().strftime("%Y-%m-%d")

    in_corso = load_watchlist_by_category("in_corso")
    in_corso.append(anime)

    save_watchlist(watchlist, "finiti_da_vedere")
    save_watchlist(in_corso, "in_corso")
    show_success(f"'{anime.get('titolo')}' spostato in In Corso!")
    wait_enter()


def _elimina_anime_finiti(watchlist: list) -> None:
    clear_screen()
    show_header("ELIMINA ANIME")
    print()
    if not watchlist:
        show_warning("Lista vuota.")
        wait_enter()
        return

    for i, a in enumerate(watchlist, 1):
        print(f"  {i:>2}.  {a.get('titolo','')}")
    print(f"  {'0':>2}.  Annulla")
    print()
    scelta = input("  Seleziona: ").strip()
    if not scelta.isdigit() or int(scelta) == 0:
        return
    idx = int(scelta) - 1
    if idx < 0 or idx >= len(watchlist):
        show_warning("Selezione non valida.")
        wait_enter()
        return

    titolo = watchlist[idx].get("titolo", "")
    print(f"\n  ⚠️  Eliminare '{titolo}'? [s/N]: ", end="")
    if input().strip().lower() == "s":
        watchlist.pop(idx)
        save_watchlist(watchlist, "finiti_da_vedere")
        show_success(f"'{titolo}' eliminato!")
    else:
        print("  Operazione annullata.")
    wait_enter()

# ============================================================================
# MENU IN CORSO
# ============================================================================

def _menu_in_corso() -> None:
    while True:
        clear_screen()
        show_header("WATCHLIST - IN CORSO")

        watchlist = load_watchlist_by_category("in_corso")

        print()
        print(f"  #    {'Titolo':<40} {'Ep':<10} {'Aggiunto':<15}")
        print("  " + "-" * 75)
        for idx, anime in enumerate(watchlist, 1):
            titolo   = anime.get("titolo", "")[:40]
            ep       = _get_ep_display(anime)
            aggiunto = anime.get("data_aggiunta", anime.get("aggiunto", "N/A"))
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

        if   scelta == "0": return
        elif scelta == "1": _aggiungi_manuale(watchlist)
        elif scelta == "2": _aggiungi_cerca_aw(watchlist)
        elif scelta == "3": _visualizza_dettaglio(watchlist)
        elif scelta == "4": _sposta_in_finiti(watchlist)
        elif scelta == "5": _elimina_anime(watchlist)
        else:
            show_warning("Opzione non valida!")
            wait_enter()

# ============================================================================
# MENU FINITI DA VEDERE
# ============================================================================

def _menu_finiti() -> None:
    while True:
        clear_screen()
        show_header("WATCHLIST - FINITI DA VEDERE")

        watchlist = load_watchlist_by_category("finiti_da_vedere")

        print()
        print(f"  #    {'Titolo':<40} {'Ep':<10} {'Aggiunto':<15}")
        print("  " + "-" * 75)
        for idx, anime in enumerate(watchlist, 1):
            titolo   = anime.get("titolo", "")[:40]
            ep       = _get_ep_display(anime)
            aggiunto = anime.get("data_aggiunta", anime.get("aggiunto", "N/A"))
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

        if   scelta == "0": return
        elif scelta == "1": _visualizza_dettaglio_finiti(watchlist)
        elif scelta == "2": _sposta_in_corso(watchlist)
        elif scelta == "3": _elimina_anime_finiti(watchlist)
        else:
            show_warning("Opzione non valida!")
            wait_enter()

# ============================================================================
# MENU PRINCIPALE
# ============================================================================

def handle_watchlist_menu(tracker=None) -> None:
    show_auto_update_in_corso()

    while True:
        clear_screen()
        show_header("WATCHLIST - MENU PRINCIPALE")
        print()
        print("  +--------------------------------------+")
        print("  |  1.  Gestione - In Corso             |")
        print("  |  2.  Gestione - Finiti da Vedere     |")
        print("  |  0.  Torna al menu precedente        |")
        print("  +--------------------------------------+")
        print()

        scelta = input("  Scegli un'opzione (0-2): ").strip()

        if   scelta == "0": return
        elif scelta == "1": _menu_in_corso()
        elif scelta == "2": _menu_finiti()
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
        import traceback; traceback.print_exc()
        sys.exit(1)
