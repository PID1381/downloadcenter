import os as _os, sys as _sys
# ── PATH GUARD (BUG-006/007B) ─────────────────────────────────────────────
_BASE_DIR = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _BASE_DIR not in _sys.path:
    _sys.path.insert(0, _BASE_DIR)
# ──────────────────────────────────────────────────────────────────────────

import importlib
from scripts.core import Core
from scripts.anime.core_anime import AnimeCore

def run():
    core = Core.get(); ac = AnimeCore.get()
    submenu = ac.get_submenu('utilita')
    while True:
        items = [{'key':it['key'],'icon':'','label':it['label'],
                  'desc':it.get('description','')} for it in submenu]
        c = core.ui.show_menu('Utilita', items)
        if c == '0': return
        it = next((x for x in submenu if x['key']==c), None)
        if not it: core.ui.error('Voce non valida.'); continue
        try: importlib.import_module(it['handler']).run()
        except ImportError:
            core.ui.error(it['label']+' non ancora implementato.'); core.ui.pause()
        except Exception as e: core.ui.error(str(e)); core.ui.pause()
