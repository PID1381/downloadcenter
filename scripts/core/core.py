# scripts/core/core.py
# [MODIFICA run#1] Aggiunto path-guard block
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

from scripts.core.file_manager  import FileManager
from scripts.core.logger        import Logger
from scripts.core.config        import Config
from scripts.core.ui            import UI
from scripts.core.cache         import Cache
from scripts.core.url_manager   import URLManager
from scripts.core.progress      import Progress
from scripts.core.backup        import Backup
from scripts.core.browser       import BrowserManager

_instance = None


class Core:
    """Singleton aggregator: espone tutti i manager del Layer 0."""

    def __init__(self):
        self.file_manager = FileManager()
        self.logger       = Logger()
        self.config       = Config()
        self.ui           = UI()
        self.cache        = Cache()
        self.url_manager  = URLManager()
        self.progress     = Progress()
        self.backup       = Backup()
        self.browser      = BrowserManager()


def get() -> Core:
    """Restituisce l'istanza singleton di Core."""
    global _instance
    if _instance is None:
        _instance = Core()
    return _instance
