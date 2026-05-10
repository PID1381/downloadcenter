import os, re
from datetime import datetime
from pathlib import Path
from scripts.core import Core
from scripts.core.file_manager import FileManager
from scripts.anime.settings_anime import SCAN_DIR

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

_VIDEO_EXT = {'.mp4','.mkv','.avi','.m4v','.ts'}

def run():
    log_debug("[Scanlocal/handlers_scanlocal] → run()")
    core = Core.get()
    items = [
        {'key':'1','icon':'','label':'Scansione cartella serie locale','desc':''},
        {'key':'2','icon':'','label':'Visualizza ultimo scan','desc':''},
        {'key':'3','icon':'','label':'Confronta scan con siti web','desc':''},
    ]
    while True:
        c = core.ui.show_menu('Scan serie locale', items)
        if c == '0': return
        elif c == '1': _scansione(core)
        elif c == '2': _visualizza(core)
        elif c == '3': _confronta(core)
        else: core.ui.error('Voce non valida.')

def _ep_nums(filename):
    log_debug("[Scanlocal/handlers_scanlocal] → _ep_nums()")
    nums = re.findall(r'(?<!\d)(\d{1,4})(?!\d)', Path(filename).stem)
    return [int(n) for n in nums if int(n) < 5000]

def _scansione(core):
    log_debug("[Scanlocal/handlers_scanlocal] → _scansione()")
    path = FileManager.clean_path(core.ui.ask_input('Percorso cartella [0=Esci]'))
    if path == '0' or not path: return
    if not Path(path).is_dir():
        core.ui.error('Percorso non valido: '+path); core.ui.pause(); return
    core.progress.spinner_start('Scansione in corso...')
    series = {}
    for root, dirs, files in os.walk(path):
        vf = [f for f in files if Path(f).suffix.lower() in _VIDEO_EXT]
        if not vf: continue
        name = Path(root).name
        ep_found = sorted(set(n for f in vf for n in _ep_nums(f)))
        missing = [i for i in range(ep_found[0], ep_found[-1]+1) if i not in ep_found] if ep_found else []
        series[name] = {'episodes': ep_found, 'missing': missing}
    core.progress.spinner_stop()
    if not series:
        core.ui.warning('Nessuna serie video trovata.'); core.ui.pause(); return
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    for name, data in series.items():
        safe = FileManager.sanitize_folder_name(name)
        sd = SCAN_DIR / (safe+'_'+ts); sd.mkdir(parents=True, exist_ok=True)
        ep_str = '-'.join(str(e) for e in data['episodes']) if data['episodes'] else 'N/D'
        miss_str = ', '.join(str(m) for m in data['missing'])
        suffix = '_EP.MAN..' if data['missing'] else ''
        lines = ['Titolo: '+name,
                 'Totale episodi: '+str(len(data['episodes'])),
                 'Sequenza: '+ep_str]
        if miss_str: lines.append('ATTENZIONE: Episodi mancanti: '+miss_str)
        (sd/(safe+suffix+'.txt')).write_text(chr(10).join(lines), encoding='utf-8')
        core.ui.info(name+' | '+('ATTENZIONE EP MANCANTI: '+miss_str if miss_str else 'OK'))
    core.ui.success('Scan completato.'); core.ui.pause()

def _visualizza(core):
    log_debug("[Scanlocal/handlers_scanlocal] → _visualizza()")
    if not SCAN_DIR.exists() or not list(SCAN_DIR.iterdir()):
        core.ui.info('Nessun scan salvato.'); core.ui.pause(); return
    dirs = sorted(SCAN_DIR.iterdir(), reverse=True)
    items = [{'key':str(i+1),'icon':'','label':d.name,'desc':''} for i,d in enumerate(dirs)]
    c = core.ui.show_menu('Scan salvati', items)
    if c == '0': return
    try: idx=int(c)-1
    except: return
    if 0 <= idx < len(dirs):
        for t in (dirs[idx]).glob('*.txt'):
            core.ui.show_sub_header(t.name)
            print(t.read_text(encoding='utf-8'))
        core.ui.pause()

def _confronta(core):
    log_debug("[Scanlocal/handlers_scanlocal] → _confronta()")
    core.ui.warning('Confronto web - TODO: richiede ricerca globale integrata.')
    core.ui.pause()
