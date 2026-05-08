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

class URLManager:
    def __init__(self):
        self._file = URLS_FILE
        raw = FileManager.load_json(self._file)
        if not raw:
            raw = dict(_URLS_DEFAULT)
            FileManager.save_json(raw, self._file)
        self._data: Dict = raw
    def get_url(self, module, key='base_url'):
        return self._data.get(module, {}).get(key)
    def set_url(self, module, key, url):
        self._data.setdefault(module, {})[key] = url
        FileManager.save_json(self._data, self._file)
    def get_all_modules(self):
        return {k: v for k, v in self._data.items() if k != '_meta'}
    def get_module_urls(self, module): return self._data.get(module, {})
    def get_all_data(self): return self._data.copy()
