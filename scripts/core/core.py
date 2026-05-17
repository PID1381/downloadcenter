from .file_manager import FileManager
from .logger import AppLogger
from .config import ConfigManager
from .cache import CacheManager
from .url_manager import URLManager
from .ui import UIManager
from .progress import ProgressAnimator
from .backup import BackupManager
from .browser import BrowserManager
from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

_instance = None

class Core:
    def __init__(self):
        log_debug("[core/core] → __init__()")
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
        try:
            from scripts.download.core_download import DownloadCore

            self.download = DownloadCore.get()
        except ImportError:
            self.download = None
    @classmethod
    def get(cls):
        log_debug("[core/core] → get()")
        global _instance
        if _instance is None: _instance = cls()
        return _instance
    @classmethod
    def reset(cls):
        log_debug("[core/core] → reset()")
        global _instance; _instance = None
