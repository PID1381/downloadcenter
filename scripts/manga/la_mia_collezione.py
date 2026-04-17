#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
la_mia_collezione.py v2.4 — RICERCA PER TITOLO / AUTORE / TITOLO+AUTORE
=========================================================================
Modulo per La mia collezione manga.
Percorso: scripts/manga/la_mia_collezione.py

PATCH v2.4 (rispetto a v2.3):
  - Menu ricerca espanso con 3 modalità:
      1. Solo titolo
      2. Solo autore/staff
      3. Titolo + Autore
  - Ogni modalità offre singola o multipla
  - Nuovi metodi MangaPageSession usati:
      fetch_animeclick_manga_search(query)          -> solo titolo (già esistente)
      fetch_animeclick_manga_search_staff(staff)    -> solo staff  (nuovo in v1.4)
      fetch_animeclick_manga_search_combined(t, s)  -> titolo+staff (nuovo in v1.4)
  - _handle_ricerca_titolo() rinominata _handle_ricerca_manga()
  - Retrocompatibilità: se i nuovi metodi non esistono in MangaPageSession,
    si usa il fallback su fetch_animeclick_manga_search(query)
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_THIS_DIR    = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()
_ANIME_DIR   = _SCRIPTS_DIR / "anime"
_TEMP_DIR    = _SCRIPTS_DIR / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

