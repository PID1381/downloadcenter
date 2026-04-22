"""
Core File Manager v2.0
Gestione centralizzata di file e percorsi.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class FileManager:
    """Gestione centralizzata di file e directory."""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', "", filename).strip()[:200]

    @staticmethod
    def sanitize_folder_name(name: str) -> str:
        return FileManager.sanitize_filename(name)

    @staticmethod
    def get_safe_path(base_path: str, ask_user: bool = True) -> Optional[str]:
        from .ui import ui
        if not Path(base_path).exists():
            try:
                Path(base_path).mkdir(parents=True, exist_ok=True)
                return base_path
            except Exception as e:
                ui.show_error(f"Errore creazione cartella: {e}")
                return None
        if not ask_user:
            return base_path
        ui.show_warning(f"'{Path(base_path).name}' esiste gia!")
        if ui.ask_yes_no("Vuoi usarlo comunque?"):
            return base_path
        counter = 1
        while Path(f"{base_path}_{counter}").exists():
            counter += 1
        new_path = f"{base_path}_{counter}"
        ui.show_success(f"Nuovo percorso: {Path(new_path).name}")
        return new_path

    @staticmethod
    def ensure_folder(path: str) -> bool:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    @staticmethod
    def load_json(file_path: str) -> Optional[Dict]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def save_json(data: Dict, file_path: str) -> bool:
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @staticmethod
    def load_urls_from_file(file_path: str) -> List[str]:
        from .ui import ui
        urls: List[str] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith("#"):
                        urls.append(url)
        except FileNotFoundError:
            ui.show_error(f"File non trovato: {file_path}")
        except Exception as e:
            ui.show_error(f"Errore lettura file: {e}")
        return urls

    @staticmethod
    def save_urls_to_file(urls: List[str], file_path: str) -> bool:
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                for url in urls:
                    f.write(url + "\n")
            return True
        except Exception:
            return False

    @staticmethod
    def normalize_url(url: str, base_url: str = "") -> str:
        if not url: return ""
        if url.startswith("http"): return url
        if base_url: return base_url.rstrip("/") + "/" + url.lstrip("/")
        return url

    @staticmethod
    def clean_path(path_str: str) -> str:
        return path_str.strip().strip('"').strip("'").strip()


file_mgr = FileManager()
