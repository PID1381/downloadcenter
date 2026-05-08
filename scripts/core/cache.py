import time
from pathlib import Path
from .settings_core import TEMP_DIR

class CacheManager:
    def __init__(self):
        self._data = {}
        Path(TEMP_DIR, 'cache').mkdir(parents=True, exist_ok=True)
    def get(self, key, default=None):
        entry = self._data.get(key)
        if entry is None: return default
        val, exp = entry
        if exp and time.time() > exp:
            del self._data[key]; return default
        return val
    def set(self, key, value, ttl=3600):
        self._data[key] = (value, time.time()+ttl if ttl else None)
    def delete(self, key): self._data.pop(key, None)
    def cleanup(self):
        now = time.time()
        expired = [k for k,(v,e) in self._data.items() if e and now>e]
        for k in expired: del self._data[k]
        return len(expired)
