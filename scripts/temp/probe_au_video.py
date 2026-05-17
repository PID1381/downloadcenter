import json
import re
import sys
from pathlib import Path

import requests

from scripts.core.logger import get_logger, log_debug

logger = get_logger(__name__)

out = Path(__file__).with_name("au_probe.txt")
lines: list[str] = []


def log(msg: str) -> None:
    log_debug("[temp/probe_au_video] → log()")
    lines.append(msg)
    print(msg, flush=True)


base = "https://www.animeunity.so"
s = requests.Session()
s.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
)

try:
    r = s.get(f"{base}/archivio", timeout=25)
    log(f"archivio status={r.status_code}")
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
    if not m:
        log("NO CSRF")
        raise SystemExit(1)
    csrf = m.group(1)
    cookie = "; ".join(f"{c.name}={c.value}" for c in r.cookies)
    headers = {
        "User-Agent": s.headers["User-Agent"],
        "x-csrf-token": csrf,
        "Cookie": cookie,
        "content-type": "application/json;charset=UTF-8",
        "Referer": f"{base}/archivio",
    }

    ep_id = "106192"
    ep_url = (
        f"{base}/anime/10893-saikyou-no-shokugyou-wa-yuusha-demo-kenja-demo-naku-"
        f"kanteishi-kari-rashii-desu-yo/{ep_id}"
    )
    log(f"ep_url={ep_url}")

    r4 = s.get(
        ep_url,
        headers={"User-Agent": s.headers["User-Agent"], "Referer": f"{base}/"},
        timeout=25,
    )
    log(f"page status={r4.status_code} len={len(r4.text)}")
    html = r4.text
    for pat in ("scws", "m3u8", "iframe", "embed-url", "vixcloud", "player"):
        log(f"count {pat}={html.lower().count(pat)}")

    for m2 in re.finditer(r'src=["\']([^"\']+)["\']', html):
        u = m2.group(1)
        if any(x in u.lower() for x in ("scws", "embed", "player", "vix", "stream")):
            log(f"src: {u[:160]}")

    # embed-url endpoint
    emb = f"{base}/embed-url/{ep_id}"
    r5 = s.get(emb, headers={"User-Agent": s.headers["User-Agent"], "Referer": ep_url}, timeout=25)
    log(f"embed-url status={r5.status_code} len={len(r5.text)}")
    for m3 in re.finditer(r'https?://[^\s"\']+\.m3u8[^\s"\']*', r5.text):
        log(f"m3u8: {m3.group(0)[:160]}")

    # info_api episode fields
    api = f"{base}/info_api/10893/"
    r3 = s.get(f"{api}1?start_range=1&end_range=1", headers=headers, timeout=25)
    log(f"info_api status={r3.status_code}")
    if r3.status_code == 200:
        data = r3.json()
        ep = (data.get("episodes") or [{}])[0]
        log(f"episode keys={list(ep.keys())}")
        for k in ("id", "number", "link", "scws_id", "embed", "url", "file"):
            if k in ep:
                log(f"  {k}={str(ep[k])[:120]}")

except Exception as exc:
    log(f"ERROR: {exc!r}")

out.write_text("\n".join(lines), encoding="utf-8")
