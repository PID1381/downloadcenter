import importlib
from scripts.core import Core
from scripts.anime.core_anime import AnimeCore

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

def run():
    log_debug("[moduli/handlers_anime_video] → run()")
    core = Core.get()
    ac   = AnimeCore.get()
    while True:
        submenu = ac.get_submenu('anime_video')
        items   = [
            {'key': it['key'], 'icon': '', 'label': it['label'],
             'desc': it.get('description', '')}
            for it in submenu
        ]
        c = core.ui.show_menu('Anime Video', items)
        if c == '0':
            return
        it = next((x for x in submenu if x['key'] == c), None)
        if not it:
            core.ui.error('Voce non valida.')
            continue
        try:
            importlib.import_module(it['handler']).run()
        except ImportError:
            core.ui.error(it['label'] + ' non ancora implementato.')
            core.ui.pause()
        except Exception as e:
            core.logger.error(str(e))
            core.ui.error(str(e))
            core.ui.pause()
