from typing import Dict, List
from scripts.core import Core

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

def search(titolo: str) -> List[Dict]:
    return []  # SILENT — TODO: scraping AnimeUnity

def get_episodes(anime_url: str) -> List[str]:
    return []  # TODO: scraping AnimeUnity

def run():
    log_debug("[AnimeUnity/handlers_animeunity] → run()")
    core = Core.get()
    items = [
        {'key':'1','icon':'','label':'Ultime uscite','desc':''},
        {'key':'2','icon':'','label':'Ricerca titolo','desc':''},
    ]
    while True:
        c = core.ui.show_menu('AnimeUnity', items)
        if c == '0': return
        elif c == '1': core.ui.warning('TODO: scraping AU.'); core.ui.pause()
        elif c == '2': _ricerca(core)
        else: core.ui.error('Voce non valida.')

def _ricerca(core):
    log_debug("[AnimeUnity/handlers_animeunity] → _ricerca()")
    t = core.ui.ask_input('Titolo o URL [0=Esci]')
    if t == '0' or not t: return
    core.progress.spinner_start('Ricerca AnimeUnity...')
    res = search(t)
    core.progress.spinner_stop()
    if not res:
        core.ui.warning('Nessun risultato su AnimeUnity.'); core.ui.pause(); return
    items = [{'key':str(i+1),'icon':'','label':r.get('titolo',''),'desc':''}
             for i,r in enumerate(res)]
    c = core.ui.show_menu('Risultati AU', items, show_version=False)
    if c == '0': return
    try: idx=int(c)-1
    except: return
    if 0 <= idx < len(res) and core.link_extractor:
        core.link_extractor.run('animeunity', res[idx].get('url',''), res[idx].get('titolo','anime'))
