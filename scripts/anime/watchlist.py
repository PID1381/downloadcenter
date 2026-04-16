#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watchlist.py v7.4 - PARITÀ FUNZIONALE FINITI/IN CORSO + ESTRAI LINK

NOVITA v7.4:
  [FEAT]  _menu_finiti: aggiunto "Aggiornamento nuovi episodi" (come IN CORSO)
  [FEAT]  _menu_finiti: aggiunto "Visualizza dettaglio" con sotto-menu
            (modifica manuale + aggiorna da AnimeWorld)
  [FEAT]  _menu_finiti: aggiunto "Estrai link download" via estrai_link_anime.py
            con selezione episodi (singolo / range / tutti)
  [REFACT] check_nuovi_episodi(cat, silent): parametro cat per usarla su
            entrambe le categorie
  [REFACT] _aggiorna_nuovi_episodi_menu(cat): idem
  [MANTIENE] tutto v7.3 invariato
"""

from __future__ import annotations
import csv
import importlib
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from anime_engine import (
        clear_screen, show_header, show_success, show_error, show_info,
        show_warning, ask_yes_no, wait_enter, sanitize_filename,
        search_animeworld, save_links, sort_links_numerically,
        setup_interrupt, teardown_interrupt, interrupted,
        HAS_PLAYWRIGHT,
    )
except ImportError as e:
    print(f"ERRORE: anime_engine non trovato: {e}")
    sys.exit(1)

_THIS_DIR = Path(__file__).parent.resolve()
_TEMP_DIR = _THIS_DIR.parent / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

_ROOT_DIR   = _THIS_DIR.parent.parent
_EXPORT_DIR = _ROOT_DIR / "export"

_PATHS = {
    "finiti_da_vedere": _TEMP_DIR / "watchlist_finiti_da_vedere.json",
    "in_corso":         _TEMP_DIR / "watchlist_in_corso.json",
}
_CATEGORIE = ["finiti_da_vedere", "in_corso"]
_LABEL     = {"finiti_da_vedere": "FINITI", "in_corso": "IN CORSO"}
_W         = 56

_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# =========================================================================
# PERSISTENZA
# =========================================================================

def _load(cat: str) -> list:
    p = _PATHS.get(cat)
    if not p or not p.is_file():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(cat: str, wl: list) -> None:
    p = _PATHS.get(cat)
    if not p:
        return
    try:
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            wl = sorted(wl, key=lambda x: x.get("data_aggiunta", ""), reverse=True)
        except Exception:
            pass
        with open(p, "w", encoding="utf-8") as f:
            json.dump(wl, f, ensure_ascii=False, indent=2)
    except OSError as e:
        show_error(f"Errore salvataggio watchlist: {e}")


def _load_all() -> dict:
    return {c: _load(c) for c in _CATEGORIE}


def _today() -> str:
    return date.today().isoformat()


def _find_by_title(titolo: str):
    t = titolo.lower().strip()
    for cat in _CATEGORIE:
        for i, a in enumerate(_load(cat)):
            if a.get("titolo", "").lower().strip() == t:
                return (cat, i)
    return None


# =========================================================================
# SCRAPING INFO DA ANIMEWORLD  (blocco .info.col-md-9 > .head)
# =========================================================================

def _fetch_anime_info(link: str) -> dict:
    """
    Recupera da AnimeWorld: data_uscita, genere, episodi_totali, episodi_usciti.

    Struttura HTML attesa:
      <div class="info col-md-9"><div class="head"><div class="c1">
        <dl>
          <dt>Data di Uscita:</dt><dd>04 Aprile 2026</dd>
          <dt>Genere:</dt><dd><a>Avventura</a>, ...</dd>
          <dt>Episodi:</dt><dd>26</dd>
        </dl>

    Episodi usciti: conta <li class="episode"> SOLO dentro
    il server "AnimeWorld Server" (via data-name del server-tab).
    """
    info = {}
    if not HAS_REQUESTS or not link:
        return info
    try:
        resp = requests.get(link, headers=_HDR, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # Blocco principale: <div class="info col-md-9">
        info_div = None
        for d in soup.find_all("div"):
            cls = " ".join(d.get("class", []))
            if "info" in cls and "col-md-9" in cls:
                info_div = d
                break

        # Leggi coppie <dt>/<dd>
        if info_div:
            for dt in info_div.find_all("dt"):
                label = dt.get_text(strip=True).rstrip(":").strip().lower()
                dd    = dt.find_next_sibling("dd")
                if not dd:
                    continue
                value = dd.get_text(" ", strip=True)

                if label in ("data di uscita", "data uscita"):
                    info["data_uscita"] = value.strip()

                elif label == "genere":
                    links_a = dd.find_all("a")
                    if links_a:
                        info["genere"] = ", ".join(
                            a.get_text(strip=True) for a in links_a
                        )
                    else:
                        info["genere"] = value.strip()

                elif label == "episodi":
                    m = re.search(r"\d+", value)
                    if m:
                        info["episodi_totali"] = int(m.group())

        # Episodi usciti: SOLO server "AnimeWorld Server"
        ep_usciti      = None
        widget_servers = soup.find("div", class_="widget servers")

        if widget_servers:
            # 1. Trova data-name del tab "AnimeWorld Server"
            aw_data_name = None
            for tab in widget_servers.find_all("span", class_="server-tab"):
                if "AnimeWorld Server" in tab.get_text(strip=True):
                    aw_data_name = tab.get("data-name")
                    break

            # 2. Conta <li class="episode"> nel server corrispondente
            if aw_data_name:
                server_div = widget_servers.find(
                    "div", attrs={"data-name": aw_data_name}
                )
                if server_div:
                    count = len(server_div.find_all("li", class_="episode"))
                    if count > 0:
                        ep_usciti = count

            # 3. Fallback: primo server "active"
            if ep_usciti is None:
                for srv in widget_servers.find_all("div", class_=True):
                    classes = srv.get("class", [])
                    if "server" in classes and "active" in classes and "widget" not in classes:
                        count = len(srv.find_all("li", class_="episode"))
                        if count > 0:
                            ep_usciti = count
                            break

            # 4. Ultimo fallback: server con più episodi
            if ep_usciti is None:
                max_count = 0
                for srv in widget_servers.find_all("div", class_=True):
                    classes = srv.get("class", [])
                    if "server" in classes and "widget" not in classes:
                        count = len(srv.find_all("li", class_="episode"))
                        if count > max_count:
                            max_count = count
                if max_count > 0:
                    ep_usciti = max_count

        if ep_usciti is not None:
            info["episodi_usciti"] = ep_usciti

    except Exception:
        pass

    return info


# =========================================================================
# AGGIORNAMENTO INFO COMPLETA (singolo anime)
# =========================================================================

def _aggiorna_info_completa(a: dict) -> dict:
    """
    Recupera TUTTI i campi da AnimeWorld per un singolo anime e aggiorna
    il dict in-place. Ritorna un dict con i campi effettivamente aggiornati.
    """
    link = a.get("link", "")
    aggiornati = {}
    if not link or not HAS_REQUESTS:
        return aggiornati

    info = _fetch_anime_info(link)

    # episodi_usciti: aggiorna sempre se il nuovo è diverso
    nuovi = info.get("episodi_usciti")
    if nuovi is not None:
        vecchio = a.get("episodi_usciti")
        if vecchio is None or nuovi != vecchio:
            aggiornati["episodi_usciti"] = (vecchio, nuovi)
            a["episodi_usciti"] = nuovi
            a["data_ep_usciti"] = _today()

    # episodi_totali: aggiorna se disponibile e diverso
    if info.get("episodi_totali"):
        if a.get("episodi_totali") != info["episodi_totali"]:
            aggiornati["episodi_totali"] = (a.get("episodi_totali"), info["episodi_totali"])
            a["episodi_totali"] = info["episodi_totali"]

    # data_uscita: aggiorna se mancante o vuota
    if info.get("data_uscita") and not a.get("data_uscita"):
        aggiornati["data_uscita"] = (None, info["data_uscita"])
        a["data_uscita"] = info["data_uscita"]

    # genere: aggiorna se mancante o vuoto
    if info.get("genere") and not a.get("genere"):
        aggiornati["genere"] = (None, info["genere"])
        a["genere"] = info["genere"]

    return aggiornati


# =========================================================================
# DISPLAY
# =========================================================================

def _fmt_ep(a: dict) -> str:
    """Formatta colonna Ep: [usciti/tot] oppure fallback su episodi_visti."""
    usciti = a.get("episodi_usciti")
    tot    = a.get("episodi_totali", "?")
    if usciti is not None:
        return f"[{usciti}/{tot}]"
    return str(a.get("episodi_visti", "?"))


def _print_list(wl: list, cat: str) -> None:
    print()
    if not wl:
        show_info(f"Nessun anime in '{_LABEL.get(cat, cat)}'.")
        return
    print(f"  {'#':<4} {'Titolo':<36} {'Ep':<10} {'Aggiunto'}")
    print("  " + "-" * 62)
    for i, a in enumerate(wl, 1):
        titolo = a.get("titolo", "N/D")
        if len(titolo) > 35:
            titolo = titolo[:32] + "..."
        ep  = _fmt_ep(a)
        dat = a.get("data_aggiunta", "")[:10]
        print(f"  {i:<4} {titolo:<36} {ep:<10} {dat}")
    print("  " + "-" * 62)
    print(f"  Totale: {len(wl)} anime")
    print()


def _print_detail(a: dict) -> None:
    print()
    print(f"  Titolo:          {a.get('titolo', 'N/D')}")
    print(f"  Episodi visti:   {a.get('episodi_visti', '?')}")
    print(
        f"  Episodi usciti:  {a.get('episodi_usciti', 'N/D')}  "
        f"(aggiornato: {a.get('data_ep_usciti', 'N/D')})"
    )
    print(f"  Episodi tot:     {a.get('episodi_totali', '?')}")
    print(f"  Data uscita:     {a.get('data_uscita', 'N/D')}")
    print(f"  Genere:          {a.get('genere', 'N/D')}")
    print(f"  Stato:           {a.get('stato', 'N/D')}")
    print(f"  Aggiunto:        {a.get('data_aggiunta', 'N/D')}")
    if a.get("link"):
        print(f"  Link:            {a['link']}")
    if a.get("note"):
        print(f"  Note:            {a['note']}")
    print()


def _select_from_list(wl: list, prompt: str = "Seleziona"):
    if not wl:
        return None
    while True:
        sel = input(f"  {prompt} (1-{len(wl)}, 0=annulla): ").strip()
        if sel == "0":
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(wl):
            return wl[int(sel) - 1]
        show_error("Selezione non valida.")


# =========================================================================
# MODIFICA MANUALE DETTAGLIO
# =========================================================================

def _edit_anime(a: dict, wl: list, cat: str) -> None:
    """Permette la modifica manuale dei campi di un anime."""
    while True:
        clear_screen()
        show_header("MODIFICA ANIME")
        _print_detail(a)
        print("  Campi modificabili:")
        print("  1. Titolo")
        print("  2. Episodi visti")
        print("  3. Episodi usciti")
        print("  4. Episodi totali")
        print("  5. Data uscita")
        print("  6. Genere")
        print("  7. Note")
        print("  0. Fine modifica")
        print()
        sc = input("  Campo da modificare (0-7): ").strip()
        if sc == "0":
            _save(cat, wl)
            show_success("Modifiche salvate.")
            wait_enter()
            return
        elif sc == "1":
            v = input(f"  Nuovo titolo [{a.get('titolo', '')}]: ").strip()
            if v:
                a["titolo"] = v
        elif sc == "2":
            v = input(f"  Episodi visti [{a.get('episodi_visti', 0)}]: ").strip()
            if v.isdigit():
                a["episodi_visti"] = int(v)
            else:
                show_error("Valore non valido.")
        elif sc == "3":
            v = input(f"  Episodi usciti [{a.get('episodi_usciti', '')}]: ").strip()
            if v.isdigit():
                a["episodi_usciti"] = int(v)
                a["data_ep_usciti"] = _today()
            else:
                show_error("Valore non valido.")
        elif sc == "4":
            v = input(f"  Episodi totali [{a.get('episodi_totali', '?')}]: ").strip()
            if v.isdigit():
                a["episodi_totali"] = int(v)
            elif v == "?":
                a["episodi_totali"] = "?"
            else:
                show_error("Valore non valido (numero o ?).")
        elif sc == "5":
            v = input(f"  Data uscita [{a.get('data_uscita', '')}]: ").strip()
            if v:
                a["data_uscita"] = v
        elif sc == "6":
            v = input(f"  Genere [{a.get('genere', '')}]: ").strip()
            if v:
                a["genere"] = v
        elif sc == "7":
            v = input(f"  Note [{a.get('note', '')}]: ").strip()
            a["note"] = v
        else:
            show_error("Opzione non valida.")


# =========================================================================
# VISUALIZZA DETTAGLIO + AZIONI  (comune a entrambe le categorie)
# =========================================================================

def _show_detail_menu(sel: dict, wl: list, cat: str) -> None:
    """
    Mostra il dettaglio di un anime con sotto-menu:
      1. Modifica manuale
      2. Aggiorna info da AnimeWorld  (se link disponibile)
      0. Torna
    """
    while True:
        clear_screen()
        show_header("DETTAGLIO ANIME")
        _print_detail(sel)
        print("  1. Modifica manuale")
        if HAS_REQUESTS and sel.get("link"):
            print("  2. Aggiorna info da AnimeWorld")
        print("  0. Torna")
        print()
        sc = input("  Scelta: ").strip()

        if sc == "0":
            return
        elif sc == "1":
            _edit_anime(sel, wl, cat)
        elif sc == "2" and HAS_REQUESTS and sel.get("link"):
            show_info("Recupero dati da AnimeWorld...")
            cambi = _aggiorna_info_completa(sel)
            if cambi:
                _save(cat, wl)
                show_success(f"Aggiornati {len(cambi)} campi:")
                for campo, (vecchio, nuovo) in cambi.items():
                    print(f"    {campo}: {vecchio!r} -> {nuovo!r}")
            else:
                show_info("Nessun campo aggiornato (già aggiornato).")
            wait_enter()
        else:
            show_error("Opzione non valida.")


# =========================================================================
# AGGIORNAMENTO NUOVI EPISODI  (comune a entrambe le categorie)
# =========================================================================

def check_nuovi_episodi(cat: str = "in_corso", silent: bool = False) -> int:
    """
    Controlla tutti gli anime in <cat> con link AnimeWorld.
    - Aggiorna episodi_usciti se sono aumentati.
    - Aggiorna episodi_totali se disponibile.
    - Riempie data_uscita e genere se mancanti nel JSON.
    Ritorna il numero di anime modificati.

    Puo essere chiamata all'avvio da main_menu.py:
        from scripts.anime.watchlist import check_nuovi_episodi
        check_nuovi_episodi(cat="in_corso", silent=True)
    """
    if not HAS_REQUESTS:
        return 0

    wl         = _load(cat)
    modificati = 0

    for a in wl:
        link = a.get("link", "")
        if not link:
            continue
        try:
            cambi = _aggiorna_info_completa(a)
            if cambi:
                modificati += 1
                if not silent:
                    titolo = a.get("titolo", "?")
                    if "episodi_usciti" in cambi:
                        vecchio, nuovo = cambi["episodi_usciti"]
                        show_success(f"{titolo} -- ep. usciti: {vecchio} -> {nuovo}")
                    if "data_uscita" in cambi:
                        show_info(f"{titolo} -- data uscita: {cambi['data_uscita'][1]}")
                    if "genere" in cambi:
                        show_info(f"{titolo} -- genere: {cambi['genere'][1]}")
        except Exception:
            pass

    if modificati > 0:
        _save(cat, wl)

    return modificati


def _aggiorna_nuovi_episodi_menu(cat: str = "in_corso") -> None:
    """Handler interattivo per 'Aggiornamento nuovi episodi'."""
    clear_screen()
    show_header(f"AGGIORNAMENTO NUOVI EPISODI — {_LABEL.get(cat, cat)}")
    if not HAS_REQUESTS:
        show_error("'requests' non installato -- aggiornamento non disponibile.")
        wait_enter()
        return

    show_info("Controllo aggiornamenti su AnimeWorld...")
    print()
    n = check_nuovi_episodi(cat=cat, silent=False)
    print()
    if n > 0:
        show_success(f"Aggiornati {n} anime.")
    else:
        show_info("Nessun aggiornamento trovato.")
    wait_enter()


# =========================================================================
# ESTRAI LINK DOWNLOAD  (solo per anime in watchlist con link AW)
# =========================================================================

def _load_estrai_link_module():
    """
    Carica estrai_link_anime.py dal percorso corrente (import lazy).
    Ritorna il modulo o None in caso di errore.
    """
    _elink_path = _THIS_DIR / "estrai_link_anime.py"
    if not _elink_path.exists():
        show_error(f"File estrai_link_anime.py non trovato in: {_THIS_DIR}")
        return None

    this_dir_s = str(_THIS_DIR)
    if this_dir_s not in sys.path:
        sys.path.insert(0, this_dir_s)

    # Riusa modulo già in cache (evita doppio exec)
    if "estrai_link_anime" in sys.modules:
        return sys.modules["estrai_link_anime"]

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "estrai_link_anime", str(_elink_path)
        )
        ela = importlib.util.module_from_spec(spec)
        sys.modules["estrai_link_anime"] = ela
        spec.loader.exec_module(ela)
        return ela
    except Exception as e:
        show_error(f"Errore caricamento estrai_link_anime: {e}")
        return None


def _estrai_link_watchlist(a: dict) -> None:
    """
    Estrae link download per un anime dalla watchlist.
    Usa le funzioni di estrai_link_anime.py:
      - _get_episode_list_requests  (fast path lista episodi)
      - _ask_episode_selection      (UI selezione singolo/range/tutti)
      - _extract_links_parallel     (estrazione parallela)
      - _extract_aw_link            (fallback episodio singolo)
    Playlist salvata con save_links() di anime_engine.
    """
    link   = a.get("link", "")
    titolo = a.get("titolo", "")

    if not link:
        show_error("Nessun link AnimeWorld associato a questo anime.")
        show_info("Modifica il record e aggiungi il link AnimeWorld.")
        wait_enter()
        return

    # Import lazy di estrai_link_anime
    ela = _load_estrai_link_module()
    if ela is None:
        wait_enter()
        return

    get_ep_list = getattr(ela, "_get_episode_list_requests", None)
    ask_ep_sel  = getattr(ela, "_ask_episode_selection", None)
    extract_par = getattr(ela, "_extract_links_parallel", None)
    extract_aw  = getattr(ela, "_extract_aw_link", None)

    if not all([get_ep_list, ask_ep_sel, extract_par, extract_aw]):
        show_error("Funzioni richieste non disponibili in estrai_link_anime.")
        wait_enter()
        return

    clear_screen()
    show_header(f"ESTRAI LINK — {titolo[:42]}")
    show_info(f"Link: {link}")
    print()

    # ── Recupera lista episodi ────────────────────────────────────────────
    show_info("Recupero lista episodi...")
    title_r, ep_links = get_ep_list(link)

    # Fallback: Playwright se fast path è vuoto
    if not ep_links and HAS_PLAYWRIGHT:
        show_info("Fast path vuoto — avvio browser per lista episodi...")
        try:
            from anime_engine import PageSession
            with PageSession() as sess:
                _, ep_links = sess.fetch_all_episodes(link)
        except Exception as ex:
            show_error(f"Errore browser: {ex}")

    # Nessuna lista → tentativo estrazione diretta (episodio singolo)
    if not ep_links:
        show_warning("Nessuna lista episodi trovata — tentativo estrazione diretta...")
        single = extract_aw(link)
        if single:
            show_success(f"Link trovato: ...{single[-65:]}")
            print()
            if ask_yes_no("Salvare il link in file .txt?"):
                fp = save_links([single], titolo)
                if fp and str(fp):
                    show_success(f"Salvato in: {fp.name}")
                    show_info(f"Percorso: {fp}")
                else:
                    show_error("Errore durante il salvataggio.")
        else:
            show_error("Nessun link trovato.")
        wait_enter()
        return

    show_success(f"Trovati {len(ep_links)} episodi.")

    # ── Selezione episodi ─────────────────────────────────────────────────
    indices = ask_ep_sel(ep_links)
    if indices is None:
        return

    selected = [ep_links[i] for i in indices]
    total_ep = len(selected)

    print()
    show_info(f"Estrazione {total_ep} episodi in parallelo...")
    show_info("Ctrl+C per interrompere e salvare i link già trovati")
    print()

    # ── Estrazione parallela ──────────────────────────────────────────────
    t_start = time.time()
    setup_interrupt()
    results, ep_ok, ep_fail, was_interrupted = extract_par(selected)
    teardown_interrupt()

    # Ordina risultati nell'ordine originale degli episodi
    ep_order = {u: i for i, u in enumerate(selected)}
    links = sort_links_numerically([
        results[u]
        for u in sorted(results, key=lambda u: ep_order.get(u, 9999))
        if results[u]
    ])

    elapsed = time.time() - t_start

    # ── Risultati ─────────────────────────────────────────────────────────
    clear_screen()
    show_header(f"RISULTATO — {titolo[:42]}")
    print(f"  Link trovati: {ep_ok}/{total_ep}")
    m_, s_ = int(elapsed // 60), int(elapsed % 60)
    print(f"  Tempo totale: {m_:02d}:{s_:02d}")
    if ep_fail > 0:
        show_warning(f"{ep_fail} episodi senza link.")
    if was_interrupted:
        show_warning("Estrazione interrotta — risultati parziali.")
    print()

    if not links:
        show_warning("Nessun link trovato.")
        wait_enter()
        return

    print("  Anteprima:")
    for i, ln in enumerate(links[:5], 1):
        print(f"  {i}. ...{ln[-65:]}")
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


# =========================================================================
# AGGIUNGI  (con arricchimento dati AnimeWorld)
# =========================================================================

def _enrich_with_aw(anime: dict) -> None:
    """Arricchisce il dict anime con i dati scraped da AnimeWorld."""
    if not anime.get("link"):
        return
    show_info("Recupero informazioni da AnimeWorld...")
    info = _fetch_anime_info(anime["link"])
    if info.get("data_uscita"):
        anime["data_uscita"] = info["data_uscita"]
    if info.get("genere"):
        anime["genere"] = info["genere"]
    if info.get("episodi_totali") and anime.get("episodi_totali") in ("?", None, 0):
        anime["episodi_totali"] = info["episodi_totali"]
    if info.get("episodi_usciti") is not None:
        anime["episodi_usciti"] = info["episodi_usciti"]
        anime["data_ep_usciti"] = _today()


def _aggiungi_manuale(cat: str) -> None:
    clear_screen()
    show_header(f"AGGIUNGI MANUALE - {_LABEL[cat]}")
    titolo = input("  Titolo anime: ").strip()
    if not titolo:
        show_error("Titolo obbligatorio.")
        wait_enter()
        return
    if _find_by_title(titolo):
        show_warning(f"'{titolo}' e gia in watchlist.")
        if not ask_yes_no("Aggiungere comunque?"):
            return

    link = input("  Link AnimeWorld (invio per saltare): ").strip()
    ep_v = input("  Episodi visti [0]: ").strip()
    ep_t = input("  Episodi totali [?]: ").strip()
    note = input("  Note (invio per saltare): ").strip()

    anime = {
        "titolo":         titolo,
        "link":           link,
        "episodi_visti":  int(ep_v) if ep_v.isdigit() else 0,
        "episodi_totali": int(ep_t) if ep_t.isdigit() else "?",
        "stato":          "In corso" if cat == "in_corso" else "Finito",
        "data_aggiunta":  _today(),
        "note":           note,
    }
    _enrich_with_aw(anime)

    wl = _load(cat)
    wl.append(anime)
    _save(cat, wl)
    show_success(f"'{titolo}' aggiunto a {_LABEL[cat]}.")
    wait_enter()


def _aggiungi_da_ricerca(cat: str) -> None:
    if not HAS_REQUESTS:
        show_error("'requests' non installato.")
        show_info("Esegui: pip install requests beautifulsoup4")
        wait_enter()
        return

    clear_screen()
    show_header(f"AGGIUNGI DA RICERCA - {_LABEL[cat]}")
    query = input("  Cerca su AnimeWorld (0=annulla): ").strip()
    if not query or query == "0":
        return

    results = search_animeworld(query)
    if not results:
        show_warning("Nessun risultato trovato.")
        wait_enter()
        return

    print()
    for i, r in enumerate(results[:15], 1):
        print(f"  {i:>2}. {r['title']}")
    print()
    print("  0. Annulla")
    print()

    sel = input("  Seleziona: ").strip()
    if sel == "0" or not sel.isdigit() or not (1 <= int(sel) <= min(15, len(results))):
        return

    r      = results[int(sel) - 1]
    titolo = r.get("raw_title", r.get("title", ""))

    if _find_by_title(titolo):
        show_warning(f"'{titolo}' e gia in watchlist.")
        if not ask_yes_no("Aggiungere comunque?"):
            return

    ep_v = input("  Episodi visti [0]: ").strip()
    ep_t = input("  Episodi totali [?]: ").strip()
    note = input("  Note (invio per saltare): ").strip()

    anime = {
        "titolo":         titolo,
        "link":           r.get("link", ""),
        "categoria_aw":   r.get("category", ""),
        "episodi_visti":  int(ep_v) if ep_v.isdigit() else 0,
        "episodi_totali": int(ep_t) if ep_t.isdigit() else "?",
        "stato":          "In corso" if cat == "in_corso" else "Finito",
        "data_aggiunta":  _today(),
        "note":           note,
    }
    _enrich_with_aw(anime)

    wl = _load(cat)
    wl.append(anime)
    _save(cat, wl)
    show_success(f"'{titolo}' aggiunto a {_LABEL[cat]}.")
    wait_enter()


# =========================================================================
# BONUS: EXPORT CSV
# =========================================================================

def handle_export_csv() -> None:
    clear_screen()
    show_header("ESPORTA WATCHLIST CSV")

    all_wl = _load_all()
    righe  = []
    for cat in _CATEGORIE:
        for a in all_wl[cat]:
            righe.append({
                "Categoria":       _LABEL.get(cat, cat),
                "Titolo":          a.get("titolo", ""),
                "Stato":           a.get("stato", ""),
                "Episodi Visti":   a.get("episodi_visti", 0),
                "Episodi Usciti":  a.get("episodi_usciti", ""),
                "Episodi Totali":  a.get("episodi_totali", "?"),
                "Data Uscita":     a.get("data_uscita", ""),
                "Genere":          a.get("genere", ""),
                "Data Aggiunta":   a.get("data_aggiunta", "")[:10],
                "Link":            a.get("link", ""),
                "Note":            a.get("note", ""),
            })

    if not righe:
        show_warning("Watchlist vuota - nessun dato da esportare.")
        wait_enter()
        return

    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = _EXPORT_DIR / f"watchlist_{date.today().isoformat()}.csv"

    cnt = 1
    while filename.exists():
        filename = _EXPORT_DIR / f"watchlist_{date.today().isoformat()}_{cnt}.csv"
        cnt += 1

    try:
        with open(filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Categoria", "Titolo", "Stato",
                "Episodi Visti", "Episodi Usciti", "Episodi Totali",
                "Data Uscita", "Genere",
                "Data Aggiunta", "Link", "Note",
            ])
            writer.writeheader()
            writer.writerows(righe)
        show_success(f"Esportati {len(righe)} anime in: {filename.name}")
        show_info(f"Percorso: {filename}")
    except Exception as e:
        show_error(f"Errore esportazione CSV: {e}")
    wait_enter()


# =========================================================================
# MENU FINITI DA VEDERE
# =========================================================================

def _menu_finiti() -> None:
    cat = "finiti_da_vedere"
    while True:
        clear_screen()
        show_header("WATCHLIST - FINITI DA VEDERE")
        wl = _load(cat)
        _print_list(wl, cat)
        print("  +--------------------------------------+")
        print("  |  1.  Aggiungi (manuale)              |")
        print("  |  2.  Aggiungi (cerca AnimeWorld)     |")
        print("  |  3.  Visualizza dettaglio            |")
        print("  |  4.  Aggiornamento nuovi episodi     |")
        print("  |  5.  Estrai link download            |")
        print("  |  6.  Sposta in IN CORSO              |")
        print("  |  7.  Elimina                         |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        sc = input("  Scelta: ").strip()

        if sc == "0":
            return
        elif sc == "1":
            _aggiungi_manuale(cat)
        elif sc == "2":
            _aggiungi_da_ricerca(cat)
        elif sc == "3":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Visualizza")
            if sel:
                _show_detail_menu(sel, wl, cat)
        elif sc == "4":
            _aggiorna_nuovi_episodi_menu(cat)
        elif sc == "5":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Seleziona anime")
            if sel:
                _estrai_link_watchlist(sel)
        elif sc == "6":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Sposta in IN CORSO")
            if not sel:
                continue
            if not ask_yes_no(f"Spostare '{sel['titolo']}' in IN CORSO?"):
                continue
            wl.remove(sel)
            _save(cat, wl)
            sel["stato"] = "In corso"
            wl2 = _load("in_corso")
            wl2.append(sel)
            _save("in_corso", wl2)
            show_success(f"'{sel['titolo']}' spostato in IN CORSO.")
            wait_enter()
        elif sc == "7":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Elimina")
            if not sel:
                continue
            if ask_yes_no(f"Eliminare '{sel['titolo']}'?"):
                wl.remove(sel)
                _save(cat, wl)
                show_success(f"'{sel['titolo']}' eliminato.")
                wait_enter()
        else:
            show_error("Opzione non valida.")
            wait_enter()


# =========================================================================
# MENU IN CORSO
# =========================================================================

def _menu_in_corso() -> None:
    cat = "in_corso"
    while True:
        clear_screen()
        show_header("WATCHLIST - IN CORSO")
        wl = _load(cat)
        _print_list(wl, cat)
        print("  +--------------------------------------+")
        print("  |  1.  Aggiungi (manuale)              |")
        print("  |  2.  Aggiungi (cerca AnimeWorld)     |")
        print("  |  3.  Visualizza dettaglio            |")
        print("  |  4.  Aggiornamento nuovi episodi     |")
        print("  |  5.  Sposta in FINITI                |")
        print("  |  6.  Elimina                         |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        sc = input("  Scelta: ").strip()

        if sc == "0":
            return
        elif sc == "1":
            _aggiungi_manuale(cat)
        elif sc == "2":
            _aggiungi_da_ricerca(cat)
        elif sc == "3":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Visualizza")
            if sel:
                _show_detail_menu(sel, wl, cat)
        elif sc == "4":
            _aggiorna_nuovi_episodi_menu(cat)
        elif sc == "5":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Sposta in FINITI")
            if not sel:
                continue
            if not ask_yes_no(f"Spostare '{sel['titolo']}' in FINITI?"):
                continue
            wl.remove(sel)
            _save(cat, wl)
            sel["stato"] = "Finito"
            wl2 = _load("finiti_da_vedere")
            wl2.append(sel)
            _save("finiti_da_vedere", wl2)
            show_success(f"'{sel['titolo']}' spostato in FINITI.")
            wait_enter()
        elif sc == "6":
            wl = _load(cat)
            if not wl:
                show_info("Lista vuota.")
                wait_enter()
                continue
            _print_list(wl, cat)
            sel = _select_from_list(wl, "Elimina")
            if not sel:
                continue
            if ask_yes_no(f"Eliminare '{sel['titolo']}'?"):
                wl.remove(sel)
                _save(cat, wl)
                show_success(f"'{sel['titolo']}' eliminato.")
                wait_enter()
        else:
            show_error("Opzione non valida.")
            wait_enter()


# =========================================================================
# MENU PRINCIPALE
# =========================================================================

def handle_watchlist_menu(tracker=None) -> None:
    while True:
        clear_screen()
        show_header("WATCHLIST")
        all_wl = _load_all()
        print()
        print(f"  1.  FINITI DA VEDERE  ({len(all_wl['finiti_da_vedere'])} anime)")
        print(f"  2.  IN CORSO          ({len(all_wl['in_corso'])} anime)")
        print()
        print("  3.  Esporta watchlist CSV")
        print()
        print("  0.  Torna al menu Anime")
        print()
        if not HAS_REQUESTS:
            show_warning("'requests' non installato - ricerca online disabilitata")
            print()
        sc = input("  Scelta: ").strip()
        if sc == "0":
            return
        elif sc == "1":
            _menu_finiti()
        elif sc == "2":
            _menu_in_corso()
        elif sc == "3":
            handle_export_csv()
        else:
            show_error("Opzione non valida.")
            wait_enter()



def handle_watchlist_menu(tracker=None) -> None:
    """
    Menu principale della Watchlist - Entry point per handlers.py
    
    Questa funzione è l'interfaccia principale per accedere alla watchlist.
    Mantiene la logica originale di check_nuovi_episodi() e _menu_in_corso()
    
    Args:
        tracker: parametro opzionale (non utilizzato, per compatibilità con handlers.py)
    """
    while True:
        clear_screen()
        show_header("WATCHLIST - MENU PRINCIPALE")
        
        print()
        print("  [1] Verificare nuovi episodi - In Corso")
        print("  [2] Verificare nuovi episodi - Finiti da Vedere")
        print("  [3] Gestione Watchlist - In Corso")
        print("  [4] Gestione Watchlist - Finiti da Vedere")
        print("  [0] Torna al menu precedente")
        print()
        
        scelta = input("  Scegli un'opzione (0-4): ").strip()
        
        if scelta == "0":
            return
        
        elif scelta == "1":
            # Verifica nuovi episodi - In Corso
            check_nuovi_episodi(cat="in_corso", silent=False)
            wait_enter()
        
        elif scelta == "2":
            # Verifica nuovi episodi - Finiti da Vedere
            check_nuovi_episodi(cat="finiti_da_vedere", silent=False)
            wait_enter()
        
        elif scelta == "3":
            # Menu In Corso
            _menu_in_corso()
        
        elif scelta == "4":
            # Menu Finiti da Vedere
            _menu_finiti()
        
        else:
            show_warning("Opzione non valida!")
            wait_enter()



if __name__ == "__main__":
    # Test
    pass
