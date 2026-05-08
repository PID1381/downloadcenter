import logging, traceback
from pathlib import Path
from typing import Optional
from .settings_core import LOG_FILE, TEMP_DIR

class AppLogger:
    _instance = None; _log = None
    def __new__(cls):
        if cls._instance is None: cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self):
        if self._log is not None: return
        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
        self._log = logging.getLogger('DownloadCenter')
        self._log.setLevel(logging.DEBUG)
        if not self._log.handlers:
            fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
            fh.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(module)s: %(message)s'))
            self._log.addHandler(fh)
    def section(self, n): self.info('--- ' + n + ' ---')
    def info(self, m, mod=''):
        if self._log: self._log.info(('['+mod+'] '+m) if mod else m)
    def error(self, m, mod='', exc=None):
        if self._log:
            self._log.error(('['+mod+'] '+m) if mod else m)
            if exc: self._log.error(traceback.format_exc())
    def warning(self, m, mod=''):
        if self._log: self._log.warning(('['+mod+'] '+m) if mod else m)
    def debug(self, m, mod=''):
        if self._log: self._log.debug(('['+mod+'] '+m) if mod else m)
    def dump_html(self, filename, content):
        d = Path(TEMP_DIR) / 'debug'; d.mkdir(parents=True, exist_ok=True)
        try: (d / filename).write_text(content, encoding='utf-8')
        except: pass

logger = AppLogger()
