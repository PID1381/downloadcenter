# Core package v2.0
from .config import config
from .ui import ui
from .logger import logger
from .file_manager import file_mgr
from .progress import progress
from .browser import browser_mgr
from .state import DownloadState, watchlist_state
from .cache import cache_mgr
from .backup import backup_mgr

__all__ = [
    "config", "ui", "logger", "file_mgr", "progress", "browser_mgr",
    "DownloadState", "watchlist_state", "cache_mgr", "backup_mgr"
]
