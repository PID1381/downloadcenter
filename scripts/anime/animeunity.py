#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
animeunity.py  v1.0
Download Center - scripts/anime/animeunity.py

Porting da Stream4me/addon/channels/animeunity.py (Alfa/Kodi)
a Python puro, integrato nell'architettura Download Center v2.1.

FLUSSO REALE (da codice sorgente S4me):
  1. _init_session()   -> GET /archivio -> estrae csrf_token + cookie
  2. mainlist()        -> categorie top-level
  3. menu()            -> sotto-categorie (Tutti, ITA, Genere, Anno, ...)
  4. genres()          -> parse JSON inline dalla pagina /archivio
  5. years()           -> parse anime_oldest_date dalla pagina /archivio
  6. peliculas()       -> POST /archivio/get-animes (JSON) -> lista anime
  7. episodios()       -> GET /info_api/{id}/1?start_range=X&end_range=Y
  8. findvideos()      -> risolve URL episodio -> link HLS via scws_resolver
  9. news()            -> GET host -> parse items-json -> ultimi episodi
  10. search()         -> chiama peliculas() con args['title']

SOSTITUZIONI KODI -> PYTHON:
  httptools.downloadpage()         -> requests.Session.get/post
  support.match(patron=...)        -> re.search(...)
  support.config.get_channel_url() -> url_manager.get("anime","animeunity")
  support.Item()                   -> dict standard
  cloudscraper                     -> requests (AU non usa CF attivo)
  autorenumber.start()             -> ordinamento per numero gia' nei dati
  support.server()                 -> scws_resolver.resolve()

