# =============================================================================
# __init__.py
# Modulo: AnimeUnity
# Branch: upgrade-3
# Struttura: /scripts/anime/moduli/animeunity/__init__.py
# =============================================================================

from .handlers_animeunity import (
    show_menu,
    get_updated,
    get_episodes,
    get_video_url,
    search_anime,
)

__all__ = [
    "show_menu",
    "get_updated",
    "get_episodes",
    "get_video_url",
    "search_anime",
]