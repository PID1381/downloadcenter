from __future__ import annotations

import importlib
from datetime import datetime
from typing import List, Optional

from scripts.core.file_manager import FileManager
from scripts.core.logger import get_logger, log_debug
from scripts.download.settings_download import DOWNLOAD_JSON, DOWNLOAD_OUTPUT_DIR
from scripts.core.settings_core import STARTUP_CHECK_FILE

logger = get_logger(__name__)

_inst: Optional['DownloadCore'] = None

_DEFAULT_DATA = {
    'section': 'download',
    'version': '1.0',
    '_meta': 'Download manager config - base comune per download video',
    'default_module': 'ytdlp',
    'settings': {
        'output_dir': '',
        'quality': 'best',
        'format': 'mp4',
        'concurrent_downloads': 3,
        'retry': 3,
        'timeout': 30,
    },
    'modules': [
        {
            'id': 'ytdlp',
            'key': '1',
            'label': 'YT-DLP',
            'description': 'Download video tramite yt-dlp',
            'handler': 'scripts.download.moduli.YTDLP.core_ytdlp',
            'entry_fn': 'run',
        }
    ],
    'module_handlers': {
        'ytdlp': 'scripts.download.moduli.YTDLP.core_ytdlp',
    },
    'pending_downloads': [],
    'sources': [],
}