DIPENDENZE:
  - requests, beautifulsoup4       (gia' usate in anime_engine.py)
  - scripts/core/url_manager.py    (gia' presente nel progetto)
  - scripts/anime/scws_resolver.py (nuovo, creato insieme a questo file)
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Path setup ───────────────────────────────────────────────────────────────
_THIS_DIR    = Path(__file__).parent.resolve()   # scripts/anime/
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()        # scripts/
_CORE_DIR    = _SCRIPTS_DIR / "core"

for _p in (str(_THIS_DIR), str(_SCRIPTS_DIR), str(_CORE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Dipendenze opzionali ─────────────────────────────────────────────────────
try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    _requests    = None  # type: ignore[assignment]
    HAS_REQUESTS = False

# ── URL Manager ───────────────────────────────────────────────────────────────
try:
    from core.url_manager import url_mgr as _url_mgr
    _HAS_URL_MGR = True
except ImportError:
    try:
        from url_manager import url_mgr as _url_mgr
        _HAS_URL_MGR = True
    except ImportError:
        _url_mgr     = None  # type: ignore[assignment]
        _HAS_URL_MGR = False

# ── Helpers UI (fallback se anime_engine non disponibile) ─────────────────────
try:
    from anime_engine import show_error, show_info, show_warning, show_success
    _HAS_ENGINE = True
except ImportError:
    _HAS_ENGINE = False
    def show_error(m):   print(f"  [X] {m}")
    def show_info(m):    print(f"  [i] {m}")
    def show_warning(m): print(f"  [!] {m}")
    def show_success(m): print(f"  [v] {m}")


# ════════════════════════════════════════════════════════════════════════════
# §1  COSTANTI
# ════════════════════════════════════════════════════════════════════════════

_BASE_URL_FALLBACK = "https://www.animeunity.to"

# Ordini disponibili (da animeunity.json settings — S4me)
ORDER_LIST = ["Standard", "Lista A-Z", "Lista Z-A", "Popolarita'", "Valutazione"]

# Valori reali da S4me
_PAGE_SIZE = 30    # anime per pagina (POST /archivio/get-animes)
_EP_LIMIT  = 120   # episodi per richiesta API (/info_api/)

_HDR_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ════════════════════════════════════════════════════════════════════════════
# §2  SESSIONE HTTP
#     Replica init di animeunity.py S4me:
#       response  = httptools.downloadpage(host + '/archivio')
#       csrf      = support.match(response.data, patron='name="csrf-token" content="([^"]+)"').match
#       headers   = {'content-type': 'application/json;charset=UTF-8',
#                    'x-csrf-token': csrf_token,
#                    'Cookie': '; '.join([x.name+'='+x.value for x in response.cookies])}
# ════════════════════════════════════════════════════════════════════════════

class _Session:
    """Sessione HTTP per AnimeUnity (lazy init)."""

    def __init__(self):
        self._sess:          Optional[object] = None   # requests.Session
        self._csrf_token:    str  = ""
        self._req_headers:   Dict = {}
        self._host:          str  = ""
        self._archivio_html: str  = ""
        self._initialized:   bool = False

    # ── host ──────────────────────────────────────────────────────────────────
    def _get_host(self) -> str:
        if _HAS_URL_MGR and _url_mgr is not None:
            try:
                url = _url_mgr.get("anime", "animeunity")
                if url:
                    return url.rstrip("/")
            except Exception:
                pass
        return _BASE_URL_FALLBACK

    # ── init (corrisponde all'init module-level di S4me) ─────────────────────
    def init(self) -> bool:
        if not HAS_REQUESTS:
            show_error("requests non installato. Esegui: pip install requests beautifulsoup4")
            return False

        self._host = self._get_host()
        self._sess = _requests.Session()
        self._sess.headers.update(_HDR_BROWSER)

        try:
            resp = self._sess.get(
                self._host + "/archivio",
                timeout=15,
                allow_redirects=True,
            )
            resp.raise_for_status()
            self._archivio_html = resp.text

            # csrf-token — identico a S4me: patron='name="csrf-token" content="([^"]+)"'
            m = re.search(r'name="csrf-token"\s+content="([^"]+)"', self._archivio_html)
            self._csrf_token = m.group(1) if m else ""

            # Cookie string — identico a S4me
            cookie_str = "; ".join(f"{c.name}={c.value}" for c in resp.cookies)

            # Headers per POST — identici a S4me
            self._req_headers = {
                "content-type":     "application/json;charset=UTF-8",
                "x-csrf-token":     self._csrf_token,
                "Cookie":           cookie_str,
                "User-Agent":       _HDR_BROWSER["User-Agent"],
                "Referer":          self._host + "/archivio",
                "X-Requested-With": "XMLHttpRequest",
            }
            self._initialized = True
            return True

        except Exception as e:
            show_error(f"Errore init AnimeUnity: {e}")
            return False

    # ── HTTP helpers ──────────────────────────────────────────────────────────
    def get(self, url: str, **kwargs) -> Optional[object]:
        if not self._initialized:
            if not self.init():
                return None
        try:
            return self._sess.get(url, timeout=15, **kwargs)
        except Exception as e:
            show_error(f"GET error {url}: {e}")
            return None

    def post_json(self, url: str, payload: dict) -> Optional[dict]:
        """POST JSON con headers csrf."""
        if not self._initialized:
            if not self.init():
                return None
        try:
            resp = self._sess.post(
                url,
                data=json.dumps(payload),
                headers=self._req_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            show_error(f"POST error {url}: {e}")
            return None

    @property
    def host(self) -> str:
        if not self._host:
            self._host = self._get_host()
        return self._host

    @property
    def archivio_html(self) -> str:
        if not self._archivio_html and not self._initialized:
            self.init()
        return self._archivio_html


# Istanza modulo-level (lazy, come S4me)
_session = _Session()


def _ensure_session() -> bool:
    if not _session._initialized:
        return _session.init()
    return True


# ════════════════════════════════════════════════════════════════════════════
# §3  FUNZIONI PUBBLICHE — porting 1:1 da S4me
# ════════════════════════════════════════════════════════════════════════════

def mainlist() -> List[Dict]:
    """
    Menu top-level AnimeUnity.
    Corrisponde a mainlist(item) in S4me.
    """
    return [
        {"label": "Ultimi Episodi", "action": "news",     "args": {},                  "content_type": "episode"},
        {"label": "Anime",          "action": "menu",      "args": {},                  "content_type": "tvshow"},
        {"label": "Film",           "action": "menu",      "args": {"type": "Movie"},   "content_type": "movie"},
        {"label": "TV",             "action": "menu",      "args": {"type": "TV"},      "content_type": "tvshow"},
        {"label": "OVA",            "action": "menu",      "args": {"type": "OVA"},     "content_type": "tvshow"},
        {"label": "ONA",            "action": "menu",      "args": {"type": "ONA"},     "content_type": "tvshow"},
        {"label": "Special",        "action": "menu",      "args": {"type": "Special"}, "content_type": "tvshow"},
    ]


def menu(args: Dict, content_type: str = "tvshow") -> List[Dict]:
    """
    Sotto-menu filtri.
    Corrisponde a menu(item) in S4me: Tutti, ITA, Genere, Anno, In Corso, Terminato.
    """
    ita_args       = copy.deepcopy(args); ita_args["title"]  = "(ita)"
    in_corso_args  = copy.deepcopy(args); in_corso_args["status"] = "In Corso"
    terminato_args = copy.deepcopy(args); terminato_args["status"] = "Terminato"

    items = [
        {"label": "Tutti",     "action": "peliculas", "args": copy.deepcopy(args), "content_type": content_type},
        {"label": "ITA",       "action": "peliculas", "args": ita_args,            "content_type": content_type},
        {"label": "Genere",    "action": "genres",    "args": copy.deepcopy(args), "content_type": content_type},
        {"label": "Anno",      "action": "years",     "args": copy.deepcopy(args), "content_type": content_type},
    ]
    if content_type == "tvshow":
        items += [
            {"label": "In Corso",  "action": "peliculas", "args": in_corso_args,  "content_type": content_type},
            {"label": "Terminato", "action": "peliculas", "args": terminato_args, "content_type": content_type},
        ]
    items.append(
        {"label": "Cerca...", "action": "search", "args": copy.deepcopy(args), "content_type": content_type}
    )
    return items


def genres(args: Dict) -> List[Dict]:
    """
    Lista generi da JSON inline /archivio.
    Corrisponde a genres(item) in S4me:
      genres = json.loads(support.match(response.data,
                patron='genres="([^"]+)').match.replace('&quot;','"'))
    """
    if not _ensure_session():
        return []

    html = _session.archivio_html
    m = re.search(r'genres="([^"]+)', html)
    if not m:
        show_warning("Lista generi non trovata.")
        return []

    try:
        genre_list = json.loads(m.group(1).replace("&quot;", '"'))
    except json.JSONDecodeError as e:
        show_error(f"Errore parse generi: {e}")
        return []

    items = []
    for genre in genre_list:
        genre_args = copy.deepcopy(args)
        genre_args["genres"] = [genre]
        items.append({
            "label":        genre.get("name", ""),
            "action":       "peliculas",
            "args":         genre_args,
            "content_type": args.get("content_type", "tvshow"),
        })
    return items


def years(args: Dict) -> List[Dict]:
    """
    Lista anni da anime_oldest_date in /archivio.
    Corrisponde a years(item) in S4me:
      oldest_year = int(support.match(response.data,
                    patron='anime_oldest_date="([^"]+)"').match)
    """
    if not _ensure_session():
        return []

    next_year = datetime.today().year + 1
    html = _session.archivio_html
    m = re.search(r'anime_oldest_date="([^"]+)"', html)
    if not m:
        show_warning("Anno piu' vecchio non trovato.")
        return []

    try:
        oldest_year = int(m.group(1)[:4])
    except (ValueError, IndexError):
        oldest_year = 1990

    items = []
    for year in reversed(range(oldest_year, next_year + 1)):
        year_args = copy.deepcopy(args)
        year_args["year"] = year
        items.append({
            "label":        str(year),
            "action":       "peliculas",
            "args":         year_args,
            "content_type": args.get("content_type", "tvshow"),
        })
    return items


def peliculas(args: Dict, page: int = 0, order_index: int = 0) -> Tuple[List[Dict], bool]:
    """
    Lista anime via POST /archivio/get-animes.
    Corrisponde a peliculas(item) in S4me.

    Args:
        args:        Filtri (type, title, status, genres, year, ...)
        page:        Pagina corrente (0-based, offset = page * 30)
        order_index: Indice in ORDER_LIST

    Returns:
        (lista_anime, has_next_page)
        Ogni anime ha chiavi:
          id, slug, title, title_eng, type, language, plot,
          thumbnail, url, episodes_count, [api_ep_url],
          content_type, action
    """
    if not _ensure_session():
        return [], False

    payload = copy.deepcopy(args)
    payload["offset"] = page * _PAGE_SIZE

    if 0 < order_index < len(ORDER_LIST):
        payload["order"] = ORDER_LIST[order_index]

    data = _session.post_json(_session.host + "/archivio/get-animes", payload)
    if not data:
        return [], False

    records = data.get("records", [])
    items   = []

    for it in records:
        # Fallback title_eng — identico a S4me
        title = it.get("title") or it.get("title_eng") or ""
        if not title:
            continue

        # Lingua: cerca (ITA) — identico a S4me
        lang_m   = re.search(r'\(([Ii][Tt][Aa])\)', title)
        language = "ITA" if lang_m else "Sub-ITA"

        # Rimuovi tag tra parentesi dal titolo — identico a S4me
        clean_title = re.sub(r'\s*\([^\)]+\)', "", title).strip()
        if not clean_title:
            clean_title = it.get("title_eng") or title

        anime_url = "{}/anime/{}-{}".format(
            _session.host, it.get("id"), it.get("slug")
        )

        anime = {
            "id":             it.get("id"),
            "slug":           it.get("slug"),
            "title":          clean_title,
            "title_eng":      it.get("title_eng") or "",
            "type":           it.get("type") or "",
            "language":       language,
            "plot":           it.get("plot") or "",
            "thumbnail":      it.get("imageurl") or "",
            "url":            anime_url,
            "episodes_count": it.get("episodes_count") or 0,
        }

        # Film (1 ep) vs Serie — identico a S4me
        if it.get("episodes_count") == 1:
            anime["content_type"] = "movie"
            anime["action"]       = "findvideos"
        else:
            anime["content_type"] = "tvshow"
            anime["action"]       = "episodios"
            anime["api_ep_url"]   = "{}/info_api/{}/".format(
                _session.host, it.get("id")
            )

        items.append(anime)

    return items, (len(records) >= _PAGE_SIZE)


def episodios(api_ep_url: str, anime_type: str = "tvshow", anime_url: str = "") -> List[Dict]:
    """
    Lista episodi paginata via GET /info_api/{id}/1?start_range=X&end_range=Y.
    Corrisponde a episodios(item) in S4me.

    Args:
        api_ep_url: URL base API episodi (es. https://www.animeunity.to/info_api/123/)
        anime_type: 'movie' o 'tvshow' (label Parte/Episodio)
        anime_url:  URL pagina anime (usato per costruire URL episodio)

    Returns:
        Lista dict episodio:
          number, title, url, ep_id, scws_id, link,
          action='findvideos', content_type='episode'
    """
    if not _ensure_session():
        return []

    label = "Parte" if anime_type.lower() == "movie" else "Episodio"
    start = 1
    all_episodes: List[Dict] = []

    while True:
        end     = start + _EP_LIMIT - 1
        ep_url  = "{}1?start_range={}&end_range={}".format(api_ep_url, start, end)
        resp    = _session.get(ep_url)
        if not resp:
            break

        try:
            full = resp.json()
        except Exception:
            break

        count    = full.get("episodes_count", 0)
        episodes = full.get("episodes", [])

        for ep in episodes:
            ep_num = ep.get("number") or len(all_episodes) + 1
            # Costruisce URL episodio: url_anime + '/' + ep_id — identico a S4me
            if anime_url:
                ep_page_url = "{}/{}".format(anime_url.rstrip("/"), ep.get("id"))
            else:
                # Fallback: ricava url anime da api_ep_url
                base = api_ep_url.replace("/info_api/", "/anime/").rstrip("/")
                # Rimuove eventuale ID finale lasciato da split
                base = re.sub(r'/\d+$', '', base)
                ep_page_url = "{}/{}".format(base, ep.get("id"))

            all_episodes.append({
                "number":       ep_num,
                "title":        "{} {}".format(label, ep_num),
                "url":          ep_page_url,
                "ep_id":        ep.get("id"),
                "scws_id":      ep.get("scws_id") or "",
                "link":         ep.get("link") or "",
                "action":       "findvideos",
                "content_type": "episode",
            })

        # Paginazione — identico a S4me: if count > start: start = start + limit
        if count > start + _EP_LIMIT - 1:
            start += _EP_LIMIT
        else:
            break

    return all_episodes


def findvideos(url: str, scws_id: str = "") -> Optional[str]:
    """
    Risolve URL episodio -> link HLS.
    Corrisponde a findvideos(item) in S4me -> server='streamingcommunityws'.

    Args:
        url:     URL pagina episodio AnimeUnity
        scws_id: ID SCWS (opzionale)

    Returns:
        URL HLS (m3u8) oppure None.
    """
    try:
        from scws_resolver import resolve as _scws_resolve
        return _scws_resolve(url, session=_session._sess)
    except ImportError:
        show_warning("scws_resolver.py non trovato — uso resolver inline")
        return _findvideos_inline(url)


def _findvideos_inline(url: str) -> Optional[str]:
    """Resolver inline (fallback). Replica streamingcommunityws.py S4me."""
    import ast
    import urllib.parse

    if not _ensure_session():
        return None

    try:
        # Step 1: GET pagina episodio -> iframe src / embed_url
        resp = _session.get(url)
        if not resp:
            return None
        html = resp.text

        # patron=['<iframe [^>]+src="([^"]+)', 'embed_url="([^"]+)'] — S4me
        iframe_m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if not iframe_m:
            iframe_m = re.search(r'embed_url="([^"]+)"', html)
        if not iframe_m:
            show_warning(f"Nessun iframe in: {url}")
            return None

        iframe_url = iframe_m.group(1).replace("&amp;", "&")

        # Step 2: GET iframe -> window.masterPlaylist
        resp2 = _session.get(iframe_url)
        if not resp2:
            return None

        # patron S4me:
        # r'window\.masterPlaylist\s+=\s+{[^{]+({[^}]+}),\s+url:\s+\'([^\']+).*?canPlayFHD\s=\s(true|false)'
        mp_m = re.search(
            r"window\.masterPlaylist\s*=\s*\{[^{]*({[^}]+}),\s*url:\s*'([^']+)'.*?canPlayFHD\s*=\s*(true|false)",
            resp2.text,
            re.DOTALL,
        )
        if not mp_m:
            show_warning("window.masterPlaylist non trovato.")
            return None

        params_raw, hls_url, fhd_str = mp_m.groups()

        try:
            master_params = ast.literal_eval(params_raw)
        except Exception:
            master_params = {}

        # canPlayFHD -> h=1 — identico a S4me
        if fhd_str == "true":
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

    except Exception as e:
        show_error(f"Errore findvideos inline: {e}")
        return None


def news(url: str = "", page: int = 1) -> Tuple[List[Dict], Optional[str]]:
    """
    Ultimi episodi dalla home page.
    Corrisponde a news(item) in S4me:
      fullJs = json.loads(support.match(httptools.downloadpage(item.url).data,
               patron=r'items-json="([^"]+)"').match.replace('&quot;','"'))

    Returns:
        (lista_episodi, next_page_url_or_None)
    """
    if not _ensure_session():
        return [], None

    target_url = url or _session.host
    resp = _session.get(target_url)
    if not resp:
        return [], None

    html = resp.text
    m = re.search(r'items-json="([^"]+)"', html)
    if not m:
        show_warning("items-json non trovato nella home.")
        return [], None

    try:
        full_js = json.loads(m.group(1).replace("&quot;", '"'))
    except json.JSONDecodeError as e:
        show_error(f"Errore parse items-json: {e}")
        return [], None

    js       = full_js.get("data", [])
    items    = []
    next_url = full_js.get("next_page_url")

    for it in js:
        anime      = it.get("anime") or {}
        title_name = anime.get("title") or anime.get("title_eng") or ""
        if not title_name:
            continue

        # Estrai numero episodio dal file_name — identico a S4me
        file_name    = it.get("file_name") or ""
        full_episode = ""
        m_ep = re.search(r'[sS](\d+)[eE](\d+)', file_name)
        if m_ep:
            s, e = m_ep.groups()
            full_episode = " - S{} E{}".format(s, e)
        else:
            m_ep2 = re.search(r'[._\s]Ep[._\s]*(\d+)', file_name)
            if m_ep2:
                full_episode = " - E{}".format(m_ep2.group(1))

        items.append({
            "title":        title_name + full_episode,
            "fulltitle":    anime.get("title") or "",
            "thumbnail":    anime.get("imageurl") or "",
            "scws_id":      it.get("scws_id") or "",
            "url":          "{}/anime/{}-{}".format(
                _session.host, anime.get("id"), anime.get("slug")
            ),
            "plot":         anime.get("plot") or "",
            "action":       "findvideos",
            "content_type": "episode",
        })

    return items, next_url


def search(text: str, args: Optional[Dict] = None) -> Tuple[List[Dict], bool]:
    """
    Ricerca anime per titolo.
    Corrisponde a search(item, text) in S4me:
      item.args['title'] = text -> chiama peliculas(item)
    """
    search_args = copy.deepcopy(args) if args else {}
    search_args["title"] = text
    return peliculas(search_args, page=0)


def reset_session() -> None:
    """Forza re-init sessione (es. dopo cambio URL in url_manager)."""
    global _session
    _session = _Session()


# ════════════════════════════════════════════════════════════════════════════
# §4  SELFTEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*56)
    print("  AnimeUnity v1.0 - selftest")
    print("="*56)
    print(f"  HAS_REQUESTS : {HAS_REQUESTS}")
    print(f"  HAS_URL_MGR  : {_HAS_URL_MGR}")
    print(f"  HOST         : {_session.host}")
    print()

    if not HAS_REQUESTS:
        print("  SKIP: requests non installato")
    else:
        print("  [1] Test init sessione...")
        ok = _session.init()
        print(f"  Init: {'OK' if ok else 'FAIL'}")
        if ok:
            print(f"  CSRF token: {_session._csrf_token[:20]}...")
            print()
            print("  [2] Test news()...")
            news_items, nxt = news()
            print(f"  News: {len(news_items)} episodi, next={nxt is not None}")
            if news_items:
                print(f"  Primo: {news_items[0]['title']}")
            print()
            print("  [3] Test search('naruto')...")
            results, has_next = search("naruto")
            print(f"  Risultati: {len(results)}, has_next={has_next}")
            if results:
                print(f"  Primo: {results[0]['title']}")
    print()
