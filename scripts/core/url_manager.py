"""
Core URL Manager v2.1
Gestione centralizzata degli URL base per siti anime/manga/download.

Compatibilita import:
  from scripts.core.url_manager import get as get_url
  from scripts.core.url_manager import get_all
  import scripts.core.url_manager as _url_mgr  ->  _url_mgr.get_all()
"""
import json
import re
from pathlib import Path
from typing import Dict, Optional


class URLManager:
    """Gestione centralizzata URL base per siti."""

    DEFAULT_URLS: Dict[str, Dict[str, str]] = {
        "anime": {
            "animeworld":        "https://www.animeworld.ac",
            "animeworld_search": "https://www.animeworld.ac/search",
            "animeworld_anime":  "https://www.animeworld.ac/anime",
            "animeunity":        "https://www.animeunity.so",
            "animeunity_archivio": "https://www.animeunity.so/archivio",
            "animeunity_search": "https://www.animeunity.so/archivio",
            "animeclick":        "https://www.animeclick.it",
            "animeclick_news":   "https://www.animeclick.it/news/rubrica/6/uscite-manga-del-mese",
        },
        "manga": {
            "mangacomicsmarket":          "https://www.mangacomicsmarket.it",
            "mangacomicsmarket_catalogo": "https://www.mangacomicsmarket.it/catalogo?genre=Manga-15&merchant=5&availability=1",
            "vinted":                     "https://www.vinted.it",
            "vinted_catalog":             "https://www.vinted.it/catalog/2309-entertainment",
        },
        "download": {
            "amazon":        "https://www.amazon.it",
            "amazon_search": "https://www.amazon.it/s?k={query}&i=",
        },
    }

    _SCAN_DIRS = ["scripts/anime", "scripts/manga", "scripts/download", "scripts/core"]
    _CAT_MAP   = {
        "scripts/anime":    "anime",
        "scripts/manga":    "manga",
        "scripts/download": "download",
        "scripts/core":     "download",
    }

    def __init__(self):
        try:
            from .config import config
            self._temp_dir = config.temp_dir
        except Exception:
            self._temp_dir = Path("scripts/temp")

        self._url_file    = self._temp_dir / "site_urls.json"
        self._scan_record = self._temp_dir / "scanned_files.json"
        self.urls         = self._load()

    def _load(self) -> Dict[str, Dict[str, str]]:
        base = {cat: dict(urls) for cat, urls in self.DEFAULT_URLS.items()}
        if self._url_file.exists():
            try:
                with open(self._url_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Supporto legacy: file piatto {chiave: url} -> migra a categorie
                if data and not any(isinstance(v, dict) for v in data.values()):
                    for key, val in data.items():
                        if any(k in key for k in ["animeworld", "animeclick"]):
                            base["anime"][key] = val
                        elif any(k in key for k in ["manga", "vinted"]):
                            base["manga"][key] = val
                        else:
                            base["download"][key] = val
                else:
                    for cat, urls in data.items():
                        base.setdefault(cat, {}).update(urls)
            except Exception:
                pass
        return base

    def save(self) -> None:
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._url_file, "w", encoding="utf-8") as f:
                json.dump(self.urls, f, indent=2, ensure_ascii=False)
        except Exception as e:
            try:
                from .logger import logger
                logger.error(f"Errore salvataggio URL: {e}", module="url_manager")
            except Exception:
                pass

    def get(self, category: str, key: str = "") -> Optional[str]:
        """
        get("anime", "animeclick")  -> URL per categoria+chiave
        get("animeclick")           -> ricerca legacy in tutte le categorie
        """
        if key:
            return (
                self.urls.get(category, {}).get(key)
                or self.DEFAULT_URLS.get(category, {}).get(key)
            )
        for cat_urls in self.urls.values():
            if category in cat_urls:
                return cat_urls[category]
        return None

    def get_all(self) -> Dict[str, Dict[str, str]]:
        return {cat: dict(urls) for cat, urls in self.urls.items()}

    def set(self, category: str, key: str, url: str = "") -> None:
        """
        set("anime", "animeclick", "https://...")   -> 3 argomenti
        set("animeclick", "https://...")             -> legacy 2 argomenti
        """
        if not url:
            url = key
            for cat, cat_urls in self.urls.items():
                if category in cat_urls:
                    if not url.startswith(("http://", "https://")):
                        raise ValueError(f"URL non valido: {url}")
                    cat_urls[category] = url
                    self.save()
                    return
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"URL non valido: {url}")
            self.urls.setdefault("download", {})[category] = url
            self.save()
            return
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL non valido: {url}")
        self.urls.setdefault(category, {})[key] = url
        self.save()

    def delete(self, category: str, key: str = "") -> None:
        if key:
            if key in self.urls.get(category, {}):
                del self.urls[category][key]
                self.save()
        else:
            for cat_urls in self.urls.values():
                if category in cat_urls:
                    del cat_urls[category]
                    self.save()
                    return

    def reset(self) -> None:
        self.urls = {cat: dict(urls) for cat, urls in self.DEFAULT_URLS.items()}
        self.save()

    def scan_new_files(self, base_path: str = ".") -> Dict:
        base   = Path(base_path)
        url_re = re.compile(r"https?://[^\s'\"\\>]+")

        if self._scan_record.exists():
            try:
                with open(self._scan_record, "r", encoding="utf-8") as f:
                    known_files = set(json.load(f))
            except Exception:
                known_files = set()
        else:
            known_files = set()

        current_files: set = set()
        for d in self._SCAN_DIRS:
            scan_dir = base / d
            if scan_dir.exists():
                for fp in scan_dir.rglob("*.py"):
                    current_files.add(str(fp.relative_to(base)))

        new_files = current_files - known_files

        self._temp_dir.mkdir(parents=True, exist_ok=True)
        with open(self._scan_record, "w", encoding="utf-8") as f:
            json.dump(sorted(current_files), f, indent=2)

        if not new_files:
            return {"new_files": [], "new_urls": {}}

        known_urls = {v for cat in self.urls.values() for v in cat.values()}
        added_urls: Dict[str, Dict[str, str]] = {}

        for rel_path in new_files:
            fp = base / rel_path
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue

            cat = "download"
            for d, c in self._CAT_MAP.items():
                if rel_path.startswith(d):
                    cat = c
                    break

            for found_url in url_re.findall(text):
                found_url = found_url.rstrip(".,)'\"")
                if found_url in known_urls:
                    continue
                domain = re.sub(r"^https?://(www\.)?", "", found_url).split("/")[0].replace(".", "_")
                key, counter = domain, 1
                while key in self.urls.get(cat, {}):
                    key = f"{domain}_{counter}"
                    counter += 1
                self.urls.setdefault(cat, {})[key] = found_url
                known_urls.add(found_url)
                added_urls.setdefault(cat, {})[key] = found_url

        if added_urls:
            self.save()

        return {"new_files": sorted(new_files), "new_urls": added_urls}


# ── Istanza globale ───────────────────────────────────────────────────────────
url_mgr = URLManager()


# ── Funzioni modulo ───────────────────────────────────────────────────────────
# Tutti i pattern di import supportati:
#   from scripts.core.url_manager import get as get_url
#   from scripts.core.url_manager import get_all
#   from scripts.core.url_manager import get_url
#   import scripts.core.url_manager as _url_mgr  ->  _url_mgr.get_all()

def get(category: str, key: str = "") -> Optional[str]:
    """from scripts.core.url_manager import get as get_url"""
    return url_mgr.get(category, key)


def get_url(category: str, key: str = "") -> str:
    """from scripts.core.url_manager import get_url"""
    return url_mgr.get(category, key) or ""


def get_all() -> Dict[str, Dict[str, str]]:
    """import url_manager as _url_mgr -> _url_mgr.get_all()"""
    return url_mgr.get_all()


def set_url(category: str, key: str, url: str = "") -> None:
    url_mgr.set(category, key, url)


def reset_urls() -> None:
    url_mgr.reset()


def scan_new_files(base_path: str = ".") -> Dict:
    return url_mgr.scan_new_files(base_path)