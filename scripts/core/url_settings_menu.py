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
    print(f"  IMPOSTAZIONI — {title}")
    print("=" * 56)
    print()

def _wait(msg: str = "  Premi INVIO per continuare..."):
    input(msg)


def _show_category(category: str):
    while True:
        _clear()
        _header(f"URL — {category.upper()}")
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
            _wait("  ✗ Scelta non valida. Premi INVIO..."); continue
        key, old_value = items[idx]
        label = key.replace("_", " ").title()
        _clear()
        _header(f"MODIFICA: {label}")
        print(f"  URL attuale:
  {old_value}
")
        new_value = input("  Nuovo URL (INVIO per annullare): ").strip()
        if not new_value:
            print("  ✗ Operazione annullata."); _wait(); continue
        if not new_value.startswith(("http://", "https://")):
            print("  ✗ URL non valido."); _wait(); continue
        print(f"
  Nuovo URL: {new_value}")
        if input("  Salvare? (s / INVIO per annullare): ").strip().lower() == "s":
            url_mgr.set(category, key, new_value)
            print("  ✓ URL aggiornato!")
        else:
            print("  ✗ Annullato.")
        _wait()


def _scan_new_urls(base_path: str = "."):
    _clear()
    _header("AGGIORNA CON NUOVI URL")
    print("  Scansione in corso...
")
    result    = url_mgr.scan_new_files(base_path)
    new_files = result["new_files"]
    new_urls  = result["new_urls"]
    if not new_files:
        print("  ✓ Nessun nuovo file trovato.")
    else:
        print(f"  ✓ Nuovi file rilevati: {len(new_files)}")
        for f in new_files: print(f"    • {f}")
        print()
    if not new_urls:
        print("  ✓ Nessun nuovo URL da aggiungere.")
    else:
        total = sum(len(v) for v in new_urls.values())
        print(f"  ✓ Nuovi URL aggiunti: {total}")
        for cat, urls in new_urls.items():
            print(f"
  [{cat.upper()}]")
            for key, val in urls.items(): print(f"    • {key}: {val}")
    print()
    _wait()


def _reset_defaults():
    _clear()
    _header("RESET URL DEFAULT")
    print("  Tutti gli URL verranno ripristinati ai valori originali.
")
    if input("  Confermi? (s / INVIO per annullare): ").strip().lower() == "s":
        url_mgr.reset()
        print("  ✓ URL ripristinati ai valori di default!")
    else:
        print("  ✗ Operazione annullata.")
    _wait()


def show_url_settings(base_path: str = "."):
    """Entry point — chiamato da main_menu.py"""
    while True:
        _clear()
        _header()
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
        else: _wait("  ✗ Opzione non valida. Premi INVIO...")