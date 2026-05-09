"""
DC3 — handlers_anime.py
Dispatcher principale sezione Anime.

BUG-006 FIX (2026-05-09):
  PRIMA: except ImportError → messaggio generico "non ancora implementato"
         anche per moduli esistenti con dipendenze mancanti (es. Playwright).
  DOPO : except ImportError → mostra il nome del modulo mancante + hint pip.
"""
import importlib
from scripts.core import Core
from scripts.anime.core_anime import AnimeCore

# Dipendenze note per moduli anime (usato nel messaggio di errore)
_KNOWN_DEPS = {
    "scripts.anime.moduli.AnimeWorld.handlers_animeworld":  ["requests", "playwright"],
    "scripts.anime.moduli.AnimeUnity.handlers_animeunity":  ["requests"],
}


def _import_error_msg(handler: str, exc: ImportError) -> str:
    """Costruisce messaggio di errore utile per ImportError."""
    missing_mod = str(exc).replace("No module named ", "").strip("'"")
    deps = _KNOWN_DEPS.get(handler, [])
    if deps:
        hint = f"  → pip install {' '.join(deps)}"
        if "playwright" in deps:
            hint += "\n  → playwright install chromium"
    else:
        hint = f"  → Modulo mancante: {missing_mod}"
    return (
        f"Impossibile caricare {handler.split('.')[-1]}:\n"
        f"  Errore: {exc}\n"
        f"{hint}"
    )


def run():
    core = Core.get()
    ac   = AnimeCore.get()
    ac.ensure_dirs()
    core.logger.section('ANIME')
    while True:
        items = [
            {'key': it['key'], 'icon': '', 'label': it['label'],
             'desc': it.get('description', '')}
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
            # BUG-006 FIX: messaggio utile invece di "non ancora implementato"
            core.logger.error(f"ImportError [{it['handler']}]: {e}")
            core.ui.error(_import_error_msg(it['handler'], e))
            core.ui.pause()
        except Exception as e:
            core.logger.error(str(e))
            core.ui.error(str(e))
            core.ui.pause()
