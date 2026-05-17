from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import importlib
from scripts.core import Core
from scripts.core.file_manager import FileManager
from scripts.anime.settings_anime import WATCHLIST_CORSO_FILE, WATCHLIST_FINITE_FILE
from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

UPDATE_FLAG = 'nuovi_episodi'


def _now():
    log_debug("[Watchlist/handlers_watchlist] → _now()")
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _date():
    log_debug("[Watchlist/handlers_watchlist] → _date()")
    return datetime.now().strftime('%Y-%m-%d')

def _load(path):
    log_debug("[Watchlist/handlers_watchlist] → _load()")
    d = FileManager.load_json(path) or {}
    d.setdefault('items', []); d.setdefault('last_update', '')
    return d

def _save(path, data):
    log_debug("[Watchlist/handlers_watchlist] → _save()")
    data['last_update'] = _now()
    FileManager.save_json(data, path)

def add_in_corso(dati: dict) -> bool:
    log_debug("[Watchlist/handlers_watchlist] → add_in_corso()")
    core = Core.get(); core.backup.backup(WATCHLIST_CORSO_FILE)
    d = _load(WATCHLIST_CORSO_FILE)
    d['items'].append({
        'titolo':           dati.get('titolo', ''),
        'episodi_in_corso': dati.get('episodi_in_corso', 0),
        'episodi_totali':   dati.get('episodi_totali', 0),
        'url':              dati.get('url', ''),
        'modulo':           dati.get('modulo', ''),
        'data_aggiunta':    _date(),
        'genere':           dati.get('genere', 'N/D'),
        'data_uscita_titolo': dati.get('data_uscita_titolo', 'N/D'),
    })
    _save(WATCHLIST_CORSO_FILE, d)
    core.logger.info('WL corso: aggiunto ' + dati.get('titolo', ''))
    return True

def add_finite(dati: dict) -> bool:
    log_debug("[Watchlist/handlers_watchlist] → add_finite()")
    core = Core.get(); core.backup.backup(WATCHLIST_FINITE_FILE)
    d = _load(WATCHLIST_FINITE_FILE)
    d['items'].append({
        'titolo':           dati.get('titolo', ''),
        'episodi_totali':   dati.get('episodi_totali', 0),
        'url':              dati.get('url', ''),
        'modulo':           dati.get('modulo', ''),
        'data_aggiunta':    _date(),
        'genere':           dati.get('genere', 'N/D'),
        'data_uscita_titolo': dati.get('data_uscita_titolo', 'N/D'),
    })
    _save(WATCHLIST_FINITE_FILE, d)
    core.logger.info('WL finite: aggiunto ' + dati.get('titolo', ''))
    return True

def get_in_corso() -> List[Dict]:
    log_debug("[Watchlist/handlers_watchlist] → get_in_corso()")
    return _load(WATCHLIST_CORSO_FILE).get('items', [])

def get_finite() -> List[Dict]:
    log_debug("[Watchlist/handlers_watchlist] → get_finite()")
    return _load(WATCHLIST_FINITE_FILE).get('items', [])


def _to_int(value, default: int = 0) -> int:
    log_debug("[Watchlist/handlers_watchlist] → _to_int()")
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _episode_count_for_item(it: dict) -> Optional[int]:
    log_debug("[Watchlist/handlers_watchlist] → _episode_count_for_item()")
    from scripts.anime.core_anime import AnimeCore

    mid = it.get('modulo', '')
    url = it.get('url', '')
    if not mid or not url:
        return None

    try:
        handler_path = AnimeCore.get().get_video_handler(mid)
    except Exception as exc:
        log_debug(f'[Watchlist] handler lookup error: {exc}')
        return None

    if not handler_path:
        return None

    try:
        mod = importlib.import_module(handler_path)
        if hasattr(mod, 'get_episode_count'):
            count = mod.get_episode_count(url)
            return _to_int(count, -1) if _to_int(count, -1) >= 0 else None
        if hasattr(mod, 'get_episodes'):
            episodes = mod.get_episodes(url) or []
            return len(episodes)
    except Exception as exc:
        log_debug(f'[Watchlist] episode count error: {exc}')
    return None


