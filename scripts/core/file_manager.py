import json
from pathlib import Path
from typing import Any, List

class FileManager:
    @staticmethod
    def load_json(p, default=None):
        try:
            with open(p, 'r', encoding='utf-8') as fh: return json.load(fh)
        except: return default
    @staticmethod
    def save_json(data, p, indent=2):
        try:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=indent, ensure_ascii=False)
            return True
        except: return False
    @staticmethod
    def read_json(p, d=None): return FileManager.load_json(p, d)
    @staticmethod
    def write_json(p, data, indent=2): return FileManager.save_json(data, p, indent)
    @staticmethod
    def read_text(p, default=''):
        try: return Path(p).read_text(encoding='utf-8')
        except: return default
    @staticmethod
    def write_text(p, content):
        try:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text(content, encoding='utf-8'); return True
        except: return False
    @staticmethod
    def ensure_folder(path):
        p = Path(path)
        if p.exists(): return False
        try: p.mkdir(parents=True, exist_ok=True); return True
        except: return False
    @staticmethod
    def ensure_dir(path): return FileManager.ensure_folder(path)
    @staticmethod
    def sanitize_filename(name):
        for c in ['<', '>', ':', '|', '?', '*']: name = name.replace(c, '')
        return name.strip()[:200]
    @staticmethod
    def sanitize_folder_name(n): return FileManager.sanitize_filename(n)
    @staticmethod
    def normalize_url(url, base=''):
        if not url: return ''
        if url.startswith('http'): return url
        return (base.rstrip('/') + '/' + url.lstrip('/')) if base else url
    @staticmethod
    def clean_path(p): return p.strip().strip('"').strip("'").strip()
    @staticmethod
    def load_urls_from_file(path):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return [l.strip() for l in fh if l.strip() and not l.strip().startswith('#')]
        except: return []
    @staticmethod
    def save_urls_to_file(urls, path):
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(chr(10).join(urls), encoding='utf-8'); return True
        except: return False

file_mgr = FileManager()
