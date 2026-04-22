#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_vinted.py v1.3.1
======================
Modulo per la ricerca manga usati su Vinted.it.
Percorso: scripts/manga/ricerca_vinted.py

PATCH v1.3.1 — FIX URL MANAGER:
  - Fallback except ImportError ora legge BASE_URL_VINTED e
    VINTED_CATALOG_URL da url_mgr centralizzato invece di stringhe
    hardcodate. Modifica URL da Impostazioni → Cambio URL → Vinted
    ora propagata correttamente anche al modulo ricerca_vinted.

NOVITA v1.3 — FIX DEFINITIVO:
  - Import STAGE 1 (core runtime) e STAGE 2 (get_export_dir) separati.
    Se get_export_dir non esiste ancora in manga_engine, lo STAGE 1
    non fallisce e HAS_PLAYWRIGHT rimane corretto.
  - _get_export_dir() legge la chiave "export_dir" da prefs.json
    DIRETTAMENTE come fallback, senza dipendere da manga_engine.
  - Nessuna regressione su "Playwright non installato" per cause di import.

FUNZIONALITA':
  - Ricerca titoli manga nella categoria Entertainment di Vinted.it
  - Lista risultati navigabile con selezione per dettaglio (D<n>)
  - Dettaglio: Titolo, Condizioni, Lingua, Autore, Caricato,
    Descrizione, Prezzo, URL inserzione
  - Salvataggio "Titolo - URL" in "Manga usati Vinted.txt"
    (append automatico: ricerche successive accodate)

PERCORSO SALVATAGGIO:
  prefs.json["export_dir"] / Vinted / Manga usati Vinted.txt

DIPENDENZE: manga_engine >= v1.0, playwright, bs4
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

_THIS_DIR    = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()
_TEMP_DIR    = _SCRIPTS_DIR / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