def check_updates_on_startup(core=None) -> List[Dict]:
    """
    Controlla rapidamente la watchlist in corso e marca i titoli con nuovi episodi.
    Ritorna una lista di update {'titolo', 'prima', 'dopo'}.
    """
    log_debug("[Watchlist/handlers_watchlist] → check_updates_on_startup()")
    core = core or Core.get()
    data = _load(WATCHLIST_CORSO_FILE)
    wl = data.get('items', [])
    if not wl:
        return []

    updates: List[Dict] = []
    changed = False
    for it in wl:
        count = _episode_count_for_item(it)
        if count is None:
            continue
        current = _to_int(it.get('episodi_in_corso', 0))
        if count > current:
            it['episodi_in_corso'] = count
            it[UPDATE_FLAG] = True
            updates.append({
                'titolo': it.get('titolo', '?'),
                'prima': current,
                'dopo': count,
            })
            changed = True

    if changed:
        core.backup.backup(WATCHLIST_CORSO_FILE)
        _save(WATCHLIST_CORSO_FILE, data)
    return updates


def show_startup_updates(core=None) -> None:
    log_debug("[Watchlist/handlers_watchlist] → show_startup_updates()")
    core = core or Core.get()
    core.progress.spinner_start('Controllo nuove uscite watchlist...')
    try:
        updates = check_updates_on_startup(core)
    finally:
        core.progress.spinner_stop()

    if not updates:
        return

    rows = [
        (u.get('titolo', '?'), f"{u.get('prima', 0)} -> {u.get('dopo', 0)} episodi")
        for u in updates
    ]
    core.ui.warning(f'Nuovi episodi disponibili: {len(updates)} titolo/i aggiornato/i.')
    core.ui.show_info_table('Aggiornamenti watchlist', rows)
    core.ui.pause()
    _serie_in_corso(core)


# ---------------------------------------------------------------------------
# Estrazione link video da watchlist
# ---------------------------------------------------------------------------

def _parse_ep_selection(scelta: str, count: int) -> Optional[List[int]]:
    """
    Parsa la selezione episodi dell'utente.
    Formati accettati: singolo '3', range '1-5', lista '1,3,5', tutti '*'.
    Ritorna lista di indici 0-based, oppure None se non valida.
    """
    log_debug("[Watchlist/handlers_watchlist] → _parse_ep_selection()")
    s = scelta.strip()
    if s == '*':
        return list(range(count))
    if '-' in s:
        parts = s.split('-', 1)
        try:
            a, b = int(parts[0]), int(parts[1])
            if 1 <= a <= b <= count:
                return list(range(a - 1, b))
        except ValueError:
            pass
        return None
    if ',' in s:
        try:
            idxs = [int(x.strip()) - 1 for x in s.split(',')]
            if all(0 <= i < count for i in idxs):
                return idxs
        except ValueError:
            pass
        return None
    try:
        n = int(s)
        if 1 <= n <= count:
            return [n - 1]
    except ValueError:
        pass
    return None


