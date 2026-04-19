#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_automatica_acquisti.py v5.3 — fix MCM ordine + filtro Amazon ISBN
=================================================================
Novita v5.2 (fix):
  F1 - Amazon: _is_italian_edition ora controlla ISBN-10 dall'URL /dp/
       ISBN inizia con '3'  -> editore germanico -> escluso
       ISBN inizia con '88' -> editore italiano  -> incluso
  F2 - Amazon: aggiunti 'taschenbuch' e 'auf deutsch' ai marcatori stranieri
  (Fix MCM ordine in ricerca_mcm.py v5.2 — file separato)

Evoluzione di v4.0: 
  - Report salvato in default_export_dir (non default_link_dir)
  - Possibilità di interrompere flusso in qualsiasi punto
  - Ctrl+C: interruzione graceful con report parziale
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

_THIS_DIR    = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent.resolve()
_ANIME_DIR   = _SCRIPTS_DIR / "anime"

for _p in [str(_ANIME_DIR), str(_THIS_DIR), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

_TEMP_DIR        = _SCRIPTS_DIR / "temp"
_PREFS_FILE      = _TEMP_DIR / "prefs.json"
_COLLECTION_JSON = _TEMP_DIR / "lamiacollezione.json"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

try:
    from manga_engine import (
        get_export_dir, clear_screen, WIDTH,
        setup_interrupt, teardown_interrupt, interrupted,
    )
except ImportError:
    def get_export_dir():
        try:
            with open(_PREFS_FILE, encoding="utf-8") as f:
                return json.load(f).get("default_export_dir", "")
        except Exception:
            return ""
    def clear_screen():
        os.system("cls" if os.name == "nt" else "clear")
    def setup_interrupt():
        pass
    def teardown_interrupt():
        pass
    class _Interrupted:
        def is_set(self):
            return False
    interrupted = _Interrupted()
    WIDTH = 70

REPORT_FOLDER = "Report acquisti manga"

_W    = 70
_EQ   = "=" * _W
_SEP  = "  " + "-" * (_W - 2)
_DEQS = "  " + "=" * (_W - 2)

_BACK = "__BACK__"
_EXIT = "__EXIT__"

_MESI_IT = [
    "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

_INCORSO_KW = [
    "in corso", "in uscita", "ongoing", "in produzione", "in pubblicazione",
    "in publicazione", "mensile", "settimanale", "in serializzazione",
    "in pubblicaz", "corso", "uscita", "corrente",
]

_IT_PUBLISHERS = {
    "star comics", "panini", "planet manga", "j-pop", "hikari",
    "dynit", "edizioni bd", "goen", "rw edizioni", "rw lion",
    "magic press", "flashbook", "coconino", "bao publishing",
    "manga senpai", "g.p. publishing", "jpop", "j pop",
    "bd edizioni", "shonen", "shojo", "shueisha italia",
}

_STATO_FIELDS = (
    "stato", "stato_italia", "stato_in_italia", "status",
    "stato_serie", "stato_pubblicazione",
)

_VOL_FORMATS = [
    "{title} {n}", "{title} vol.{n}", "{title} vol. {n}",
    "{title} v.{n}", "{title} volume {n}", "{title} (Vol. {n})",
    "{title} #{n}", "{title} n.{n}", "{title} n. {n}", "{title} tome {n}",
]
_MAX_TARGETED_SEARCHES = 5  # FIX-B: alzato da 3 a 5
_URL_MAX_LEN = 65


def _build_next_volume_queries(title: str, next_vol: int) -> list[str]:
    return [fmt.format(title=title, n=next_vol) for fmt in _VOL_FORMATS]


def _truncate_url(url: str, max_len: int = _URL_MAX_LEN) -> str:
    if not url:
        return url
    short = url.split("?")[0]
    if len(short) > max_len:
        short = short[: max_len - 1] + "…"
    return short


def _load_prefs() -> dict:
    try:
        with open(_PREFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _date_str() -> str:
    n = datetime.now()
    return f"{n.day:02d} {_MESI_IT[n.month]} {n.year}"


def _get_stato(manga: dict) -> str:
    for field in _STATO_FIELDS:
        val = manga.get(field)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _is_in_corso(manga: dict) -> bool:
    stato = _get_stato(manga).lower()
    if not stato:
        return False
    return any(kw in stato for kw in _INCORSO_KW)


def _read_collection() -> list[dict]:
    if not _COLLECTION_JSON.exists():
        return []
    try:
        with open(_COLLECTION_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _parse_volume_count(s: str) -> int | None:
    if not s:
        return None
    nums = [int(n) for n in re.findall(r'\d+', s)]
    return max(nums) if nums else None


def _extract_volume_from_title(title: str) -> int | None:
    patterns = [
        r'[Vv]ol(?:ume|\.)?\s*\.?\s*(\d+)',
        r'[Nn](?:\.\s?|\s)(\d+)\b',
        r'#\s*(\d+)',
        r'\bvol\.\s*(\d+)',
        r'\b(\d{1,3})\s*$',
        r'\b(\d{1,3})\b(?=\s*[-–(])',
    ]
    found: list[int] = []
    for pat in patterns:
        for m in re.finditer(pat, title):
            val = int(m.group(1))
            if 1 <= val <= 999:
                found.append(val)
    return max(found) if found else None


def _merge_items(base: list[dict], extra: list[dict], key: str) -> list[dict]:
    seen   = {it.get(key, "") for it in base if it.get(key)}
    merged = list(base)
    for it in extra:
        k = it.get(key, "")
        if k and k not in seen:
            seen.add(k)
            merged.append(it)
        elif not k:
            merged.append(it)
    return merged


def _is_italian_edition(item: dict) -> bool:
    """
    Determina se un item Amazon e un'edizione italiana.

    v5.2 — aggiunto controllo ISBN-10 dall'URL /dp/<codice>:
      - ISBN-10 che inizia con "3"  -> editore germanico  -> False
      - ISBN-10 che inizia con "88" -> editore italiano   -> True
    """
    text = " ".join([
        item.get("titolo", ""),
        item.get("autore", ""),
    ]).lower()

    # -- Controllo ISBN-10 dall'URL /dp/<codice> --------------------------
    url = item.get("url", "")
    _isbn_m = re.search(r'/dp/([0-9]{9}[0-9Xx])(?:[/?]|$)', url)
    if _isbn_m:
        isbn10 = _isbn_m.group(1).upper()
        if isbn10.startswith("88"):
            return True   # ISBN italiano confermato
        if isbn10.startswith("3"):
            return False  # ISBN germanico (DE/AT/CH) -> escludi

    # -- Editori italiani noti nel testo ----------------------------------
    if any(pub in text for pub in _IT_PUBLISHERS):
        return True
    if re.search(r'edizione\s+ital', text):
        return True
    if re.search(r'\bital(?:iana?|iano)\b', text):
        return True
    if re.search(r'\bitalia\b', text):
        return True

    # -- Indicatori di edizione straniera ---------------------------------
    _non_it = [
        "english edition", "english language", "edizione inglese",
        "edizione in inglese", "french edition", "edizione francese",
        "german edition", "edizione tedesca", "spanish edition",
        "edizione spagnola", "japanese edition", "edizione giapponese",
        "jp edition", "us edition", "american edition",
        "taschenbuch",
        "auf deutsch",
    ]
    if any(x in text for x in _non_it):
        return False

    return True
def _check_volume_novelty(
    col_max: int | None,
    results: list[dict],
) -> tuple[bool, str, list[dict]]:
    if not results:
        return False, "", []

    if col_max is None:
        return True, "Nessun dato volume in collezione — verifica manuale", results[:3]

    new_items: list[tuple[int, dict]] = []
    for it in results:
        v = _extract_volume_from_title(it.get("titolo", ""))
        if v is not None and v > col_max:
            new_items.append((v, it))

    if new_items:
        new_items.sort(key=lambda x: x[0])
        max_found = new_items[-1][0]
        delta     = max_found - col_max
        desc = (
            f"+{delta} vol. (trovato vol. {max_found} · collezione: vol. {col_max})"
        )
        return True, desc, [x[1] for x in new_items[:3]]

    return False, f"Aggiornato (nessun vol. > {col_max})", []


def _search_mcm(title: str, col_max: int | None) -> tuple[list[dict], bool, str]:
    try:
        import ricerca_mcm as _rcm

        pages = _rcm._fetch_search_pages(title, mode="auto")
        all_items: list[dict] = []
        if pages:
            all_items = _rcm._extract_all_pages(pages)

        if col_max is not None:
            is_nov_base, _, _ = _check_volume_novelty(col_max, all_items)
            if not is_nov_base:
                next_vol  = col_max + 1
                queries   = _build_next_volume_queries(title, next_vol)
                attempts  = 0
                for q in queries:
                    if attempts >= _MAX_TARGETED_SEARCHES:
                        break
                    if interrupted.is_set():
                        break
                    try:
                        extra_pages = _rcm._fetch_search_pages(q)
                        if extra_pages:
                            extra_items = _rcm._extract_all_pages(extra_pages)
                            all_items   = _merge_items(all_items, extra_items, "link")
                            is_nov, _, _ = _check_volume_novelty(col_max, all_items)
                            if is_nov:
                                break
                        attempts += 1
                    except Exception:
                        attempts += 1
                        continue

        if not all_items:
            return [], False, "Nessun risultato"

        keywords = [w for w in title.lower().split() if len(w) >= 3]

        def _is_relevant_mcm(it: dict) -> bool:
            t = it.get("titolo", "").lower()
            if not keywords:
                return True
            matches = sum(1 for kw in keywords if kw in t)
            threshold = max(1, round(len(keywords) * 0.7))  # FIX-2: soglia alzata a 70%
            return matches >= threshold

        relevant = [it for it in all_items if _is_relevant_mcm(it)]
        if not relevant:
            return [], False, "Nessun risultato"
        relevant = relevant[:96]

        is_novelty, delta, matched = _check_volume_novelty(col_max, relevant)
        return (matched if is_novelty else relevant[:3]), is_novelty, delta

    except Exception as exc:
        return [], False, f"Errore: {exc}"


def _search_amazon(title: str, col_max: int | None) -> tuple[list[dict], bool, str]:
    try:
        import acquisti_manga_amazon as _amz

        base_query = f"{title} manga"  # FIX: rimosso "edizione italiana" → query più ampia
        all_items  = _amz._fetch_amazon_search(base_query)
        italian    = [it for it in all_items if _is_italian_edition(it)]  # FIX: rimosso fallback "or all_items"

        if col_max is not None:
            is_nov_base, _, _ = _check_volume_novelty(col_max, italian)
            if not is_nov_base:
                next_vol = col_max + 1
                queries  = _build_next_volume_queries(title, next_vol)
                attempts = 0
                for q in queries:
                    if attempts >= _MAX_TARGETED_SEARCHES:
                        break
                    if interrupted.is_set():
                        break
                    try:
                        extra_raw    = _amz._fetch_amazon_search_sorted(q)  # FIX: query diretta senza suffissi


                        extra_it     = [it for it in extra_raw if _is_italian_edition(it)]  # FIX: rimosso fallback "or extra_raw"
                        italian      = _merge_items(italian, extra_it, "url")
                        is_nov, _, _ = _check_volume_novelty(col_max, italian)
                        if is_nov:
                            break
                        attempts += 1
                    except Exception:
                        attempts += 1
                        continue

        if not italian:
            return [], False, "Nessun risultato"

        keywords = [w for w in title.lower().split() if len(w) >= 3]

        def _is_relevant_amz(it: dict) -> bool:
            t = it.get("titolo", "").lower()
            # Esclusione esplicita edizioni non italiane
            if "edizione inglese" in t or "english edition" in t:
                return False
            if not keywords:
                return True
            matches = sum(1 for kw in keywords if kw in t)
            threshold = max(1, round(len(keywords) * 0.7))  # FIX-2: soglia alzata a 70%
            return matches >= threshold

        relevant = [it for it in italian if _is_relevant_amz(it)]
        if not relevant:
            return [], False, "Nessun risultato"
        relevant = relevant[:96]

        is_novelty, delta, matched = _check_volume_novelty(col_max, relevant)
        return (matched if is_novelty else relevant[:3]), is_novelty, delta

    except Exception as exc:
        return [], False, f"Errore: {exc}"


def _analyse_one(manga: dict, sources: set[str]) -> dict:
    titolo    = manga["titolo"]
    vol_col   = manga.get("volumi", "")
    stato_col = _get_stato(manga)
    col_max   = _parse_volume_count(vol_col)

    result: dict = {
        "titolo":    titolo,
        "vol_col":   vol_col or "—",
        "stato_col": stato_col or "—",
        "col_max":   col_max,
        "mcm":       [],
        "mcm_nov":   False,
        "mcm_delta": "",
        "amz":       [],
        "amz_nov":   False,
        "amz_delta": "",
        "novita":    False,
        "delta":     "",
    }

    if "mcm" in sources:
        if interrupted.is_set():
            return result
        mcm_items, mcm_nov, mcm_delta = _search_mcm(titolo, col_max)
        result["mcm"]       = mcm_items
        result["mcm_nov"]   = mcm_nov
        result["mcm_delta"] = mcm_delta
        if mcm_nov:
            result["novita"] = True
            result["delta"]  = mcm_delta

    if "amz" in sources:
        if interrupted.is_set():
            return result
        amz_items, amz_nov, amz_delta = _search_amazon(titolo, col_max)
        result["amz"]       = amz_items
        result["amz_nov"]   = amz_nov
        result["amz_delta"] = amz_delta
        if amz_nov and not result["novita"]:
            result["novita"] = True
            result["delta"]  = amz_delta

    return result


def _print_report(report: list[dict], sources: set[str], scope_label: str) -> None:
    novita    = [r for r in report if r.get("novita")]
    senza_nov = [r for r in report if not r.get("novita")]
    src_label = " + ".join([
        x for x in [
            "MCM"       if "mcm" in sources else "",
            "Amazon.it" if "amz" in sources else "",
        ] if x
    ])

    print()
    print(_EQ)
    print("  REPORT  RICERCA AUTOMATICA ACQUISTI MANGA")
    print(f"  Data   : {_date_str()}")
    print(f"  Fonti  : {src_label}")
    print(f"  Scope  : {scope_label}")
    print(_EQ)

    if novita:
        print()
        print(_DEQS)
        print(f"  NOVITA TROVATE  ({len(novita)} titoli)")
        print(_DEQS)

        for r in novita:
            col_info = f"vol. {r['vol_col']}"
            print()
            print(f"  NOVITA: {r['titolo']}")
            print(f"  Collezione  : {col_info:<18}  stato: {r['stato_col']}")

            if "mcm" in sources:
                mcm = r.get("mcm", [])
                if r.get("mcm_nov") and mcm:
                    print(f"  MCM  [{r['mcm_delta']}]")
                    for it in mcm[:2]:
                        t  = it.get("titolo", "")[:54]
                        p  = f"  {it.get('prezzo', '')}" if it.get("prezzo") else ""
                        pr = f"  [Preord.: {it['preordine']}]" if it.get("preordine") else ""
                        print(f"    * {t}{p}{pr}")
                        if it.get("link"):
                            print(f"      {_truncate_url(it['link'])}")
                elif mcm:
                    print(f"  MCM         : {len(mcm)} ris. trovati, nessun vol. successivo")
                else:
                    print(f"  MCM         : nessun risultato")

            if "amz" in sources:
                amz = r.get("amz", [])
                if r.get("amz_nov") and amz:
                    print(f"  Amazon  [{r['amz_delta']}]  (ed. italiana)")
                    for it in amz[:2]:
                        t = it.get("titolo", "")[:54]
                        p = f"  {it.get('prezzo', '')}" if it.get("prezzo") else ""
                        print(f"    * {t}{p}")
                        if it.get("url"):
                            print(f"      {_truncate_url(it['url'])}")
                elif amz:
                    print(f"  Amazon (it.): {len(amz)} ris. trovati, nessun vol. successivo")
                else:
                    print(f"  Amazon (it.): nessun risultato")

    if senza_nov:
        print()
        print(_SEP)
        print(f"  TITOLI AGGIORNATI / SENZA NOVITA  ({len(senza_nov)})")
        print(_SEP)
        for r in senza_nov:
            v = r["vol_col"]
            mcm_note = ""
            if "mcm" in sources and r.get("mcm_delta") and not r.get("mcm_nov"):
                mcm_note = f"  [MCM: {r['mcm_delta']}]"
            print(f"  {r['titolo']:<50}  vol. {v}{mcm_note}")

    print()
    print(_DEQS)
    print(f"  Totale analizzati   : {len(report)}")
    print(f"  Con novita          : {len(novita)}")
    print(f"  Aggiornati          : {len(senza_nov)}")
    print(_DEQS)
    print()


def _save_report(report: list[dict], sources: set[str], scope_label: str) -> None:
    base = get_export_dir()
    if not base:
        print("  Percorso 'default_export_dir' non configurato nelle Impostazioni.")
        print("  Report NON salvato.")
        return
    folder = os.path.join(base, REPORT_FOLDER)
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as exc:
        print(f"  Errore creazione cartella: {exc}")
        return

    fname = f"Report acquisti {_date_str()}.txt"
    fpath = os.path.join(folder, fname)

    novita    = [r for r in report if r.get("novita")]
    senza_nov = [r for r in report if not r.get("novita")]
    src_label = " + ".join([
        x for x in [
            "MCM"       if "mcm" in sources else "",
            "Amazon.it" if "amz" in sources else "",
        ] if x
    ])

    lines = [
        _EQ,
        "  REPORT  RICERCA AUTOMATICA ACQUISTI MANGA",
        f"  Data   : {_date_str()}",
        f"  Fonti  : {src_label}",
        f"  Scope  : {scope_label}",
        _EQ,
    ]

    if novita:
        lines += [
            "",
            "=" * (_W - 2),
            f"  NOVITA TROVATE  ({len(novita)} titoli)",
            "=" * (_W - 2),
        ]
        for r in novita:
            lines.append("")
            lines.append(f"  [NOVITA] {r['titolo']}")
            lines.append(f"      Collezione  : vol. {r['vol_col']}  |  stato: {r['stato_col']}")
            if "mcm" in sources:
                if r.get("mcm_nov") and r.get("mcm"):
                    lines.append(f"      MCM -> {r['mcm_delta']}")
                    for it in r.get("mcm", [])[:2]:
                        t  = it.get("titolo", "")
                        p  = f"  {it.get('prezzo', '')}" if it.get("prezzo") else ""
                        pr = f"  [Preord.: {it['preordine']}]" if it.get("preordine") else ""
                        lines.append(f"        * {t}{p}{pr}")
                        if it.get("link"):
                            lines.append(f"          {it['link']}")
                elif r.get("mcm"):
                    lines.append(f"      MCM : {len(r['mcm'])} ris., nessun vol. successivo")
                else:
                    lines.append("      MCM : nessun risultato")
            if "amz" in sources:
                if r.get("amz_nov") and r.get("amz"):
                    lines.append(f"      Amazon (ed. italiana) -> {r['amz_delta']}")
                    for it in r.get("amz", [])[:2]:
                        t = it.get("titolo", "")
                        p = f"  {it.get('prezzo', '')}" if it.get("prezzo") else ""
                        lines.append(f"        * {t}{p}")
                        if it.get("url"):
                            lines.append(f"          {it['url']}")
                elif r.get("amz"):
                    lines.append(f"      Amazon: {len(r['amz'])} ris., nessun vol. successivo")
                else:
                    lines.append("      Amazon: nessun risultato")

    if senza_nov:
        lines += [
            "",
            "-" * (_W - 2),
            f"  TITOLI SENZA NOVITA  ({len(senza_nov)})",
            "-" * (_W - 2),
        ]
        for r in senza_nov:
            lines.append(f"  {r['titolo']:<50}  vol. {r['vol_col']}")

    lines += [
        "",
        f"Totale: {len(report)}  |  Novita: {len(novita)}  |  Aggiornati: {len(senza_nov)}",
        _EQ,
    ]

    try:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  Report salvato: {fpath}")
    except OSError as exc:
        print(f"  Errore salvataggio: {exc}")


def _step_header(passo: int, titolo_passo: str, collection_len: int) -> None:
    _clear()
    print(_EQ)
    print("  RICERCA AUTOMATICA ACQUISTI MANGA")
    print(f"  Passo {passo} / 4  —  {titolo_passo}")
    print(_EQ)
    print(f"  Collezione: {collection_len} manga")
    print()


def _step_scope(collection: list[dict]):
    in_corso = [m for m in collection if _is_in_corso(m)]
    tutti    = collection

    while True:
        _step_header(1, "Ambito ricerca", len(collection))
        print(f"  A  Tutti i titoli della collezione       ({len(tutti)} manga)")
        print(f"  C  Solo titoli In corso                  ({len(in_corso)} manga)")

        if in_corso:
            preview = ", ".join(m["titolo"] for m in in_corso[:3])
            if len(in_corso) > 3:
                preview += f" ... +{len(in_corso) - 3} altri"
            print(f"       {preview}")

        print()
        print("  0  Torna al menu principale")
        sc = input("  Scelta (A / C / 0): ").strip().upper()

        if sc == "0":
            return _EXIT
        elif sc == "A":
            return tutti, "Tutti i titoli"
        elif sc == "C":
            if not in_corso:
                print()
                print("  Nessun titolo 'In corso' trovato.")
                input("  Premi INVIO...")
                continue
            return in_corso, f"Solo titoli In corso ({len(in_corso)} su {len(tutti)})"
        else:
            print("  Opzione non valida.")
            input("  Premi INVIO...")


def _step_fonti(collection_len: int):
    while True:
        _step_header(2, "Selezione fonti", collection_len)
        print("  M  MangaComicsMarket (MCM)")
        print("  Z  Amazon.it (ed. italiana)")
        print("  T  Entrambe le fonti")
        print()
        print("  0  Torna al passo precedente")
        print()
        raw = input("  Seleziona (es. M,Z oppure T): ").strip().upper()

        if raw == "0":
            return _BACK
        if not raw or raw == "T":
            return {"mcm", "amz"}

        sources: set[str] = set()
        if "M" in raw:
            sources.add("mcm")
        if "Z" in raw:
            sources.add("amz")

        if not sources:
            print("  Nessuna fonte valida.")
            input("  Premi INVIO...")
            continue

        return sources


def _step_filtro(scope_manga: list[dict], scope_label: str):
    while True:
        _step_header(3, "Filtro manga", len(scope_manga))
        print(f"  Scope attivo: {scope_label}")
        print()
        print("  T          Tutti (default)")
        print("  N          Solo manga senza dati sui volumi")
        print("  1,3,5-8    Numeri / intervalli separati da virgola")
        print()
        print("  0          Torna al passo precedente")
        print()
        print(f"  {'N':>3}   {'Titolo':<44}  {'Volumi':<14}")
        print(_SEP)
        for i, m in enumerate(scope_manga, 1):
            v     = m.get("volumi") or "—"
            print(f"  {i:>3}.  {m['titolo']:<44}  {v:<14}")
        print(_SEP)
        print()
        filtro = input("  Filtro (0 = indietro / Invio = tutti): ").strip().upper()

        if filtro == "0":
            return _BACK
        if not filtro or filtro == "T":
            return scope_manga
        if filtro == "N":
            sel = [m for m in scope_manga if not m.get("volumi")]
            if not sel:
                print()
                print("  Nessun manga senza dati volume trovato.")
                input("  Premi INVIO...")
                continue
            return sel

        sel_idx: list[int] = []
        for part in [p.strip() for p in filtro.split(",") if p.strip()]:
            if "-" in part:
                try:
                    a, b = [int(x) for x in part.split("-", 1)]
                    if a > b:
                        a, b = b, a
                    sel_idx.extend(range(a, b + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                sel_idx.append(int(part))

        selected = [
            scope_manga[i - 1] for i in sel_idx
            if 1 <= i <= len(scope_manga)
        ]

        if not selected:
            print()
            print("  Nessun manga selezionato.")
            input("  Premi INVIO...")
            continue

        return selected


def _step_confirm(
    selected_manga: list[dict],
    sources: set[str],
    scope_label: str,
):
    n_manga  = len(selected_manga)
    src_disp = " + ".join([
        x for x in [
            "MCM"       if "mcm" in sources else "",
            "Amazon.it" if "amz" in sources else "",
        ] if x
    ])

    while True:
        _clear()
        print(_EQ)
        print("  RICERCA AUTOMATICA ACQUISTI MANGA")
        print("  Passo 4 / 4  —  Riepilogo e conferma")
        print(_EQ)
        print()
        print(f"  Scope               : {scope_label}")
        print(f"  Manga da analizzare : {n_manga}")
        print(f"  Fonti attive        : {src_disp}")
        print(f"  Ricerca mirata      : SI  (+3 tentativi per fonte per manga)")
        print(f"  Amazon filtro       : Solo edizioni Italia")
        print(f"  Report salvato in   : default_export_dir/{REPORT_FOLDER}/")
        print(f"  Interruzione        : Ctrl+C per fermare (report parziale salvato)")
        print()
        print(_SEP)
        print(f"  {'N':>3}   {'Titolo':<44}  Volumi")
        print(_SEP)
        for i, m in enumerate(selected_manga, 1):
            v = m.get("volumi") or "—"
            print(f"  {i:>3}.  {m['titolo']:<44}  {v}")
        print(_SEP)
        print()
        print("  S  Avvia analisi")
        print("  0  Torna al passo precedente")
        print("  N  Annulla")
        print()

        sc = input("  Scelta (S / 0 / N): ").strip().upper()

        if sc == "0":
            return _BACK
        elif sc in ("S", "SI", "Y"):
            return True
        elif sc in ("N", "NO"):
            return False
        else:
            print("  Opzione non valida.")
            input("  Premi INVIO...")


def handle_ricerca_automatica() -> None:
    """Entry point chiamato da manga_handlers.py."""

    collection = _read_collection()

    if not collection:
        _clear()
        print(_EQ)
        print("  RICERCA AUTOMATICA ACQUISTI MANGA")
        print(_EQ)
        print()
        if not _COLLECTION_JSON.exists():
            print(f"  File collezione non trovato.")
            print(f"  {_COLLECTION_JSON}")
        else:
            print("  La collezione è vuota.")
        print("  Aggiungi manga tramite 'La mia collezione'.")
        input("\n  Premi INVIO per tornare...")
        return

    step: int = 1
    scope_manga:    list[dict] | None = None
    scope_label:    str        | None = None
    sources:        set[str]   | None = None
    selected_manga: list[dict] | None = None

    while True:

        if step == 1:
            result = _step_scope(collection)
            if result == _EXIT:
                return
            scope_manga, scope_label = result
            step = 2

        elif step == 2:
            result = _step_fonti(len(collection))
            if result == _BACK:
                step = 1
                continue
            sources = result
            step = 3

        elif step == 3:
            result = _step_filtro(scope_manga, scope_label)
            if result == _BACK:
                step = 2
                continue
            selected_manga = result
            step = 4

        elif step == 4:
            result = _step_confirm(selected_manga, sources, scope_label)
            if result == _BACK:
                step = 3
                continue
            if not result:
                return
            break

    setup_interrupt()
    
    report: list[dict] = []
    total  = len(selected_manga)

    print()
    try:
        for i, manga in enumerate(selected_manga, 1):
            if interrupted.is_set():
                print(f"\n\nInterruzione utente — report parziale.")
                break
            
            label = manga["titolo"][:34]
            pct   = int((i - 1) / total * 30)
            bar   = "[" + "#" * pct + "-" * (30 - pct) + "]"
            print(f"\r  {bar}  {i}/{total}  {label:<36}", end="", flush=True)
            result = _analyse_one(manga, sources)
            report.append(result)
    except KeyboardInterrupt:
        print(f"\n\n  [!] Interruzione da tastiera (Ctrl+C) — report parziale generato.\n")
    finally:
        teardown_interrupt()

    processed = len(report)
    print(f"\r  [COMPLETATO]  {processed}/{total} manga analizzati.                              ")
    print()

    _print_report(report, sources, scope_label)

    if report:
        ans = input("  Vuoi salvare il report? (s/n): ").strip().lower()
        if ans in ("s", "si", "y"):
            _save_report(report, sources, scope_label)

    input("\n  Premi INVIO per tornare al menu...")


if __name__ == "__main__":
    handle_ricerca_automatica()