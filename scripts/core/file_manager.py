import json
from pathlib import Path
from typing import Any, List

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

class FileManager:
    @staticmethod
    def load_json(p, default=None):
        log_debug("[core/file_manager] → load_json()")
        try:
            with open(p, 'r', encoding='utf-8') as fh: return json.load(fh)
        except: return default
    @staticmethod
    def save_json(data, p, indent=2):
        log_debug("[core/file_manager] → save_json()")
        try:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=indent, ensure_ascii=False)
            return True
        except: return False
    @staticmethod
    def read_json(p, d=None):
        log_debug("[core/file_manager] → read_json()")
        return FileManager.load_json(p, d)
    @staticmethod
    def write_json(p, data, indent=2):
        log_debug("[core/file_manager] → write_json()")
        return FileManager.save_json(data, p, indent)
    @staticmethod
    def read_text(p, default=''):
        log_debug("[core/file_manager] → read_text()")
        try: return Path(p).read_text(encoding='utf-8')
        except: return default
    @staticmethod
    def write_text(p, content):
        log_debug("[core/file_manager] → write_text()")
        try:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text(content, encoding='utf-8'); return True
        except: return False
    @staticmethod
    def ensure_folder(path):
        log_debug("[core/file_manager] → ensure_folder()")
        p = Path(path)
        if p.exists(): return False
        try: p.mkdir(parents=True, exist_ok=True); return True
        except: return False
    @staticmethod
    def ensure_dir(path):
        log_debug("[core/file_manager] → ensure_dir()")
        return FileManager.ensure_folder(path)
    @staticmethod
    def sanitize_filename(name):
        log_debug("[core/file_manager] → sanitize_filename()")
        for c in ['<', '>', ':', '|', '?', '*']: name = name.replace(c, '')
        return name.strip()[:200]
    @staticmethod
    def sanitize_folder_name(n):
        log_debug("[core/file_manager] → sanitize_folder_name()")
        return FileManager.sanitize_filename(n)
    @staticmethod
    def normalize_url(url, base=''):
        log_debug("[core/file_manager] → normalize_url()")
        if not url: return ''
        if url.startswith('http'): return url
        return (base.rstrip('/') + '/' + url.lstrip('/')) if base else url
    @staticmethod
    def clean_path(p):
        log_debug("[core/file_manager] → clean_path()")
        return p.strip().strip('"').strip("'").strip()
    @staticmethod
    def load_urls_from_file(path):
        log_debug("[core/file_manager] → load_urls_from_file()")
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return [l.strip() for l in fh if l.strip() and not l.strip().startswith('#')]
        except: return []
    @staticmethod
    def save_urls_to_file(urls, path):
        log_debug("[core/file_manager] → save_urls_to_file()")
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(chr(10).join(urls), encoding='utf-8'); return True
        except: return False

file_mgr = FileManager()
