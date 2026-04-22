#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estrai_link_anime.py v4.0 - FAST EXTRACTION (REFACTORED)
Download Center - scripts/anime/estrai_link_anime.py

NOVITA v4.0 (refactoring da v4.3):
  [REFACTOR] Codice comune migrato in anime_engine.py v2.0:
               PageSession, is_video, parse_episode_selection, save_links,
               setup_interrupt, teardown_interrupt, interrupted,
               extract_episode_links, VIDEO_EXT, COOKIE_SEL, COOKIE_TEXTS
  [REFACTOR] _print_progress sostituito da print_progress_eta (engine §5)
  [MANTIENE] Logica dominio AnimeWorld:
               _extract_aw_link     (alternativeDownloadLink)
               _extract_links_parallel (ThreadPoolExecutor, 8 workers)
               _get_episode_list_requests (fast path lista episodi)
               _ricerca_e_seleziona (UI ricerca)
               _ask_episode_selection (UI selezione range/lista)
               estrai_singolo       (orchestratore principale)

Metodo estrazione : <a id='alternativeDownloadLink'> via requests+BS4
Estrazione        : PARALLELA, 8 episodi simultanei (ThreadPoolExecutor)
Ctrl+C            : interrompe e salva i link gia trovati
"""
from __future__ import annotations

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment]
    HAS_BS4 = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    _requests    = None  # type: ignore[assignment]
    HAS_REQUESTS = False

try:
    from anime_engine import (
        clear_screen, show_header, show_success, show_error, show_info,
        show_warning, ask_yes_no, wait_enter, get_valid_choice,
        save_links, search_animeworld, sort_links_numerically,
        print_progress_eta, is_video, PageSession,
        setup_interrupt, teardown_interrupt, interrupted,
        parse_episode_selection, extract_episode_links,
        BASE_URL, HAS_PLAYWRIGHT,
    )
except ImportError as e:
    print(f"ERRORE: anime_engine non trovato: {e}")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# COSTANTI DOMINIO
# ════════════════════════════════════════════════════════════════════════════

_WORKERS         = 8     # episodi estratti in parallelo
_TIMEOUT         = 12    # timeout HTTP in secondi
_AW_CDN_DOMAINS  = ["sweetpixel.org"]
_AW_DDL_PATHS    = ["/DDL/ANIME/", "/DDL/"]

_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ════════════════════════════════════════════════════════════════════════════
# HELPER DOMINIO
# ════════════════════════════════════════════════════════════════════════════

def _is_aw_server_link(url: str) -> bool:
    """True se l'URL punta al CDN AnimeWorld (sweetpixel / DDL path)."""
    if not url or not is_video(url):
        return False
    return (
        any(d in url for d in _AW_CDN_DOMAINS)
        or any(p in url for p in _AW_DDL_PATHS)
    )


def _abs_url(url: str, base: str = BASE_URL) -> str:
    """Rende assoluto un URL relativo rispetto a base."""
    return url if url.startswith("http") else base.rstrip("/") + "/" + url.lstrip("/")


def _extract_title(soup) -> str:
    """Estrae titolo pagina da BeautifulSoup (helper locale privato)."""
    for tag, attrs in [("h1", {"class": "title"}), ("h1", {"id": "anime-title"})]:
        el = soup.find(tag, attrs)
        if el:
            return el.get_text(strip=True)
    el = soup.find(id="anime-title")
    if el:
        return el.get_text(strip=True)
    t = soup.find("title")
    if t:
        text = t.get_text(strip=True)
        for sep in (" - AnimeWorld", " | AnimeWorld"):
            if sep in text:
                text = text[: text.index(sep)]
        return text.strip()
    return ""


# ════════════════════════════════════════════════════════════════════════════
# CORE ESTRAZIONE — requests+BS4, NESSUN browser
# ════════════════════════════════════════════════════════════════════════════

