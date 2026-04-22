"""
Menu Impostazioni URL - Download Center v2.1
Chiamato da main_menu.py -> Impostazioni -> opzione 4 (Cambio URL moduli)
"""
import os

try:
    from .url_manager import url_mgr
except ImportError:
    from url_manager import url_mgr


def _clear():
    os.system("cls" if os.name == "nt" else "clear")

def _header(title: str = "CAMBIO URL MODULI"):
    print("=" * 56)
    print(f"  IMPOSTAZIONI \u2014 {title}")
    print("=" * 56)
    print()

def _wait(msg: str = "  Premi INVIO per continuare..."):
    input(msg)


def _show_category(category: str):
    while True:
        _clear()
        _header(f"URL \u2014 {category.upper()}")
        urls  = url_mgr.urls.get(category, {})
        items = list(urls.items())
        if not items:
            print("  Nessun URL presente in questa sezione.")
            _wait(); return
        for i, (key, value) in enumerate(items, 1):
            label   = key.replace("_", " ").title()
            display = value if len(value) <= 60 else value[:57] + "..."
            print(f"  {i}. {label}")
            print(f"     {display}")
            print()
        print("  " + "-" * 44)
        print("  0.  Torna")
        print()
        scelta = input(f"  Seleziona URL da modificare (0-{len(items)}): ").strip()
        if scelta == "0": return
        try:
            idx = int(scelta) - 1
            if not (0 <= idx < len(items)): raise ValueError
        except ValueError:
            _wait("  \u2717 Scelta non valida. Premi INVIO..."); continue
        key, old_value = items[idx]
        label = key.replace("_", " ").title()
        _clear()
        _header(f"MODIFICA: {label}")
        print(f"  URL attuale:\n  {old_value}\n")
        new_value = input("  Nuovo URL (INVIO per annullare): ").strip()
        if not new_value:
            print("  \u2717 Operazione annullata."); _wait(); continue
        if not new_value.startswith(("http://", "https://")):
            print("  \u2717 URL non valido."); _wait(); continue
        print(f"\n  Nuovo URL: {new_value}")
        if input("  Salvare? (s / INVIO per annullare): ").strip().lower() == "s":
            url_mgr.set(category, key, new_value)
            print("  \u2713 URL aggiornato!")
        else:
            print("  \u2717 Annullato.")
        _wait()


def _scan_new_urls(base_path: str = "."):
    _clear()
    _header("AGGIORNA CON NUOVI URL")
    print("  Scansione in corso...\n")
    result    = url_mgr.scan_new_files(base_path)
    new_files = result["new_files"]
    new_urls  = result["new_urls"]
    if not new_files:
        print("  \u2713 Nessun nuovo file trovato.")
    else:
        print(f"  \u2713 Nuovi file rilevati: {len(new_files)}")
        for f in new_files: print(f"    \u2022 {f}")
        print()
    if not new_urls:
        print("  \u2713 Nessun nuovo URL da aggiungere.")
    else:
        total = sum(len(v) for v in new_urls.values())
        print(f"  \u2713 Nuovi URL aggiunti: {total}")
        for cat, urls in new_urls.items():
            print(f"\n  [{cat.upper()}]")
            for key, val in urls.items(): print(f"    \u2022 {key}: {val}")
    print()
    _wait()


def _reset_defaults():
    _clear()
    _header("RESET URL DEFAULT")
    print("  Tutti gli URL verranno ripristinati ai valori originali.\n")
    if input("  Confermi? (s / INVIO per annullare): ").strip().lower() == "s":
        url_mgr.reset()
        print("  \u2713 URL ripristinati ai valori di default!")
    else:
        print("  \u2717 Operazione annullata.")
    _wait()


def show_url_settings(base_path: str = "."):
    """Entry point \u2014 chiamato da main_menu.py"""
    while True:
        _clear()
        _header()

        # ── FIX: visualizza URL attuali prima del menu ─────────────
        # Legge il primo URL di ogni categoria (URL principale del sito)
        _cats = [
            ("Anime",    "anime"),
            ("Manga",    "manga"),
            ("Download", "download"),
        ]
        print("  URL Attuali:")
        for i, (label, cat) in enumerate(_cats, 1):
            vals = list(url_mgr.urls.get(cat, {}).values())
            url  = vals[0] if vals else "N/D"
            print(f"  {i}. {label:<10} {url}")
        print()
        # ──────────────────────────────────────────────────────────

        print("  +--------------------------------------+")
        print("  |  1.  URL sezione anime               |")
        print("  |  2.  URL sezione manga               |")
        print("  |  3.  URL sezione download            |")
        print("  |  4.  Aggiorna con nuovi URL          |")
        print("  |  5.  Reset URL default               |")
        print("  |  0.  Torna                           |")
        print("  +--------------------------------------+")
        print()
        scelta = input("  Scegli un'opzione (0-5): ").strip()
        if   scelta == "0": break
        elif scelta == "1": _show_category("anime")
        elif scelta == "2": _show_category("manga")
        elif scelta == "3": _show_category("download")
        elif scelta == "4": _scan_new_urls(base_path)
        elif scelta == "5": _reset_defaults()
        else: _wait("  \u2717 Opzione non valida. Premi INVIO...")
