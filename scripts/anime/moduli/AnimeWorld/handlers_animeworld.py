"""
DC3 — Modulo AnimeWorld
════════════════════════════════════════════════════════════════
Stack HTTP:
  Playwright  → fetch HTML (gestisce JS, antibot, cookie)
  requests    → chiamate API episodi (usa cookie estratti da Playwright)

Browser lifecycle:
  • Lanciato al primo uso se non già attivo
  • NON chiuso all'uscita dal modulo (lifecycle = sessione app)
  • Ogni fetch usa una pagina dedicata → page.close() dopo uso

Contratti pubblici (SILENT — zero output, zero eccezioni non gestite):
  search(titolo: str)       → list[dict]   usato da handlers_ricerca_globale
  get_episodes(anime_url)   → list[str]    usato da link_extractor

Parametro lingua (config):
  config.get_pref('anime.lang', 'all')
    'all'  → nessun filtro  (omette dub)
    'ita'  → dub=1          (solo doppiato)
    'sub'  → dub=0          (solo sottotitolato)
════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import re
import urllib.parse
import requests
from pathlib import PurePath

# ─────────────────────────────────────────────────────────────
# COSTANTI
# ─────────────────────────────────────────────────────────────
MODULE_KEY  = 'animeworld'
MODULE_NAME = 'AnimeWorld'

_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)
_BASE_HEADERS = {
    'User-Agent':      _UA,
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Accept':          'application/json, text/html, */*',
}

# ─────────────────────────────────────────────────────────────
# REGEX
# Nota: basate sulla struttura HTML di AnimeWorld.
# Se il sito cambia layout, aggiornare SOLO questi pattern.
# ─────────────────────────────────────────────────────────────

# Lista anime — pagina search/filter
# Cattura: url, thumb, titolo, ep_info (opzionale)
_RE_ITEM = re.compile(
    r'<div[^>]+class="[^"]*item[^"]*"[^>]*>'
    r'.*?<a[^>]+href="(?P<url>/anime/[^"?#]+)"[^>]*>'
    r'.*?<img[^>]+src="(?P<thumb>[^"]+)"'
    r'.*?<h3[^>]*>(?P<titolo>[^<]+)</h3>'
    r'(?:.*?<div[^>]+class="[^"]*ep[^"]*"[^>]*>(?P<ep_info>[^<]*)</div>)?',
    re.DOTALL,
)

# Lista episodi aggiornati — pagina /updated
# URL episodio include numero: /anime/slug/42
_RE_UPDATED = re.compile(
    r'<div[^>]+class="[^"]*item[^"]*"[^>]*>'
    r'.*?<a[^>]+href="(?P<url>/anime/[^"?#]+/\d+)"[^>]*>'
    r'.*?<img[^>]+src="(?P<thumb>[^"]+)"'
    r'.*?<h3[^>]*>(?P<titolo>[^<]+)</h3>'
    r'(?:.*?<div[^>]+class="[^"]*ep[^"]*"[^>]*>(?P<ep_label>[^<]*)</div>)?',
    re.DOTALL,
)

# Scheda serie — info tabella <dl>
_RE_SCHEDA_TITOLO = re.compile(
    r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>\s*(?P<t>[^<]+?)\s*</h1>'
)
_RE_SCHEDA_STATO  = re.compile(r'Stato</dt>\s*<dd[^>]*>(?P<v>[^<]+)</dd>',  re.DOTALL)
_RE_SCHEDA_GENERE = re.compile(r'Genere</dt>\s*<dd[^>]*>(?P<v>[^<]+)</dd>', re.DOTALL)
_RE_SCHEDA_ANNO   = re.compile(r'Anno</dt>\s*<dd[^>]*>(?P<v>[^<]+)</dd>',   re.DOTALL)
_RE_SCHEDA_EP     = re.compile(r'Episodi</dt>\s*<dd[^>]*>(?P<v>[^<]+)</dd>', re.DOTALL)

# Episodi nella pagina serie — attributi data-id e data-number
_RE_EPISODIO = re.compile(
    r'<li[^>]*data-id="(?P<ep_id>\d+)"[^>]*data-number="(?P<num>[^"]+)"'
)


# ═════════════════════════════════════════════════════════════
# HELPER — BROWSER
# ═════════════════════════════════════════════════════════════

def _ensure_browser(core) -> bool:
    """
    Lancia il browser Playwright se non già attivo.
    Return True se il browser è pronto, False se fallisce.
    """
    if getattr(core.browser, '_launched', False):
        return True
    headless = core.config.is_headless() if hasattr(core.config, 'is_headless') else True
    return core.browser.launch(headless=headless)


def _get_page(url: str, core) -> tuple[str, dict]:
    """
    Fetch HTML tramite Playwright + estrai cookies.

    Return: (html: str, cookies: dict)
    Apre una nuova pagina, naviga, estrae HTML e cookies, chiude la pagina.
    Il BROWSER rimane aperto (lifecycle = sessione app).
    Lancia eccezione in caso di errore — il chiamante è responsabile del try/except.
    """
    page = core.browser.new_page()
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30_000)
        html    = page.content()
        raw_ck  = page.context.cookies()
        cookies = {c['name']: c['value'] for c in raw_ck}
        return html, cookies
    finally:
        page.close()   # chiude LA PAGINA, non il browser


# ═════════════════════════════════════════════════════════════
# HELPER — API EPISODI (requests)
# ═════════════════════════════════════════════════════════════

def _resolve_ep(ep_id: str, base_url: str, cookies: dict) -> str | None:
    """
    Risolve un ep_id in URL diretto via API AnimeWorld.
    Usa requests con i cookie estratti da Playwright.

    GET {base_url}/api/episode/info?id={ep_id}&alt=0
    JSON response: { "grabber": "https://...", ... }

    Return: URL diretto (str) o None se fallisce / non trovato.
    """
    api_url = f"{base_url}/api/episode/info?id={ep_id}&alt=0"
    headers = {**_BASE_HEADERS, 'Referer': base_url}
    try:
        r = requests.get(api_url, headers=headers, cookies=cookies, timeout=15)
        r.raise_for_status()
        data    = r.json()
        grabber = data.get('grabber', '').strip()
        return grabber if grabber else None
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════
# HELPER — PARSE
# ═════════════════════════════════════════════════════════════

def _parse_lista(html: str) -> list[dict]:
    """
    Parsing lista anime da pagina search/filter.
    Return: list[dict] con keys: titolo, url, thumb, ep_info, modulo
    """
    results = []
    for m in _RE_ITEM.finditer(html):
        results.append({
            'titolo':  m.group('titolo').strip(),
            'url':     m.group('url').strip(),
            'thumb':   m.group('thumb').strip(),
            'ep_info': (m.group('ep_info') or '').strip(),
            'modulo':  MODULE_KEY,
        })
    return results


def _parse_updated(html: str) -> list[dict]:
    """
    Parsing lista episodi recenti da /updated.
    Return: list[dict] con keys: titolo, url_ep, url_serie, thumb, ep_label, modulo
    """
    results = []
    for m in _RE_UPDATED.finditer(html):
        ep_url    = m.group('url').strip()
        serie_url = str(PurePath(ep_url).parent)   # strip num episodio
        results.append({
            'titolo':    m.group('titolo').strip(),
            'url_ep':   ep_url,
            'url_serie': serie_url,
            'thumb':    m.group('thumb').strip(),
            'ep_label': (m.group('ep_label') or '').strip(),
            'modulo':   MODULE_KEY,
        })
    return results


def _parse_scheda(html: str) -> dict:
    """
    Parsing pagina scheda serie.
    Return: dict con keys: titolo, stato, genere, anno, ep_totali, modulo
    """
    def _ext(pattern, group='v'):
        m = pattern.search(html)
        return m.group(group).strip() if m else '—'

    return {
        'titolo':    _ext(_RE_SCHEDA_TITOLO, 't'),
        'stato':    _ext(_RE_SCHEDA_STATO),
        'genere':   _ext(_RE_SCHEDA_GENERE),
        'anno':     _ext(_RE_SCHEDA_ANNO),
        'ep_totali': _ext(_RE_SCHEDA_EP),
        'modulo':   MODULE_KEY,
    }


def _parse_episodi(html: str) -> list[str]:
    """
    Estrae lista ep_id dalla pagina serie.
    Return: list[str] di ep_id (ordinati per numero episodio)
    """
    episodi = [
        (m.group('ep_id'), m.group('num'))
        for m in _RE_EPISODIO.finditer(html)
    ]
    # Ordina per numero episodio (gestisce anche numeri con decimali tipo "1.5")
    try:
        episodi.sort(key=lambda x: float(x[1]))
    except ValueError:
        pass
    return [ep_id for ep_id, _ in episodi]


def _build_dub_param(core) -> str:
    """
    Costruisce il parametro dub per la query di ricerca.
    Legge da config.get_pref('anime.lang', 'all').
    """
    lang = core.config.get_pref('anime.lang', 'all')
    if lang == 'ita':
        return '&dub=1'
    if lang == 'sub':
        return '&dub=0'
    return ''   # 'all' → nessun filtro


def _normalize_url(url: str, base_url: str) -> str:
    """Restituisce URL assoluta: aggiunge base_url se l'url è relativo."""
    if url.startswith('http'):
        return url
    return base_url.rstrip('/') + '/' + url.lstrip('/')


