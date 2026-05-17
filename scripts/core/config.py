import copy
from typing import Any, Dict, List, Optional
from .file_manager import FileManager
from scripts.core.logger import get_logger, log_debug
from .settings_core import (
    PREFS_FILE, CORE_JSON, TEMP_DIR, BASE_DIR,
    DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT, PROJECT_VERSION,
)

logger = get_logger(__name__)

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
        log_debug("[core/config] → __init__()")
        self._pf=pf; self._cj=cj; self._p={}; self._r={}
        self.temp_dir=TEMP_DIR; self.root_dir=BASE_DIR
        self._load(); self._dirs()
    @classmethod
    def _build(cls):
        log_debug("[core/config] → _build()")
        global _inst
        if _inst is None: _inst = cls()
        return _inst
    @classmethod
    def get(cls):        # alias backward-compat → _build()
        log_debug("[core/config] → get()")
        return cls._build()
    def _load(self):
        log_debug("[core/config] → _load()")
        raw = FileManager.load_json(self._pf) or {}
        for s, defs in _DEFAULTS.items():
            raw.setdefault(s, {})
            for k, v in defs.items(): raw[s].setdefault(k, v)
        self._p = raw; self._save()
        self._r = FileManager.load_json(self._cj) or {}
    def _save(self):
        log_debug("[core/config] → _save()")
        FileManager.save_json(self._p, self._pf)
    def _dirs(self):
        log_debug("[core/config] → _dirs()")
        for k, d in [('download_dir', DOWNLOAD_DIR_DEFAULT),
                     ('link_dir', LINK_DIR_DEFAULT),
                     ('export_dir', EXPORT_DIR_DEFAULT)]:
            FileManager.ensure_folder(self._p.get('core', {}).get(k, d))
    def get_pref(self, s, k, default=None):
        log_debug("[core/config] → get_pref()")
        return self._p.get(s, {}).get(k, default)
    def set(self, s, k, v):
        log_debug("[core/config] → set()")
        self._p.setdefault(s, {})[k]=v; self._save()
    def get_all(self, s):
        log_debug("[core/config] → get_all()")
        return self._p.get(s, {}).copy()
    def get_section_prefs(self, s):
        log_debug("[core/config] → get_section_prefs()")
        return self._p.get(s, {}).copy()
    def get_full_prefs(self):
        log_debug("[core/config] → get_full_prefs()")
        return copy.deepcopy(self._p)
    def set_section(self, s, data):
        log_debug("[core/config] → set_section()")
        self._p[s]=data; self._save()
    def get_sections(self):
        log_debug("[core/config] → get_sections()")
        return self._r.get('sections', [])
    def get_enabled_sections(self):
        log_debug("[core/config] → get_enabled_sections()")
        return [x for x in self.get_sections() if x.get('enabled', True)]
    def get_project_info(self):
        log_debug("[core/config] → get_project_info()")
        return self._r.get('project', {})
    def get_settings_menu(self):
        log_debug("[core/config] → get_settings_menu()")
        return self._r.get('settings_menu', {})
    def get_version(self):
        log_debug("[core/config] → get_version()")
        return self._r.get('project', {}).get('version', PROJECT_VERSION)
    def is_debug(self):
        log_debug("[core/config] → is_debug()")
        return bool(self._p.get('core', {}).get('debug_mode', False))
    def is_headless(self):
        log_debug("[core/config] → is_headless()")
        return bool(self._p.get('core', {}).get('headless_browser', True))
    def get_timeout(self):
        log_debug("[core/config] → get_timeout()")
        return int(self._p.get('core', {}).get('timeout_navigation', 30))
    def get_download_dir(self):
        log_debug("[core/config] → get_download_dir()")
        return self._p.get('core', {}).get('download_dir', DOWNLOAD_DIR_DEFAULT)
    def get_link_dir(self):
        log_debug("[core/config] → get_link_dir()")
        return self._p.get('core', {}).get('link_dir', LINK_DIR_DEFAULT)
    def get_export_dir(self):
        log_debug("[core/config] → get_export_dir()")
        return self._p.get('core', {}).get('export_dir', EXPORT_DIR_DEFAULT)
    def set_dir(self, key, path):
        log_debug("[core/config] → set_dir()")
        if key not in ('download_dir', 'link_dir', 'export_dir'):
            raise ValueError('Chiave non valida: ' + key)
        self.set('core', key, path); FileManager.ensure_folder(path)

config = ConfigManager._build()
