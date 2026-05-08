from .settings_core import (
    Colors, Box, PROJECT_NAME, PROJECT_VERSION,
    BASE_DIR, SCRIPTS_DIR, CORE_DIR, TEMP_DIR, VARIE_DIR,
    DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT,
    PREFS_FILE, URLS_FILE, LOG_FILE, CORE_JSON, STARTUP_CHECK_FILE,
)
from .file_manager import FileManager, file_mgr
from .logger import AppLogger, logger
from .config import ConfigManager, config
from .cache import CacheManager
from .url_manager import URLManager
from .ui import UIManager, ui
from .progress import ProgressAnimator
from .backup import BackupManager
from .browser import BrowserManager
from .core import Core
from .startup_check import run_startup_checks
from . import settings_handler
try:
    from .link_extractor import EstrazioneLink
except ImportError:
    EstrazioneLink = None
