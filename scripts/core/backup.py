import shutil
from datetime import datetime
from pathlib import Path
from .settings_core import TEMP_DIR

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

class BackupManager:
    def __init__(self):
        log_debug("[core/backup] → __init__()")
        self._dir = Path(TEMP_DIR) / 'backups'
        self._dir.mkdir(parents=True, exist_ok=True)
    def backup(self, file_path):
        log_debug("[core/backup] → backup()")
        p = Path(file_path)
        if not p.exists(): return False
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = self._dir / (p.stem + '_' + ts + p.suffix)
        try: shutil.copy2(p, dst); return True
        except: return False
    def list_backups(self, pattern=''):
        log_debug("[core/backup] → list_backups()")
        files = sorted(self._dir.glob('*'+pattern+'*'), reverse=True)
        return [str(x) for x in files]