# ═════════════════════════════════════════════════════════════
# UI HELPER
# ═════════════════════════════════════════════════════════════

def _show_lista(core, items: list[dict], key_ep: str = 'ep_info') -> None:
    """Stampa lista numerata di anime / episodi."""
    for i, it in enumerate(items, 1):
        label = it.get('titolo', '?')
        sub   = it.get(key_ep, '').strip()
        if sub:
            print(f"  {i:>3}. {label}  [{sub}]")
        else:
            print(f"  {i:>3}. {label}")


def _ask_index(core, items: list, prompt: str = 'Seleziona: ') -> int | None:
    """
    Chiede un indice numerico all'utente.
    Return: indice 0-based valido, oppure None se l'utente sceglie 0/indietro.
    """
    scelta = core.ui.ask_input(prompt).strip()
    if scelta == '0':
        return None
    if scelta.isdigit() and 1 <= int(scelta) <= len(items):
        return int(scelta) - 1
    core.ui.warning('Scelta non valida.')
    return -1   # segnale "input non valido, ripeti il loop"


# ═════════════════════════════════════════════════════════════
# DETTAGLIO SERIE
# ═════════════════════════════════════════════════════════════

def _dettaglio(core, item: dict) -> None:
    """
    Mostra scheda serie e menu azioni:
      A → Aggiungi a Watchlist (In corso)
      B → Aggiungi a Watchlist (Finite)
      C → Estrai link episodi (link_extractor)
      0 → Indietro

    item deve contenere almeno: 'url' (relativo o assoluto), 'titolo'
    """
    # Import locali per evitare circular import
    from scripts.anime.moduli.Utilita.Watchlist import handlers_watchlist   # TODO: adatta import al tuo percorso

    base_url  = core.url_manager.get_url(MODULE_KEY, 'base_url')
    serie_url = _normalize_url(item['url'], base_url)

    # ── Carica scheda ───────────────────────────────────────
    try:
        html, _ = _get_page(serie_url, core)
        scheda  = _parse_scheda(html)
    except Exception as exc:
        print(f'⚠  Impossibile caricare la scheda della serie. ({exc})', 'warn')
        return

    # ── Mostra info ─────────────────────────────────────────
    core.ui.show_sub_header(scheda['titolo'])
    print(f"  Stato    : {scheda['stato']}")
    print(f"  Genere   : {scheda['genere']}")
    print(f"  Anno     : {scheda['anno']}")
    print(f"  Episodi  : {scheda['ep_totali']}")
    print(f"  Modulo   : {MODULE_NAME}")
    print('')

    # Dati per watchlist
    wl_data = {
        'titolo':     scheda['titolo'],
        'url':        item['url'],
        'url_piena':  serie_url,
        'modulo':     MODULE_KEY,
        'ep_totali':  scheda['ep_totali'],
        'ep_corrente': '1',
    }

    # ── Menu azioni ─────────────────────────────────────────
    while True:
        _menu_opts = [
            ('A', 'Aggiungi a Watchlist — In corso'),
            ('B', 'Aggiungi a Watchlist — Finite'),
            ('C', 'Estrai link episodi'),
            ('0', 'Indietro'),
        ]
        for _mi, _mo in enumerate(_menu_opts, 1): print(f'  {_mi}. {_mo}')
        scelta = core.ui.ask_input("Scelta: ")
        scelta = scelta.upper().strip()

        if scelta == 'A':
            handlers_watchlist.add_in_corso(wl_data)
            print('✅  Aggiunto alla watchlist (In corso).', 'ok')

        elif scelta == 'B':
            handlers_watchlist.add_finite(wl_data)
            print('✅  Aggiunto alla watchlist (Finite).', 'ok')

        elif scelta == 'C':
            core.link_extractor.run(MODULE_KEY, serie_url, scheda['titolo'])

        elif scelta == '0':
            return


