"""
Core Configuration Manager v2.0
Unico punto di gestione preferenze dell'applicazione.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Singleton per gestione preferenze centralizzata."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.root_dir    = Path(__file__).parent.parent.parent.resolve()
        self.scripts_dir = self.root_dir / "scripts"
        self.temp_dir    = self.scripts_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.prefs_file  = self.temp_dir / "prefs.json"
        self.version     = "2.0.0"
        self.default_prefs: Dict[str, Any] = {
            "default_download_dir":   str(self.root_dir / "downloads"),
            "default_link_dir":       str(self.root_dir / "link_estratti"),
            "default_export_dir":     str(self.root_dir / "export"),
            "browser_headless":       True,
            "timeout_navigation":     30,
            "first_run":              True,
            "last_manga_export_path": "",
            "debug_mode":             False,
            "last_path":              "",
            "manga_last_first":       None,
            "last_startup_check":     "",  # NUOVO: Timestamp dell'ultimo check (ISO format)
        }
        self.prefs = self._load()
        self._initialized = True

    def _load(self) -> Dict[str, Any]:
        if self.prefs_file.exists():
            try:
                with open(self.prefs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {**self.default_prefs, **data}
            except Exception as e:
                print(f"  Errore caricamento prefs: {e}")
        return dict(self.default_prefs)

    def save(self) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.prefs_file, "w", encoding="utf-8") as f:
                json.dump(self.prefs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  Errore salvataggio prefs: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.prefs.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.prefs[key] = value
        self.save()

    def get_download_dir(self) -> Path:      return Path(self.get("default_download_dir"))
    def get_link_dir(self) -> Path:          return Path(self.get("default_link_dir"))
    def get_export_dir(self) -> Path:        return Path(self.get("default_export_dir"))
    def is_headless(self) -> bool:           return bool(self.get("browser_headless", True))
    def get_timeout(self) -> int:            return int(self.get("timeout_navigation", 30))
    def is_debug(self) -> bool:              return bool(self.get("debug_mode", False))
    def is_first_run(self) -> bool:          return bool(self.get("first_run", True))
    def get_last_path(self) -> str:          return str(self.get("last_path", ""))
    def set_last_path(self, p: str) -> None: self.set("last_path", p)

    def get_manga_last_first(self) -> Optional[Dict]:
        return self.get("manga_last_first")

    def set_manga_last_first(self, article: Dict) -> None:
        self.set("manga_last_first", {
            "titolo": article.get("titolo", ""),
            "link":   article.get("link",   ""),
        })

    def ensure_directories(self) -> None:
        """Crea tutte le directory necessarie."""
        for key in ("default_download_dir", "default_link_dir", "default_export_dir"):
            Path(self.get(key)).mkdir(parents=True, exist_ok=True)
        for d in (self.scripts_dir / "anime", self.scripts_dir / "manga",
                  self.scripts_dir / "download", self.temp_dir):
            d.mkdir(parents=True, exist_ok=True)

    def reset_to_defaults(self) -> None:
        self.prefs = dict(self.default_prefs)
        self.save()


config = ConfigManager()
