from typing import Dict, List
from scripts.core import Core

def search(titolo: str) -> List[Dict]:
    return []  # SILENT — TODO: scraping AnimeWorld

def get_episodes(anime_url: str) -> List[str]:
    return []  # TODO: scraping AnimeWorld

def run():
    core = Core.get()
    items = [
        {'key':'1','icon':'','label':'Ultime uscite','desc':''},
        {'key':'2','icon':'','label':'Ricerca titolo','desc':''},
    ]
    while True:
        c = core.ui.show_menu('AnimeWorld', items)
        if c == '0': return
        elif c == '1': core.ui.warning('TODO: scraping AW.'); core.ui.pause()
        elif c == '2': _ricerca(core)
        else: core.ui.error('Voce non valida.')

def _ricerca(core):
    t = core.ui.ask_input('Titolo o URL [0=Esci]')
    if t == '0' or not t: return
    core.progress.spinner_start('Ricerca AnimeWorld...')
    res = search(t)
    core.progress.spinner_stop()
    if not res:
        core.ui.warning('Nessun risultato su AnimeWorld.'); core.ui.pause(); return
    items = [{'key':str(i+1),'icon':'','label':r.get('titolo',''),'desc':r.get('genere','')}
             for i,r in enumerate(res)]
    c = core.ui.show_menu('Risultati AW', items, show_version=False)
    if c == '0': return
    try: idx=int(c)-1
    except: return
    if 0 <= idx < len(res): _dettaglio(core, res[idx])

def _dettaglio(core, res):
    from scripts.anime.moduli.Utilita.Watchlist.handlers_watchlist import add_in_corso, add_finite
    rows = [(k,str(v)) for k,v in res.items()]
    core.ui.show_info_table(res.get('titolo','?'), rows)
    items = [
        {'key':'A','icon':'','label':'Watchlist in corso','desc':''},
        {'key':'B','icon':'','label':'Watchlist finite','desc':''},
        {'key':'C','icon':'','label':'Estrai link video','desc':''},
    ]
    c = core.ui.show_menu('Azioni', items, show_version=False)
    if c == '0': return
    cu = c.upper()
    if cu=='A': add_in_corso(res); core.ui.success('Aggiunto.')
    elif cu=='B': add_finite(res); core.ui.success('Aggiunto.')
    elif cu=='C' and core.link_extractor:
        core.link_extractor.run('animeworld', res.get('url',''), res.get('titolo','anime'))
    core.ui.pause()