# ═════════════════════════════════════════════════════════════
# NAVIGAZIONE — ULTIME USCITE
# ═════════════════════════════════════════════════════════════

def _ultime_uscite(core) -> None:
    """
    Mostra gli episodi aggiornati di recente (/updated).
    Selezionando un episodio si accede alla scheda della serie.
    """
    base_url = core.url_manager.get_url(MODULE_KEY, 'base_url')

    core.ui.info('Caricamento ultime uscite...')
    try:
        html, _ = _get_page(f"{base_url}/updated", core)
    except Exception as exc:
        print(f'⚠  Impossibile raggiungere AnimeWorld. ({exc})', 'warn')
        return

    items = _parse_updated(html)
    if not items:
        core.ui.warning('Nessun episodio trovato nella pagina /updated.')
        return

    while True:
        core.ui.show_sub_header(f'{MODULE_NAME} — Ultime uscite')
        _show_lista(core, items, key_ep='ep_label')
        print('')
        print('  0. Indietro')
        print('')

        idx = _ask_index(core, items, 'Seleziona episodio: ')
        if idx is None:
            return
        if idx == -1:
            continue   # input non valido → ripeti

        ep = items[idx]
        # Vai alla scheda della SERIE (non dell'episodio singolo)
        serie_item = {
            'url':    ep['url_serie'],
            'titolo': ep['titolo'],
        }
        _dettaglio(core, serie_item)


