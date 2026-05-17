from pathlib import Path

from scripts.core import Core
from scripts.core.file_manager import FileManager
from scripts.core.logger import get_logger, log_debug
from scripts.download.core_download import DownloadCore

logger = get_logger(__name__)

MODULE_KEY = 'download'
MODULE_NAME = 'Download'


def _pause_continue(core):
    core.ui.pause()
    core.ui.clear()


def _format_duration(seconds) -> str:
    try:
        total = int(seconds or 0)
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        return 'N/D'
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def _download_single(core, dc: DownloadCore) -> None:
    log_debug("[download/handlers_download] → _download_single()")
    url = core.ui.ask_input('URL video [0=annulla]')
    if url == '0' or not url:
        return
    core.progress.spinner_start('Download video...')
    try:
        result = dc.download_url(core, url)
    finally:
        core.progress.spinner_stop()
    if result.get('ok'):
        paths = result.get('paths') or []
        msg = 'Download completato.'
        if paths:
            msg += '\n' + '\n'.join(paths)
        core.ui.show_success(msg)
    else:
        core.ui.warning('Download non completato: ' + result.get('error', 'errore sconosciuto'))
    core.ui.pause()


def _show_info(core, dc: DownloadCore) -> None:
    log_debug("[download/handlers_download] → _show_info()")
    url = core.ui.ask_input('URL video [0=annulla]')
    if url == '0' or not url:
        return
    core.progress.spinner_start('Lettura informazioni video...')
    try:
        info = dc.get_info(core, url)
    finally:
        core.progress.spinner_stop()
    if not info:
        core.ui.warning('Nessuna informazione disponibile per questo URL.')
        core.ui.pause()
        return
    rows = [
        ('Titolo', info.get('title') or 'N/D'),
        ('ID', info.get('id') or 'N/D'),
        ('Sorgente', info.get('extractor') or 'N/D'),
        ('Durata', _format_duration(info.get('duration'))),
        ('Formati', str(info.get('formats_count') or 0)),
        ('Playlist items', str(info.get('playlist_count') or 0)),
        ('URL', info.get('webpage_url') or url),
    ]
    core.ui.show_info_table('Informazioni video', rows)
    core.ui.pause()


def _download_from_file(core, dc: DownloadCore) -> None:
    log_debug("[download/handlers_download] → _download_from_file()")
    path = FileManager.clean_path(core.ui.ask_input('File URL [0=annulla]'))
    if path == '0' or not path:
        return
    urls = FileManager.load_urls_from_file(path)
    if not urls:
        core.ui.warning('Nessun URL valido trovato nel file.')
        core.ui.pause()
        return
    core.progress.spinner_start(f'Download lista URL ({len(urls)})...')
    try:
        results = dc.download_urls(core, urls)
    finally:
        core.progress.spinner_stop()
    ok = [r for r in results if r.get('ok')]
    ko = [r for r in results if not r.get('ok')]
    core.ui.show_info_table(
        'Riepilogo download',
        [('Completati', str(len(ok))), ('Falliti', str(len(ko)))]
    )
    core.ui.pause()


def _pending_downloads(core, dc: DownloadCore) -> None:
    log_debug("[download/handlers_download] → _pending_downloads()")
    while True:
        pending = dc.get_pending_downloads()
        if not pending:
            core.ui.info('Nessun download pendente.')
            core.ui.pause()
            return
        items = [
            {
                'key': str(i + 1),
                'icon': '',
                'label': (item.get('url') or 'URL non disponibile')[:45],
                'desc': item.get('status', 'pendente'),
            }
            for i, item in enumerate(pending)
        ]
        items.extend([
            {'key': 'R', 'icon': '', 'label': 'Riprendi tutti', 'desc': str(len(pending)) + ' pendenti'},
            {'key': 'C', 'icon': '', 'label': 'Svuota lista pendenti', 'desc': 'non elimina file .part'},
        ])
        c = core.ui.show_menu('Download pendenti', items, show_version=False)
        if c == '0':
            return
        if c == 'R':
            core.progress.spinner_start('Ripresa download pendenti...')
            try:
                results = dc.resume_all_pending(core)
            finally:
                core.progress.spinner_stop()
            ok = [r for r in results if r.get('ok')]
            ko = [r for r in results if not r.get('ok')]
            core.ui.show_info_table('Ripresa download', [('Completati', str(len(ok))), ('Falliti', str(len(ko)))])
            core.ui.pause()
            continue
        if c == 'C':
            conferma = core.ui.ask_input('Svuotare lista pendenti? (s/N)', 'N')
            if conferma.strip().lower() == 's':
                dc.clear_pending()
                core.ui.show_success('Lista pendenti svuotata.')
                core.ui.pause()
                return
            core.ui.info('Operazione annullata.')
            core.ui.pause()
            continue
        try:
            idx = int(c) - 1
        except ValueError:
            core.ui.error('Voce non valida.')
            core.ui.pause()
            continue
        if not (0 <= idx < len(pending)):
            core.ui.error('Voce non valida.')
            core.ui.pause()
            continue
        item = pending[idx]
        rows = [
            ('Stato', item.get('status', '')),
            ('Modulo', item.get('module_id', '')),
            ('Output dir', item.get('output_dir', '')),
            ('Aggiornato', item.get('updated_at', '')),
            ('Errore', item.get('error', '')),
            ('URL', item.get('url', '')),
        ]
        core.ui.show_info_table('Dettaglio pendente', rows)
        scelta = core.ui.ask_input('Riprendere questo download? (s/N)', 'N')
        if scelta.strip().lower() != 's':
            continue
        core.progress.spinner_start('Ripresa download...')
        try:
            result = dc.resume_pending(core, item.get('id', ''))
        finally:
            core.progress.spinner_stop()
        if result.get('ok'):
            core.ui.show_success('Download completato.')
        else:
            core.ui.warning('Download non completato: ' + result.get('error', 'errore sconosciuto'))
        core.ui.pause()


