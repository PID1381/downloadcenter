from datetime import datetime
from pathlib import Path
from typing import Dict, List
from scripts.core import Core
from scripts.core.file_manager import FileManager
from scripts.anime.settings_anime import WATCHLIST_CORSO_FILE, WATCHLIST_FINITE_FILE

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

def _now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_debug("[Watchlist/handlers_watchlist] → _now()")
def _date(): return datetime.now().strftime('%Y-%m-%d')
    log_debug("[Watchlist/handlers_watchlist] → _date()")

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
    core = Core.get(); core.backup.backup(WATCHLIST_CORSO_FILE)
    d = _load(WATCHLIST_CORSO_FILE)
    d['items'].append({
        'titolo': dati.get('titolo',''),
        'episodi_in_corso': dati.get('episodi_in_corso', 0),
        'episodi_totali': dati.get('episodi_totali', 0),
        'url': dati.get('url',''), 'modulo': dati.get('modulo',''),
        'data_aggiunta': _date(), 'genere': dati.get('genere','N/D'),
        'data_uscita_titolo': dati.get('data_uscita_titolo','N/D'),
    })
    _save(WATCHLIST_CORSO_FILE, d)
    core.logger.info('WL corso: aggiunto '+dati.get('titolo','')); return True

def add_finite(dati: dict) -> bool:
    core = Core.get(); core.backup.backup(WATCHLIST_FINITE_FILE)
    d = _load(WATCHLIST_FINITE_FILE)
    d['items'].append({
        'titolo': dati.get('titolo',''),
        'episodi_totali': dati.get('episodi_totali', 0),
        'url': dati.get('url',''), 'modulo': dati.get('modulo',''),
        'data_aggiunta': _date(), 'genere': dati.get('genere','N/D'),
        'data_uscita_titolo': dati.get('data_uscita_titolo','N/D'),
    })
    _save(WATCHLIST_FINITE_FILE, d)
    core.logger.info('WL finite: aggiunto '+dati.get('titolo','')); return True

def get_in_corso() -> List[Dict]: return _load(WATCHLIST_CORSO_FILE).get('items', [])
def get_finite()   -> List[Dict]: return _load(WATCHLIST_FINITE_FILE).get('items', [])

def run():
    log_debug("[Watchlist/handlers_watchlist] → run()")
    core = Core.get()
    items = [
        {'key':'1','icon':'','label':'Serie in corso','desc':''},
        {'key':'2','icon':'','label':'Serie finite','desc':''},
    ]
    while True:
        c = core.ui.show_menu('Watchlist', items)
        if c == '0': return
        elif c == '1': _serie_in_corso(core)
        elif c == '2': _serie_finite(core)
        else: core.ui.error('Voce non valida.')

def _serie_in_corso(core):
    log_debug("[Watchlist/handlers_watchlist] → _serie_in_corso()")
    data = _load(WATCHLIST_CORSO_FILE); wl = data['items']
    if not wl: core.ui.info('Watchlist in corso vuota.'); core.ui.pause(); return
    rows = [(it.get('titolo','?'),
             str(it.get('episodi_in_corso',0))+'/'+str(it.get('episodi_totali',0))+
             ' - '+it.get('data_aggiunta','')) for it in wl]
    core.ui.show_info_table('Serie in corso', rows)
    items = [{'key':str(i+1),'icon':'','label':it.get('titolo','?'),'desc':''}
             for i,it in enumerate(wl)]
    c = core.ui.show_menu('Serie in corso', items, show_version=False)
    if c == '0': return
    try: idx=int(c)-1
    except: return
    if 0 <= idx < len(wl): _det_corso(core, wl, idx, data)

def _det_corso(core, wl, idx, data):
    log_debug("[Watchlist/handlers_watchlist] → _det_corso()")
    it = wl[idx]
    core.ui.show_info_table(it.get('titolo','?'), [(k,str(v)) for k,v in it.items()])
    azioni = [
        {'key':'A','icon':'','label':'Modifica episodi in corso','desc':''},
        {'key':'B','icon':'','label':'Sposta in serie finite','desc':''},
    ]
    c = core.ui.show_menu('Azioni', azioni, show_version=False)
    if c == '0': return
    elif c.upper() == 'A':
        ep = core.ui.ask_input('Episodi visti', str(it.get('episodi_in_corso',0)))
        try: wl[idx]['episodi_in_corso'] = int(ep)
        except: core.ui.error('Numero non valido.'); return
        core.backup.backup(WATCHLIST_CORSO_FILE)
        _save(WATCHLIST_CORSO_FILE, data); core.ui.success('Aggiornato.')
    elif c.upper() == 'B':
        add_finite(it); del wl[idx]
        core.backup.backup(WATCHLIST_CORSO_FILE)
        _save(WATCHLIST_CORSO_FILE, data); core.ui.success('Spostato in serie finite.')
    core.ui.pause()

def _serie_finite(core):
    log_debug("[Watchlist/handlers_watchlist] → _serie_finite()")
    wl = get_finite()
    if not wl: core.ui.info('Watchlist finite vuota.'); core.ui.pause(); return
    items = [{'key':str(i+1),'icon':'','label':it.get('titolo','?'),
              'desc':it.get('data_aggiunta','')} for i,it in enumerate(wl)]
    c = core.ui.show_menu('Serie finite', items)
    if c == '0': return
    try: idx=int(c)-1
    except: return
    if 0 <= idx < len(wl):
        core.ui.show_info_table(wl[idx].get('titolo','?'),
                                [(k,str(v)) for k,v in wl[idx].items()])
        core.ui.pause()
