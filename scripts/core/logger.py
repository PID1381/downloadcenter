"""
Core Logger Module v2.0
Logging strutturato centralizzato su file.
"""
import logging
import traceback
from pathlib import Path
from typing import Optional


class AppLogger:
    """Logging strutturato per Download Center."""
    _instance = None
    _log      = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._log is not None:
            return
        self._setup()

    def _setup(self) -> None:
        try:
            from .config import config
            log_dir = config.temp_dir
        except Exception:
            log_dir = Path("scripts/temp")
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log = logging.getLogger("DownloadCenter")
        self._log.setLevel(logging.DEBUG)
        if not self._log.handlers:
            fh = logging.FileHandler(str(log_dir / "app.log"), encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(module)s: %(message)s"))
            self._log.addHandler(fh)

    def _pfx(self, module: str) -> str:
        return f"[{module}] " if module else ""

    def info(self, msg: str, module: str = "") -> None:
        if self._log: self._log.info(self._pfx(module) + msg)

    def error(self, msg: str, module: str = "",
              exc: Optional[Exception] = None) -> None:
        if self._log:
            self._log.error(self._pfx(module) + msg)
            if exc: self._log.error(traceback.format_exc())

    def debug(self, msg: str, module: str = "") -> None:
        try:
            from .config import config
            if config.is_debug() and self._log:
                self._log.debug(self._pfx(module) + msg)
        except Exception:
            pass

    def warning(self, msg: str, module: str = "") -> None:
        if self._log: self._log.warning(self._pfx(module) + msg)


logger = AppLogger()
