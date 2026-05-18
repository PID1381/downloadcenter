import importlib
import re
import textwrap
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
        episodi_in_corso = 0
        try:
            handler_path = AnimeCore.get().get_video_handler(mid)
            if handler_path:
                mod = importlib.import_module(handler_path)
                if hasattr(mod, 'get_show_meta') or hasattr(mod, 'get_episode_count'):
                    core.progress.spinner_start('Recupero metadati...')
                    try:
                        if hasattr(mod, 'get_show_meta'):
                            meta = mod.get_show_meta(url) or {}
                        if hasattr(mod, 'get_episode_count'):
                            episodi_in_corso = int(mod.get_episode_count(url) or 0)
                    finally:
                        core.progress.spinner_stop()
        except Exception:
            meta = {}
            episodi_in_corso = 0
        dati = {
            'titolo':             titolo,
            'episodi_totali':     meta.get('episodi_totali') or res.get('episodi_totali', 0),
            'episodi_in_corso':   episodi_in_corso,
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
    autore = core.ui.ask_input('Autore/Staff opzionale [Invio=salta]')
    all_res = {}
    core.progress.spinner_start('Ricerca schede...')
    try:
        for mid in ac.get_moduli_schede():
            hp = ac.get_schede_handler(mid)
            if not hp:
                continue
            try:
                mod = importlib.import_module(hp)
                try:
                    all_res[mid] = mod.search_scheda(titolo, autore)
                except TypeError:
                    all_res[mid] = mod.search_scheda(titolo)
            except Exception:
                all_res[mid] = []
    finally:
        core.progress.spinner_stop()
    flat = [(mid, r) for mid, res in all_res.items() for r in res]
    if not flat:
        core.ui.warning('Nessuna scheda trovata.')
        core.ui.pause()
        return
    items = [
        {
            'key': str(i + 1),
            'icon': '',
            'label': '[' + f[0] + '] ' + f[1].get('titolo', ''),
            'desc': _desc_scheda(f[1]),
        }
        for i, f in enumerate(flat)
    ]
    while True:
        c = core.ui.show_menu('Schede: ' + titolo, items, show_version=False)
        if c == '0':
            return
        try:
            idx = int(c) - 1
        except ValueError:
            core.ui.error('Voce non valida.')
            continue
        if 0 <= idx < len(flat):
            _dettaglio_scheda(core, flat[idx][1], flat[idx][0], titolo)
        else:
            core.ui.error('Voce non valida.')


def _salva_scheda(core, res, mid, titolo):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _salva_scheda()")
    from pathlib import Path
    from scripts.core.file_manager import FileManager

    handler_path = AnimeCore.get().get_schede_handler(mid)
    if handler_path:
        try:
            mod = importlib.import_module(handler_path)
            if hasattr(mod, 'esporta_scheda'):
                path = mod.esporta_scheda(core, res, titolo)
                core.ui.success('Scheda salvata: ' + str(path))
                return
        except Exception:
            pass

    export = Path(core.config.get_export_dir())
    export.mkdir(parents=True, exist_ok=True)
    fname = _safe_filename(FileManager, res.get('titolo', titolo)) + '_' + mid + '.txt'
    lines = _scheda_lines(res, mid)
    (export / fname).write_text(chr(10).join(lines), encoding='utf-8')
    core.ui.success('Scheda salvata: ' + str(export / fname))


def _safe_filename(file_manager, value):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _safe_filename()")
    safe = file_manager.sanitize_filename(str(value or 'scheda'))
    for char in ('/', '\\', '"'):
        safe = safe.replace(char, '-')
    return safe.strip(' .') or 'scheda'


def _desc_scheda(res):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _desc_scheda()")
    parts = [
        res.get('tipo') or res.get('categoria'),
        res.get('anno'),
        res.get('valutazione_cc'),
    ]
    return ' | '.join(str(p) for p in parts if p and p != 'N/D')


def _carica_dettaglio_scheda(core, res, mid):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _carica_dettaglio_scheda()")
    detail = dict(res or {})
    handler_path = AnimeCore.get().get_schede_handler(mid)
    url = detail.get('url') or detail.get('url_piena')
    if not handler_path or not url:
        return detail
    try:
        mod = importlib.import_module(handler_path)
        if not hasattr(mod, 'get_scheda_details'):
            return detail
        core.progress.spinner_start('Caricamento dettagli scheda...')
        try:
            fetched = mod.get_scheda_details(url) or {}
        finally:
            core.progress.spinner_stop()
        for key, value in fetched.items():
            if value and value != 'N/D':
                detail[key] = value
    except Exception:
        return detail
    return detail


def _scheda_lines(res, mid):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _scheda_lines()")
    fields = [
        ('Titolo', res.get('titolo')),
        ('Titolo originale', res.get('titolo_originale')),
        ('Titolo inglese', res.get('titolo_inglese')),
        ('Categoria', res.get('categoria') or res.get('tipo')),
        ('Genere', res.get('genere')),
        ('Anno', res.get('anno')),
        ('Episodi', res.get('episodi') or res.get('episodi_totali')),
        ('Stato in patria', res.get('stato_in_patria')),
        ('Stato in Italia', res.get('stato_in_italia')),
        ('Valutazione cc', res.get('valutazione_cc')),
        ('Trama', res.get('trama') or res.get('plot')),
        ('URL scheda', res.get('url') or res.get('url_piena')),
    ]
    lines = [str(res.get('titolo', '')) + ' - ' + str(mid), '']
    lines.extend(label + ': ' + str(value or 'N/D') for label, value in fields)
    return lines


def _dettaglio_scheda(core, res, mid, titolo):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _dettaglio_scheda()")
    detail = _carica_dettaglio_scheda(core, res, mid)
    while True:
        core.ui.clear()
        _show_scheda_table(core, detail, mid)
        print()
        core.ui.show_info('E. Esporta scheda')
        core.ui.show_info('0. Esci / Indietro')
        print()
        c = core.ui.ask_input('Scelta').strip().upper()
        if c == '0':
            return
        if c == 'E':
            _salva_scheda(core, detail, mid, titolo)
            core.ui.pause()
            return
        core.ui.error('Voce non valida.')


def _show_scheda_table(core, res, mid):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _show_scheda_table()")
    rows = [
        ('Modulo', _fit_value(mid, 38)),
        ('Titolo', _fit_value(res.get('titolo'), 38)),
        ('Titolo originale', _fit_value(res.get('titolo_originale'), 38)),
        ('Titolo inglese', _fit_value(res.get('titolo_inglese'), 38)),
        ('Categoria', _fit_value(res.get('categoria') or res.get('tipo'), 38)),
        ('Genere', _fit_value(res.get('genere'), 38)),
        ('Anno', _fit_value(res.get('anno'), 38)),
        ('Episodi', _fit_value(res.get('episodi') or res.get('episodi_totali'), 38)),
        ('Stato in patria', _fit_value(res.get('stato_in_patria'), 38)),
        ('Stato in Italia', _fit_value(res.get('stato_in_italia'), 38)),
        ('Valutazione cc', _fit_value(res.get('valutazione_cc'), 38)),
        ('URL scheda', _fit_value(res.get('url') or res.get('url_piena'), 38)),
    ]
    core.ui.show_info_table(res.get('titolo', 'Scheda'), rows)
    core.ui.show_info_table('Trama', _trama_rows(res))


def _trama_rows(res):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _trama_rows()")
    trama = str(res.get('trama') or res.get('plot') or 'N/D').strip()
    lines = textwrap.wrap(trama, width=38) or ['N/D']
    return [('Trama', lines[0])] + [('', line) for line in lines[1:8]]


def _fit_value(value, width):
    log_debug("[ricerca_globale/handlers_ricerca_globale] → _fit_value()")
    text = re.sub(r'\s+', ' ', str(value or 'N/D')).strip()
    return text if len(text) <= width else text[: width - 3] + '...'
