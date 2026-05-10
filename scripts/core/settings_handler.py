# scripts/core/settings_handler.py
# [MODIFICA run#1] Aggiunto path-guard + validazione os.path.isdir in change_download_dir()
import sys as _sys
import os as _os

_PROJECT_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

import json
import os

from scripts.core.settings_core import PREFS_FILE, URLS_CONFIG, colorize


def _load_prefs() -> dict:
    if os.path.exists(PREFS_FILE):
        with open(PREFS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_prefs(prefs: dict) -> None:
    with open(PREFS_FILE, "w", encoding="utf-8") as fh:
        json.dump(prefs, fh, indent=2, ensure_ascii=False)


def run_settings_menu() -> None:
    """Menu impostazioni interattivo."""
    while True:
        print(colorize("\n── Impostazioni ──", "cyan"))
        print("1) Toggle debug")
        print("2) Toggle headless browser")
        print("3) Cambia cartella download")
        print("4) Override URL")
        print("5) Toggle yt-dlp")
        print("0) Indietro")
        choice = input("Scelta: ").strip()
        if choice == "1":
            toggle_debug()
        elif choice == "2":
            toggle_headless()
        elif choice == "3":
            change_download_dir()
        elif choice == "4":
            override_urls()
        elif choice == "5":
            toggle_ytdlp()
        elif choice == "0":
            break
        else:
            print(colorize("Scelta non valida.", "red"))


def toggle_debug() -> None:
    prefs = _load_prefs()
    prefs["debug"] = not prefs.get("debug", False)
    _save_prefs(prefs)
    state = colorize("ON", "green") if prefs["debug"] else colorize("OFF", "red")
    print(f"Debug: {state}")


def toggle_headless() -> None:
    prefs = _load_prefs()
    prefs["headless"] = not prefs.get("headless", True)
    _save_prefs(prefs)
    state = colorize("ON", "green") if prefs["headless"] else colorize("OFF", "red")
    print(f"Headless: {state}")


def change_download_dir() -> None:
    """[MODIFICA run#1] Validazione: il path deve esistere ed essere una directory."""
    new_dir = input("Nuova cartella download (path assoluto): ").strip()
    if not new_dir:
        print(colorize("Operazione annullata.", "yellow"))
        return
    if not os.path.isdir(new_dir):
        print(colorize(f"[ERRORE] Il percorso '{new_dir}' non esiste o non è una directory.", "red"))
        return
    prefs = _load_prefs()
    prefs["download_dir"] = new_dir
    _save_prefs(prefs)
    print(colorize(f"Cartella download impostata: {new_dir}", "green"))


def override_urls() -> None:
    data = {}
    if os.path.exists(URLS_CONFIG):
        with open(URLS_CONFIG, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print(colorize("URL correnti:", "cyan"))
        for k, v in data.items():
            print(f"  {k}: {v}")
    key   = input("Chiave URL da modificare: ").strip()
    value = input("Nuovo valore: ").strip()
    if key and value:
        data[key] = value
        with open(URLS_CONFIG, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        print(colorize("URL aggiornato.", "green"))


def toggle_ytdlp() -> None:
    prefs = _load_prefs()
    prefs["use_ytdlp"] = not prefs.get("use_ytdlp", False)
    _save_prefs(prefs)
    state = colorize("ON", "green") if prefs["use_ytdlp"] else colorize("OFF", "red")
    print(f"yt-dlp: {state}")
