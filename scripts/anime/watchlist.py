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

def _print_watchlist_table(watchlist: list) -> None:
    """Tabella watchlist con box-drawing standard ┌─┬┐."""
    headers = ["N", "Titolo", "Ep", "Aggiunto"]
    col_w   = [3, 40, 10, 15]

    def _cell(val, w):
        val = str(val)
        if len(val) > w: val = val[:w-2] + ".."
        return val.ljust(w)

    def _border(l, m, r, f):
        return "  " + l + m.join(f*(w+2) for w in col_w) + r

    def _row(vals):
        parts = [f" {_cell(str(v), col_w[i])} " for i,v in enumerate(vals)]
        return "  │" + "│".join(parts) + "│"

    print(_border("┌","┬","┐","─"))
    print(_row(headers))
    print(_border("├","┼","┤","─"))
    for idx, anime in enumerate(watchlist, 1):
        titolo   = anime.get("titolo", "")
        ep       = _get_ep_display(anime)
        aggiunto = anime.get("data_aggiunta", anime.get("aggiunto", "N/A"))
        print(_row([idx, titolo, ep, aggiunto]))
    print(_border("└","┴","┘","─"))
    print(f"  Totale: {len(watchlist)} anime")
    print()



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
            import time as _t
            _filled = int((idx / total) * 40)
            _bar    = "█" * _filled + "░" * (40 - _filled)
            _chars  = ["◐","◓","◑","◒"]
            _anim   = _chars[int(_t.time() * 4) % 4]
            print(f"\r      Scansione: |{_bar}| {int((idx/total)*100):.1f}% {_anim}", end="", flush=True)
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


# ============================================================================
# MODIFICA DETTAGLIO
# ============================================================================

def _modifica_dettaglio(a: dict, watchlist: list, idx: int, category: str) -> None:
    """Modifica interattiva dei campi di un anime dalla schermata dettaglio."""
    CAMPI = [
        ("titolo",         "Titolo"),
        ("stato",          "Stato"),
        ("episodi_usciti", "Episodi usciti"),
        ("episodi_totali", "Episodi totali"),
        ("episodi_visti",  "Episodi visti"),
        ("data_aggiunta",  "Data aggiunta"),
        ("data_uscita",    "Data uscita"),
        ("genere",         "Genere"),
        ("link",           "Link"),
        ("note",           "Note"),
    ]

    while True:
        clear_screen()
        show_header(f"MODIFICA - {a.get('titolo', '')}")
        print()
        for i, (key, label) in enumerate(CAMPI, 1):
            valore = a.get(key, "")
            print(f"  {i:>2}.  {label:<20} {valore}")
        print()
        print(f"  {'0':>2}.  Salva e torna")
        print()

        scelta = input("  Campo da modificare (0 per salvare): ").strip()

        if scelta == "0":
            watchlist[idx] = a
            save_watchlist(watchlist, category)
            show_success("Modifiche salvate!")
            wait_enter()
            return

        if not scelta.isdigit():
            show_warning("Inserisci un numero valido.")
            wait_enter()
            continue

        campo_idx = int(scelta) - 1
        if campo_idx < 0 or campo_idx >= len(CAMPI):
            show_warning("Selezione non valida.")
            wait_enter()
            continue

        key, label = CAMPI[campo_idx]
        valore_attuale = a.get(key, "")
        print(f"\n  {label} attuale: {valore_attuale}")
        nuovo_valore = input("  Nuovo valore (INVIO per non cambiare): ").strip()

        if nuovo_valore == "":
            continue

        if key in ("episodi_usciti", "episodi_visti"):
            if nuovo_valore.isdigit():
                a[key] = int(nuovo_valore)
            else:
                show_warning("Inserisci un numero intero.")
                wait_enter()
        elif key == "episodi_totali":
            a[key] = int(nuovo_valore) if nuovo_valore.isdigit() else nuovo_valore
        else:
            a[key] = nuovo_valore


def _visualizza_dettaglio(watchlist: list, category: str = "in_corso") -> None:
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
    print("  M.  Modifica questo titolo")
    print()
    scelta_post = input("  Premi INVIO per continuare o M per modificare: ").strip().upper()
    if scelta_post == "M":
        _modifica_dettaglio(a, watchlist, idx, category)


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
    _visualizza_dettaglio(watchlist, category="finiti_da_vedere")


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
        _print_watchlist_table(watchlist)

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
        elif scelta == "3": _visualizza_dettaglio(watchlist, "in_corso")
        elif scelta == "4": _sposta_in_finiti(watchlist)
        elif scelta == "5": _elimina_anime(watchlist)
        else:
            show_warning("Opzione non valida!")
            wait_enter()


# ============================================================================
# ESTRAI LINK DA WATCHLIST (Finiti da Vedere)
# ============================================================================

