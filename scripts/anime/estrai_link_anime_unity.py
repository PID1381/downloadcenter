#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estrai_link_anime_unity.py v2.0 - AnimeUnity Link Extractor
Download Center - scripts/anime/estrai_link_anime_unity.py

NOVITA v2.0:
  [REFACTOR] Ricerca migrata in anime_engine.search_animeunity()
             (stessa logica di search_animeworld per AnimeWorld)
  [IMPROVE]  _ricerca_e_seleziona_au() mostra anno/tipo/episodi
  [IMPROVE]  Livesearch: digita nel campo input.search-bar + legge .results
  [MANTIENE] Logica dominio AU:
               _extract_au_link     (intercettazione network m3u8/mp4)
               _get_episode_list_au (lista episodi via Playwright)
               _extract_links_sequential_au (loop sequenziale)
               estrai_singolo_au    (orchestratore principale)

Struttura AnimeUnity (animeunity.so):
  - Sito SPA (Vue.js) — contenuto caricato via JavaScript
  - Ricerca: livesearch reattiva su campo input.search-bar
  - Pagina serie : /anime/{id}-{slug}
  - Pagina episodio : /anime/{id}-{slug}/{ep_number}
  - Video: CDN Vixcloud (m3u8/mp4) intercettato via Playwright network

Metodo estrazione: Playwright + intercettazione network (m3u8/mp4)
Ctrl+C           : interrompe e salva i link gia trovati
"""
from __future__ import annotations

import re
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    from anime_engine import (
        clear_screen, show_header, show_success, show_error, show_info,
        show_warning, ask_yes_no, wait_enter, get_valid_choice,
        save_links, sort_links_numerically,
        print_progress_eta, is_video, PageSession,
        setup_interrupt, teardown_interrupt, interrupted,
        parse_episode_selection,
        search_animeunity,
        HAS_PLAYWRIGHT,
    )
except ImportError as e:
    print(f"ERRORE: anime_engine non trovato: {e}")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# COSTANTI DOMINIO ANIMEUNITY
# ════════════════════════════════════════════════════════════════════════════

_BASE_URL_AU = "https://www.animeunity.so"
_TIMEOUT     = 15

_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":  "application/json, text/html, */*",
    "Referer": _BASE_URL_AU,
}

# Estensioni video da intercettare nella rete Playwright
_VIDEO_EXTS_AU = (".mp4", ".mkv", ".m3u8", ".ts")

# Pattern URL video AnimeUnity (CDN Vixcloud / Vixo)
_AU_CDN_PATTERNS = [
    "vixcloud", "vixo", "animeunity", "cdn", "storage",
    ".m3u8", ".mp4",
]


# ════════════════════════════════════════════════════════════════════════════
# HELPER DOMINIO
# ════════════════════════════════════════════════════════════════════════════

def _abs_url_au(url: str) -> str:
    """Rende assoluto un URL relativo rispetto alla base AnimeUnity."""
    return url if url.startswith("http") else _BASE_URL_AU.rstrip("/") + "/" + url.lstrip("/")


def _is_au_video_link(url: str) -> bool:
    """True se l'URL e un link video AnimeUnity (CDN o estensione video)."""
    if not url:
        return False
    url_lower = url.lower()
    return any(p in url_lower for p in _AU_CDN_PATTERNS)


# ════════════════════════════════════════════════════════════════════════════
# ESTRAZIONE LISTA EPISODI — AnimeUnity
# ════════════════════════════════════════════════════════════════════════════

def _get_episode_list_au(serie_url: str) -> Tuple[str, List[str]]:
    """
    Recupera lista episodi dalla pagina serie AnimeUnity via Playwright.

    AnimeUnity e una SPA Vue.js: il DOM viene renderizzato lato client.
    Gli episodi sono in elementi <a> con href /anime/{id}-{slug}/{ep}.

    Returns:
        (titolo, [ep_url, ...])
    """
    titolo   = ""
    ep_links = []

    if not HAS_PLAYWRIGHT:
        show_warning("Playwright richiesto per AnimeUnity (SPA).")
        return titolo, ep_links

    try:
        with PageSession() as sess:
            sess._page.goto(serie_url, wait_until="networkidle")
            sess.dismiss_cookies()
            sess._page.wait_for_timeout(2000)

            # Attendi caricamento lista episodi
            for sel in [
                ".episodes-wrapper",
                ".episode-list",
                "a[href*='/anime/']",
                ".episodes",
            ]:
                try:
                    sess._page.wait_for_selector(sel, timeout=6000)
                    break
                except Exception:
                    continue

            sess._page.wait_for_timeout(1000)

            # Estrai titolo
            try:
                raw_title = sess._page.title()
                for sep in (" - AnimeUnity", " | AnimeUnity", " | Guarda"):
                    if sep in raw_title:
                        raw_title = raw_title[: raw_title.index(sep)]
                titolo = raw_title.strip()
            except Exception:
                pass

            # Estrai link episodi via JS
            # Pattern: /anime/{id}-{slug}/{numero_episodio}
            ep_links = sess._page.evaluate("""() => {
                const links = new Set();
                document.querySelectorAll('a[href]').forEach(a => {
                    const h = a.href || '';
                    if (h && /\/anime\/.+-\d+\/\d+/.test(h)) {
                        links.add(h);
                    }
                });
                return Array.from(links);
            }""")

            ep_links = sort_links_numerically(ep_links)

    except Exception as ex:
        show_error(f"Errore get_episode_list_au: {ex}")

    return titolo, ep_links


