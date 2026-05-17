import json, logging, traceback
from pathlib import Path
from typing import Optional
from .settings_core import LOG_FILE, PREFS_FILE, TEMP_DIR


def _is_debug_on() -> bool:
    """Legge debug_mode direttamente da prefs.json senza passare da ConfigManager."""
    try:
        with open(PREFS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh) or {}
        return bool(data.get('core', {}).get('debug_mode', False))
    except Exception:
        return False


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
        """Scrive solo se debug_mode è ON in ConfigManager."""
        if self._log and _is_debug_on():
            self._log.debug(('['+mod+'] '+m) if mod else m)
    def dump_html(self, filename, content):
        """Salva HTML di debug solo se debug_mode è ON."""
        if not _is_debug_on():
            return
        d = Path(TEMP_DIR) / 'debug'; d.mkdir(parents=True, exist_ok=True)
        try: (d / filename).write_text(content, encoding='utf-8')
        except: pass

logger = AppLogger()

def get_logger(name: str = __name__):
    """Restituisce il logger singleton (compatibilità con get_logger pattern)."""
    return logger

def log_debug(msg: str, mod: str = ""):
    """Scrive msg come debug tramite il logger singleton."""
    logger.debug(msg, mod)