# ═════════════════════════════════════════════════════════════
# NAVIGAZIONE — RICERCA
# ═════════════════════════════════════════════════════════════

def _ricerca(core) -> None:
    """Ricerca anime per titolo con filtro lingua da config."""
    base_url = core.url_manager.get_url(MODULE_KEY, 'base_url')

    titolo = core.ui.ask_input('Titolo da cercare: ').strip()
    if not titolo:
        return

    dub_param   = _build_dub_param(core)
    keyword_enc = urllib.parse.quote_plus(titolo)
    search_url  = f"{base_url}/filter?keyword={keyword_enc}&sort={dub_param}"

    core.progress.spinner_start('Ricerca in corso...')
    try:
        html, _ = _get_page(search_url, core)
    except Exception as exc:
        core.progress.spinner_stop()
        print(f'⚠  Errore durante la ricerca. ({exc})', 'warn')
        return
    finally:
        core.progress.spinner_stop()

    items = _parse_lista(html)
    if not items:
        core.ui.warning(f'Nessun risultato per "{titolo}".')
        return

    while True:
        core.ui.show_sub_header(f'{MODULE_NAME} — Risultati per "{titolo}"')
        _show_lista(core, items)
        print('')
        print('  0. Indietro')
        print('')

        idx = _ask_index(core, items, 'Seleziona serie: ')
        if idx is None:
            return
        if idx == -1:
            continue

        _dettaglio(core, items[idx])


