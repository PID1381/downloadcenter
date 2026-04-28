#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
animeunity_handler.py  v1.0
Download Center - scripts/anime/animeunity_handler.py

Handler UI per AnimeUnity: collegamento tra animeunity.py
e il sistema menu/download del Download Center.

FLUSSO UI:
  run()
    └─ _menu_principale()
         ├─ 1. Ultimi episodi   -> news()     -> seleziona -> findvideos() -> download
         ├─ 2. Cerca titolo     -> search()   -> _mostra_lista_anime()
         ├─ 3. Sfoglia catalogo -> mainlist() -> menu() -> peliculas() -> _mostra_lista_anime()
         └─ 0. Torna

  _mostra_lista_anime(items)
    └─ selezione -> _gestisci_anime(anime)
         ├─ film (1 ep) -> findvideos() -> _offri_download(url)
         └─ serie       -> episodios()  -> _mostra_episodi(eps) -> _offri_download(url)

  _offri_download(hls_url)
    └─ salva .txt + avvia download_diretto_anime.download_video()
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR    = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()
_CORE_DIR    = _SCRIPTS_DIR / "core"
_DL_DIR      = _SCRIPTS_DIR / "download"

for _p in (str(_THIS_DIR), str(_SCRIPTS_DIR), str(_CORE_DIR), str(_DL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Import animeunity ─────────────────────────────────────────────────────────
try:
    import animeunity as _au
    _HAS_AU = True
except ImportError:
    _au     = None  # type: ignore[assignment]
    _HAS_AU = False

# ── UI helpers ────────────────────────────────────────────────────────────────
try:
    from anime_engine import (
        clear_screen, show_header, show_error, show_info,
        show_warning, show_success, wait_enter, ask_yes_no,
        get_valid_choice, save_links, load_prefs,
    )
    _HAS_ENGINE = True
except ImportError:
    _HAS_ENGINE = False
    def clear_screen():                       pass
    def show_header(t, b=""):                 print(f"\n{'='*56}\n  {t}\n{'='*56}")
    def show_error(m):                        print(f"  [X] {m}")
    def show_info(m):                         print(f"  [i] {m}")
    def show_warning(m):                      print(f"  [!] {m}")
    def show_success(m):                      print(f"  [v] {m}")
    def wait_enter(m="Premi INVIO..."):        input(f"  {m}")
    def ask_yes_no(q):                        return input(f"  {q} (s/n): ").strip().lower() in ("s","si","y")
    def save_links(links, name):              return None
    def load_prefs():                         return {}
    def get_valid_choice(p, opts):
        while True:
            c = input(f"  {p}").strip()
            if c in opts:
                return c
            print(f"  Valori validi: {opts}")


# ════════════════════════════════════════════════════════════════════════════
# HELPERS UI
# ════════════════════════════════════════════════════════════════════════════

def _print_box(*lines: str) -> None:
    """Stampa riquadro menu."""
    print("  +" + "-"*40 + "+")
    for line in lines:
        print(f"  | {line:<38} |")
    print("  +" + "-"*40 + "+")


def _print_list(items: list, key: str = "title", max_show: int = 20) -> None:
    """Stampa lista numerata anime/episodi."""
    for i, item in enumerate(items[:max_show], 1):
        label  = item.get(key) or item.get("label") or str(item)
        lang   = item.get("language")
        lang_s = f" [{lang}]" if lang else ""
        e_cnt  = item.get("episodes_count")
        cnt_s  = f" ({e_cnt} ep)" if e_cnt else ""
        print(f"  {i:>3}. {label}{lang_s}{cnt_s}")
    if len(items) > max_show:
        show_info(f"...e altri {len(items) - max_show} risultati (pagina successiva)")


# ════════════════════════════════════════════════════════════════════════════
# DOWNLOAD
# ════════════════════════════════════════════════════════════════════════════

def _offri_download(hls_url: str, titolo: str = "") -> None:
    """
    Presenta il link HLS all'utente:
    1. Mostra il link trovato
    2. Chiede se salvare in file .txt
    3. Chiede se avviare download diretto
    """
    if not hls_url:
        show_warning("Nessun link video trovato.")
        wait_enter()
        return

    print()
    show_success("Link HLS trovato:")
    # Mostra link troncato per leggibilita'
    display = hls_url if len(hls_url) <= 90 else hls_url[:87] + "..."
    print(f"  {display}")
    print()

    # ── Salva in .txt ─────────────────────────────────────────────────────────
    if ask_yes_no("Salvare il link in file .txt?"):
        try:
            fp = save_links([hls_url], titolo or "animeunity_episodio")
            if fp:
                show_success(f"Salvato in: {Path(fp).name}")
                show_info(f"Percorso  : {fp}")
            else:
                show_warning("save_links non ha restituito un percorso.")
        except Exception as e:
            show_error(f"Errore salvataggio: {e}")

    print()

    # ── Download diretto ─────────────────────────────────────────────────────
    if ask_yes_no("Avviare download diretto?"):
        try:
            from download_diretto_anime import download_video

            prefs  = load_prefs()
            dl_dir = prefs.get("default_download_dir", str(Path.home() / "Downloads"))
            fname  = (titolo or "episodio").replace("/", "_").replace("\\", "_") + ".ts"

            print()
            show_info(f"Cartella : {dl_dir}")
            show_info(f"File     : {fname}")
            print()

            result = download_video(hls_url, dl_dir, fname)
            if result is True:
                show_success("Download completato!")
            elif result is None:
                show_warning("Download annullato.")
            else:
                show_error("Download fallito.")

        except ImportError:
            show_warning("download_diretto_anime.py non trovato.")
            show_info("Copia il link e aprilo con VLC / mpv / ffmpeg.")

    wait_enter()


# ════════════════════════════════════════════════════════════════════════════
# LOGICA ANIME
# ════════════════════════════════════════════════════════════════════════════

def _gestisci_anime(anime: Dict) -> None:
    """
    Gestisce la selezione di un anime:
    - Film (1 ep) : risolve subito il video
    - Serie       : mostra lista episodi -> selezione -> risolve
    """
    title   = anime.get("title") or "N/D"
    action  = anime.get("action") or ""
    url     = anime.get("url") or ""
    api_url = anime.get("api_ep_url") or ""

    clear_screen()
    show_header("ANIMEUNITY", f"Anime > {title}")
    print(f"  Titolo  : {title}")
    print(f"  Tipo    : {anime.get('type') or 'N/D'}")
    print(f"  Lingua  : {anime.get('language') or 'N/D'}")
    print(f"  Episodi : {anime.get('episodes_count') or '?'}")
    if anime.get("plot"):
        trama = anime["plot"]
        print(f"  Trama   : {(trama[:100] + '...') if len(trama) > 100 else trama}")
    print()

    if action == "findvideos":
        # Film: risolve direttamente
        show_info("Risoluzione link video in corso...")
        hls = _au.findvideos(url)
        _offri_download(hls, title)

    elif action == "episodios":
        if not api_url:
            show_error("api_ep_url mancante nell'oggetto anime.")
            wait_enter()
            return
        show_info("Caricamento lista episodi...")
        episodes = _au.episodios(api_url, anime.get("type") or "tvshow", url)
        if not episodes:
            show_warning("Nessun episodio trovato.")
            wait_enter()
            return
        _mostra_episodi(episodes, title)

    else:
        show_error(f"Azione non gestita: {action}")
        wait_enter()


def _mostra_episodi(episodes: List[Dict], serie_title: str = "") -> None:
    """Selezione episodio da lista."""
    _PAGE_EP = 20  # episodi per pagina

    page = 0
    while True:
        start  = page * _PAGE_EP
        end    = start + _PAGE_EP
        subset = episodes[start:end]

        clear_screen()
        show_header("EPISODI", f"AnimeUnity > {serie_title}")
        print(f"  Totale episodi: {len(episodes)}   "
              f"Pagina: {page+1}/{((len(episodes)-1)//_PAGE_EP)+1}")
        print()

        for i, ep in enumerate(subset, start + 1):
            print(f"  {i:>4}. {ep.get('title') or f'Episodio {i}'}")

        print()
        nav = []
        if page > 0:
            nav.append("p=Precedente")
        if end < len(episodes):
            nav.append("n=Successiva")
        nav.append("0=Torna")
        print(f"  [{' | '.join(nav)}]")
        print()

        raw = input(f"  Episodio ({start+1}-{min(end,len(episodes))}, 0/n/p): ").strip().lower()

        if raw == "0":
            return
        if raw == "n" and end < len(episodes):
            page += 1
            continue
        if raw == "p" and page > 0:
            page -= 1
            continue

        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(episodes):
                ep       = episodes[idx - 1]
                ep_url   = ep.get("url") or ""
                ep_title = f"{serie_title} - {ep.get('title') or ''}"
                if not ep_url:
                    show_error("URL episodio mancante.")
                    continue
                show_info(f"Risoluzione: {ep_title}...")
                hls = _au.findvideos(ep_url, ep.get("scws_id") or "")
                _offri_download(hls, ep_title)
                continue

        show_error("Input non valido.")


def _mostra_lista_anime(items: List[Dict], titolo_menu: str = "RISULTATI") -> None:
    """Selezione anime da lista con paginazione."""
    if not items:
        show_warning("Nessun risultato trovato.")
        wait_enter()
        return

    _PAGE = 20
    page  = 0

    while True:
        start  = page * _PAGE
        end    = start + _PAGE
        subset = items[start:end]

        clear_screen()
        show_header("ANIMEUNITY", f"AnimeUnity > {titolo_menu}")
        print(f"  {len(items)} anime trovati   "
              f"Pagina: {page+1}/{((len(items)-1)//_PAGE)+1}")
        print()
        _print_list(subset, key="title", max_show=_PAGE)
        print()

        nav = []
        if page > 0:
            nav.append("p=Prec")
        if end < len(items):
            nav.append("n=Succ")
        nav.append("0=Torna")
        print(f"  [{' | '.join(nav)}]")
        print()

        raw = input(f"  Selezione (1-{len(subset)}, 0/n/p): ").strip().lower()

        if raw == "0":
            return
        if raw == "n" and end < len(items):
            page += 1
            continue
        if raw == "p" and page > 0:
            page -= 1
            continue
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(subset):
                _gestisci_anime(subset[idx - 1])
                continue
        show_error("Selezione non valida.")


# ════════════════════════════════════════════════════════════════════════════
# MENU SFOGLIA CATALOGO
# ════════════════════════════════════════════════════════════════════════════

def _menu_sfoglia() -> None:
    """Sfoglia catalogo: mainlist -> sotto-menu -> peliculas."""
    top        = _au.mainlist()
    categorie  = [t for t in top if t["action"] == "menu"]

    while True:
        clear_screen()
        show_header("ANIMEUNITY", "AnimeUnity > Sfoglia Catalogo")
        for i, cat in enumerate(categorie, 1):
            print(f"  {i:>2}. {cat['label']}")
        print()
        print("  0. Torna")
        print()

        raw = input(f"  Categoria (1-{len(categorie)}, 0=torna): ").strip()
        if raw == "0":
            return
        if not (raw.isdigit() and 1 <= int(raw) <= len(categorie)):
            continue

        cat_sel   = categorie[int(raw) - 1]
        sub_items = _au.menu(cat_sel["args"], cat_sel.get("content_type", "tvshow"))
        # Mostra solo voci che portano a una lista (non 'genres', 'years', 'search')
        sub_lista = [s for s in sub_items if s["action"] in ("peliculas",)]
        sub_extra = [s for s in sub_items if s["action"] in ("genres", "years")]

        clear_screen()
        show_header("ANIMEUNITY", f"AnimeUnity > {cat_sel['label']}")
        all_sub = sub_lista + sub_extra
        for i, s in enumerate(all_sub, 1):
            print(f"  {i:>2}. {s['label']}")
        print()
        print("  0. Torna")
        print()

        raw2 = input(f"  Filtro (1-{len(all_sub)}, 0=torna): ").strip()
        if raw2 == "0":
            continue
        if not (raw2.isdigit() and 1 <= int(raw2) <= len(all_sub)):
            continue

        filtro = all_sub[int(raw2) - 1]

        if filtro["action"] == "genres":
            show_info("Caricamento generi...")
            genre_items = _au.genres(filtro["args"])
            if not genre_items:
                show_warning("Nessun genere trovato.")
                wait_enter()
                continue
            # Mostra generi come sotto-lista
            clear_screen()
            show_header("ANIMEUNITY", f"AnimeUnity > {cat_sel['label']} > Genere")
            for i, g in enumerate(genre_items, 1):
                print(f"  {i:>3}. {g['label']}")
            print()
            print("  0. Torna")
            print()
            raw3 = input(f"  Genere (1-{len(genre_items)}, 0=torna): ").strip()
            if raw3 == "0":
                continue
            if raw3.isdigit() and 1 <= int(raw3) <= len(genre_items):
                g_sel = genre_items[int(raw3) - 1]
                show_info(f"Caricamento: {g_sel['label']}...")
                anime_list, _ = _au.peliculas(g_sel["args"], page=0)
                _mostra_lista_anime(anime_list, f"{cat_sel['label']} > {g_sel['label']}")

        elif filtro["action"] == "years":
            show_info("Caricamento anni...")
            year_items = _au.years(filtro["args"])
            if not year_items:
                show_warning("Nessun anno trovato.")
                wait_enter()
                continue
            clear_screen()
            show_header("ANIMEUNITY", f"AnimeUnity > {cat_sel['label']} > Anno")
            for i, y in enumerate(year_items[:30], 1):
                print(f"  {i:>3}. {y['label']}")
            print()
            print("  0. Torna")
            print()
            raw3 = input(f"  Anno (1-{min(len(year_items),30)}, 0=torna): ").strip()
            if raw3 == "0":
                continue
            if raw3.isdigit() and 1 <= int(raw3) <= min(len(year_items), 30):
                y_sel = year_items[int(raw3) - 1]
                show_info(f"Caricamento anno {y_sel['label']}...")
                anime_list, _ = _au.peliculas(y_sel["args"], page=0)
                _mostra_lista_anime(anime_list, f"{cat_sel['label']} > {y_sel['label']}")

        else:
            # peliculas dirette
            show_info(f"Caricamento: {filtro['label']}...")
            anime_list, _ = _au.peliculas(filtro["args"], page=0)
            _mostra_lista_anime(anime_list, f"{cat_sel['label']} > {filtro['label']}")


# ════════════════════════════════════════════════════════════════════════════
# MENU PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════

def _menu_principale() -> None:
    while True:
        clear_screen()
        show_header("ANIMEUNITY", "Anime > Anime Video > AnimeUnity")
        print()
        _print_box(
            "1.  Ultimi episodi",
            "2.  Cerca per titolo",
            "3.  Sfoglia catalogo",
            "0.  Torna",
        )
        print()

        sc = get_valid_choice("Scelta (0-3): ", ["0", "1", "2", "3"])

        if sc == "0":
            return

        elif sc == "1":
            show_info("Caricamento ultimi episodi...")
            news_items, _ = _au.news()
            if not news_items:
                show_warning("Nessun episodio recente trovato.")
                wait_enter()
                continue

            _PAGE_N = 20
            page    = 0
            while True:
                start  = page * _PAGE_N
                end    = start + _PAGE_N
                subset = news_items[start:end]

                clear_screen()
                show_header("ANIMEUNITY", "AnimeUnity > Ultimi Episodi")
                print(f"  {len(news_items)} episodi recenti   "
                      f"Pagina: {page+1}/{((len(news_items)-1)//_PAGE_N)+1}")
                print()
                for i, ep in enumerate(subset, start + 1):
                    print(f"  {i:>4}. {ep.get('title') or 'N/D'}")
                print()
                nav = []
                if page > 0:
                    nav.append("p=Prec")
                if end < len(news_items):
                    nav.append("n=Succ")
                nav.append("0=Torna")
                print(f"  [{' | '.join(nav)}]")
                print()

                raw = input(
                    f"  Seleziona ({start+1}-{min(end,len(news_items))}, 0/n/p): "
                ).strip().lower()

                if raw == "0":
                    break
                if raw == "n" and end < len(news_items):
                    page += 1
                    continue
                if raw == "p" and page > 0:
                    page -= 1
                    continue
                if raw.isdigit():
                    idx = int(raw)
                    if 1 <= idx <= len(news_items):
                        ep = news_items[idx - 1]
                        show_info(f"Risoluzione: {ep.get('title')}...")
                        hls = _au.findvideos(ep.get("url") or "", ep.get("scws_id") or "")
                        _offri_download(hls, ep.get("title") or "episodio")
                        continue
                show_error("Input non valido.")

        elif sc == "2":
            print()
            query = input("  Titolo da cercare (0=annulla): ").strip()
            if not query or query == "0":
                continue
            show_info(f"Ricerca '{query}'...")
            results, _ = _au.search(query)
            _mostra_lista_anime(results, f"Ricerca: {query}")

        elif sc == "3":
            _menu_sfoglia()


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def run() -> None:
    """Entry point chiamato da handlers.py -> show_anime_video_submenu()."""
    if not _HAS_AU:
        clear_screen()
        show_header("ANIMEUNITY — ERRORE")
        show_error("animeunity.py non trovato o non importabile.")
        show_info("Verifica che animeunity.py sia in scripts/anime/")
        wait_enter()
        return

    if not _au.HAS_REQUESTS:
        clear_screen()
        show_header("ANIMEUNITY — DIPENDENZE MANCANTI")
        show_error("Librerie mancanti: requests, beautifulsoup4")
        show_info("Esegui: pip install requests beautifulsoup4")
        wait_enter()
        return

    _menu_principale()


if __name__ == "__main__":
    run()
