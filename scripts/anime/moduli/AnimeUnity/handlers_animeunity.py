#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers_animeunity.py  –  modulo AnimeUnity per Download Center (upgrade-3)
Generato automaticamente – pattern identico a handlers_animeworld.py
"""

from __future__ import annotations
import os, re, sys, json, time, logging
from typing import Optional, List, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Logger ────────────────────────────────────────────────────────────────────
try:
    from scripts.core.logger import get_logger, log_debug
except ImportError:
    try:
        from scripts.anime.core_anime import get_logger, log_debug
    except ImportError:
        def get_logger(name): import logging; return logging.getLogger(name)
        def log_debug(msg, *a, **kw): pass
_log = get_logger("AnimeUnity")

# ── Costanti ──────────────────────────────────────────────────────────────────
_DEFAULT_BASE = "https://www.animeunity.so"
_CFG_KEY      = "animeunity_base_url"
_CFG_FILE     = os.path.join(os.path.dirname(__file__), "animeunity_cfg.json")

MODULE_KEY  = "animeunity"
MODULE_NAME = "AnimeUnity"
_HEADERS      = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": _DEFAULT_BASE + "/",
    "Accept-Language": "it-IT,it;q=0.9",
}

_SESSION: Optional["requests.Session"] = None  # singleton

# ── Helpers config ────────────────────────────────────────────────────────────
def _load_cfg() -> Dict[str, Any]:
    try:
        with open(_CFG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cfg(cfg: Dict[str, Any]) -> None:
    with open(_CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _base_url() -> str:
    return _load_cfg().get(_CFG_KEY, _DEFAULT_BASE).rstrip("/")

# ── Session con retry ─────────────────────────────────────────────────────────
def _session() -> requests.Session:
    """Sessione requests singleton con retry automatico."""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504])
        _SESSION.mount("https://", HTTPAdapter(max_retries=retry))
        _SESSION.mount("http://",  HTTPAdapter(max_retries=retry))
        _SESSION.headers.update(_HEADERS)
    return _SESSION

def _scws_get_iframe_url(episode_url: str) -> Optional[str]:
    """Recupera l'URL dell'iframe video dall'episodio."""
    try:
        s = _session()
        r = s.get(episode_url, timeout=15)
        m = re.search(r'src=["\']([^"\']*scws[^"\']*)["\']', r.text)
        if m:
            return m.group(1)
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text)
        return m.group(1) if m else None
    except Exception as e:
        log_debug(f"[AnimeUnity] _scws_get_iframe_url error: {e}")
        return None

def _scws_resolve(iframe_url: str) -> Optional[str]:
    """Risolve l'iframe SCWS e restituisce l'URL HLS m3u8."""
    try:
        s = _session()
        r = s.get(iframe_url, timeout=15)
        m = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m:
            return m.group(1)
        m = re.search(r'file:\s*["\']([^"\']+)["\']', r.text)
        return m.group(1) if m else None
    except Exception as e:
        log_debug(f"[AnimeUnity] _scws_resolve error: {e}")
        return None

def _get_video_url(episode_url: str) -> Optional[str]:
    """Pipeline completa: episodio → iframe → HLS."""
    iframe = _scws_get_iframe_url(episode_url)
    if not iframe:
        return None
    if iframe.startswith("//"):
        iframe = "https:" + iframe
    return _scws_resolve(iframe)

# ── API AnimeUnity ────────────────────────────────────────────────────────────
def search(titolo: str) -> List[Dict[str, Any]]:
    """
    Cerca anime su AnimeUnity.
    Contratto SILENT: restituisce lista vuota in caso di errore.
    """
    log_debug("search chiamato")
    base = _base_url()
    try:
        s = _session()
        r = s.get(f"{base}/archivio", params={"title": titolo}, timeout=15)
        results: List[Dict[str, Any]] = []
        for m in re.finditer(
            r'<a[^>]+href=["\']([^"\']+/anime/\d+[^"\']*)["\'][^>]*>'
            r'[\s\S]*?<h3[^>]*>([^<]+)</h3>',
            r.text
        ):
            href, title = m.group(1).strip(), m.group(2).strip()
            if not href.startswith("http"):
                href = base + href
            results.append({"title": title, "url": href})
        log_debug(f"[AnimeUnity] search('{titolo}'): {len(results)} risultati")
        return results
    except Exception as e:
        log_debug(f"[AnimeUnity] search error: {e}")
        return []

def get_episodes(anime_url: str) -> List[str]:
    """
    Restituisce lista di URL HLS per gli episodi di un anime.
    Contratto SILENT: restituisce lista vuota in caso di errore.
    """
    log_debug("get_episodes chiamato")
    base = _base_url()
    try:
        s = _session()
        r = s.get(anime_url, timeout=15)
        ep_urls: List[str] = []
        for m in re.finditer(
            r'<a[^>]+href=["\']([^"\']+/episodio/\d+[^"\']*)["\']',
            r.text
        ):
            href = m.group(1).strip()
            if not href.startswith("http"):
                href = base + href
            ep_urls.append(href)
        hls_list: List[str] = []
        for ep in ep_urls:
            hls = _get_video_url(ep)
            if hls:
                hls_list.append(hls)
        log_debug(f"[AnimeUnity] get_episodes: {len(hls_list)}/{len(ep_urls)} HLS")
        return hls_list
    except Exception as e:
        log_debug(f"[AnimeUnity] get_episodes error: {e}")
        return []

