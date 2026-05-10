from scripts.core.file_manager import FileManager
from scripts.anime.settings_anime import ANIME_JSON, SCHEDE_DIR, SCAN_DIR, LINK_COMPL_DIR

_inst = None

class AnimeCore:
    def __init__(self):
        self._data = FileManager.load_json(str(ANIME_JSON)) or {}
        self._menu = self._data.get('menu', [])
        self._mv   = self._data.get('moduli_video', [])
        self._ms   = self._data.get('moduli_schede', [])
        self._mvh  = self._data.get('moduli_video_handlers', {})
        self._msh  = self._data.get('moduli_schede_handlers', {})
    @classmethod
    def get(cls):
        global _inst
        if _inst is None: _inst = cls()
        return _inst
    def get_menu(self): return self._menu
    def get_submenu(self, parent_id):
        for it in self._menu:
            if it.get('id') == parent_id: return it.get('submenu', [])
        return []
    def get_moduli_video(self): return self._mv
    def get_moduli_schede(self): return self._ms
    def get_video_handler(self, mid): return self._mvh.get(mid)
    def get_schede_handler(self, mid): return self._msh.get(mid)
    def get_menu_item(self, item_id):
        def _s(items):
            for it in items:
                if it.get('id')==item_id: return it
                found = _s(it.get('submenu',[]))
                if found: return found
            return None
        return _s(self._menu)
    def ensure_dirs(self):
        for d in [SCHEDE_DIR, SCAN_DIR, LINK_COMPL_DIR]:
            FileManager.ensure_folder(str(d))
