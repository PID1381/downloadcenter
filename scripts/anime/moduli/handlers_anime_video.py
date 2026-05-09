"""
DC3 — handlers_anime_video.py
Dispatcher sottomenu "Anime Video".

BUG-006 FIX (2026-05-09):
  PRIMA: except ImportError → messaggio generico "non ancora implementato"
         anche per handlers_animeworld (571 righe, pienamente implementato)
         quando Playwright o requests non sono installati.
  DOPO : - Verifica dipendenze PRIMA dell'import (fail fast + messaggio chiaro).
         - except ImportError mostra errore reale + hint installazione.
"""
import importlib
from scripts.core import Core
from scripts.anime.core_anime import AnimeCore

# Dipendenze richieste per ogni handler video
_DEPS: dict[str, list[str]] = {
    "scripts.anime.moduli.AnimeWorld.handlers_animeworld":  ["requests", "playwright"],
    "scripts.anime.moduli.AnimeUnity.handlers_animeunity":  ["requests"],
}


def _missing_deps(handler: str) -> list[str]:
    """Ritorna lista di dipendenze non installate per il dato handler."""
    missing = []
    for dep in _DEPS.get(handler, []):
        try:
            importlib.import_module(dep)
        except ImportError:
            missing.append(dep)
    return missing


def _import_error_msg(handler: str, exc: ImportError) -> str:
    """Costruisce messaggio di errore utile per ImportError."""
    deps = _DEPS.get(handler, [])
    if deps:
        hint = f"  → pip install {' '.join(deps)}"
        if "playwright" in deps:
            hint += "\n  → playwright install chromium"
    else:
        hint = f"  → Modulo mancante: {str(exc)}"
    return (
        f"Impossibile caricare {handler.split('.')[-1]}:\n"
        f"  Errore: {exc}\n"
        f"{hint}"
    )


def run():
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

        handler = it['handler']

        # ── Verifica dipendenze PRIMA dell'import (fail fast) ──────────────
        missing = _missing_deps(handler)
        if missing:
            deps_str = ' '.join(missing)
            msg = (
                f"{it['label']}: dipendenze mancanti.\n"
                f"  Esegui: pip install {deps_str}"
            )
            if "playwright" in missing:
                msg += "\n  Poi: playwright install chromium"
            core.ui.error(msg)
            core.ui.pause()
            continue

        # ── Import e lancio ────────────────────────────────────────────────
        try:
            importlib.import_module(handler).run()
        except ImportError as e:
            # BUG-006 FIX: errore reale, non "non ancora implementato"
            core.logger.error(f"ImportError [{handler}]: {e}")
            core.ui.error(_import_error_msg(handler, e))
            core.ui.pause()
        except Exception as e:
            core.logger.error(str(e))
            core.ui.error(str(e))
            core.ui.pause()