# ── UI helpers ────────────────────────────────────────────────────────────────
def _stampa_lista(items: List[Dict], campo: str = "title") -> None:
    if not items:
        print("  (nessun risultato)")
        return
    for i, item in enumerate(items, 1):
        print(f"  {i:>3}. {item.get(campo, item)}")

def _scegli(items: List[Dict], campo: str = "title") -> Optional[Dict]:
    _stampa_lista(items, campo)
    try:
        n = int(input("\nScegli numero (0=annulla): ").strip())
        return items[n - 1] if 1 <= n <= len(items) else None
    except (ValueError, IndexError):
        return None

# ── Funzioni pubbliche ────────────────────────────────────────────────────────
def cambio_url(core=None) -> None:
    """Permette di modificare l'URL base di AnimeUnity."""
    global _SESSION
    log_debug("cambio_url chiamato")
    cfg = _load_cfg()
    attuale = cfg.get(_CFG_KEY, _DEFAULT_BASE)
    print(f"\n[AnimeUnity] URL base attuale: {attuale}")
    nuovo = input("Nuovo URL base (invio = mantieni attuale): ").strip()
    if nuovo:
        cfg[_CFG_KEY] = nuovo.rstrip("/")
        _save_cfg(cfg)
        _SESSION = None  # reset sessione al cambio URL
        print(f"  ✔ URL aggiornato: {cfg[_CFG_KEY]}")
    else:
        print("  ✔ URL invariato.")

def debug_modulo(core=None) -> None:
    """Pannello diagnostico interattivo per AnimeUnity."""
    log_debug("debug_modulo chiamato")
    print("\n" + "═" * 56)
    print("  DEBUG – AnimeUnity")
    print("═" * 56)

    # 1. Stato URL
    base = _base_url()
    print(f"  URL base     : {base}")

    # 2. Modalità debug logger
    lvl = _log.getEffectiveLevel()
    print(f"  Log level    : {logging.getLevelName(lvl)}")

    # 3. Dipendenze
    deps = ["requests"]
    for dep in deps:
        try:
            __import__(dep)
            print(f"  {dep:<14}: ✔ disponibile")
        except ImportError:
            print(f"  {dep:<14}: ✗ MANCANTE")

    # 4. Test connettività
    print(f"\n  Test GET {base} …")
    try:
        s = _session()
        t0 = time.time()
        r = s.get(base, timeout=10)
        ms = int((time.time() - t0) * 1000)
        print(f"  Status: {r.status_code}  ({ms} ms)")
    except Exception as e:
        print(f"  ERRORE connettività: {e}")

    # 5. Ultime righe log
    print("\n  (log in-memory non disponibile in questa sessione)")
    print("═" * 56)

    input("\nPremi INVIO per tornare al menu…")

def _ultime_uscite() -> None:
    """Mostra le ultime uscite da AnimeUnity."""
    base = _base_url()
    try:
        s = _session()
        r = s.get(base, timeout=15)
        items: List[Dict] = []
        for m in re.finditer(
            r'<a[^>]+href=["\']([^"\']+/anime/\d+[^"\']*)["\'][^>]*>'
            r'[\s\S]*?<h3[^>]*>([^<]+)</h3>',
            r.text
        ):
            href, title = m.group(1).strip(), m.group(2).strip()
            if not href.startswith("http"):
                href = base + href
            items.append({"title": title, "url": href})
        items = items[:20]
        if not items:
            print("  Nessuna uscita recente trovata.")
            return
        scelta = _scegli(items)
        if scelta:
            _naviga_anime(scelta["url"], scelta["title"])
    except Exception as e:
        print(f"  Errore ultime uscite: {e}")

def _ricerca_titolo() -> None:
    """Ricerca un titolo su AnimeUnity."""
    titolo = input("Titolo da cercare: ").strip()
    if not titolo:
        return
    print(f"  Ricerca '{titolo}'…")
    results = search(titolo)
    if not results:
        print("  Nessun risultato.")
        return
    scelta = _scegli(results)
    if scelta:
        _naviga_anime(scelta["url"], scelta["title"])

def _naviga_anime(anime_url: str, titolo: str) -> None:
    """Naviga gli episodi di un anime e avvia la riproduzione."""
    print(f"\n  Carico episodi di \'{titolo}\'…")
    hls_list = get_episodes(anime_url)
    if not hls_list:
        print("  Nessun episodio HLS trovato.")
        return
    print(f"\n  Episodi disponibili ({len(hls_list)}):")
    for i, url in enumerate(hls_list, 1):
        print(f"    {i:>3}. {url[:80]}")
    try:
        n = int(input("\nScegli episodio (0=annulla): ").strip())
        if 1 <= n <= len(hls_list):
            print(f"\n  ▶ {hls_list[n-1]}")
    except (ValueError, IndexError):
        pass

# ── Entry point ───────────────────────────────────────────────────────────────
def run(core=None) -> None:
    """Menu principale AnimeUnity."""
    while True:
        print("\n" + "─" * 50)
        print("  AnimeUnity")
        print("─" * 50)
        print("  1. Ultime uscite")
        print("  2. Ricerca titolo")
        print("  3. Debug modulo")
        print("  4. Cambio URL")
        print("  0. Torna indietro")
        scelta = input("\nScelta: ").strip()
        if   scelta == "1": _ultime_uscite()
        elif scelta == "2": _ricerca_titolo()
        elif scelta == "3": debug_modulo(core)
        elif scelta == "4": cambio_url(core)
        elif scelta == "0": break
        else: print("  Scelta non valida.")
