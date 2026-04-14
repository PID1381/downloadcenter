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

    def get(self, site: str) -> Optional[str]:
        """Ottiene URL per un sito."""
        return self.urls.get(site)

    def get_all(self) -> Dict[str, str]:
        """Ottiene tutti gli URL."""
        return dict(self.urls)

    def set(self, site: str, url: str) -> None:
        """Imposta URL per un sito."""
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL non valido: {url}")
        self.urls[site] = url
        self.save()

    def delete(self, site: str) -> None:
        """Elimina URL per un sito."""
        if site in self.urls:
            del self.urls[site]
            self.save()

    def reset(self) -> None:
        """Ripristina URL di default."""
        self.urls = dict(self.default_urls)
        self.save()


# Istanza globale
url_mgr = URLManager()
