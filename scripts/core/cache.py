"""
Core Cache Manager v2.0
Gestione centralizzata della cache e pulizia file temporanei.
"""
import os
import shutil
from pathlib import Path
from typing import Tuple


class CacheManager:
    """Gestione cache, log e file temporanei."""

    def __init__(self):
        try:
            from .config import config
            self._temp_dir = config.temp_dir
            self._root_dir = config.root_dir
        except Exception:
            self._temp_dir = Path("scripts/temp")
            self._root_dir = Path.cwd()

    def clear_temp_files(self) -> Tuple[int, int]:
        """
        Cancella file temporanei e debug HTML.
        
        Ritorna: (num_file_cancellati, num_errori)
        """
        if not self._temp_dir.exists():
            return (0, 0)
        
        deleted = 0
        errors = 0
        
        patterns = ["debug_*.html", "*.tmp", "*.cache"]
        
        for pattern in patterns:
            for file in self._temp_dir.glob(pattern):
                try:
                    if file.is_file():
                        file.unlink()
                        deleted += 1
                except Exception:
                    errors += 1
        
        return (deleted, errors)

    def clear_logs(self, keep_days: int = 7) -> Tuple[int, int]:
        """
        Cancella log file vecchi (default: > 7 giorni).
        
        Ritorna: (num_log_cancellati, num_errori)
        """
        if not self._temp_dir.exists():
            return (0, 0)
        
        log_file = self._temp_dir / "app.log"
        deleted = 0
        errors = 0
        
        if log_file.exists():
            try:
                log_file.unlink()
                deleted += 1
            except Exception:
                errors += 1
        
        return (deleted, errors)

    def get_cache_size(self) -> int:
        """Restituisce la dimensione totale della cache in bytes."""
        if not self._temp_dir.exists():
            return 0
        
        total_size = 0
        try:
            for file in self._temp_dir.rglob("*"):
                if file.is_file():
                    total_size += file.stat().st_size
        except Exception:
            pass
        
        return total_size

    def clear_all_cache(self) -> dict:
        """
        Cancella tutto: temp files, logs, debug HTML.
        
        Ritorna: dict con statistiche delle operazioni
        """
        result = {
            "temp_files_deleted": 0,
            "temp_errors": 0,
            "logs_deleted": 0,
            "log_errors": 0,
            "cache_size_before": 0,
            "cache_size_after": 0,
        }
        
        result["cache_size_before"] = self.get_cache_size()
        
        temp_del, temp_err = self.clear_temp_files()
        result["temp_files_deleted"] = temp_del
        result["temp_errors"] = temp_err
        
        log_del, log_err = self.clear_logs()
        result["logs_deleted"] = log_del
        result["log_errors"] = log_err
        
        result["cache_size_after"] = self.get_cache_size()
        
        return result

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Converte bytes in formato leggibile (KB, MB, GB)."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"


cache_mgr = CacheManager()
