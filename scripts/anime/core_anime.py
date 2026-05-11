from scripts.core.file_manager import FileManager
from scripts.anime.settings_anime import ANIME_JSON, SCHEDE_DIR, SCAN_DIR, LINK_COMPL_DIR
from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)


_inst = None

class AnimeCore:
    def __init__(self):
        log_debug("[anime/core_anime] → __init__()")
        self._data = FileManager.load_json(str(ANIME_JSON)) or {}
        self._menu = self._data.get('menu', [])
        self._mv   = self._data.get('moduli_video', [])
        self._ms   = self._data.get('moduli_schede', [])
        self._mvh  = self._data.get('moduli_video_handlers', {})
        self._msh  = self._data.get('moduli_schede_handlers', {})
    @classmethod
    def get(cls):
        log_debug("[anime/core_anime] → get()")
        global _inst
        if _inst is None: _inst = cls()
        return _inst
    def get_menu(self):
        log_debug("[anime/core_anime] → get_menu()")
        return self._menu
    def get_submenu(self, parent_id):
        log_debug("[anime/core_anime] → get_submenu()")
        for it in self._menu:
            if it.get('id') == parent_id: return it.get('submenu', [])
        return []
    def get_moduli_video(self):
        log_debug("[anime/core_anime] → get_moduli_video()")
        return self._mv
    def get_moduli_schede(self):
        log_debug("[anime/core_anime] → get_moduli_schede()")
        return self._ms
    def get_video_handler(self, mid):
        log_debug("[anime/core_anime] → get_video_handler()")
        return self._mvh.get(mid)
    def get_schede_handler(self, mid):
        log_debug("[anime/core_anime] → get_schede_handler()")
        return self._msh.get(mid)
    def get_menu_item(self, item_id):
        log_debug("[anime/core_anime] → get_menu_item()")
        def _s(items):
            log_debug("[anime/core_anime] → _s()")
            for it in items:
                if it.get('id')==item_id: return it
                found = _s(it.get('submenu',[]))
                if found: return found
            return None
        return _s(self._menu)
    def ensure_dirs(self):
        log_debug("[anime/core_anime] → ensure_dirs()")
        for d in [SCHEDE_DIR, SCAN_DIR, LINK_COMPL_DIR]:
            FileManager.ensure_folder(str(d))