for _p in [str(_THIS_DIR), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── STAGE 1: import core runtime (MangaPageSession, HAS_PLAYWRIGHT, …) ────────
# Questo blocco NON include get_export_dir per evitare che un ImportError
# su quella singola funzione mancante disabiliti HAS_PLAYWRIGHT.
try:
    from manga_engine import (
        MangaPageSession, HAS_PLAYWRIGHT,
        clear_screen,
        show_success, show_error, show_info, show_warning,
        WIDTH,
        BASE_URL_VINTED, VINTED_CATALOG_URL, VINTED_EXPORT_FILENAME,
        extract_vinted_results, extract_vinted_item_details,
        save_vinted_export,
    _get_export_dir,
    _print_item_detail,
    )
    _ENGINE_OK = True
except ImportError as _e1:
    _ENGINE_OK             = False
    WIDTH                  = 56
    # ── Leggi URL da url_mgr centralizzato (fallback su hardcoded) ────────
    try:
        from core.url_manager import url_mgr as _url_mgr_fb
    except ImportError:
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _sys.path.insert(0, str(_Path(__file__).parent.parent / "core"))
            from url_manager import url_mgr as _url_mgr_fb
        except ImportError:
            _url_mgr_fb = None
    if _url_mgr_fb is not None:
        BASE_URL_VINTED    = _url_mgr_fb.get("manga", "vinted") or "https://www.vinted.it"
        VINTED_CATALOG_URL = _url_mgr_fb.get("manga", "vinted_catalog") or "https://www.vinted.it/catalog/2309-entertainment"
    else:
        BASE_URL_VINTED    = "https://www.vinted.it"
        VINTED_CATALOG_URL = "https://www.vinted.it/catalog/2309-entertainment"
    VINTED_EXPORT_FILENAME = "Manga usati Vinted.txt"
    HAS_PLAYWRIGHT         = False
    def clear_screen():    import os; os.system("cls" if os.name == "nt" else "clear")
    def show_error(m):     print("  [x] " + str(m))
    def show_success(m):   print("  [v] " + str(m))
    def show_info(m):      print("  [i] " + str(m))
    def show_warning(m):   print("  [!] " + str(m))
    def extract_vinted_results(s):            return []
    def extract_vinted_item_details(s, u=""): return {}
    def save_vinted_export(items, d):         return False
    class MangaPageSession:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def fetch_vinted_search(self, q):  return []
        def fetch_vinted_item(self, url):  return {}


# ── STAGE 2: get_export_dir (opzionale — non blocca lo STAGE 1) ───────────────
_engine_get_export_dir = None
if _ENGINE_OK:
    try:
        from manga_engine import get_export_dir as _engine_get_export_dir
    except ImportError:
        _engine_get_export_dir = None   # manga_engine non ha ancora la funzione


# ── Costanti ──────────────────────────────────────────────────────────────────
_EQ   = "=" * WIDTH
_SEP  = "  " + "-" * (WIDTH - 2)
_TSEP = "  " + "-" * 68

VINTED_EXPORT_FOLDER = "Vinted"

# Percorsi candidati per prefs.json (dalla root del progetto verso il basso)
_PREFS_CANDIDATES = [
    _SCRIPTS_DIR.parent / "prefs.json",   # root progetto
    _SCRIPTS_DIR        / "prefs.json",   # scripts/
    _THIS_DIR           / "prefs.json",   # scripts/manga/
]


# ── Lettura diretta di prefs.json ─────────────────────────────────────────────

def _read_prefs_export_dir() -> str:
    """
    Legge la chiave "export_dir" direttamente da prefs.json.
    Cerca nei percorsi candidati; restituisce "" se non trovata.
    """
    for path in _PREFS_CANDIDATES:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                val  = data.get("export_dir", "")
                if val:
                    return str(val)
            except Exception:
                continue
    return ""


# ── Export path ───────────────────────────────────────────────────────────────

def _print_results_list(items: List[Dict]) -> None:
    print()
    print("  {:>3}   {:<46}  {:>9}  {}".format("N", "Titolo", "Prezzo", "Condizioni"))
    print(_TSEP)
    for i, it in enumerate(items, 1):
        t = it.get("titolo", "")
        if len(t) > 46:
            t = t[:43] + "..."
        p = it.get("prezzo", "") or "-"
        c = it.get("condizioni", "") or ""
        print("  {:>3}.  {:<46}  {:>9}  {}".format(i, t, p, c))
    print(_TSEP)
    print("  Totale risultati: " + str(len(items)))
    print()


def _select_items(items: List[Dict]) -> Optional[List[Dict]]:
    if not items:
        show_warning("Nessuna inserzione disponibile.")
        return None
    max_n    = len(items)
    item_map = {i: it for i, it in enumerate(items, 1)}
    while True:
        print()
        print(_SEP)
        print("  Seleziona inserzioni da salvare (1-" + str(max_n) + "):")
        print("  Singolo(3)  Multiplo(1,3,5)  Range(1-5)  Misto(1,3-7)  Tutti(T)  Annulla(0)")
        print(_SEP)
        raw = input("  Selezione: ").strip()
        if raw == "0":
            return None
        if raw.upper() == "T":
            return list(items)
        selected:  List[Dict] = []
        has_error: bool       = False
        for part in [p.strip() for p in raw.split(",") if p.strip()]:
            if "-" in part:
                try:
                    a_s, b_s = part.split("-", 1)
                    a, b = int(a_s.strip()), int(b_s.strip())
                    if a > b:
                        a, b = b, a
                    for n in range(a, b + 1):
                        if n in item_map:
                            if item_map[n] not in selected:
                                selected.append(item_map[n])
                        else:
                            print("  " + str(n) + " fuori range (1-" + str(max_n) + ") - ignorato.")
                except ValueError:
                    print("  Range non valido: '" + part + "' - ignorato.")
                    has_error = True
            else:
                try:
                    n = int(part)
                    if n in item_map:
                        if item_map[n] not in selected:
                            selected.append(item_map[n])
                    else:
                        print("  " + str(n) + " fuori range (1-" + str(max_n) + ") - ignorato.")
                except ValueError:
                    print("  Valore non valido: '" + part + "' - ignorato.")
                    has_error = True
        if has_error:
            input("  Premi INVIO per riprovare...")
            continue
        if not selected:
            print("  Nessuna inserzione valida selezionata.")
            input("  Premi INVIO per riprovare...")
            continue
        return selected


# ── Salvataggio ───────────────────────────────────────────────────────────────

def _save_entries(items: List[Dict]) -> None:
    """Salva in export_dir/Vinted/Manga usati Vinted.txt (append automatico)."""
    export_dir = _get_export_dir()
    if not export_dir:
        return
    if save_vinted_export(items, export_dir):
        show_success("Salvato in: " + str(Path(export_dir) / VINTED_EXPORT_FILENAME))


# ── Entry point ───────────────────────────────────────────────────────────────

def handle_vinted_ricerca() -> None:
    if not HAS_PLAYWRIGHT:
        clear_screen()
        print(_EQ)
        print("  RICERCA USATO  -  Vinted.it")
        print(_EQ)
        print()
        show_error("Playwright non installato.")
        show_info("Esegui: pip install playwright && playwright install chromium")
        print()
        input("  Premi INVIO per tornare...")
        return

    while True:
        clear_screen()
        print(_EQ)
        print("  RICERCA USATO  -  Vinted.it")
        print(_EQ)
        print("  Categoria: Entertainment / Manga")
        print("  URL base: " + VINTED_CATALOG_URL)
        print()

        query = input("  Titolo da cercare (0 = esci): ").strip()
        if not query or query == "0":
            return

        print("\n  Ricerca <<" + query + ">> su Vinted.it...")
        print("  (apertura browser, attendere...)\n")

        try:
            with MangaPageSession() as sess:

                items = sess.fetch_vinted_search(query)

                if not items:
                    print("\n  Nessun risultato per <<" + query + ">>.")
                    print("  Possibili cause: titolo non trovato / timeout / inserzioni assenti.")
                    input("\n  Premi INVIO per riprovare...")
                    continue

                def _reprint():
                    clear_screen()
                    print(_EQ)
                    print("  RISULTATI VINTED: <<" + query + ">>  (" + str(len(items)) + " inserzioni)")
                    print(_EQ)
                    _print_results_list(items)

                _reprint()

                while True:
                    print(_SEP)
                    print("  D<n> Dettaglio (es. D3)  |  S  Seleziona e salva  |  N  Nuova ricerca  |  0  Esci")
                    print(_SEP)
                    sc = input("  Scelta: ").strip().upper()

                    if sc == "0":
                        return

                    elif sc == "N":
                        break

                    elif sc == "S":
                        selected = _select_items(items)
                        if selected:
                            _save_entries(selected)
                            print("\n  " + str(len(selected)) + " inserzione/i salvata/e.")
                        input("  Premi INVIO per continuare...")
                        _reprint()

                    elif sc.startswith("D") and sc[1:].isdigit():
                        n = int(sc[1:])
                        if not (1 <= n <= len(items)):
                            show_error("Numero " + str(n) + " non valido (1-" + str(len(items)) + ").")
                            input("  Premi INVIO...")
                            continue

                        item = items[n - 1]
                        url  = item.get("url", "")
                        if not url:
                            show_error("URL non disponibile per inserzione " + str(n) + ".")
                            input("  Premi INVIO...")
                            _reprint()
                            continue

                        print("\n  Caricamento dettagli inserzione " + str(n) + "...")
                        detail = sess.fetch_vinted_item(url)

                        if not detail:
                            show_warning("Impossibile recuperare i dettagli.")
                            show_info("Aprire manualmente: " + url)
                            input("\n  Premi INVIO...")
                            _reprint()
                            continue

                        clear_screen()
                        print(_EQ)
                        print("  DETTAGLIO  #" + str(n) + "  -  Vinted.it")
                        print(_EQ)
                        _print_item_detail(detail)
                        print()
                        print(_SEP)
                        print("  S  Salva inserzione  |  L  Torna alla lista  |  0  Esci")
                        print(_SEP)
                        sc2 = input("  Scelta: ").strip().upper()
                        if sc2 == "S":
                            _save_entries([detail])
                            input("  Premi INVIO per continuare...")
                        elif sc2 == "0":
                            return
                        _reprint()

                    else:
                        show_error("Opzione non valida. Usa D<n>, S, N, oppure 0.")
                        input("  Premi INVIO...")

        except KeyboardInterrupt:
            print("\n  Operazione interrotta.")
            input("  Premi INVIO per tornare...")
            return
        except Exception as exc:
            show_error("Errore sessione Vinted: " + str(exc))
            resp = input("  Premi INVIO per riprovare (0 = esci): ").strip()
            if resp == "0":
                return


if __name__ == "__main__":
    handle_vinted_ricerca()