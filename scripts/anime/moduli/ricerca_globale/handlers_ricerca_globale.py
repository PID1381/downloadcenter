import importlib
from scripts.core import Core
from scripts.anime.core_anime import AnimeCore
from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)


def run():
    log_debug("[ricerca_globale/handlers_ricerca_globale] → run()")
    core = Core.get()
    items = [
        {'key': '1', 'icon': '', 'label': 'Ricerca titolo', 'desc': 'Tutti i moduli anime video'},
        {'key': '2', 'icon': '', 'label': 'Ricerca scheda', 'desc': 'Tutti i moduli schede'},
    ]
    while True:
        c = core.ui.show_menu('Ricerca globale', items)
        if c == '0':
            return
        elif c == '1':
            _ricerca_titolo(core)
        elif c == '2':
            _ricerca_scheda(core)
        else:
            core.ui.error('Voce non valida.')


def _ricerca_titolo(core):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _ricerca_titolo()")
    ac = AnimeCore.get()
    titolo = core.ui.ask_input('Titolo [0=Esci]')
    if titolo == '0' or not titolo:
        return
    all_res = {}
    core.progress.spinner_start('Ricerca in corso...')
    for mid in ac.get_moduli_video():
        hp = ac.get_video_handler(mid)
        if not hp:
            continue
        try:
            all_res[mid] = importlib.import_module(hp).search(titolo)
        except Exception:
            all_res[mid] = []
    core.progress.spinner_stop()
    flat = [(mid, r) for mid, res in all_res.items() for r in res]
    if not flat:
        core.ui.warning('Nessun risultato per: ' + titolo)
        core.ui.pause()
        return
    items = [
        {'key': str(i + 1), 'icon': '', 'label': '[' + f[0] + '] ' + f[1].get('titolo', ''),
         'desc': f[1].get('genere', '')}
        for i, f in enumerate(flat)
    ]
    while True:
        c = core.ui.show_menu('Risultati: ' + titolo, items, show_version=False)
        if c == '0':
            return
        try:
            idx = int(c) - 1
        except ValueError:
            core.ui.error('Voce non valida.')
            continue
        if 0 <= idx < len(flat):
            _azioni(core, flat[idx][0], flat[idx][1])


def _azioni(core, mid, res):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _azioni()")
    from scripts.anime.moduli.Utilita.Watchlist.handlers_watchlist import (
        add_in_corso,
        add_finite,
        get_in_corso,
        get_finite,
    )
    items = [
        {'key': 'A', 'icon': '', 'label': 'Watchlist in corso', 'desc': ''},
        {'key': 'B', 'icon': '', 'label': 'Watchlist finite',   'desc': ''},
        {'key': 'C', 'icon': '', 'label': 'Estrai link video',  'desc': ''},
    ]
    c = core.ui.show_menu(res.get('titolo', '?'), items, show_version=False)
    if c == '0':
        return
    cu = c.upper()
    if cu in ('A', 'B'):
        titolo = res.get('titolo', '')
        url    = res.get('url', '')
        # Verifica duplicati
        titolo_norm = titolo.strip().lower()
        url_norm    = url.strip().rstrip('/')
        for item in get_in_corso():
            if item.get('url', '').rstrip('/') == url_norm or item.get('titolo', '').strip().lower() == titolo_norm:
                core.ui.warning(f'"{titolo}" e\' gia\' in Watchlist Serie in corso.')
                core.ui.pause()
                return
        for item in get_finite():
            if item.get('url', '').rstrip('/') == url_norm or item.get('titolo', '').strip().lower() == titolo_norm:
                core.ui.warning(f'"{titolo}" e\' gia\' in Watchlist Serie finite.')
                core.ui.pause()
                return
        # Arricchisce i metadati chiamando get_show_meta() sul modulo sorgente,
        # se disponibile — così genere, episodi_totali e anno vengono popolati
        # anche per titoli aggiunti dalla ricerca globale.
        meta = {}
        try:
            handler_path = AnimeCore.get().get_video_handler(mid)
            if handler_path:
                mod = importlib.import_module(handler_path)
                if hasattr(mod, 'get_show_meta'):
                    core.progress.spinner_start('Recupero metadati...')
                    try:
                        meta = mod.get_show_meta(url) or {}
                    finally:
                        core.progress.spinner_stop()
        except Exception:
            meta = {}
        dati = {
            'titolo':             titolo,
            'episodi_totali':     meta.get('episodi_totali') or res.get('episodi_totali', 0),
            'episodi_in_corso':   0,
            'url':                url,
            'modulo':             res.get('modulo', mid),
            'genere':             meta.get('genere') or res.get('genere', 'N/D'),
            'data_uscita_titolo': meta.get('anno') or res.get('data_uscita_titolo', res.get('anno', 'N/D')),
        }
        if cu == 'A':
            add_in_corso(dati)
            core.ui.success('Aggiunto a Watchlist in corso')
        else:
            add_finite(dati)
            core.ui.success('Aggiunto a Watchlist finite')
    elif cu == 'C':
        url = res.get('url', '')
        if not url:
            core.ui.error('URL non disponibile.')
            core.ui.pause()
            return
        if core.link_extractor:
            core.link_extractor.run(mid, url, res.get('titolo', 'anime'))
        else:
            core.ui.error('link_extractor non disponibile.')
    core.ui.pause()


def _ricerca_scheda(core):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _ricerca_scheda()")
    ac = AnimeCore.get()
    titolo = core.ui.ask_input('Titolo scheda [0=Esci]')
    if titolo == '0' or not titolo:
        return
    all_res = {}
    core.progress.spinner_start('Ricerca schede...')
    for mid in ac.get_moduli_schede():
        hp = ac.get_schede_handler(mid)
        if not hp:
            continue
        try:
            all_res[mid] = importlib.import_module(hp).search_scheda(titolo)
        except Exception:
            all_res[mid] = []
    core.progress.spinner_stop()
    flat = [(mid, r) for mid, res in all_res.items() for r in res]
    if not flat:
        core.ui.warning('Nessuna scheda trovata.')
        core.ui.pause()
        return
    items = [
        {'key': str(i + 1), 'icon': '', 'label': '[' + f[0] + '] ' + f[1].get('titolo', ''), 'desc': ''}
        for i, f in enumerate(flat)
    ]
    c = core.ui.show_menu('Schede: ' + titolo, items, show_version=False)
    if c == '0':
        return
    try:
        idx = int(c) - 1
    except ValueError:
        return
    if 0 <= idx < len(flat):
        _salva_scheda(core, flat[idx][1], flat[idx][0], titolo)


def _salva_scheda(core, res, mid, titolo):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _salva_scheda()")
    from pathlib import Path
    from scripts.core.file_manager import FileManager

    export = Path(core.config.get_export_dir()) / titolo
    export.mkdir(parents=True, exist_ok=True)
    fname = FileManager.sanitize_filename(res.get('titolo', titolo)) + '_' + mid + '.txt'
    lines = [
        res.get('titolo', '') + ' - ' + mid, '',
        'Episodi totali: ' + str(res.get('episodi_totali', 'N/D')),
        'Genere: '         + str(res.get('genere', 'N/D')),
        'Trama: '          + str(res.get('trama', 'N/D')),
        'URL scheda: '     + str(res.get('url', 'N/D')),
    ]
    (export / fname).write_text(chr(10).join(lines), encoding='utf-8')
    core.ui.success('Scheda salvata: ' + str(export / fname))