class DownloadCore:
    def __init__(self):
        log_debug("[download/core_download] → __init__()")
        self._data = self._load()
        FileManager.ensure_folder(str(DOWNLOAD_OUTPUT_DIR))

    @classmethod
    def get(cls):
        log_debug("[download/core_download] → get()")
        global _inst
        if _inst is None:
            _inst = cls()
        return _inst

    def _load(self) -> dict:
        log_debug("[download/core_download] → _load()")
        data = FileManager.load_json(str(DOWNLOAD_JSON)) or {}
        merged = dict(_DEFAULT_DATA)
        merged.update(data)
        merged.setdefault('settings', {}).update(data.get('settings', {}))
        merged.setdefault('modules', _DEFAULT_DATA['modules'])
        merged.setdefault('module_handlers', _DEFAULT_DATA['module_handlers'])
        merged.setdefault('pending_downloads', [])
        merged.setdefault('sources', [])
        FileManager.save_json(merged, str(DOWNLOAD_JSON))
        self._sync_startup_pending(merged.get('pending_downloads', []))
        return merged

    def reload(self):
        log_debug("[download/core_download] → reload()")
        self._data = self._load()
        return self

    def save(self) -> None:
        log_debug("[download/core_download] → save()")
        FileManager.save_json(self._data, str(DOWNLOAD_JSON))
        self._sync_startup_pending(self.get_pending_downloads())

    def _sync_startup_pending(self, pending: List[dict]) -> None:
        log_debug("[download/core_download] → _sync_startup_pending()")
        data = FileManager.load_json(STARTUP_CHECK_FILE) or {}
        data['pending_downloads'] = [
            {
                'id': item.get('id', ''),
                'url': item.get('url', ''),
                'status': item.get('status', ''),
                'updated_at': item.get('updated_at', ''),
            }
            for item in pending
        ]
        FileManager.save_json(data, STARTUP_CHECK_FILE)

    def _now(self) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_settings(self) -> dict:
        return self._data.get('settings', {}).copy()

    def get_modules(self) -> List[dict]:
        return list(self._data.get('modules', []))

    def get_default_module(self) -> str:
        return self._data.get('default_module') or 'ytdlp'

    def set_default_module(self, module_id: str) -> None:
        log_debug("[download/core_download] → set_default_module()")
        self._data['default_module'] = module_id
        self.save()

    def get_module_handler(self, module_id: str = ''):
        log_debug("[download/core_download] → get_module_handler()")
        mid = module_id or self.get_default_module()
        handler = self._data.get('module_handlers', {}).get(mid)
        if not handler:
            raise RuntimeError(f'Handler download non configurato per "{mid}".')
        return importlib.import_module(handler)

    def get_output_dir(self, core, override: str = '') -> str:
        raw = (override or '').strip()
        if raw:
            return raw
        settings_dir = (self._data.get('settings', {}).get('output_dir') or '').strip()
        return settings_dir or core.config.get_download_dir() or str(DOWNLOAD_OUTPUT_DIR)

    def get_pending_downloads(self) -> List[dict]:
        log_debug("[download/core_download] → get_pending_downloads()")
        return list(self._data.get('pending_downloads', []))

    def pending_count(self) -> int:
        log_debug("[download/core_download] → pending_count()")
        return len(self.get_pending_downloads())

    def add_pending(self, url: str, module_id: str = '', output_dir: str = '', status: str = 'pending', error: str = '') -> dict:
        log_debug("[download/core_download] → add_pending()")
        pending = self._data.setdefault('pending_downloads', [])
        mid = module_id or self.get_default_module()
        out_dir = output_dir or ''
        existing = next(
            (
                item for item in pending
                if item.get('url') == url and item.get('module_id') == mid and item.get('output_dir', '') == out_dir
            ),
            None,
        )
        now = self._now()
        if existing:
            existing.update({'status': status, 'updated_at': now, 'error': error})
            self.save()
            return existing
        item = {
            'id': now.replace('-', '').replace(':', '').replace(' ', '_') + '_' + str(len(pending) + 1),
            'url': url,
            'module_id': mid,
            'output_dir': out_dir,
            'status': status,
            'created_at': now,
            'updated_at': now,
            'error': error,
            'paths': [],
        }
        pending.append(item)
        self.save()
        return item

    def update_pending(self, pending_id: str, **updates) -> None:
        log_debug("[download/core_download] → update_pending()")
        for item in self._data.setdefault('pending_downloads', []):
            if item.get('id') == pending_id:
                item.update(updates)
                item['updated_at'] = self._now()
                self.save()
                return

    def remove_pending(self, pending_id: str) -> None:
        log_debug("[download/core_download] → remove_pending()")
        self._data['pending_downloads'] = [
            item for item in self._data.get('pending_downloads', [])
            if item.get('id') != pending_id
        ]
        self.save()

    def clear_pending(self) -> None:
        log_debug("[download/core_download] → clear_pending()")
        self._data['pending_downloads'] = []
        self.save()

    def set_output_dir(self, path: str) -> None:
        log_debug("[download/core_download] → set_output_dir()")
        self._data.setdefault('settings', {})['output_dir'] = path
        self.save()

    def get_info(self, core, url: str, module_id: str = '') -> dict:
        log_debug("[download/core_download] → get_info()")
        return self.get_module_handler(module_id).get_info(core, url)

    def download_url(self, core, url: str, module_id: str = '', output_dir: str = '') -> dict:
        log_debug("[download/core_download] → download_url()")
        out_dir = self.get_output_dir(core, output_dir)
        mid = module_id or self.get_default_module()
        pending = self.add_pending(url, mid, out_dir, status='downloading')
        try:
            result = self.get_module_handler(mid).download_url(core, url, output_dir=out_dir)
        except KeyboardInterrupt:
            self.update_pending(pending['id'], status='interrotto', error='Interrotto dall\'utente.')
            raise
        if result.get('ok'):
            self.remove_pending(pending['id'])
        else:
            self.update_pending(pending['id'], status='errore', error=result.get('error', 'errore sconosciuto'))
        return result

    def download_urls(self, core, urls: List[str], module_id: str = '', output_dir: str = '') -> List[dict]:
        log_debug("[download/core_download] → download_urls()")
        out_dir = self.get_output_dir(core, output_dir)
        results = []
        for url in urls:
            results.append(self.download_url(core, url, module_id=module_id, output_dir=out_dir))
        return results

    def resume_pending(self, core, pending_id: str) -> dict:
        log_debug("[download/core_download] → resume_pending()")
        item = next((x for x in self.get_pending_downloads() if x.get('id') == pending_id), None)
        if not item:
            return {'ok': False, 'error': 'Download pendente non trovato.', 'paths': []}
        return self.download_url(
            core,
            item.get('url', ''),
            module_id=item.get('module_id') or self.get_default_module(),
            output_dir=item.get('output_dir', ''),
        )

    def resume_all_pending(self, core) -> List[dict]:
        log_debug("[download/core_download] → resume_all_pending()")
        pending = list(self.get_pending_downloads())
        results = []
        for item in pending:
            results.append(self.resume_pending(core, item.get('id', '')))
        return results


def get_info(url: str, module_id: str = '') -> dict:
    log_debug("[download/core_download] → get_info()")
    from scripts.core import Core
    core = Core.get()
    return DownloadCore.get().get_info(core, url, module_id=module_id)


def download_video(url: str, module_id: str = '', output_dir: str = '') -> dict:
    log_debug("[download/core_download] → download_video()")
    from scripts.core import Core
    core = Core.get()
    return DownloadCore.get().download_url(core, url, module_id=module_id, output_dir=output_dir)


def download_videos(urls: List[str], module_id: str = '', output_dir: str = '') -> List[dict]:
    log_debug("[download/core_download] → download_videos()")
    from scripts.core import Core
    core = Core.get()
    return DownloadCore.get().download_urls(core, urls, module_id=module_id, output_dir=output_dir)


def resume_pending(pending_id: str) -> dict:
    log_debug("[download/core_download] → resume_pending()")
    from scripts.core import Core
    core = Core.get()
    return DownloadCore.get().resume_pending(core, pending_id)


def resume_all_pending() -> List[dict]:
    log_debug("[download/core_download] → resume_all_pending()")
    from scripts.core import Core
    core = Core.get()
    return DownloadCore.get().resume_all_pending(core)