def _estrai_link_da_watchlist(watchlist: list) -> None:
    """Seleziona un anime dai Finiti da Vedere ed estrae i link via AnimeWorld."""
    clear_screen()
    show_header("ESTRAI LINK - FINITI DA VEDERE")
    print()

    if not watchlist:
        show_warning("Lista vuota.")
        wait_enter()
        return

    for i, a in enumerate(watchlist, 1):
        print(f"  {i:>2}.  {a.get('titolo','')}")
    print(f"  {'0':>2}.  Annulla")
    print()
    scelta = input("  Seleziona anime: ").strip()
    if not scelta.isdigit() or int(scelta) == 0:
        return
    idx = int(scelta) - 1
    if idx < 0 or idx >= len(watchlist):
        show_warning("Selezione non valida.")
        wait_enter()
        return

    anime  = watchlist[idx]
    titolo = anime.get("titolo", "")
    link   = anime.get("link", "")

    clear_screen()
    show_header(f"ESTRAI LINK - {titolo}")
    print()

    # Importa le funzioni di estrazione da estrai_link_anime.py
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from estrai_link_anime import (
            _get_episode_list_requests,
            _extract_links_parallel,
            _ask_episode_selection,
        )
        from anime_engine import (
            save_links, search_animeworld, sort_links_numerically,
            show_info, show_success, show_error, show_warning,
            ask_yes_no, setup_interrupt, teardown_interrupt,
        )
    except ImportError as e:
        show_error(f"Impossibile importare moduli estrazione: {e}")
        wait_enter()
        return

    # ── 1. Recupera URL pagina anime ─────────────────────────────────────────
    if not link:
        print("  Nessun link salvato per questo anime.")
        print("  Inserisci l'URL AnimeWorld manualmente:")
        link = input("  URL (0=annulla): ").strip()
        if not link or link == "0":
            return

    # ── 2. Recupera lista episodi ─────────────────────────────────────────────
    print()
    show_info(f"Raccolta episodi da AnimeWorld per: {titolo}")
    title_r, ep_links = _get_episode_list_requests(link)

    if not ep_links:
        show_warning("Impossibile ottenere la lista episodi dal link salvato.")
        show_info("Prova a cercare il titolo su AnimeWorld:")
        results = search_animeworld(titolo)
        if not results:
            show_error("Nessun risultato trovato.")
            wait_enter()
            return
        print()
        for i, r in enumerate(results[:10], 1):
            print(f"  {i:>2}. {r['title']}")
        print(f"  {'0':>2}. Annulla")
        print()
        sc = input("  Seleziona: ").strip()
        if not sc.isdigit() or sc == "0":
            return
        sc_idx = int(sc) - 1
        if sc_idx < 0 or sc_idx >= min(10, len(results)):
            show_warning("Selezione non valida.")
            wait_enter()
            return
        link_new = results[sc_idx].get("link", "")
        title_r, ep_links = _get_episode_list_requests(link_new)
        if not ep_links:
            show_error("Impossibile ottenere episodi neanche dal nuovo link.")
            wait_enter()
            return

    show_success(f"Trovati {len(ep_links)} episodi.")

    # ── 3. Selezione episodi ──────────────────────────────────────────────────
    indices = _ask_episode_selection(ep_links)
    if indices is None:
        return
    selected = [ep_links[i] for i in indices]

    # ── 4. Estrazione parallela ───────────────────────────────────────────────
    print()
    show_info(f"Estrazione {len(selected)} episodi in corso...")
    show_info("Ctrl+C per interrompere e salvare i link già trovati")
    print()

    import time
    t0 = time.time()
    setup_interrupt()
    results_dict, ep_ok, ep_fail, was_interrupted = _extract_links_parallel(selected)
    teardown_interrupt()

    ep_order = {u: i for i, u in enumerate(selected)}
    links = [
        results_dict[u]
        for u in sorted(results_dict, key=lambda u: ep_order.get(u, 9999))
        if results_dict[u]
    ]
    links = sort_links_numerically(links)

    elapsed = time.time() - t0
    clear_screen()
    show_header("RISULTATO ESTRAZIONE")
    print(f"  Anime:        {titolo}")
    print(f"  Link trovati: {len(links)}")
    print(f"  Tempo:        {round(elapsed, 1)}s")
    if was_interrupted:
        show_warning("Estrazione interrotta — risultati parziali.")
    if ep_fail > 0:
        show_warning(f"{ep_fail} episodi senza link trovato.")
    print()

    if not links:
        show_warning("Nessun link trovato.")
        wait_enter()
        return

    print("  Anteprima link:")
    for i, ln in enumerate(links[:5], 1):
        print(f"  {i}. ...{ln[-68:]}")
    if len(links) > 5:
        show_info(f"...e altri {len(links) - 5} link")
    print()

    if ask_yes_no("Salvare i link in file .txt?"):
        fp = save_links(links, titolo)
        if fp and str(fp):
            show_success(f"Salvati {len(links)} link in: {fp.name}")
            show_info(f"Percorso: {fp}")
        else:
            show_error("Errore durante il salvataggio.")

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
        _print_watchlist_table(watchlist)

        print("  +--------------------------------------+")
        print("  |  1.  Visualizza dettaglio            |")
        print("  |  2.  Estrai link                     |")
        print("  |  3.  Sposta in IN CORSO              |")
        print("  |  4.  Elimina                         |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        print()

        scelta = input("  Scelta: ").strip()

        if   scelta == "0": return
        elif scelta == "1": _visualizza_dettaglio_finiti(watchlist)
        elif scelta == "2": _estrai_link_da_watchlist(watchlist)
        elif scelta == "3": _sposta_in_corso(watchlist)
        elif scelta == "4": _elimina_anime_finiti(watchlist)
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
