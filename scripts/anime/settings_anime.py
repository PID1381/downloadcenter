from scripts.core.settings_core import SCRIPTS_DIR, VARIE_DIR, TEMP_DIR
ANIME_DIR       = SCRIPTS_DIR / 'anime'
MODULI_DIR      = ANIME_DIR   / 'moduli'
ANIME_JSON      = ANIME_DIR   / 'anime.json'
ANIMEWORLD_DIR  = MODULI_DIR  / 'AnimeWorld'
ANIMEUNITY_DIR  = MODULI_DIR  / 'AnimeUnity'
UTILITA_DIR     = MODULI_DIR  / 'Utilita'
RIC_SCHEDE_DIR  = UTILITA_DIR / 'ricerca_schede'
ANIMECLICK_DIR  = RIC_SCHEDE_DIR / 'AnimeClick_anime'
ANIMESOCIAL_DIR = RIC_SCHEDE_DIR / 'Animesocial'
WATCHLIST_DIR   = UTILITA_DIR / 'Watchlist'
SCANLOCAL_DIR   = UTILITA_DIR / 'Scanlocal'
WATCHLIST_CORSO_FILE  = str(TEMP_DIR / 'watchlist_in_corso.json')
WATCHLIST_FINITE_FILE = str(TEMP_DIR / 'watchlist_finite.json')
SCHEDE_DIR     = VARIE_DIR / 'Schede_anime'
SCAN_DIR       = VARIE_DIR / 'Export' / 'Scan_serie_locali'
LINK_COMPL_DIR = VARIE_DIR / 'Link' / 'Serie_da_completare'
QUALITY_OPTIONS = ['360p', '480p', '720p', '1080p']
