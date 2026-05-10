from pathlib import Path
BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = BASE_DIR / 'scripts'
CORE_DIR    = SCRIPTS_DIR / 'core'
TEMP_DIR    = SCRIPTS_DIR / 'temp'
VARIE_DIR   = BASE_DIR / 'varie'
DOWNLOAD_DIR_DEFAULT = str(VARIE_DIR / 'Download')
LINK_DIR_DEFAULT     = str(VARIE_DIR / 'Link')
EXPORT_DIR_DEFAULT   = str(VARIE_DIR / 'export')
PREFS_FILE         = str(TEMP_DIR / 'prefs.json')
URLS_FILE          = str(TEMP_DIR / 'urls_config.json')
LOG_FILE           = str(TEMP_DIR / 'app.log')
CORE_JSON          = str(CORE_DIR / 'core.json')
STARTUP_CHECK_FILE = str(TEMP_DIR / 'startup_check.json')
PROJECT_NAME    = 'DOWNLOAD CENTER 3.0'
PROJECT_VERSION = '1.0'
_E = chr(27)
class Colors:
    RESET=_E+'[0m'; BOLD=_E+'[1m'; DIM=_E+'[2m'
    CYAN=_E+'[36m'; YELLOW=_E+'[33m'; GREEN=_E+'[32m'
    RED=_E+'[31m'; WHITE=_E+'[97m'; GRAY=_E+'[90m'
    BLUE=_E+'[34m'; MAGENTA=_E+'[35m'
    CYAN_BOLD=_E+'[1;36m'; GREEN_BOLD=_E+'[1;32m'; RED_BOLD=_E+'[1;31m'
class Box:
    TL=chr(0x2554);TR=chr(0x2557);BL=chr(0x255a);BR=chr(0x255d)
    H=chr(0x2550);V=chr(0x2551);ML=chr(0x2560);MR=chr(0x2563)
    WIDTH=66
