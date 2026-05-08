from typing import Dict, List
from scripts.core import Core
from scripts.core.file_manager import FileManager

def search_scheda(titolo: str) -> List[Dict]:
    return []  # SILENT — TODO: scraping AnimeClick

def run():
    core = Core.get()
    items = [
        {'key':'1','icon':'','label':'Ricerca titolo','desc':''},
        {'key':'2','icon':'','label':'Ricerca per URL diretto','desc':''},
    ]
    while True:
        c = core.ui.show_menu('AnimeClick', items)
        if c == '0': return
        elif c == '1': _ricerca_titolo(core)
        elif c == '2': core.ui.warning('TODO: scraping diretto.'); core.ui.pause()
        else: core.ui.error('Voce non valida.')

def _ricerca_titolo(core):
    t = core.ui.ask_input('Titolo [0=Esci]')
    if t == '0' or not t: return
    core.progress.spinner_start('Ricerca AnimeClick...')
    res = search_scheda(t)
    core.progress.spinner_stop()
    if not res:
        core.ui.warning('Nessun risultato su AnimeClick.'); core.ui.pause(); return
    items = [{'key':str(i+1),'icon':'','label':r.get('titolo',''),'desc':''}
             for i,r in enumerate(res)]
    c = core.ui.show_menu('Risultati AC', items, show_version=False)
    if c == '0': return
    try: idx=int(c)-1
    except: return
    if 0 <= idx < len(res): _salva(core, res[idx], t)

def _salva(core, res, titolo_ricerca):
    from pathlib import Path
    from scripts.anime.settings_anime import SCHEDE_DIR
    titolo = FileManager.sanitize_folder_name(res.get('titolo', titolo_ricerca))
    d = SCHEDE_DIR / titolo; d.mkdir(parents=True, exist_ok=True)
    fname = titolo+'_animeclick.txt'
    lines = [titolo+' - animeclick', '',
             'Episodi totali: '+str(res.get('episodi_totali','N/D')),
             'Genere: '+str(res.get('genere','N/D')),
             'Trama: '+str(res.get('trama','N/D')),
             'URL scheda: '+str(res.get('url','N/D'))]
    (d/fname).write_text(chr(10).join(lines), encoding='utf-8')
    core.ui.success('Scheda salvata: '+str(d/fname))
    core.ui.pause()
