#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytdlp_wrapper.py  v1.0
Download Center  —  scripts/download/ytdlp_wrapper.py

Wrapper leggero attorno a yt-dlp (import Python).
Integrazione minimo-invasiva: non modifica nessun altro file preesistente.

DIPENDENZE:
    pip install yt-dlp

FUNZIONI PUBBLICHE:
    check_installed()          -> bool
    get_version()              -> str
    download_url(url, outdir, filename, progress_cb) -> bool
    download_hls(url, outdir, filename, progress_cb) -> bool
    get_formats(url)           -> List[Dict]
    _get_download_dir()        -> str   (usata anche da handlers.py)
"""
from __future__ import annotations

import os
import sys
import re
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR    = Path(__file__).parent.resolve()   # scripts/download/
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()        # scripts/

for _p in (str(_THIS_DIR), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Costanti ──────────────────────────────────────────────────────────────────
_FORMAT_BEST_MP4 = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
_FORMAT_HLS      = "best"
_MERGE_FORMAT    = "mp4"

# ── Verifica installazione ────────────────────────────────────────────────────
def check_installed() -> bool:
    """Ritorna True se yt-dlp è importabile."""
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def get_version() -> str:
    """Ritorna la versione di yt-dlp, o stringa vuota."""
    try:
        import yt_dlp
        return getattr(yt_dlp.version, "__version__", "?")
    except Exception:
        return ""


# ── Leggi cartella download da prefs.json ────────────────────────────────────
def _get_download_dir() -> str:
    """
    Legge default_download_dir da prefs.json
    (stessa logica di download_diretto_anime.py → get_download_dir_from_settings).
    """
    candidates = [
        _SCRIPTS_DIR / "temp"   / "prefs.json",
        _SCRIPTS_DIR / "prefs.json",
        _SCRIPTS_DIR / "config" / "settings.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                d = (cfg.get("default_download_dir") or
                     cfg.get("default_Download_dir") or
                     cfg.get("download_dir"))
                if d:
                    return d
            except Exception:
                pass
    return "."


# ── Sanitize filename ─────────────────────────────────────────────────────────
def _sanitize(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "", name)
    return cleaned.strip(". ")[:180] or "video"


# ── Progress hook ─────────────────────────────────────────────────────────────
def _make_progress_hook(progress_cb: Optional[Callable] = None):
    """
    Crea un hook compatibile con yt-dlp.
    progress_cb(downloaded_bytes, total_bytes) se fornita,
    altrimenti stampa barra ASCII inline.
    """
    _last_print = [0]

    def _hook(d: Dict) -> None:
        if d.get("status") == "downloading":
            downloaded = d.get("downloaded_bytes", 0) or 0
            total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            # throttle: aggiorna ogni 512 KB
            if downloaded - _last_print[0] < 524_288 and total and downloaded < total:
                return
            _last_print[0] = downloaded
            if progress_cb:
                progress_cb(downloaded, total)
            else:
                _print_bar(downloaded, total)
        elif d.get("status") == "finished":
            print()  # newline dopo la barra

    return _hook


def _print_bar(current: int, total: int, length: int = 40) -> None:
    import time
    chars  = ["◐", "◓", "◑", "◒"]
    anim   = chars[int(time.time() * 4) % 4]
    if total > 0:
        pct    = 100 * current / total
        filled = int(length * current // total)
    else:
        pct    = 0.0
        filled = 0
    bar  = "█" * filled + "░" * (length - filled)
    line = f"\r  yt-dlp: |{bar}| {pct:.1f}% {anim}" + " " * 10
    print(line, end="", flush=True)


# ── Core download ─────────────────────────────────────────────────────────────
def _run_ytdlp(
    url: str,
    outdir: Optional[str],
    filename: Optional[str],
    fmt: str,
    progress_cb: Optional[Callable],
    extra_opts: Optional[Dict] = None,
) -> bool:
    """Esegue il download con yt-dlp. Ritorna True se OK."""
    if not check_installed():
        print("  ✗ yt-dlp non installato. Esegui: pip install yt-dlp")
        return False

    import yt_dlp

    if not outdir:
        outdir = _get_download_dir()
    Path(outdir).mkdir(parents=True, exist_ok=True)

    if filename:
        safe      = _sanitize(filename)
        otemplate = str(Path(outdir) / (safe + ".%(ext)s"))
    else:
        otemplate = str(Path(outdir) / "%(title)s.%(ext)s")

    ydl_opts: Dict = {
        "format":               fmt,
        "outtmpl":              otemplate,
        "merge_output_format":  _MERGE_FORMAT,
        "quiet":                True,
        "no_warnings":          True,
        "progress_hooks":       [_make_progress_hook(progress_cb)],
        "noprogress":           False,
        "skip_unavailable_fragments": True,
        "ignoreerrors":         False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    }

    if extra_opts:
        ydl_opts.update(extra_opts)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ret = ydl.download([url])
        return ret == 0
    except yt_dlp.utils.DownloadError as e:
        print(f"\n  ✗ yt-dlp DownloadError: {e}")
        return False
    except Exception as e:
        print(f"\n  ✗ yt-dlp errore: {e}")
        return False


# ── API pubblica ──────────────────────────────────────────────────────────────
def download_url(
    url: str,
    outdir: Optional[str] = None,
    filename: Optional[str] = None,
    progress_cb: Optional[Callable] = None,
) -> bool:
    """Download generico (best MP4)."""
    return _run_ytdlp(url, outdir, filename, _FORMAT_BEST_MP4, progress_cb)


def download_hls(
    url: str,
    outdir: Optional[str] = None,
    filename: Optional[str] = None,
    progress_cb: Optional[Callable] = None,
) -> bool:
    """Download stream HLS/M3U8."""
    extra = {"hls_prefer_native": url.endswith(".m3u8")}
    return _run_ytdlp(url, outdir, filename, _FORMAT_HLS, progress_cb, extra)


def get_formats(url: str) -> List[Dict]:
    """Ritorna la lista dei formati disponibili per l'URL."""
    if not check_installed():
        return []
    import yt_dlp
    ydl_opts = {"quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("formats", []) if info else []
    except Exception:
        return []


# ── Selftest ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== ytdlp_wrapper selftest ===")
    inst = check_installed()
    print(f"  yt-dlp installato : {inst}")
    if inst:
        print(f"  versione          : {get_version()}")
        print(f"  cartella default  : {_get_download_dir()}")
    else:
        print("  → pip install yt-dlp")