for _p in [str(_ANIME_DIR), str(_THIS_DIR), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Import da manga_engine ────────────────────────────────────────────────────
try:
    from manga_engine import (
        load_collection, save_collection,
        export_collection_csv, export_collection_txt,
        get_collection_path, get_link_dir,
        sanitize_filename, clear_screen,
        show_success, show_error, show_info, show_warning,
        WIDTH, MangaPageSession,
    )
    _ENGINE_OK = True
except ImportError:
    _ENGINE_OK = False
    WIDTH = 56
    def clear_screen():
        import os; os.system("cls" if os.name == "nt" else "clear")
    def show_error(m):   print(f"  [x] {m}")
    def show_success(m): print(f"  [v] {m}")
    def show_info(m):    print(f"  [i] {m}")
    def show_warning(m): print(f"  [!] {m}")
    def sanitize_filename(n): return re.sub(r'[\\/:*?"<>|]', "_", n).strip()
    def get_link_dir():
        import json
        try:
            with open(_TEMP_DIR / "prefs.json", encoding="utf-8") as f:
                return json.load(f).get("default_link_dir", "")
        except Exception: return ""
    def get_collection_path(): return _TEMP_DIR / "lamiacollezione.json"
    def load_collection(path=None):
        import json; fp = path or get_collection_path()
        try:
            with open(fp, encoding="utf-8") as f: d = json.load(f)
            return d if isinstance(d, list) else []
        except Exception: return []
    def save_collection(collection, path=None):
        import json; fp = path or get_collection_path()
        try:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(collection, f, indent=2, ensure_ascii=False)
            return True
        except Exception: return False
    def export_collection_csv(collection, export_path):
        import csv
        try:
            with open(export_path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(
                    f, fieldnames=["titolo","edizione","variant","stato_italia","volumi"],
                    extrasaction="ignore")
                w.writeheader(); w.writerows(collection)
            return True
        except Exception: return False
    def export_collection_txt(collection, export_path):
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                for e in sorted(collection, key=lambda r: r.get("titolo","").lower()):
                    f.write(e.get("titolo","") + "\n")
            return True
        except Exception: return False
    MangaPageSession = None

# ── Import da ricerca_scheda_anime ─────────────────────────────────────────────
try:
    import ricerca_scheda_anime as _rsa
    _AnimeTracker       = _rsa.AnimeTracker
    _build_groups_fn    = _rsa._build_groups       if hasattr(_rsa, "_build_groups")            else None
    _print_groups_fn    = _rsa._print_multi_groups  if hasattr(_rsa, "_print_multi_groups")      else None
    _parse_multi_sel_fn = _rsa._parse_multi_selection if hasattr(_rsa, "_parse_multi_selection") else None
    _BASE_URL           = _rsa.BASE_URL
    _IMPORT_OK          = True
except ImportError:
    _IMPORT_OK    = False
    _AnimeTracker = None
    _BASE_URL     = "https://www.animeclick.it"
    _build_groups_fn    = None
    _print_groups_fn    = None
    _parse_multi_sel_fn = None

# ── Monkey-patch v2.3: search_manga() con Playwright ──────────────────────────
if _IMPORT_OK and _AnimeTracker is not None:
    if not hasattr(_AnimeTracker, "search_manga"):
        def _search_manga(self, query: str, silent: bool = False) -> list:
            if MangaPageSession is None:
                if not silent:
                    show_error("MangaPageSession non disponibile.")
                return []
            try:
                with MangaPageSession() as sess:
                    return sess.fetch_animeclick_manga_search(query)
            except Exception as e:
                if not silent:
                    show_error(f"Errore search_manga: {e}")
                return []
        _AnimeTracker.search_manga = _search_manga

# ── Costanti modulo ────────────────────────────────────────────────────────────
_SEP = "  " + "-" * (WIDTH - 2)
_EQ  = "=" * WIDTH

_MESI_IT = [
    "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

COLLECTION_FOLDER = "La mia collezione manga"
_COMPLETATO_RE    = re.compile(r"complet|conclus|finit|terminat|fine\b", re.IGNORECASE)
_COL_CAPS         = {"titolo": 32, "edizione": 20, "variant": 14, "stato": 16, "volumi": 8}


def _date_str() -> str:
    n = date.today()
    return f"{n.day:02d} {_MESI_IT[n.month]} {n.year}"

def _is_completato(stato: str) -> bool:
    return bool(_COMPLETATO_RE.search(stato))

def _ask_field(label: str, current: str) -> str | None:
    val = input(f"  {label} [{current or 'vuoto'}]: ").strip()
    if val == "0": return None
    return val if val else current


# ── Cartella export ────────────────────────────────────────────────────────────

def _get_export_folder() -> str | None:
    base = get_link_dir()
    if not base:
        print("\n  Percorso 'default_link_dir' non configurato.")
        base = input("  Inserisci percorso base alternativo (invio = annulla): ").strip()
        if not base: print("  Operazione annullata."); return None
    folder = str(Path(base) / COLLECTION_FOLDER)
    try: Path(folder).mkdir(parents=True, exist_ok=True); return folder
    except OSError as exc: show_error(f"Impossibile creare la cartella: {exc}"); return None


# ── Gestione collezione ────────────────────────────────────────────────────────

def _make_entry(titolo, edizione, variant, stato, volumi) -> dict:
    return {"titolo": titolo, "edizione": edizione, "variant": variant,
            "stato_italia": stato, "volumi": volumi}

def _add_to_collection(titolo, edizione, variant, stato, volumi) -> bool:
    rows = load_collection()
    dup  = next((i for i, r in enumerate(rows) if r.get("titolo","").lower() == titolo.lower()), -1)
    if dup >= 0:
        print(f"\n  '{titolo}' è già presente nella collezione.")
        if input("  Sovrascrivere? (s/n): ").strip().lower() not in ("s","si","y"):
            return False
        rows[dup] = _make_entry(titolo, edizione, variant, stato, volumi)
    else:
        rows.append(_make_entry(titolo, edizione, variant, stato, volumi))
    if save_collection(rows):
        show_success(f"Salvato in: {get_collection_path()}"); return True
    return False


# ── Tabella ASCII ──────────────────────────────────────────────────────────────

def _build_table_lines(rows_data: list) -> list:
    if not rows_data: return ["  (nessun elemento da mostrare)"]
    headers = ["N","Titolo","Edizione","Variant","Stato Italia","Volumi"]
    table   = []
    for i, row in enumerate(rows_data, 1):
        table.append([str(i), row.get("titolo","") or "", row.get("edizione","") or "",
                      row.get("variant","") or "", row.get("stato_italia","") or "",
                      row.get("volumi","") or ""])
    caps   = [999, _COL_CAPS["titolo"], _COL_CAPS["edizione"], _COL_CAPS["variant"],
              _COL_CAPS["stato"], _COL_CAPS["volumi"]]
    widths = [len(h) for h in headers]
    for row in table:
        for i, c in enumerate(row): widths[i] = max(widths[i], len(c))
    widths = [min(w, caps[i]) for i, w in enumerate(widths)]

    def _cell(val, w):
        if len(val) > w: val = val[:w-2] + ".."
        return val.ljust(w)

    def _border(left, mid, right, fill):
        return "  " + left + mid.join(fill*(w+2) for w in widths) + right

    top_bar  = _border('┌','┬','┐','─')
    head_sep = _border('├','┼','┤','─')
    bot_bar  = _border('└','┴','┘','─')

    def _row_str(vals):
        parts = [f" {_cell(v, widths[i])} " for i, v in enumerate(vals)]
        return '  │' + '│'.join(parts) + '│'

    out = [top_bar, _row_str(headers), head_sep]
    for row in table: out.append(_row_str(row))
    out.append(bot_bar)
    return out


# ── Prompt salvataggio ─────────────────────────────────────────────────────────

def _prompt_save(details: dict) -> None:
    print(); print(_SEP)
    if input("  Vuoi salvare questo manga nella tua collezione? (s/n): ").strip().lower() \
            not in ("s","si","y"):
        return
    titolo = (details.get("titolo_originale") or details.get("titolo") or details.get("title","")).strip()
    stato  = (details.get("stato_italia") or details.get("stato","")).strip()
    volumi = details.get("volumi","").strip()
    if not titolo: titolo = input("  Titolo non rilevato. Inseriscilo: ").strip()
    if not titolo: print("  Salvataggio annullato (titolo mancante)."); return
    print(); print(f"  Titolo : {titolo}")
    print(f"  Stato  : {stato or '(non rilevato)'}")
    print(f"  Volumi : {volumi or '(non rilevato)'}")
    print("\n  Campi opzionali (INVIO = lascia vuoto):")
    edizione = input("  Edizione (es. Star Comics, Planet Manga): ").strip()
    variant  = input("  Presenza variant (es. Si, No, Variant 1): ").strip()
    if not stato:  stato  = input("  Stato in Italia [invio = vuoto]: ").strip()
    if not volumi: volumi = input("  Volumi (es. 1-12) [invio = vuoto]: ").strip()
    _add_to_collection(titolo, edizione, variant, stato, volumi)


# ── Helper: esegui ricerca con la modalità giusta ─────────────────────────────

def _search_by_mode(tracker, mode: str, titolo: str = "", autore: str = "",
                    silent: bool = False) -> list:
    """
    Esegue la ricerca su AnimeClick in base alla modalità scelta.

    mode:
      "titolo"   -> fetch_animeclick_manga_search(titolo)
      "autore"   -> fetch_animeclick_manga_search_staff(autore)   [fallback: titolo=autore]
      "combined" -> fetch_animeclick_manga_search_combined(titolo, autore)
                    [fallback: titolo+" "+autore]
    """
    if MangaPageSession is None:
        if not silent:
            show_error("MangaPageSession non disponibile.")
        return []

    try:
        with MangaPageSession() as sess:
            if mode == "autore":
                if hasattr(sess, "fetch_animeclick_manga_search_staff"):
                    return sess.fetch_animeclick_manga_search_staff(autore)
                else:
                    # fallback: cerca autore nel campo titolo
                    return sess.fetch_animeclick_manga_search(autore)

            elif mode == "combined":
                if hasattr(sess, "fetch_animeclick_manga_search_combined"):
                    return sess.fetch_animeclick_manga_search_combined(titolo, autore)
                else:
                    # fallback: concatena titolo + autore
                    query = f"{titolo} {autore}".strip()
                    return sess.fetch_animeclick_manga_search(query)

            else:  # "titolo" (default)
                return sess.fetch_animeclick_manga_search(titolo)

    except Exception as e:
        if not silent:
            show_error(f"Errore ricerca: {e}")
        return []


# ── Ricerca manga (menu principale modalità) ───────────────────────────────────

def _handle_ricerca_manga(tracker) -> None:
    """Menu principale ricerca manga. v2.4: 3 modalità di ricerca."""
    while True:
        clear_screen()
        print("  " + _EQ)
        print("  LA MIA COLLEZIONE  —  Ricerca manga")
        print("  " + _EQ); print()
        print("  1. Solo titolo")
        print("  2. Solo autore / staff")
        print("  3. Titolo + Autore")
        print("  0. Torna"); print()
        sc = input("  Scelta (0-3): ").strip()

        if sc == "0":
            return
        elif sc == "1":
            _handle_ricerca_per_modalita(tracker, mode="titolo")
        elif sc == "2":
            _handle_ricerca_per_modalita(tracker, mode="autore")
        elif sc == "3":
            _handle_ricerca_per_modalita(tracker, mode="combined")
        else:
            show_error("Opzione non valida.")
            input("  Premi INVIO...")


def _handle_ricerca_per_modalita(tracker, mode: str) -> None:
    """Sotto-menu: singola o multipla, per la modalità indicata."""
    labels = {
        "titolo":   "SOLO TITOLO",
        "autore":   "SOLO AUTORE / STAFF",
        "combined": "TITOLO + AUTORE",
    }
    label = labels.get(mode, mode.upper())

    while True:
        clear_screen()
        print("  " + _EQ)
        print(f"  RICERCA MANGA  —  {label}")
        print("  " + _EQ); print()
        print("  1. Ricerca singola")
        print("  2. Ricerca multipla")
        print("  0. Torna"); print()
        sc = input("  Scelta (0-2): ").strip()

        if sc == "0":
            return
        elif sc == "1":
            _handle_singola(tracker, mode=mode)
        elif sc == "2":
            _handle_multipla(tracker, mode=mode)
        else:
            show_error("Opzione non valida.")
            input("  Premi INVIO...")


def _ask_search_params(mode: str) -> tuple | None:
    """
    Chiede i parametri di ricerca in base alla modalità.
    Ritorna (titolo, autore) oppure None se l'utente vuole tornare.
    """
    titolo = ""
    autore = ""

    if mode == "titolo":
        titolo = input("  Titolo da cercare (0 = torna): ").strip()
        if not titolo or titolo == "0":
            return None

    elif mode == "autore":
        autore = input("  Autore / staff da cercare (0 = torna): ").strip()
        if not autore or autore == "0":
            return None

    elif mode == "combined":
        titolo = input("  Titolo (0 = torna): ").strip()
        if not titolo or titolo == "0":
            return None
        autore = input("  Autore / staff (invio = salta): ").strip()

    return titolo, autore


def _label_query(mode: str, titolo: str, autore: str) -> str:
    """Stringa descrittiva per la query, da mostrare nei risultati."""
    if mode == "titolo":
        return titolo
    elif mode == "autore":
        return autore
    else:
        parts = [p for p in [titolo, autore] if p]
        return " + ".join(parts)


# ── Ricerca singola ────────────────────────────────────────────────────────────

def _handle_singola(tracker, mode: str = "titolo") -> None:
    """Ricerca singola con la modalità indicata."""
    while True:
        clear_screen()
        print("  " + _EQ)
        print("  RICERCA SINGOLA  (Manga)")
        print("  " + _EQ); print()

        params = _ask_search_params(mode)
        if params is None:
            return
        titolo, autore = params
        query_label = _label_query(mode, titolo, autore)

        print(f"\n  Ricerca '{query_label}' in corso...")
        results = _search_by_mode(tracker, mode=mode, titolo=titolo,
                                  autore=autore, silent=True)

        if not results:
            print(f"\n  Nessun risultato trovato per '{query_label}'.")
            input("  Premi INVIO per riprovare..."); continue

        while True:
            clear_screen()
            print("  " + _EQ)
            print(f"  RISULTATI [Manga]: '{query_label}'  ({len(results)} trovati)")
            print("  " + _EQ); print()
            for i, r in enumerate(results, 1):
                print(f"    {i:>3}.  {r.get('title', r.get('titolo', ''))}")
            print(); print("  " + _SEP)
            print(f"  Numero (1-{len(results)}) per dettagli  |  0 torna")
            print("  " + _SEP)
            sc = input("  Scelta: ").strip()
            if sc == "0":
                break
            if not sc.isdigit() or not (1 <= int(sc) <= len(results)):
                show_error("Selezione non valida."); input("  Premi INVIO..."); continue
            entry = results[int(sc)-1]
            print(f"\n  Caricamento dettagli: {entry.get('title', entry.get('titolo', ''))}...")
            details = tracker.get_anime_details(entry["link"])
            if details:
                _prompt_save(details)
            else:
                show_info("Impossibile recuperare i dettagli.")
            input("\n  Premi INVIO per continuare...")


# ── Ricerca multipla ───────────────────────────────────────────────────────────

def _handle_multipla(tracker, mode: str = "titolo") -> None:
    """Ricerca multipla con la modalità indicata."""
    while True:
        clear_screen()
        print("  " + _EQ)
        print("  RICERCA MULTIPLA  (Manga)")
        print("  " + _EQ); print()

        if mode == "titolo":
            print("  Inserisci i titoli separati da virgola:")
            raw = input("  Titoli (0 = torna): ").strip()
            if not raw or raw == "0":
                return
            queries_t = [q.strip() for q in raw.split(",") if q.strip()]
            queries_a = [""] * len(queries_t)

        elif mode == "autore":
            print("  Inserisci gli autori/staff separati da virgola:")
            raw = input("  Autori (0 = torna): ").strip()
            if not raw or raw == "0":
                return
            queries_a = [q.strip() for q in raw.split(",") if q.strip()]
            queries_t = [""] * len(queries_a)

        else:  # combined
            print("  Inserisci i titoli separati da virgola:")
            raw_t = input("  Titoli (0 = torna): ").strip()
            if not raw_t or raw_t == "0":
                return
            queries_t = [q.strip() for q in raw_t.split(",") if q.strip()]
            print("  Inserisci gli autori corrispondenti (virgola, stesso ordine):")
            print("  (invio = lascia vuoti)")
            raw_a = input("  Autori: ").strip()
            queries_a_raw = [q.strip() for q in raw_a.split(",") if raw_a]
            queries_a = []
            for i in range(len(queries_t)):
                queries_a.append(queries_a_raw[i] if i < len(queries_a_raw) else "")

        if not queries_t and not queries_a:
            continue

        n = max(len(queries_t), len(queries_a))
        query_labels = [
            _label_query(mode,
                         queries_t[i] if i < len(queries_t) else "",
                         queries_a[i] if i < len(queries_a) else "")
            for i in range(n)
        ]

        clear_screen()
        print("  " + _EQ)
        print("  ANALISI IN CORSO..."); print("  " + _EQ); print()

        multi_results: dict = {}
        total_q = n

        for i in range(n):
            t = queries_t[i] if i < len(queries_t) else ""
            a = queries_a[i] if i < len(queries_a) else ""
            label = query_labels[i]
            pct   = max(0, int(i / total_q * 28))
            bar   = "[" + "#"*pct + "-"*(28-pct) + "]"
            disp  = (label[:22]+"...") if len(label) > 22 else label
            print(f"\r  {bar}  {i+1:>2}/{total_q}  {disp:<25}", end="", flush=True)
            multi_results[label] = _search_by_mode(
                tracker, mode=mode, titolo=t, autore=a, silent=True)

        print(f"\r  [OK]  {total_q}/{total_q} ricerche completate.                          ")
        print()

        while True:
            clear_screen()
            print("  " + _EQ)
            print("  RISULTATI MULTIPLA  [Manga]"); print("  " + _EQ); print()

            if _build_groups_fn and _print_groups_fn and _parse_multi_sel_fn:
                groups = _build_groups_fn(query_labels, multi_results)
                _print_groups_fn(groups)
                print("  " + _SEP)
                print("  1. Visualizza dettagli  |  2. Nuova ricerca  |  0. Torna")
                print("  " + _SEP)
                azione = input("  Scelta (0-2): ").strip()
                if azione == "0":
                    return
                elif azione == "2":
                    break
                elif azione == "1":
                    cod = input("  Codice scheda (es. A1, B3): ").strip()
                    if not cod:
                        continue
                    sel = _parse_multi_sel_fn(cod, groups)
                    if not sel:
                        show_info("Nessuna selezione valida.")
                        input("  Premi INVIO..."); continue
                    done = False
                    for _letter, items in sel.items():
                        if done: break
                        for entry in items:
                            print(f"\n  Caricamento: {entry.get('title', entry.get('titolo', ''))}...")
                            details = tracker.get_anime_details(entry["link"])
                            if details:
                                _prompt_save(details)
                            else:
                                show_info("Nessun dato estratto.")
                            if input("\n  Premi INVIO (0=ferma): ").strip() == "0":
                                done = True; break
                else:
                    show_error("Opzione non valida."); input("  Premi INVIO...")
            else:
                flat: list = []
                for label in query_labels:
                    res = multi_results.get(label, [])
                    if res:
                        print(f"  [{label}]  ({len(res)} risultati)")
                        for r in res:
                            flat.append(r)
                            print(f"    {len(flat):>3}.  {r.get('title', r.get('titolo', ''))}")
                    else:
                        print(f"  [{label}]  nessun risultato")
                if not flat:
                    print("  Nessun risultato trovato.")
                    input("  Premi INVIO..."); return
                print(); print("  " + _SEP)
                print(f"  Numero (1-{len(flat)}) per dettagli  |  0 torna")
                print("  " + _SEP)
                sc = input("  Scelta: ").strip()
                if sc == "0":
                    return
                if sc.isdigit() and 1 <= int(sc) <= len(flat):
                    entry = flat[int(sc)-1]
                    print(f"\n  Caricamento: {entry.get('title', entry.get('titolo', ''))}...")
                    details = tracker.get_anime_details(entry["link"])
                    if details:
                        _prompt_save(details)
                    else:
                        show_info("Nessun dato estratto.")
                    input("\n  Premi INVIO per continuare...")
                break


# ── Ricerca per URL ────────────────────────────────────────────────────────────

def _handle_url_diretto(tracker) -> None:
    while True:
        clear_screen(); print("  " + _EQ)
        print('  LA MIA COLLEZIONE  —  Ricerca per URL diretto')
        print("  " + _EQ); print()
        print("  Incolla URL scheda manga AnimeClick, es.:")
        print("  https://www.animeclick.it/manga/12345-titolo"); print()
        url = input("  URL (0 = torna): ").strip()
        if not url or url == "0": return
        if not url.startswith("http"): url = _BASE_URL + "/" + url.lstrip("/")
        print("\n  Caricamento scheda...")
        details = tracker.get_anime_details(url)
        if not details: show_info("Nessun dato estratto."); input("\n  Premi INVIO per riprovare..."); continue
        _prompt_save(details)
        print(); print("  " + _SEP)
        print("  1. Inserisci un altro URL  |  0. Torna"); print("  " + _SEP)
        if input("  Scelta: ").strip() != "1": return


# ── Aggiorna titolo ────────────────────────────────────────────────────────────

def _handle_aggiorna_volumi() -> None:
    while True:
        rows = load_collection()
        if not rows:
            clear_screen(); print("  " + _EQ)
            print('  LA MIA COLLEZIONE  —  Aggiorna titolo'); print('  ' + _EQ); print()
            print("  La collezione è vuota."); input("\n  Premi INVIO per tornare..."); return
        sorted_rows = sorted(rows, key=lambda r: r.get("titolo","").lower())
        clear_screen(); print("  " + _EQ)
        print(f'  LA MIA COLLEZIONE  —  Aggiorna titolo  ({len(rows)} titoli)')
        print("  " + _EQ); print()
        for line in _build_table_lines(sorted_rows): print(line)
        print(); print("  " + _SEP)
        print(f"  Numero da aggiornare (1-{len(sorted_rows)})  |  0 torna al menu")
        print("  " + _SEP)
        sc = input("  Scelta: ").strip()
        if sc == "0": return
        if not sc.isdigit() or not (1 <= int(sc) <= len(sorted_rows)):
            show_error("Selezione non valida."); input("  Premi INVIO..."); continue
        row = sorted_rows[int(sc)-1]
        titolo_cur  = row.get("titolo",""); edizione_cur = row.get("edizione","")
        variant_cur = row.get("variant",""); stato_cur = row.get("stato_italia","")
        volumi_cur  = row.get("volumi","")
        clear_screen(); print("  " + _EQ)
        print(f"  Aggiornamento: {titolo_cur}"); print("  " + _EQ); print()
        print(f"  {'Titolo corrente':<28} : {titolo_cur or '(non impostato)'}")
        print(f"  {'Edizione corrente':<28} : {edizione_cur or '(non impostato)'}")
        print(f"  {'Presenza variant corrente':<28} : {variant_cur or '(non impostato)'}")
        print(f"  {'Stato in Italia corrente':<28} : {stato_cur or '(non impostato)'}")
        print(f"  {'Volumi correnti':<28} : {volumi_cur or '(non impostato)'}")
        print("\n  INVIO = mantieni valore  |  0 = annulla\n")
        nuovo_titolo   = _ask_field("Titolo",           titolo_cur)
        if nuovo_titolo   is None: print("  Annullato."); input("  Premi INVIO..."); continue
        nuova_edizione = _ask_field("Edizione",         edizione_cur)
        if nuova_edizione is None: print("  Annullato."); input("  Premi INVIO..."); continue
        nuovo_variant  = _ask_field("Presenza variant", variant_cur)
        if nuovo_variant  is None: print("  Annullato."); input("  Premi INVIO..."); continue
        nuovo_stato    = _ask_field("Stato in Italia",  stato_cur)
        if nuovo_stato    is None: print("  Annullato."); input("  Premi INVIO..."); continue
        nuovi_volumi   = _ask_field("Volumi",           volumi_cur)
        if nuovi_volumi   is None: print("  Annullato."); input("  Premi INVIO..."); continue
        if (nuovo_titolo == titolo_cur and nuova_edizione == edizione_cur
                and nuovo_variant == variant_cur and nuovo_stato == stato_cur
                and nuovi_volumi == volumi_cur):
            print("\n  Nessuna modifica."); input("  Premi INVIO..."); continue
        orig_idx = next(
            (i for i, r in enumerate(rows) if r.get("titolo","").lower() == titolo_cur.lower()), -1)
        if orig_idx < 0: show_error("Voce non trovata."); input("  Premi INVIO..."); continue
        rows[orig_idx] = _make_entry(nuovo_titolo, nuova_edizione, nuovo_variant,
                                     nuovo_stato, nuovi_volumi)
        if save_collection(rows):
            show_success(f"Aggiornato: {get_collection_path()}")
        input("  Premi INVIO per continuare...")


# ── Visualizza / Esporta ───────────────────────────────────────────────────────

def _build_display_lines(sorted_rows: list, separate: bool) -> list:
    lines = []; total = len(sorted_rows)
    header_date = f"  La mia collezione manga al {_date_str()}"
    if not separate:
        lines += [_EQ, header_date, f"  Totale: {total} titoli", _EQ, ""]
        lines.extend(_build_table_lines(sorted_rows))
        lines += ["", _EQ]
    else:
        in_corso   = [r for r in sorted_rows if not _is_completato(r.get("stato_italia",""))]
        completati = [r for r in sorted_rows if     _is_completato(r.get("stato_italia",""))]
        lines += [_EQ, header_date,
                  f"  Totale: {total}  (In corso: {len(in_corso)}  |  Completati: {len(completati)})", _EQ]
        lines += ['', '  ' + '─'*(WIDTH-2),
                  f'  ▶  IN CORSO  ({len(in_corso)} titoli)', '  ' + '─'*(WIDTH-2), '']
        lines.extend(_build_table_lines(in_corso) if in_corso else ["  (nessun manga in corso)"])
        lines += ['', '  ' + '─'*(WIDTH-2),
                  f'  ✓  COMPLETATI  ({len(completati)} titoli)', '  ' + '─'*(WIDTH-2), '']
        lines.extend(_build_table_lines(completati) if completati else ["  (nessun manga completato)"])
        lines += ["", _EQ]
    return lines

def _print_paged(lines: list, page_size: int = 24) -> None:
    for i, line in enumerate(lines):
        print(line)
        if (i+1) % page_size == 0 and i+1 < len(lines):
            if input("\n  [ INVIO continua  |  0 ferma ]: ").strip() == "0": break
            print()

def _export_to_txt_local(lines: list, separate: bool) -> None:
    folder = _get_export_folder()
    if not folder: return
    suffix = " (separato)" if separate else ""
    fname  = sanitize_filename(f"La mia collezione manga al {_date_str()}{suffix}.txt")
    fpath  = str(Path(folder) / fname)
    if Path(fpath).exists():
        base, ext = fpath.rsplit(".", 1); c = 1
        while Path(f"{base}_{c}.{ext}").exists(): c += 1
        fpath = f"{base}_{c}.{ext}"
    try:
        with open(fpath, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
        show_success(f"Esportato: {fpath}")
    except OSError as exc: show_error(f"Errore esportazione: {exc}")

def _export_to_csv_local(rows: list) -> None:
    folder = _get_export_folder()
    if not folder: return
    fname = sanitize_filename(f"La mia collezione manga al {_date_str()}.csv")
    fpath = str(Path(folder) / fname)
    export_collection_csv(rows, fpath)

def _handle_visualizza_collezione() -> None:
    rows = load_collection()
    if not rows:
        clear_screen(); print("  " + _EQ)
        print('  LA MIA COLLEZIONE  —  Visualizza'); print('  ' + _EQ); print()
        print("  La collezione è vuota."); input("\n  Premi INVIO per tornare..."); return
    while True:
        rows        = load_collection()
        sorted_rows = sorted(rows, key=lambda r: r.get("titolo","").lower())
        n_incorso   = sum(1 for r in sorted_rows if not _is_completato(r.get("stato_italia","")))
        n_comp      = len(sorted_rows) - n_incorso
        clear_screen(); print("  " + _EQ)
        print(f'  LA MIA COLLEZIONE MANGA  —  {len(rows)} titoli'); print('  ' + _EQ); print()
        print(f'  ▶  In corso    : {n_incorso}')
        print(f'  ✓  Completati  : {n_comp}'); print()
        print("  " + _SEP)
        print("  1.  Visualizza a video   (lista unificata)")
        print("  2.  Visualizza a video   (In corso / Completati separati)")
        print("  3.  Esporta .txt         (lista unificata)")
        print("  4.  Esporta .txt         (In corso / Completati separati)")
        print("  5.  Esporta .csv         (compatibile Excel)")
        print("  0.  Torna al menu")
        print("  " + _SEP)
        sc = input("  Scelta (0-5): ").strip()
        if sc == "0": return
        elif sc in ("1","2"):
            sep = (sc == "2"); lns = _build_display_lines(sorted_rows, separate=sep)
            clear_screen(); _print_paged(lns); input("\n  Premi INVIO per tornare...")
        elif sc in ("3","4"):
            sep = (sc == "4"); lns = _build_display_lines(sorted_rows, separate=sep)
            _export_to_txt_local(lns, separate=sep); input("\n  Premi INVIO per continuare...")
        elif sc == "5":
            _export_to_csv_local(sorted_rows); input("\n  Premi INVIO per continuare...")
        else: show_error("Opzione non valida."); input("  Premi INVIO...")


# ── Entry point ────────────────────────────────────────────────────────────────

def handle_collezione() -> None:
    """Entry point chiamato da handlers.py."""
    if not _IMPORT_OK or _AnimeTracker is None:
        clear_screen(); print("  " + _EQ)
        print("  LA MIA COLLEZIONE MANGA"); print("  " + _EQ); print()
        show_error("Impossibile importare 'ricerca_scheda_anime.py'.")
        show_info("Verifica che il file esista in: scripts/anime/")
        input("\n  Premi INVIO per tornare..."); return

    tracker = _AnimeTracker()
    while True:
        clear_screen(); print("  " + _EQ)
        print("  LA MIA COLLEZIONE MANGA"); print("  " + _EQ); print()
        print("  1. Ricerca manga (titolo / autore / titolo+autore)")
        print("  2. Ricerca per URL diretto")
        print("  3. Aggiorna titolo con nuovi volumi")
        print("  4. Visualizza collezione")
        print("  0. Torna al menu precedente"); print()
        sc = input("  Scelta (0-4): ").strip()
        if sc == "0": return
        elif sc == "1": _handle_ricerca_manga(tracker)
        elif sc == "2": _handle_url_diretto(tracker)
        elif sc == "3": _handle_aggiorna_volumi()
        elif sc == "4": _handle_visualizza_collezione()
        else: show_error("Opzione non valida."); input("  Premi INVIO...")


if __name__ == "__main__":
    handle_collezione()
