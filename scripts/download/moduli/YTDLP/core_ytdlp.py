from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from scripts.core.file_manager import FileManager
from scripts.core.logger import get_logger, log_debug
from scripts.download.settings_download import DOWNLOAD_OUTPUT_DIR, YTDLP_JSON

logger = get_logger(__name__)

MODULE_KEY = 'ytdlp'
MODULE_NAME = 'YT-DLP'

_DEFAULT_OPTIONS = {
    'format': 'bestvideo+bestaudio/best',
    'merge_output_format': 'mp4',
    'outtmpl': '%(title)s [%(id)s].%(ext)s',
    'writesubtitles': False,
    'subtitleslangs': ['it', 'en'],
    'noplaylist': True,
    'continuedl': True,
    'nopart': False,
    'concurrent_fragment_downloads': 3,
    'windowsfilenames': True,
    'restrictfilenames': False,
    'noprogress': True,
    'quiet': False,
    'ignoreerrors': False,
}


class _YTDLPLogger:
    def debug(self, msg):
        log_debug(f"[{MODULE_KEY}] {msg}")

    def warning(self, msg):
        logger.warning(str(msg))

    def error(self, msg):
        logger.error(str(msg))


def _load_config() -> dict:
    log_debug(f"[{MODULE_KEY}] → _load_config()")
    data = FileManager.load_json(str(YTDLP_JSON)) or {}
    data.setdefault('_meta', 'yt-dlp config - gestore download video')
    data.setdefault('options', {})
    for key, value in _DEFAULT_OPTIONS.items():
        data['options'].setdefault(key, value)
    data.setdefault('cookies_file', '')
    data.setdefault('sources', [])
    FileManager.save_json(data, str(YTDLP_JSON))
    return data


def _save_config(data: dict) -> None:
    log_debug(f"[{MODULE_KEY}] → _save_config()")
    FileManager.save_json(data, str(YTDLP_JSON))


def _import_ytdlp():
    log_debug(f"[{MODULE_KEY}] → _import_ytdlp()")
    try:
        import yt_dlp
        return yt_dlp
    except ImportError as exc:
        raise RuntimeError('Dipendenza yt-dlp mancante. Installa con: pip install yt-dlp') from exc


def is_available() -> bool:
    log_debug(f"[{MODULE_KEY}] → is_available()")
    try:
        _import_ytdlp()
        return True
    except RuntimeError:
        return False


def _download_dir(core, override: str = '') -> Path:
    raw = (override or '').strip() or core.config.get_download_dir() or str(DOWNLOAD_OUTPUT_DIR)
    path = Path(FileManager.clean_path(raw))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _progress_hook(status: dict) -> None:
    state = status.get('status')
    filename = status.get('filename') or status.get('tmpfilename') or ''
    if state == 'finished':
        log_debug(f"[{MODULE_KEY}] download finished: {filename}")
    elif state == 'error':
        log_debug(f"[{MODULE_KEY}] download error: {filename}")


def _ydl_options(core, output_dir: str = '', extra: Optional[dict] = None) -> dict:
    log_debug(f"[{MODULE_KEY}] → _ydl_options()")
    cfg = _load_config()
    options = dict(cfg.get('options') or {})
    outtmpl = options.pop('outtmpl', _DEFAULT_OPTIONS['outtmpl'])
    opts = {
        **options,
        'paths': {'home': str(_download_dir(core, output_dir))},
        'outtmpl': {'default': outtmpl},
        'logger': _YTDLPLogger(),
        'progress_hooks': [_progress_hook],
        'quiet': True,
        'no_warnings': False,
    }
    cookies_file = (cfg.get('cookies_file') or '').strip()
    if cookies_file:
        opts['cookiefile'] = cookies_file
    if extra:
        opts.update(extra)
    return {k: v for k, v in opts.items() if v not in ('', None)}


def _collect_paths(info: dict) -> List[str]:
    paths: List[str] = []
    if not isinstance(info, dict):
        return paths
    for item in info.get('requested_downloads') or []:
        path = item.get('filepath') or item.get('_filename')
        if path:
            paths.append(str(path))
    filename = info.get('_filename') or info.get('filepath')
    if filename:
        paths.append(str(filename))
    for entry in info.get('entries') or []:
        paths.extend(_collect_paths(entry))
    return sorted(set(paths))


def get_info(core, url: str) -> dict:
    """Estrae metadati senza scaricare."""
    log_debug(f"[{MODULE_KEY}] → get_info()")
    if not url:
        return {}
    try:
        yt_dlp = _import_ytdlp()
        opts = _ydl_options(core, extra={'skip_download': True, 'simulate': True})
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] get_info error: {exc}")
        return {}
    if not isinstance(info, dict):
        return {}
    return {
        'title': info.get('title') or '',
        'id': info.get('id') or '',
        'extractor': info.get('extractor') or info.get('extractor_key') or '',
        'webpage_url': info.get('webpage_url') or url,
        'duration': info.get('duration') or 0,
        'playlist_count': len(info.get('entries') or []),
        'formats_count': len(info.get('formats') or []),
        'ext': info.get('ext') or '',
    }


def download_url(core, url: str, output_dir: str = '', extra_opts: Optional[dict] = None) -> dict:
    """Scarica un singolo URL usando yt-dlp."""
    log_debug(f"[{MODULE_KEY}] → download_url()")
    if not url:
        return {'ok': False, 'error': 'URL non disponibile.', 'paths': []}
    try:
        yt_dlp = _import_ytdlp()
        opts = _ydl_options(core, output_dir=output_dir, extra=extra_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        return {
            'ok': True,
            'title': (info or {}).get('title', '') if isinstance(info, dict) else '',
            'paths': _collect_paths(info or {}),
            'url': url,
        }
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        log_debug(f"[{MODULE_KEY}] download_url error: {exc}")
        return {'ok': False, 'error': str(exc), 'paths': [], 'url': url}


def download_urls(core, urls: List[str], output_dir: str = '') -> List[dict]:
    log_debug(f"[{MODULE_KEY}] → download_urls()")
    results = []
    for url in urls:
        results.append(download_url(core, url, output_dir=output_dir))
    return results


def update_option(key: str, value) -> None:
    log_debug(f"[{MODULE_KEY}] → update_option()")
    cfg = _load_config()
    cfg.setdefault('options', {})[key] = value
    _save_config(cfg)


def set_cookies_file(path: str) -> None:
    log_debug(f"[{MODULE_KEY}] → set_cookies_file()")
    cfg = _load_config()
    cfg['cookies_file'] = path
    _save_config(cfg)


def run() -> None:
    """Menu diretto del modulo YT-DLP."""
    log_debug(f"[{MODULE_KEY}] → run()")
    from scripts.core import Core

    core = Core.get()
    core.ui.show_info('Modulo tecnico YT-DLP. Usa la sezione Download per le azioni principali.')
    core.ui.pause()


def show_menu() -> None:
    run()
