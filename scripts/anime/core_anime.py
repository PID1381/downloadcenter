# scripts/anime/core_anime.py
# [MODIFICA run#1] Aggiunto path-guard
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import json
import os

_ANIME_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anime.json")
_menu_data  = None


def _load() -> dict:
    global _menu_data
    if _menu_data is None:
        with open(_ANIME_JSON, "r", encoding="utf-8") as fh:
            _menu_data = json.load(fh)
    return _menu_data


def get_main_menu() -> dict:
    """Restituisce il dizionario del menu principale anime."""
    return _load().get("main_menu", {})


def get_submenu(key: str) -> dict:
    """Restituisce il sottomenu per la chiave fornita."""
    return _load().get("submenus", {}).get(key, {})


def get_handler_path(key: str) -> str:
    """Restituisce il path del handler associato alla chiave."""
    return _load().get("handlers", {}).get(key, "")
