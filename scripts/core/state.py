"""
Core State Module v2.0
Gestione stato centralizzata: download (resume) + watchlist (3 categorie).
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


class DownloadState:
    """Stato download con supporto pause/resume."""

    def __init__(self, state_file: Optional[str] = None):
        if state_file is None:
            try:
                from .config import config
                state_file = str(config.temp_dir / ".download_state.json")
            except Exception:
                state_file = "scripts/temp/.download_state.json"
        self.state_file = state_file
        self.state: Dict = {}

    def load(self) -> bool:
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                return True
        except Exception:
            pass
        return False

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.state_file)), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def create_session(self, session_id: str, video_links: List[str],
                       download_folder: str) -> None:
        files_dict: Dict = {}
        for link in video_links:
            fname = os.path.basename(urlparse(link).path)
            if not fname:
                fname = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            files_dict[fname] = {
                "url": link, "status": "pending",
                "size": 0,   "downloaded": 0,
                "timestamp": datetime.now().isoformat(),
            }
        self.state = {
            "session_id":      session_id,
            "created_at":      datetime.now().isoformat(),
            "download_folder": download_folder,
            "files":           files_dict,
        }
        self.save()

    def start_download(self, filename: str) -> None:
        try:
            if "files" in self.state and filename in self.state["files"]:
                self.state["files"][filename]["status"]     = "in_progress"
                self.state["files"][filename]["start_time"] = datetime.now().isoformat()
                self.save()
        except Exception:
            pass

    def update_progress(self, filename: str, downloaded: int, total_size: int) -> None:
        try:
            if "files" in self.state and filename in self.state["files"]:
                self.state["files"][filename]["downloaded"] = downloaded
                self.state["files"][filename]["size"]       = total_size
                self.state["files"][filename]["status"]     = "in_progress"
                self.save()
        except Exception:
            pass

    def mark_completed(self, filename: str) -> None:
        try:
            if "files" in self.state and filename in self.state["files"]:
                self.state["files"][filename]["status"]         = "completed"
                self.state["files"][filename]["completed_time"] = datetime.now().isoformat()
                self.save()
        except Exception:
            pass

    def mark_failed(self, filename: str) -> None:
        try:
            if "files" in self.state and filename in self.state["files"]:
                self.state["files"][filename]["status"] = "failed"
                self.save()
        except Exception:
            pass

    def is_complete(self) -> bool:
        try:
            if "files" in self.state:
                for fi in self.state["files"].values():
                    if isinstance(fi, dict) and fi.get("status") != "completed":
                        return False
                return True
        except Exception:
            pass
        return True

    def clear(self) -> None:
        try:
            self.state = {}
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        except Exception:
            pass


class WatchlistState:
    """Gestione stato watchlist — 3 categorie."""
    CATEGORIES = ["finiti_da_vedere", "in_corso", "download"]

    def __init__(self):
        try:
            from .config import config
            self._temp_dir = config.temp_dir
        except Exception:
            self._temp_dir = Path("scripts/temp")
        self._paths = {
            "finiti_da_vedere": self._temp_dir / "watchlist_finiti_da_vedere.json",
            "in_corso":         self._temp_dir / "watchlist_in_corso.json",
            "download":         self._temp_dir / "watchlist_download.json",
        }

    def load_category(self, category: str) -> List[Dict]:
        path = self._paths.get(category)
        if not path or not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save_category(self, category: str, wl: List[Dict]) -> None:
        path = self._paths.get(category)
        if not path:
            return
        try:
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            try:
                wl_s = sorted(wl, key=lambda x: x.get("data_uscita", ""), reverse=True)
            except Exception:
                wl_s = wl
            with open(path, "w", encoding="utf-8") as f:
                json.dump(wl_s, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            from .ui import ui
            ui.show_error(f"Errore salvataggio watchlist: {exc}")

    def find_by_title(self, titolo: str) -> Optional[Tuple[str, int]]:
        t = titolo.lower().strip()
        for cat in self.CATEGORIES:
            for i, a in enumerate(self.load_category(cat)):
                if a.get("titolo", "").lower().strip() == t:
                    return (cat, i)
        return None

    def get_all(self) -> Dict[str, List[Dict]]:
        return {c: self.load_category(c) for c in self.CATEGORIES}


watchlist_state = WatchlistState()
