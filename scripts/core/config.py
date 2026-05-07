from typing import Any, Dict, List, Optional
from .file_manager import FileManager

_PREFS_DEFAULT: Dict = {
    "core": {
        "theme": "default",
        "last_section": None,
        "clear_screen": True,
        "show_descriptions": True
    },
    "main_menu": {
        "show_version": True
    },
    "anime": {
        "default_quality": "1080p",
        "download_path": "",
        "subtitles": True,
        "subtitles_lang": "it",
        "auto_next": False,
        "preferred_source": None
    },
    "manga": {
        "download_path": "",
        "output_format": "cbz",
        "auto_next_chapter": False,
        "preferred_source": None
    },
    "download": {
        "default_path": "",
        "max_concurrent": 3,
        "overwrite": False,
        "notify_on_complete": True
    }
}

_instance: Optional["ConfigManager"] = None


class ConfigManager:
    def __init__(self, prefs_file: str, core_json: str):
        self._prefs_file = prefs_file
        self._core_json  = core_json
        self._prefs:    Dict = {}
        self._registry: Dict = {}
        self._load()

    @classmethod
    def get(cls) -> "ConfigManager":
        global _instance
        if _instance is None:
            from .settings_core import PREFS_FILE, CORE_JSON
            _instance = cls(PREFS_FILE, CORE_JSON)
        return _instance

    def _load(self):
        self._prefs = FileManager.read_json(self._prefs_file, {})
        for section, defaults in _PREFS_DEFAULT.items():
            if section not in self._prefs:
                self._prefs[section] = defaults.copy()
            else:
                for k, v in defaults.items():
                    self._prefs[section].setdefault(k, v)
        self._save()
        self._registry = FileManager.read_json(self._core_json, {})

    def _save(self):
        FileManager.write_json(self._prefs_file, self._prefs)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._prefs.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any):
        self._prefs.setdefault(section, {})[key] = value
        self._save()

    def get_all(self, section: str) -> Dict:
        return self._prefs.get(section, {}).copy()

    def get_section_prefs(self, section: str) -> Dict:
        return self._prefs.get(section, {}).copy()

    def get_full_prefs(self) -> Dict:
        import copy
        return copy.deepcopy(self._prefs)

    def set_section(self, section: str, data: Dict):
        self._prefs[section] = data
        self._save()

    def get_sections(self) -> List[Dict]:
        return self._registry.get("sections", [])

    def get_enabled_sections(self) -> List[Dict]:
        return [s for s in self.get_sections() if s.get("enabled", True)]

    def get_project_info(self) -> Dict:
        return self._registry.get("project", {})

    def get_settings_menu(self) -> Dict:
        return self._registry.get("settings_menu", {})
