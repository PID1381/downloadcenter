import time, importlib
from .file_manager import FileManager
from .settings_core import STARTUP_CHECK_FILE

_DEPS = [
    ('playwright', 'playwright'),
    ('requests',   'requests'),
    ('bs4',        'beautifulsoup4'),
    ('yt_dlp',     'yt-dlp'),
    ('rich',       'rich'),
]

def run_startup_checks(force=False):
    from .core import Core
    core = Core.get(); ui = core.ui
    data = FileManager.load_json(STARTUP_CHECK_FILE) or {}
    last = data.get('last_check', 0)
    if not force and (time.time() - last) < 86400: return False
    ui.clear()
    ui.print_startup_header()
    missing = []
    ui.print_section_label('Dipendenze Python')
    for mod, pkg in _DEPS:
        try: importlib.import_module(mod); ui.print_check_row(pkg, True)
        except ImportError: ui.print_check_row(pkg, False); missing.append(pkg)
    ui.print_section_label('Download pendenti')
    pending = data.get('pending_downloads', [])
    if pending: ui.print_check_row(str(len(pending))+' download in sospeso', None)
    else: ui.print_check_row('Nessun download pendente', True)
    ui.print_section_label('Pulizia cache')
    removed = core.cache.cleanup()
    ui.print_check_row('Cache: '+str(removed)+' elementi rimossi', True)
    if missing:
        ui.print_section_label('Attenzione')
        ui.print_check_row('Mancanti: '+', '.join(missing), False)
        ui.print_check_row('pip install '+' '.join(missing), None)
    data['last_check'] = time.time()
    FileManager.save_json(data, STARTUP_CHECK_FILE)
    ui.print_startup_footer()
    return True
