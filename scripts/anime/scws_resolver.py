#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scws_resolver.py  v1.0
Download Center - scripts/anime/scws_resolver.py

Resolver standalone per server StreamingCommunityWS (scws.work).
Porting da Stream4me/addon/servers/streamingcommunityws.py senza xbmc/Kodi.

LOGICA REALE (da streamingcommunityws.py S4me):

  test_video_exists(page_url):
    1. GET page_url
    2. Estrae iframe src o embed_url
    3. GET iframe_url
    4. Estrae window.masterPlaylist = {...}, url: '...', canPlayFHD = true/false

  get_video_url(page_url):
    params, url, canPlayFHD = iframeParams
    split_url  = urllib.parse.urlsplit(url)
    url_params = urllib.parse.parse_qsl(split_url.query)
    masterPlaylistParams = ast.literal_eval(params)
    if canPlayFHD == 'true': masterPlaylistParams['h'] = 1
    masterPlaylistParams.update(url_params)
    url = '{}://{}{}?{}'.format(scheme, netloc, path, urlencode(masterPlaylistParams))
    return [['hls [FullHD|HD]', url]]

INTEGRAZIONE:
  - Importato da animeunity.py -> findvideos()
  - Accetta sessione requests opzionale (riusa cookie AnimeUnity)
  - Standalone: funziona anche senza sessione (apre sessione propria)
"""
from __future__ import annotations

import ast
import re
import urllib.parse
from typing import Optional, Tuple

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    _requests    = None  # type: ignore[assignment]
    HAS_REQUESTS = False

_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ════════════════════════════════════════════════════════════════════════════
# HELPERS (implementazione patron S4me)
# ════════════════════════════════════════════════════════════════════════════

def _get_iframe_url(html: str) -> str:
    """
    Estrae URL iframe da HTML pagina episodio.
    patron S4me: ['<iframe [^>]+src="([^"]+)', 'embed_url="([^"]+)']
    """
    m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
    if m:
        return m.group(1).replace("&amp;", "&")
    m = re.search(r'embed_url="([^"]+)"', html)
    if m:
        return m.group(1).replace("&amp;", "&")
    return ""


def _parse_master_playlist(iframe_html: str) -> Tuple[str, str, bool]:
    """
    Estrae parametri window.masterPlaylist dalla pagina iframe.
    patron S4me:
      r'window\\.masterPlaylist\\s+=\\s+{[^{]+({[^}]+}),\\s+url:\\s+\'([^\']+).*?canPlayFHD\\s=\\s(true|false)'

    Returns:
        (params_raw_str, hls_url, can_play_fhd)
    """
    m = re.search(
        r"window\.masterPlaylist\s*=\s*\{[^{]*({[^}]+}),\s*url:\s*'([^']+)'.*?canPlayFHD\s*=\s*(true|false)",
        iframe_html,
        re.DOTALL,
    )
    if not m:
        return "", "", False
    params_raw, hls_url, fhd_str = m.groups()
    return params_raw, hls_url, (fhd_str == "true")


def _build_hls_url(params_raw: str, hls_url: str, can_fhd: bool) -> str:
    """
    Ricostruisce URL HLS finale.
    Corrisponde a get_video_url() in streamingcommunityws.py S4me:
      masterPlaylistParams = ast.literal_eval(params)
      if canPlayFHD == 'true': masterPlaylistParams['h'] = 1
      masterPlaylistParams.update(url_params)
      url = '{}://{}{}?{}'.format(scheme, netloc, path, urlencode(masterPlaylistParams))
    """
    try:
        master_params = ast.literal_eval(params_raw)
    except Exception:
        master_params = {}

    if can_fhd:
        master_params["h"] = 1

    split_url  = urllib.parse.urlsplit(hls_url)
    url_params = dict(urllib.parse.parse_qsl(split_url.query))
    master_params.update(url_params)

    return "{}://{}{}?{}".format(
        split_url.scheme,
        split_url.netloc,
        split_url.path,
        urllib.parse.urlencode(master_params),
    )


# ════════════════════════════════════════════════════════════════════════════
# API PUBBLICA
# ════════════════════════════════════════════════════════════════════════════

def resolve(
    episode_url: str,
    session:     Optional[object] = None,
    timeout:     int = 15,
) -> Optional[str]:
    """
    Risolve URL episodio AnimeUnity -> URL HLS m3u8.

    Args:
        episode_url: URL pagina episodio AnimeUnity
                     (es. https://www.animeunity.to/anime/123-slug/456)
        session:     requests.Session opzionale (riusa cookie AnimeUnity)
        timeout:     Timeout HTTP in secondi

    Returns:
        URL HLS (stringa) o None se fallito.
    """
    if not HAS_REQUESTS:
        print("  [X] requests non installato — pip install requests")
        return None

    # Usa sessione fornita o crea una propria
    if session is not None:
        def _get(url):
            return session.get(url, timeout=timeout)
    else:
        _s = _requests.Session()
        _s.headers.update(_HDR)
        def _get(url):
            return _s.get(url, timeout=timeout)

    try:
        # Step 1: GET pagina episodio
        resp = _get(episode_url)
        if not resp or resp.status_code >= 400:
            return None
        html = resp.text

        # Step 2: Estrai iframe URL
        iframe_url = _get_iframe_url(html)
        if not iframe_url:
            print(f"  [!] Nessun iframe trovato in: {episode_url}")
            return None

        # Step 3: GET iframe
        resp2 = _get(iframe_url)
        if not resp2 or resp2.status_code >= 400:
            return None
        iframe_html = resp2.text

        # Step 4: Estrai window.masterPlaylist
        params_raw, hls_url, can_fhd = _parse_master_playlist(iframe_html)
        if not hls_url:
            print("  [!] window.masterPlaylist non trovato.")
            return None

        # Step 5: Costruisci URL finale
        return _build_hls_url(params_raw, hls_url, can_fhd)

    except Exception as e:
        print(f"  [X] scws_resolver error: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# SELFTEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*56)
    print("  scws_resolver v1.0 - selftest")
    print("="*56)
    print(f"  HAS_REQUESTS: {HAS_REQUESTS}")
    print()
    print("  Funzioni esportate:")
    print("    resolve(episode_url, session=None, timeout=15)")
    print()
    print("  Utilizzo da animeunity.py:")
    print("    from scws_resolver import resolve")
    print("    hls_url = resolve(episode_url, session=_session._sess)")
    print()
