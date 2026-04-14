"""
Core URL Manager v2.0
Gestione centralizzata degli URL base per siti anime/manga.
Evita modifiche manuali quando i domini cambiano.

FUNZIONALITA':
  - Gestione URL base per siti multipli
  - Persistenza su file site_urls.json
  - Reset ai default
  - Validazione URL
"""
import json
from pathlib import Path
from typing import Dict, Optional


class URLManager:
    """Gestione centralizzata URL base per siti."""

    def __init__(self):
        try:
            from .config import config
            self._temp_dir = config.temp_dir
        except Exception:
            self._temp_dir = Path("scripts/temp")
        
        self._url_file = self._temp_dir / "site_urls.json"
        
        # URL base default (modificabili)
        self.default_urls: Dict[str, str] = {
            "animeworld": "https://www.animeworld.ac",
            "animeworld_search": "https://www.animeworld.ac/search",
            "animeworld_anime": "https://www.animeworld.ac/anime",
            # Aggiungi altri domini qui quando servono
        }
        
        self.urls = self._load()

    def _load(self) -> Dict[str, str]:
        """Carica gli URL dal file, usa default se non esiste."""
        if self._url_file.exists():
            try:
                with open(self._url_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Merge con defaults per eventuali nuovi siti
                return {**self.default_urls, **data}
            except Exception:
                pass
        return dict(self.default_urls)

    def save(self) -> None:
        """Salva gli URL nel file."""
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._url_file, "w", encoding="utf-8") as f:
                json.dump(self.urls, f, indent=2, ensure_ascii=False)
        except Exception as e:
            from .logger import logger
            logger.error(f"Errore salvataggio URL: {e}", module="url_manager")

    def get(self, site_key: str, default: str = "") -> str:
        """Ottiene l'URL base per un sito."""
        return self.urls.get(site_key, default or self.default_urls.get(site_key, ""))

    def set(self, site_key: str, url: str) -> None:
        """Modifica l'URL base per un sito."""
        self.urls[site_key] = url.rstrip("/")  # Rimuovi trailing slash
        self.save()

    def reset(self, site_key: str) -> None:
        """Ripristina l'URL di default per un sito."""
        if site_key in self.default_urls:
            self.urls[site_key] = self.default_urls[site_key]
            self.save()

    def reset_all(self) -> None:
        """Ripristina tutti gli URL ai default."""
        self.urls = dict(self.default_urls)
        self.save()

    def get_all(self) -> Dict[str, str]:
        """Ritorna tutti gli URL."""
        return dict(self.urls)

    def list_sites(self) -> list:
        """Elenca tutti i siti configurati."""
        return sorted(self.urls.keys())

    def validate_url(self, url: str) -> bool:
        """Valida che l'URL sia un HTTP/HTTPS valido."""
        return url.startswith(("http://", "https://"))

    def get_info(self, site_key: str) -> Dict:
        """Ritorna info dettagliate su un sito."""
        default = self.default_urls.get(site_key, "")
        current = self.urls.get(site_key, default)
        return {
            "key": site_key,
            "current": current,
            "default": default,
            "modified": current != default,
        }


url_mgr = URLManager()