def _settings(core, dc: DownloadCore) -> None:
    log_debug("[download/handlers_download] → _settings()")
    from scripts.download.moduli.YTDLP import core_ytdlp

    while True:
        settings = dc.get_settings()
        info_rows = [
            ('Modulo predefinito', dc.get_default_module()),
            ('Output dir', dc.get_output_dir(core)),
            ('yt-dlp disponibile', 'SI' if core_ytdlp.is_available() else 'NO'),
        ]
        items = [
            {'key': '1', 'icon': '', 'label': 'Cambia cartella output', 'desc': ''},
            {'key': '2', 'icon': '', 'label': 'Cambia formato yt-dlp', 'desc': 'format selector'},
            {'key': '3', 'icon': '', 'label': 'Cambia cookies file', 'desc': 'Netscape cookies'},
        ]
        c = core.ui.show_menu('Impostazioni Download', items, show_version=False, info_rows=info_rows)
        if c == '0':
            return
        if c == '1':
            current = dc.get_output_dir(core)
            path = FileManager.clean_path(core.ui.ask_input('Cartella output', current))
            if path:
                Path(path).mkdir(parents=True, exist_ok=True)
                dc.set_output_dir(path)
                core.ui.show_success('Cartella output aggiornata.')
                core.ui.pause()
        elif c == '2':
            fmt = core.ui.ask_input('Formato yt-dlp', 'bestvideo+bestaudio/best')
            if fmt:
                core_ytdlp.update_option('format', fmt)
                core.ui.show_success('Formato yt-dlp aggiornato.')
                core.ui.pause()
        elif c == '3':
            cookies = FileManager.clean_path(core.ui.ask_input('Percorso cookies.txt [vuoto=disabilita]', ''))
            core_ytdlp.set_cookies_file(cookies)
            core.ui.show_success('Cookies file aggiornato.')
            core.ui.pause()
        else:
            core.ui.error('Voce non valida.')
            core.ui.pause()


def run() -> None:
    log_debug("[download/handlers_download] → run()")
    core = Core.get()
    dc = DownloadCore.get()
    items = [
        {'key': '1', 'icon': '', 'label': 'Scarica video da URL', 'desc': 'yt-dlp'},
        {'key': '2', 'icon': '', 'label': 'Informazioni URL', 'desc': 'metadata senza download'},
        {'key': '3', 'icon': '', 'label': 'Scarica lista URL da file', 'desc': 'uno per riga'},
        {'key': '4', 'icon': '', 'label': 'Download pendenti', 'desc': 'stop/resume'},
        {'key': '5', 'icon': '', 'label': 'Impostazioni Download', 'desc': 'output, formato, cookies'},
    ]
    while True:
        c = core.ui.show_menu(MODULE_NAME, items)
        if c == '0':
            return
        try:
            if c == '1':
                _download_single(core, dc)
            elif c == '2':
                _show_info(core, dc)
            elif c == '3':
                _download_from_file(core, dc)
            elif c == '4':
                _pending_downloads(core, dc)
            elif c == '5':
                _settings(core, dc)
            else:
                core.ui.error('Voce non valida.')
        except KeyboardInterrupt:
            core.progress.spinner_stop()
            core.ui.warning('Operazione interrotta dall\'utente.')
            core.ui.pause()


def show_menu() -> None:
    run()


def run_pending_downloads() -> None:
    log_debug("[download/handlers_download] → run_pending_downloads()")
    core = Core.get()
    _pending_downloads(core, DownloadCore.get())
