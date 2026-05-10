# scripts/anime/moduli/ricerca_globale/handlers_ricerca_globale.py
# [MODIFICA run#1] Aggiunto path-guard + try/except per import provider parziali
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(
        _os.path.dirname(
            _os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__))
            )
        )
    )
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

from scripts.core.settings_core import colorize

_providers = {}

try:
    from scripts.anime.moduli.AnimeWorld import handlers_animeworld as _aw
    _providers["AnimeWorld"] = _aw
except ImportError as _e:
    print(colorize(f"[AVVISO] AnimeWorld non disponibile: {_e}", "yellow"))

try:
    from scripts.anime.moduli.AnimeUnity import handlers_animeunity as _au
    _providers["AnimeUnity"] = _au
except ImportError as _e:
    print(colorize(f"[AVVISO] AnimeUnity non disponibile: {_e}", "yellow"))


def _display_global_results(results: dict) -> None:
    if not results:
        print(colorize("Nessun risultato trovato.", "yellow"))
        return
    for provider, links in results.items():
        print(colorize(f"\n── {provider} ──", "cyan"))
        if links:
            for i, lnk in enumerate(links, 1):
                print(f"  {i}) {lnk}")
        else:
            print("  (nessun risultato)")


def run() -> None:
    """Ricerca globale su tutti i provider disponibili."""
    if not _providers:
        print(colorize("[ERRORE] Nessun provider disponibile.", "red"))
        return

    query = input("Titolo da cercare (ricerca globale): ").strip()
    if not query:
        return

    results = {}
    for name, mod in _providers.items():
        if hasattr(mod, "search_anime"):
            results[name] = mod.search_anime(query)
        else:
            results[name] = []

    _display_global_results(results)