def _extract_aw_link(episode_url: str) -> str:
    """
    Estrae il link diretto AnimeWorld da una pagina episodio.

    Metodo primario : <a id="alternativeDownloadLink" href="...mp4">
    Fallback         : qualsiasi <a href> CDN AW (sweetpixel / DDL)
    Puro requests+BS4 — nessun browser necessario.
    """
    try:
        r = _requests.get(episode_url, headers=_HDR, timeout=_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        # Primario: id="alternativeDownloadLink"
        a = soup.find("a", id="alternativeDownloadLink")
        if a:
            href = a.get("href", "").strip()
            if href:
                return href

        # Fallback: link CDN AW
        for tag in soup.find_all("a", href=True):
            h = tag["href"].strip()
            if _is_aw_server_link(h):
                return h

    except Exception:
        pass
    return ""


def _extract_links_parallel(
    ep_urls: List[str],
    workers: int = _WORKERS,
) -> Tuple[Dict[str, str], int, int, bool]:
    """
    Estrae link da tutti gli URL episodio in PARALLELO (ThreadPoolExecutor).
    Il progresso viene mostrato con print_progress_eta dall'engine.

    Returns:
        (results_dict, ep_ok, ep_fail, was_interrupted)
          results_dict : {ep_url: video_link}
          ep_ok        : episodi con link trovato
          ep_fail      : episodi senza link
          was_interrupted: True se Ctrl+C premuto
    """
    total    = len(ep_urls)
    results: Dict[str, str] = {}
    ep_ok    = 0
    ep_fail  = 0
    done     = 0
    t0       = time.time()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_extract_aw_link, url): url for url in ep_urls}
        try:
            for fut in as_completed(futures):
                if interrupted.is_set():
                    for f in futures:
                        f.cancel()
                    break
                url = futures[fut]
                try:
                    link = fut.result()
                    if link:
                        results[url] = link
                        ep_ok += 1
                    else:
                        ep_fail += 1
                except Exception:
                    ep_fail += 1
                done += 1
                fail_s  = f" fail:{ep_fail}" if ep_fail > 0 else ""
                prefix  = f"Download  ok:{ep_ok}{fail_s}"
                print_progress_eta(done, total, prefix=prefix, start_time=t0)
        except KeyboardInterrupt:
            interrupted.set()

    print("")   # vai a capo dopo la progress bar
    return results, ep_ok, ep_fail, interrupted.is_set()