# ═════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════

def run() -> None:
    """
    Entry point del modulo AnimeWorld.
    Chiamato dal dispatcher quando l'utente seleziona AnimeWorld.
    """
    from scripts.core import Core
    core     = Core.get()
    base_url = core.url_manager.get_url(MODULE_KEY, 'base_url')
    if not base_url:
        core.ui.error(
            'URL AnimeWorld non configurato. '
            'Vai in Impostazioni → Cambio URL moduli.'
        )
        core.ui.pause()
        return

    if not _ensure_browser(core):
        core.ui.error('Impossibile avviare il browser (Playwright).')
        core.ui.pause()
        return

    items = [
        {'key': '1', 'icon': '', 'label': 'Ultime uscite', 'desc': 'Episodi aggiornati'},
        {'key': '2', 'icon': '', 'label': 'Ricerca',       'desc': 'Cerca per titolo'},
    ]
    while True:
        c = core.ui.show_menu(MODULE_NAME, items)
        if c == '0':
            return
        elif c == '1':
            _ultime_uscite(core)
        elif c == '2':
            _ricerca(core)
        else:
            core.ui.error('Voce non valida.')

def search(titolo: str) -> list[dict]:
    """
    [SILENT] Ricerca anime su AnimeWorld.
    Usato da handlers_ricerca_globale.

    Gestisce autonomamente:
      • accesso al Core singleton
      • avvio browser se non attivo
      • apertura/chiusura pagina Playwright
      • gestione errori (return [] in caso di fallimento)

    Return: list[dict] con keys:
      titolo, url, url_piena, thumb, ep_info, modulo
    """
    try:
        from scripts.core import Core        # TODO: adatta import
        core = Core.get()

        base_url = core.url_manager.get_url(MODULE_KEY, 'base_url')
        if not base_url:
            return []

        if not _ensure_browser(core):
            return []

        dub_param   = _build_dub_param(core)
        keyword_enc = urllib.parse.quote_plus(titolo)
        search_url  = f"{base_url}/filter?keyword={keyword_enc}&sort={dub_param}"

        html, _ = _get_page(search_url, core)
        items   = _parse_lista(html)

        # Arricchisci con URL assoluta per comodità dei chiamanti
        for it in items:
            it['url_piena'] = _normalize_url(it['url'], base_url)

        return items

    except Exception:
        return []


def get_episodes(anime_url: str) -> list[str]:
    """
    [SILENT] Recupera lista URL diretti di tutti gli episodi.

    Flusso:
      1. Playwright → HTML pagina serie + cookies
      2. _parse_episodi(html) → list[ep_id]  (ordinati per numero ep)
      3. Per ogni ep_id:
           requests → GET /api/episode/info?id={ep_id}&alt=0
           JSON { "grabber": "https://..." }
           → aggiunge grabber URL alla lista

    Return: list[str] di grabber URL (vuota se errore o nessun episodio)
    """
    try:
        from scripts.core import Core        # TODO: adatta import
        core = Core.get()

        base_url = core.url_manager.get_url(MODULE_KEY, 'base_url')
        if not base_url:
            return []

        if not _ensure_browser(core):
            return []

        full_url = _normalize_url(anime_url, base_url)

        # ── Step 1: Playwright → HTML + cookies ──────────────
        html, cookies = _get_page(full_url, core)

        # ── Step 2: Estrai ep_id (già ordinati) ──────────────
        ep_ids = _parse_episodi(html)
        if not ep_ids:
            return []

        # ── Step 3: Risolvi ogni episodio via API requests ────
        urls = []
        for ep_id in ep_ids:
            grabber = _resolve_ep(ep_id, base_url, cookies)
            if grabber:
                urls.append(grabber)

        return urls

    except Exception:
        return []