# ════════════════════════════════════════════════════════════════════════════
# ESTRAZIONE LINK VIDEO — AnimeUnity (Playwright + intercettazione network)
# ════════════════════════════════════════════════════════════════════════════

def _extract_au_link(episode_url: str) -> str:
    """
    Estrae il link video diretto da una pagina episodio AnimeUnity.

    Metodo: Playwright con intercettazione richieste di rete.
    AnimeUnity carica il video tramite player embed (Vixcloud CDN).
    Il link m3u8/mp4 viene catturato intercettando le richieste network.

    Returns:
        URL video (m3u8 o mp4) o stringa vuota se non trovato.
    """
    if not HAS_PLAYWRIGHT:
        return ""

    found_url = ""

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = browser.new_context(
                user_agent=_HDR["User-Agent"],
                locale="it-IT",
            )
            page = ctx.new_page()
            page.set_default_timeout(20000)

            captured = []

            def _on_request(request):
                url = request.url
                url_lower = url.lower()
                if any(ext in url_lower for ext in _VIDEO_EXTS_AU):
                    if _is_au_video_link(url):
                        captured.append(url)

            page.on("request", _on_request)

            try:
                page.goto(episode_url, wait_until="networkidle")
                page.wait_for_timeout(4000)

                # Prova a cliccare play se presente
                for play_sel in [
                    "button.play",
                    ".vjs-big-play-button",
                    ".play-button",
                    "video",
                    ".player-container",
                ]:
                    try:
                        el = page.query_selector(play_sel)
                        if el:
                            el.click()
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass

                page.wait_for_timeout(3000)

                # Fallback: cerca src nel DOM
                if not captured:
                    dom_src = page.evaluate("""() => {
                        const v = document.querySelector('video');
                        if (v && v.src) return v.src;
                        const s = document.querySelector('source[src]');
                        if (s) return s.src;
                        const vp = document.querySelector('video-player');
                        if (vp) {
                            return vp.getAttribute('src') ||
                                   vp.getAttribute(':src') ||
                                   vp.getAttribute('data-src') || '';
                        }
                        return '';
                    }""")
                    if dom_src and _is_au_video_link(dom_src):
                        captured.append(dom_src)

            except Exception:
                pass
            finally:
                browser.close()

            # Preferisci m3u8, poi mp4
            m3u8_links = [u for u in captured if ".m3u8" in u.lower()]
            mp4_links  = [u for u in captured if ".mp4"  in u.lower()]
            found_url  = (m3u8_links or mp4_links or captured or [""])[0]

    except Exception:
        pass

    return found_url


def _extract_links_sequential_au(
    ep_urls: List[str],
) -> Tuple[Dict[str, str], int, int, bool]:
    """
    Estrae link da tutti gli URL episodio in SEQUENZA.

    AnimeUnity richiede Playwright per ogni episodio (SPA + CDN):
    la parallelizzazione pesante causa blocchi lato server,
    quindi si usa estrazione sequenziale.

    Returns:
        (results_dict, ep_ok, ep_fail, was_interrupted)
    """
    total   = len(ep_urls)
    results: Dict[str, str] = {}
    ep_ok   = 0
    ep_fail = 0
    t0      = time.time()

    setup_interrupt()
    try:
        for i, url in enumerate(ep_urls, 1):
            if interrupted.is_set():
                break
            link = _extract_au_link(url)
            if link:
                results[url] = link
                ep_ok += 1
            else:
                ep_fail += 1
            fail_s = f" fail:{ep_fail}" if ep_fail > 0 else ""
            prefix = f"Estrazione  ok:{ep_ok}{fail_s}"
            print_progress_eta(i, total, prefix=prefix, start_time=t0)
    except KeyboardInterrupt:
        interrupted.set()
    finally:
        teardown_interrupt()

    print("")
    return results, ep_ok, ep_fail, interrupted.is_set()


# ════════════════════════════════════════════════════════════════════════════
# UI — RICERCA E SELEZIONE
# ════════════════════════════════════════════════════════════════════════════