def _get_episode_list_requests(url: str) -> Tuple[str, List[str]]:
    """Fast path: lista episodi via requests+BS4 (nessun browser)."""
    try:
        r    = _requests.get(url, headers=_HDR, timeout=_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        return _extract_title(soup), extract_episode_links(soup, url)
    except Exception:
        return "", []


# ════════════════════════════════════════════════════════════════════════════
# UI — RICERCA E SELEZIONE
# ════════════════════════════════════════════════════════════════════════════

def _ricerca_e_seleziona() -> Optional[dict]:
    """Ricerca interattiva su AnimeWorld e selezione risultato."""
    query = input("  Titolo da cercare (0=annulla): ").strip()
    if not query or query == "0":
        return None

    results = search_animeworld(query)
    if not results:
        show_warning("Nessun risultato trovato.")
        wait_enter()
        return None

    print()
    for i, r in enumerate(results[:15], 1):
        print(f"  {i:>2}. {r['title']}")
    print()
    print("  0. Annulla")
    print()

    sel = input("  Seleziona: ").strip()
    if not sel.isdigit() or sel == "0" or not (1 <= int(sel) <= min(15, len(results))):
        return None
    return results[int(sel) - 1]


def _ask_episode_selection(ep_links: List[str]) -> Optional[List[int]]:
    """Menu selezione episodi. Ritorna lista indici 0-based o None se annullato."""
    total     = len(ep_links)
    all_label = f"Tutti gli {total} episodi"

    print()
    print(f"  Episodi disponibili: {total}")
    print()
    print("  +--------------------------------------+")
    print("  |  1.  Singolo episodio                |")
    print("  |  2.  Range / lista                   |")
    print("  |       1-12    3,7,15    1-6,10-12    |")
    print(f"  |  3.  {all_label:<32}|")
    print("  |  0.  Annulla                         |")
    print("  +--------------------------------------+")
    print()
    sc = get_valid_choice("Scegli (0-3): ", ["0", "1", "2", "3"])

    if sc == "0":
        return None

    if sc == "1":
        print()
        show_info(f"Episodi (1-{total}):")
        for i, ep_url in enumerate(ep_links[:10], 1):
            m   = re.search(r"(\d+)(?:[/?#]|$)", ep_url)
            lbl = f"Ep.{m.group(1)}" if m else f"#{i}"
            print(f"    {i:>3}. {lbl:<8}  ...{ep_url[-50:]}")
        if total > 10:
            show_info(f"... e altri {total - 10} episodi")
        print()
        raw = input(f"  Numero episodio (1-{total}): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= total:
            return [int(raw) - 1]
        show_error("Numero non valido.")
        return None

    if sc == "2":
        print()
        show_info("Formato: 1-12  |  3,7,15  |  1-6,10-12")
        raw  = input(f"  Selezione (1-{total}): ").strip()
        idxs = parse_episode_selection(raw, total)
        if not idxs:
            show_error("Nessun episodio valido selezionato.")
            return None
        show_success(f"Selezionati {len(idxs)} episodi.")
        return idxs

    return list(range(total))   # sc == "3": tutti


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def estrai_singolo(prefs=None) -> None:
    """
    Orchestratore principale dell'estrazione link anime.
    Chiamato da: handlers.py -> AnimeHandlers._handle_estrai_link()
    """
    clear_screen()
    show_header("ESTRAI LINK ANIME v4.0", "Anime > Ricerca Anime Video")
    show_info(
        f"Metodo: #alternativeDownloadLink  |  "
        f"requests+BS4 parallelo ({_WORKERS} workers)"
    )
    print()

    if not HAS_REQUESTS or not HAS_BS4:
        show_error("Librerie mancanti: requests, beautifulsoup4")
        show_info("Esegui: pip install requests beautifulsoup4")
        wait_enter()
        return

    # ── 1. Sorgente ──────────────────────────────────────────────────────────
    print("  +--------------------------------------+")
    print("  |  1.  Cerca per titolo                |")
    print("  |  2.  Inserisci URL diretto           |")
    print("  |  0.  Torna                           |")
    print("  +--------------------------------------+")
    print()
    sc = get_valid_choice("Scelta: ", ["0", "1", "2"])
    if sc == "0":
        return

    titolo = ""
    url    = ""

    if sc == "1":
        r = _ricerca_e_seleziona()
        if not r:
            return
        url    = r.get("link", "")
        titolo = r.get("raw_title", r.get("title", ""))
        if not url:
            show_error("Link non disponibile.")
            wait_enter()
            return
    else:
        url = input("  URL pagina anime/episodio (0=annulla): ").strip()
        if not url or url == "0":
            return
        if not url.startswith("http"):
            url = BASE_URL + ("" if url.startswith("/") else "/") + url

    # ── 2. Modalita ───────────────────────────────────────────────────────────
    print()
    print("  +--------------------------------------+")
    print("  |  1.  Episodio singolo                |")
    print("  |  2.  Seleziona episodi (range/lista) |")
    print("  |  3.  Tutti gli episodi               |")
    print("  |  0.  Annulla                         |")
    print("  +--------------------------------------+")
    print()
    modo = get_valid_choice("Modalita (0-3): ", ["0", "1", "2", "3"])
    if modo == "0":
        return

    links:          List[str] = []
    titolo_trovato: str       = titolo
    t_total:        float     = time.time()
    was_interrupted: bool     = False

    # ── 3. Estrazione ─────────────────────────────────────────────────────────

    if modo == "1":
        # Episodio singolo: estrazione diretta
        print()
        show_info(f"Estrazione da: {url}")
        link = _extract_aw_link(url)
        if link:
            links = [link]
            show_success(f"Link trovato: ...{link[-65:]}")
        else:
            show_warning("Nessun link trovato per questo episodio.")
        if not titolo_trovato:
            try:
                r2             = _requests.get(url, headers=_HDR, timeout=_TIMEOUT)
                soup           = BeautifulSoup(r2.content, "html.parser")
                titolo_trovato = _extract_title(soup)
            except Exception:
                pass

    else:
        # Multi-episodio: lista episodi + estrazione parallela
        print()
        show_info(f"Raccolta lista episodi da: {url}")

        title_r, ep_links = _get_episode_list_requests(url)
        if title_r and not titolo_trovato:
            titolo_trovato = title_r

        # Fallback: Playwright solo per recuperare la lista episodi
        if not ep_links and HAS_PLAYWRIGHT:
            show_info("Fast path vuoto — avvio browser per lista episodi...")
            try:
                with PageSession() as sess:
                    title_p, ep_links = sess.fetch_all_episodes(url)
                    if title_p and not titolo_trovato:
                        titolo_trovato = title_p
            except Exception as ex:
                show_error(f"Errore browser: {ex}")

        if not ep_links:
            show_warning("Impossibile ottenere la lista episodi.")
            show_info("Prova con URL diretto (modalita Episodio singolo).")
            wait_enter()
            return

        show_success(f"Trovati {len(ep_links)} episodi.")

        # Selezione episodi
        if modo == "2":
            indices = _ask_episode_selection(ep_links)
            if indices is None:
                return
            selected = [ep_links[i] for i in indices]
        else:
            selected = ep_links  # modo == "3": tutti

        total_ep = len(selected)
        print()
        show_info(
            f"Estrazione {total_ep} episodi  "
            f"[{_WORKERS} paralleli | metodo: #alternativeDownloadLink]"
        )
        show_info("Ctrl+C per interrompere e salvare i link gia trovati")
        print()

        setup_interrupt()
        results, ep_ok, ep_fail, was_interrupted = _extract_links_parallel(selected)
        teardown_interrupt()

        # Ricostruisce lista nell'ordine originale degli episodi
        ep_order = {u: i for i, u in enumerate(selected)}
        links = [
            results[u]
            for u in sorted(results, key=lambda u: ep_order.get(u, 9999))
            if results[u]
        ]
        links = sort_links_numerically(links)

        elapsed = time.time() - t_total
        if was_interrupted:
            show_warning(f"Interrotto — trovati {ep_ok}/{total_ep} link")
        else:
            m_  = int(elapsed // 60)
            s_  = int(elapsed % 60)
            spd = (ep_ok / elapsed * 60) if elapsed > 0 else 0
            show_success(
                f"Completato: {ep_ok} link in {m_:02d}:{s_:02d}"
                f"  ({spd:.1f} ep/min)"
            )
        if ep_fail > 0:
            show_warning(
                f"{ep_fail} episodi senza link "
                "(nessun #alternativeDownloadLink trovato)"
            )

    # ── 4. Risultati ──────────────────────────────────────────────────────────
    elapsed_tot = time.time() - t_total
    clear_screen()
    show_header("RISULTATO ESTRAZIONE v4.0")
    print(f"  Anime:        {titolo_trovato or 'N/D'}")
    print(f"  Link trovati: {len(links)}")
    print(f"  Tempo totale: {round(elapsed_tot, 1)}s")
    if was_interrupted:
        show_warning("Estrazione interrotta — risultati parziali.")
    print()

    if not links:
        show_warning("Nessun link trovato.")
        show_info("Controlla che la pagina contenga #alternativeDownloadLink.")
        wait_enter()
        return

    print("  Anteprima link:")
    for i, ln in enumerate(links[:5], 1):
        print(f"  {i}. ...{ln[-68:]}")
    if len(links) > 5:
        show_info(f"...e altri {len(links) - 5} link")
    print()

    if ask_yes_no("Salvare i link in file .txt?"):
        fp = save_links(links, titolo_trovato)
        if fp and str(fp):
            show_success(f"Salvati {len(links)} link in: {fp.name}")
            show_info(f"Percorso: {fp}")
        else:
            show_error("Errore durante il salvataggio.")

    wait_enter()


if __name__ == "__main__":
    estrai_singolo()