def _estrai_link_watchlist(core, it: dict, show_extracted_links: bool = True) -> None:
    """
    Estrae i link video di una serie in watchlist.
    Usa get_episodes() del modulo sorgente (animeworld, animeunity, ecc.).
    Presenta selezione: singolo / range / lista / tutti.
    """
    log_debug("[Watchlist/handlers_watchlist] → _estrai_link_watchlist()")
    from scripts.anime.core_anime import AnimeCore

    mid    = it.get('modulo', '')
    url    = it.get('url', '')
    titolo = it.get('titolo', '?')

    if not mid or not url:
        core.ui.error('Modulo o URL non disponibili per questo titolo.')
        core.ui.pause()
        return

    # Recupera handler path dal routing anime
    try:
        handler_path = AnimeCore.get().get_video_handler(mid)
    except Exception:
        handler_path = None

    if not handler_path:
        core.ui.error(f'Handler non trovato per il modulo "{mid}".')
        core.ui.pause()
        return

    # Carica episodi via get_episodes()
    core.progress.spinner_start('Caricamento episodi...')
    try:
        mod      = importlib.import_module(handler_path)
        episodes = mod.get_episodes(url) if hasattr(mod, 'get_episodes') else []
    except Exception as exc:
        log_debug(f'[Watchlist] get_episodes error: {exc}')
        episodes = []
    finally:
        core.progress.spinner_stop()

    if not episodes:
        core.ui.warning('Nessun episodio disponibile.')
        core.ui.pause()
        return

    count = len(episodes)
    core.ui.show_info_table(
        f'{titolo} — {count} episodi',
        [('Formato selezione', 'singolo: 3  |  range: 1-5  |  lista: 1,3,5  |  tutti: *  |  indietro: 0')]
    )
    scelta = core.ui.ask_input(f'Episodi (1-{count}, 0=annulla)', '*')
    if scelta.strip() == '0':
        return
    indici = _parse_ep_selection(scelta, count)

    if indici is None:
        core.ui.error('Selezione non valida.')
        core.ui.pause()
        return

    selected = [episodes[i] for i in indici]
    if show_extracted_links:
        core.ui.show_info_table(
            f'Link estratti ({len(selected)})',
            [(str(indici[i] + 1), url_ep) for i, url_ep in enumerate(selected)]
        )

    # Salva su file
    try:
        from scripts.anime.settings_anime import LINK_COMPL_DIR
        out_dir = Path(LINK_COMPL_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in titolo).strip()
        out_file  = out_dir / f'{safe_name}_links.txt'
        with open(out_file, 'w', encoding='utf-8') as f:
            for i, url_ep in zip(indici, selected):
                f.write(f'Ep.{i + 1}: {url_ep}\n')
        core.ui.success(f'Link estratti ({len(selected)}) e salvati nel file testo: {out_file}')
    except Exception as exc:
        log_debug(f'[Watchlist] salvataggio link error: {exc}')
        core.ui.warning('Link estratti ma non salvati su file.')

    core.ui.pause()




def run():
    log_debug("[Watchlist/handlers_watchlist] → run()")
    core = Core.get()
    items = [
        {'key': '1', 'icon': '', 'label': 'Serie in corso', 'desc': ''},
        {'key': '2', 'icon': '', 'label': 'Serie finite',   'desc': ''},
    ]
    while True:
        c = core.ui.show_menu('Watchlist', items)
        if c == '0':
            return
        elif c == '1':
            _serie_in_corso(core)
        elif c == '2':
            _serie_finite(core)
        else:
            core.ui.error('Voce non valida.')


# ---------------------------------------------------------------------------
# Serie in corso
# ---------------------------------------------------------------------------

def _serie_in_corso(core):
    log_debug("[Watchlist/handlers_watchlist] → _serie_in_corso()")
    data = _load(WATCHLIST_CORSO_FILE)
    wl = data['items']
    if not wl:
        core.ui.info('Watchlist in corso vuota.')
        core.ui.pause()
        return

    # Tabella riepilogativa
    rows = [
        ((f"! {it.get('titolo', '?')}" if it.get(UPDATE_FLAG) else it.get('titolo', '?')),
         str(it.get('episodi_in_corso', 0)) + '/' + str(it.get('episodi_totali', 0))
         + ' - ' + it.get('data_aggiunta', ''))
        for it in wl
    ]
    core.ui.show_info_table('Serie in corso', rows)

    # Menu selezione titolo
    menu_items = [
        {'key': str(i + 1), 'icon': '', 'label': (f"! {it.get('titolo', '?')}" if it.get(UPDATE_FLAG) else it.get('titolo', '?')), 'desc': ''}
        for i, it in enumerate(wl)
    ]
    c = core.ui.show_menu('Seleziona titolo', menu_items, show_version=False)
    if c == '0':
        return
    try:
        idx = int(c) - 1
    except ValueError:
        return
    if 0 <= idx < len(wl):
        _det_corso(core, wl, idx, data)