def _ricerca_e_seleziona_au() -> Optional[dict]:
    """
    Ricerca interattiva su AnimeUnity e selezione risultato.
    Chiama search_animeunity() dall'engine (livesearch Vue.js).
    Mostra: titolo, anno, tipo, episodi.
    """
    query = input("  Titolo da cercare (0=annulla): ").strip()
    if not query or query == "0":
        return None

    show_info(f"Ricerca '{query}' su AnimeUnity...")
    results = search_animeunity(query)

    if not results:
        show_warning("Nessun risultato trovato.")
        wait_enter()
        return None

    print()
    for i, r in enumerate(results[:15], 1):
        # Mostra info aggiuntive se disponibili
        year = r.get("year", "")
        typ  = r.get("type", "")
        eps  = r.get("episodes", "")
        meta = "  ".join(filter(None, [year, typ, eps]))
        if meta:
            print(f"  {i:>2}. {r['title']}  [{meta}]")
        else:
            print(f"  {i:>2}. {r['title']}")
    print()
    print("  0. Annulla")
    print()

    sel = input("  Seleziona: ").strip()
    if not sel.isdigit() or sel == "0" or not (1 <= int(sel) <= min(15, len(results))):
        return None
    return results[int(sel) - 1]


def _ask_episode_selection_au(ep_links: List[str]) -> Optional[List[int]]:
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
            m   = re.search(r"/(\d+)$", ep_url)
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

    return list(range(total))


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def estrai_singolo_au(prefs=None) -> None:
    """
    Orchestratore principale dell'estrazione link AnimeUnity.
    Chiamato da: handlers.py -> AnimeHandlers.show_anime_video_submenu()
    """
    clear_screen()
    show_header("ESTRAI LINK ANIME UNITY v2.0", "Anime > Anime Video > AnimeUnity")
    show_info(
        f"Metodo: Playwright + intercettazione network  |  "
        f"Sito: {_BASE_URL_AU}"
    )
    print()

    if not HAS_PLAYWRIGHT:
        show_error("Playwright e obbligatorio per AnimeUnity (SPA).")
        show_info("Esegui: pip install playwright && playwright install chromium")
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
        r = _ricerca_e_seleziona_au()
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
            url = _BASE_URL_AU + ("" if url.startswith("/") else "/") + url

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

    links:           List[str] = []
    titolo_trovato:  str       = titolo
    t_total:         float     = time.time()
    was_interrupted: bool      = False

    # ── 3. Estrazione ─────────────────────────────────────────────────────────

    if modo == "1":
        print()
        show_info(f"Estrazione da: {url}")
        show_info("Avvio browser (Playwright)...")
        link = _extract_au_link(url)
        if link:
            links = [link]
            show_success(f"Link trovato: ...{link[-65:]}")
        else:
            show_warning("Nessun link trovato per questo episodio.")

    else:
        print()
        show_info(f"Raccolta lista episodi da: {url}")
        show_info("Avvio browser (Playwright)...")

        title_r, ep_links = _get_episode_list_au(url)
        if title_r and not titolo_trovato:
            titolo_trovato = title_r

        if not ep_links:
            show_warning("Impossibile ottenere la lista episodi.")
            show_info("Prova con URL diretto (modalita Episodio singolo).")
            wait_enter()
            return

        show_success(f"Trovati {len(ep_links)} episodi.")

        if modo == "2":
            indices = _ask_episode_selection_au(ep_links)
            if indices is None:
                return
            selected = [ep_links[i] for i in indices]
        else:
            selected = ep_links

        total_ep = len(selected)
        print()
        show_info(
            f"Estrazione {total_ep} episodi  "
            f"[sequenziale | Playwright + network intercept]"
        )
        show_info("Ctrl+C per interrompere e salvare i link gia trovati")
        show_warning(f"Stima: ~{total_ep * 8}s - {total_ep * 12}s totali")
        print()

        results, ep_ok, ep_fail, was_interrupted = _extract_links_sequential_au(selected)

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
            m_ = int(elapsed // 60)
            s_ = int(elapsed % 60)
            show_success(f"Completato: {ep_ok} link in {m_:02d}:{s_:02d}")
        if ep_fail > 0:
            show_warning(f"{ep_fail} episodi senza link trovato")

    # ── 4. Risultati ──────────────────────────────────────────────────────────
    elapsed_tot = time.time() - t_total
    clear_screen()
    show_header("RISULTATO ESTRAZIONE ANIMEUNITY v2.0")
    print(f"  Anime:        {titolo_trovato or 'N/D'}")
    print(f"  Link trovati: {len(links)}")
    print(f"  Tempo totale: {round(elapsed_tot, 1)}s")
    if was_interrupted:
        show_warning("Estrazione interrotta — risultati parziali.")
    print()

    if not links:
        show_warning("Nessun link trovato.")
        show_info("AnimeUnity usa CDN Vixcloud — verifica che Playwright sia aggiornato.")
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
    estrai_singolo_au()
