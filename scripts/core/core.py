from .file_manager import FileManager
from .logger import AppLogger
from .config import ConfigManager
from .cache import CacheManager
from .url_manager import URLManager
from .ui import UIManager
from .progress import ProgressAnimator
from .backup import BackupManager
from .browser import BrowserManager

_instance = None

class Core:
    def __init__(self):
        self.file_manager = FileManager()
        self.logger       = AppLogger()
        self.config       = ConfigManager._build()
        self.cache        = CacheManager()
        self.url_manager  = URLManager()
        self.ui           = UIManager()
        self.progress     = ProgressAnimator()
        self.backup       = BackupManager()
        self.browser      = BrowserManager()
        try:
            from .link_extractor import EstrazioneLink
            self.link_extractor = EstrazioneLink()
        except ImportError:
            self.link_extractor = None
    @classmethod
    def get(cls):
        global _instance
        if _instance is None: _instance = cls()
        return _instance
    @classmethod
    def reset(cls):
        global _instance; _instance = None
