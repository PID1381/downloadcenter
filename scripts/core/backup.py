"""
Core Backup Manager v2.0
Gestione backup di file sensibili (preferenze, collezioni, watchlist).
"""
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple


class BackupManager:
    """Gestione backup dei file importanti."""

    BACKUP_FOLDER_NAME = "backups"
    SENSITIVE_FILES = [
        "prefs.json",
        "lamiacollezione.json",
        "watchlist_finiti_da_vedere.json",
        "watchlist_in_corso.json",
        "watchlist_download.json",
        ".download_state.json",
        "site_urls.json",
    ]

    def __init__(self):
        try:
            from .config import config
            self._temp_dir = config.temp_dir
            self._root_dir = config.root_dir
        except Exception:
            self._temp_dir = Path("scripts/temp")
            self._root_dir = Path.cwd()
        
        self._backup_dir = self._root_dir / self.BACKUP_FOLDER_NAME
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> dict:
        """
        Crea un backup di tutti i file sensibili.
        
        Ritorna: dict con info sul backup creato
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = self._backup_dir / f"backup_{timestamp}"
        backup_subdir.mkdir(parents=True, exist_ok=True)
        
        result = {
            "timestamp": timestamp,
            "backup_path": str(backup_subdir),
            "files_backed_up": 0,
            "files_failed": 0,
            "errors": [],
        }
        
        for filename in self.SENSITIVE_FILES:
            source = self._temp_dir / filename
            
            if not source.exists():
                continue
            
            try:
                dest = backup_subdir / filename
                shutil.copy2(source, dest)
                result["files_backed_up"] += 1
            except Exception as e:
                result["files_failed"] += 1
                result["errors"].append(f"{filename}: {str(e)}")
        
        if result["files_backed_up"] > 0:
            manifest = {
                "timestamp": timestamp,
                "files_count": result["files_backed_up"],
                "errors_count": result["files_failed"],
            }
            manifest_path = backup_subdir / "manifest.json"
            try:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
            except Exception:
                pass
        
        return result

    def list_backups(self) -> List[dict]:
        """
        Elenca tutti i backup disponibili.
        
        Ritorna: list di dict con info su cada backup
        """
        backups = []
        
        if not self._backup_dir.exists():
            return backups
        
        for backup_path in sorted(self._backup_dir.glob("backup_*"), reverse=True):
            if backup_path.is_dir():
                manifest_file = backup_path / "manifest.json"
                info = {
                    "path": str(backup_path),
                    "name": backup_path.name,
                    "files_count": 0,
                    "timestamp": "",
                }
                
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        info["timestamp"] = manifest.get("timestamp", "")
                        info["files_count"] = manifest.get("files_count", 0)
                    except Exception:
                        pass
                
                backups.append(info)
        
        return backups

    def restore_backup(self, backup_name: str) -> dict:
        """
        Ripristina un backup specifico.
        
        Ritorna: dict con risultati del ripristino
        """
        backup_path = self._backup_dir / backup_name
        
        result = {
            "success": False,
            "files_restored": 0,
            "files_failed": 0,
            "errors": [],
        }
        
        if not backup_path.exists():
            result["errors"].append(f"Backup non trovato: {backup_name}")
            return result
        
        for file_path in backup_path.glob("*.json"):
            dest = self._temp_dir / file_path.name
            
            try:
                dest_backup = dest.with_suffix(".backup")
                if dest.exists():
                    shutil.copy2(dest, dest_backup)
                
                shutil.copy2(file_path, dest)
                result["files_restored"] += 1
            except Exception as e:
                result["files_failed"] += 1
                result["errors"].append(f"{file_path.name}: {str(e)}")
        
        result["success"] = result["files_restored"] > 0
        return result

    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        Cancella i backup più vecchi, mantenendo i keep_count più recenti.
        
        Ritorna: numero di backup cancellati
        """
        deleted = 0
        
        if not self._backup_dir.exists():
            return deleted
        
        backup_dirs = sorted(self._backup_dir.glob("backup_*"))
        
        while len(backup_dirs) > keep_count:
            oldest = backup_dirs.pop(0)
            try:
                shutil.rmtree(oldest)
                deleted += 1
            except Exception:
                pass
        
        return deleted

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Converte bytes in formato leggibile."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"


backup_mgr = BackupManager()