def _det_corso(core, wl, idx, data):
    log_debug("[Watchlist/handlers_watchlist] → _det_corso()")
    it = wl[idx]
    if it.pop(UPDATE_FLAG, None):
        core.backup.backup(WATCHLIST_CORSO_FILE)
        _save(WATCHLIST_CORSO_FILE, data)

    # Dati del titolo come info_rows nel menu — scheda e azioni in un'unica tabella
    info_rows = [(k, str(v)) for k, v in it.items() if k != UPDATE_FLAG]
    azioni = [
        {'key': 'A', 'icon': '', 'label': 'Modifica episodi in corso', 'desc': ''},
        {'key': 'B', 'icon': '', 'label': 'Sposta in serie finite',    'desc': ''},
        {'key': 'E', 'icon': '', 'label': 'Estrai link video',         'desc': ''},
        {'key': 'C', 'icon': '', 'label': 'Elimina dalla watchlist',   'desc': ''},
    ]
    c = core.ui.show_menu(it.get('titolo', '?'), azioni, show_version=False, info_rows=info_rows)
    if c == '0':
        return
    elif c.upper() == 'A':
        ep = core.ui.ask_input('Episodi in corso', str(it.get('episodi_in_corso', 0)))
        try:
            wl[idx]['episodi_in_corso'] = int(ep)
        except ValueError:
            core.ui.error('Numero non valido.')
            return
        core.backup.backup(WATCHLIST_CORSO_FILE)
        _save(WATCHLIST_CORSO_FILE, data)
        core.ui.success('Aggiornato.')
    elif c.upper() == 'B':
        add_finite(it)
        del wl[idx]
        core.backup.backup(WATCHLIST_CORSO_FILE)
        _save(WATCHLIST_CORSO_FILE, data)
        core.ui.success('Spostato in serie finite.')
    elif c.upper() == 'E':
        _estrai_link_watchlist(core, it)
        return
    elif c.upper() == 'C':
        titolo = it.get('titolo', '?')
        conferma = core.ui.ask_input(f'Eliminare "{titolo}"? (s/N)', 'N')
        if conferma.strip().lower() == 's':
            del wl[idx]
            core.backup.backup(WATCHLIST_CORSO_FILE)
            _save(WATCHLIST_CORSO_FILE, data)
            core.ui.success(f'"{titolo}" eliminato dalla watchlist.')
        else:
            core.ui.info('Operazione annullata.')
    core.ui.pause()


# ---------------------------------------------------------------------------
# Serie finite
# ---------------------------------------------------------------------------

def _serie_finite(core):
    log_debug("[Watchlist/handlers_watchlist] → _serie_finite()")
    data = _load(WATCHLIST_FINITE_FILE)
    wl = data['items']
    if not wl:
        core.ui.info('Watchlist finite vuota.')
        core.ui.pause()
        return

    menu_items = [
        {'key': str(i + 1), 'icon': '', 'label': it.get('titolo', '?'),
         'desc': it.get('data_aggiunta', '')}
        for i, it in enumerate(wl)
    ]
    c = core.ui.show_menu('Serie finite', menu_items)
    if c == '0':
        return
    try:
        idx = int(c) - 1
    except ValueError:
        return
    if 0 <= idx < len(wl):
        _det_finite(core, wl, idx, data)


def _det_finite(core, wl, idx, data):
    log_debug("[Watchlist/handlers_watchlist] → _det_finite()")
    it = wl[idx]

    # Dati del titolo come info_rows nel menu — scheda e azioni in un'unica tabella
    info_rows = [(k, str(v)) for k, v in it.items()]
    azioni = [
        {'key': 'E', 'icon': '', 'label': 'Estrai link video',       'desc': ''},
        {'key': 'C', 'icon': '', 'label': 'Elimina dalla watchlist', 'desc': ''},
    ]
    c = core.ui.show_menu(it.get('titolo', '?'), azioni, show_version=False, info_rows=info_rows)
    if c == '0':
        return
    elif c.upper() == 'E':
        _estrai_link_watchlist(core, it, show_extracted_links=False)
        return
    elif c.upper() == 'C':
        titolo = it.get('titolo', '?')
        conferma = core.ui.ask_input(f'Eliminare "{titolo}"? (s/N)', 'N')
        if conferma.strip().lower() == 's':
            del wl[idx]
            core.backup.backup(WATCHLIST_FINITE_FILE)
            _save(WATCHLIST_FINITE_FILE, data)
            core.ui.success(f'"{titolo}" eliminato dalla watchlist.')
        else:
            core.ui.info('Operazione annullata.')
    core.ui.pause()
