import copy
from typing import Any, Dict, List, Optional
from .file_manager import FileManager
from .settings_core import (
    PREFS_FILE, CORE_JSON, TEMP_DIR, BASE_DIR,
    DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT, PROJECT_VERSION,
)

_DEFAULTS: Dict = {
    'core': {
        'theme': 'default', 'last_section': None, 'clear_screen': True,
        'show_descriptions': True, 'debug_mode': False, 'headless_browser': True,
        'download_dir': DOWNLOAD_DIR_DEFAULT, 'link_dir': LINK_DIR_DEFAULT,
        'export_dir': EXPORT_DIR_DEFAULT, 'timeout_navigation': 30,
    },
    'main_menu': {'show_version': True},
    'anime': {
        'default_quality': '1080p', 'download_path': '', 'subtitles': True,
        'subtitles_lang': 'it', 'auto_next': False, 'preferred_source': None,
    },
    'manga': {'download_path': '', 'output_format': 'cbz',
              'auto_next_chapter': False, 'preferred_source': None},
    'download': {'default_path': '', 'max_concurrent': 3,
                 'overwrite': False, 'notify_on_complete': True},
}
_inst: Optional['ConfigManager'] = None

class ConfigManager:
    def __init__(self, pf=PREFS_FILE, cj=CORE_JSON):
        self._pf=pf; self._cj=cj; self._p={}; self._r={}
        self.temp_dir=TEMP_DIR; self.root_dir=BASE_DIR
        self._load(); self._dirs()
    @classmethod
    def get(cls):
        global _inst
        if _inst is None: _inst = cls()
        return _inst
    def _load(self):
        raw = FileManager.load_json(self._pf) or {}
        for s, defs in _DEFAULTS.items():
            raw.setdefault(s, {})
            for k, v in defs.items(): raw[s].setdefault(k, v)
        self._p = raw; self._save()
        self._r = FileManager.load_json(self._cj) or {}
    def _save(self): FileManager.save_json(self._p, self._pf)
    def _dirs(self):
        for k, d in [('download_dir', DOWNLOAD_DIR_DEFAULT),
                     ('link_dir', LINK_DIR_DEFAULT),
                     ('export_dir', EXPORT_DIR_DEFAULT)]:
            FileManager.ensure_folder(self._p.get('core', {}).get(k, d))
    def get(self, s, k, default=None): return self._p.get(s, {}).get(k, default)
    def set(self, s, k, v): self._p.setdefault(s, {})[k]=v; self._save()
    def get_all(self, s): return self._p.get(s, {}).copy()
    def get_section_prefs(self, s): return self._p.get(s, {}).copy()
    def get_full_prefs(self): return copy.deepcopy(self._p)
    def set_section(self, s, data): self._p[s]=data; self._save()
    def get_sections(self): return self._r.get('sections', [])
    def get_enabled_sections(self):
        return [x for x in self.get_sections() if x.get('enabled', True)]
    def get_project_info(self): return self._r.get('project', {})
    def get_settings_menu(self): return self._r.get('settings_menu', {})
    def get_version(self):
        return self._r.get('project', {}).get('version', PROJECT_VERSION)
    def is_debug(self): return bool(self._p.get('core', {}).get('debug_mode', False))
    def is_headless(self): return bool(self._p.get('core', {}).get('headless_browser', True))
    def get_timeout(self): return int(self._p.get('core', {}).get('timeout_navigation', 30))
    def get_download_dir(self):
        return self._p.get('core', {}).get('download_dir', DOWNLOAD_DIR_DEFAULT)
    def get_link_dir(self):
        return self._p.get('core', {}).get('link_dir', LINK_DIR_DEFAULT)
    def get_export_dir(self):
        return self._p.get('core', {}).get('export_dir', EXPORT_DIR_DEFAULT)
    def set_dir(self, key, path):
        if key not in ('download_dir', 'link_dir', 'export_dir'):
            raise ValueError('Chiave non valida: ' + key)
        self.set('core', key, path); FileManager.ensure_folder(path)

config = ConfigManager.get()
