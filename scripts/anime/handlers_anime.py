from scripts.core import Core
from scripts.core.dispatcher import run_configured_handler
from scripts.anime.core_anime import AnimeCore

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

def run():
    log_debug("[anime/handlers_anime] → run()")
    core = Core.get(); ac = AnimeCore.get()
    ac.ensure_dirs()
    core.logger.section('ANIME')
    while True:
        items = [{'key':it['key'],'icon':'','label':it['label'],
                  'desc':it.get('description','')} for it in ac.get_menu()]
        c = core.ui.show_menu('Anime', items)
        if c == '0': return
        it = next((x for x in ac.get_menu() if x['key']==c), None)
        if not it: core.ui.error('Voce non valida.'); continue
        try: run_configured_handler(core, it)
        except KeyboardInterrupt:
            core.progress.spinner_stop()
            core.ui.warning('Operazione interrotta dall\'utente.')
            core.ui.pause()
        except Exception as e:
            core.logger.error(str(e)); core.ui.error(str(e)); core.ui.pause()
