from typing import Dict, Optional
from .file_manager import FileManager
from .settings_core import URLS_FILE

_URLS_DEFAULT = {
    '_meta': 'URL moduli - gestito da URLManager',
    'animeworld':  {'base_url': 'https://www.animeworld.so'},
    'animeunity':  {'base_url': 'https://www.animeunity.to'},
    'animeclick':  {'base_url': 'https://www.animeclick.it'},
    'animesocial': {'base_url': 'https://www.animesaturn.cx'},
}


def _is_legacy(data: dict) -> bool:
    """
    Rileva struttura legacy flat: almeno un valore è str invece di dict.
    Es: {"anime_base": "https://..."} oppure {"animeworld": "https://..."}
    """
    for k, v in data.items():
        if k == '_meta':
            continue
        if isinstance(v, str):
            return True
    return False


def _migrate(data: dict) -> dict:
    """
    Converte struttura legacy → struttura corrente.
    Strategia: ripristina _URLS_DEFAULT preservando eventuali URL
    già presenti nel legacy che corrispondono a moduli noti.

    Mapping legacy → modulo:
      anime_base    → animeworld (base_url)
      manga_base    → (ignorato, non è un modulo video)
      download_base → (ignorato)
      animeworld    → animeworld (base_url)  [se era str diretta]
      animeunity    → animeunity (base_url)
      animeclick    → animeclick (base_url)
      animesocial   → animesocial (base_url)
    """
    import copy
    result = copy.deepcopy(_URLS_DEFAULT)

    LEGACY_MAP = {
        'anime_base':    ('animeworld',  'base_url'),
        'animeworld':    ('animeworld',  'base_url'),
        'animeunity':    ('animeunity',  'base_url'),
        'animeclick':    ('animeclick',  'base_url'),
        'animesocial':   ('animesocial', 'base_url'),
    }

    for legacy_key, url_val in data.items():
        if legacy_key == '_meta':
            continue
        if isinstance(url_val, str) and url_val.startswith('http'):
            if legacy_key in LEGACY_MAP:
                mod, subkey = LEGACY_MAP[legacy_key]
                result[mod][subkey] = url_val
        elif isinstance(url_val, dict):
            # Già formato corretto per questo modulo — preserva
            if legacy_key in result:
                result[legacy_key].update(url_val)

    return result


class URLManager:
    def __init__(self):
        self._file = URLS_FILE
        raw = FileManager.load_json(self._file)
        if not raw:
            raw = dict(_URLS_DEFAULT)
            FileManager.save_json(raw, self._file)
        elif _is_legacy(raw):
            # Struttura legacy su disco: migra e salva
            raw = _migrate(raw)
            FileManager.save_json(raw, self._file)
        self._data: Dict = raw

    def get_url(self, module: str, key: str = 'base_url') -> Optional[str]:
        entry = self._data.get(module)
        if isinstance(entry, dict):
            return entry.get(key)
        return None

    def set_url(self, module: str, key: str, url: str) -> None:
        if not isinstance(self._data.get(module), dict):
            self._data[module] = {}
        self._data[module][key] = url
        FileManager.save_json(self._data, self._file)

    def get_all_modules(self) -> Dict[str, dict]:
        result = {}
        for k, v in self._data.items():
            if k == '_meta':
                continue
            if isinstance(v, dict):
                result[k] = v
            elif isinstance(v, str):
                # Fallback difensivo: non dovrebbe accadere dopo la migrazione
                result[k] = {'base_url': v}
        return result

    def get_module_urls(self, module: str) -> dict:
        entry = self._data.get(module, {})
        return entry if isinstance(entry, dict) else {}

    def get_all_data(self) -> dict:
        return self._data.copy()
