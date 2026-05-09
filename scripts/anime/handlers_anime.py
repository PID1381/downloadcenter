import importlib
from scripts.core import Core
from scripts.anime.core_anime import AnimeCore


def run():
    core = Core.get()
    ac = AnimeCore.get()
    ac.ensure_dirs()
    core.logger.section('ANIME')
    while True:
        items = [
            {
                'key':  it['key'],
                'icon': '',
                'label': it['label'],
                'desc': it.get('description', ''),
            }
            for it in ac.get_menu()
        ]
        c = core.ui.show_menu('Anime', items)
        if c == '0':
            return
        it = next((x for x in ac.get_menu() if x['key'] == c), None)
        if not it:
            core.ui.error('Voce non valida.')
            continue
        try:
            importlib.import_module(it['handler']).run()
        except ImportError as e:
            msg = (
                f"Modulo '{it['label']}' non disponibile.\n"
                f"Dettaglio: {e}\n"
                "Verifica che tutte le dipendenze siano installate."
            )
            core.logger.error(msg)
            core.ui.error(msg)
            core.ui.pause()
        except Exception as e:
            core.logger.error(str(e))
            core.ui.error(str(e))
            core.ui.pause()
