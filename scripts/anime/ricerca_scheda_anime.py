#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ricerca_scheda_anime.py — PATCH: Fix metodo search_anime
========================================================
PROBLEMA RISOLTO:
  Il vecchio codice usava `page.expect_response(lambda r: ...)` per intercettare
  la POST AJAX di AnimeClick. Il listener veniva aperto DOPO che `page.type()`
  aveva già digitato la query, quindi la POST partiva PRIMA che il listener fosse
  attivo. Il risultato era una risposta vuota da 472 chars invece dei risultati reali.

FIX APPLICATO:
  Sostituito `expect_response` con `page.on("response", callback)` che registra
  il listener PRIMA di digitare. Tutte le POST su /ricerca/anime vengono catturate
  in tempo reale. Viene scelta la risposta più lunga che contiene la query.

COME USARE QUESTO FILE:
  Sostituisci il metodo `search_anime` nel file originale con quello qui sotto.
  Il resto della classe rimane invariato.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  METODO SOSTITUTIVO — incolla questo dentro la tua classe AnimeClickScraper
#  (o come si chiama nel tuo progetto), sostituendo il vecchio search_anime.
# ══════════════════════════════════════════════════════════════════════════════

PATCHED_METHOD = """
    def search_anime(self, query: str, silent: bool = False) -> list[dict]:
        \'\'\'Cerca anime su AnimeClick e restituisce una lista di risultati.\'\'\'
        risultati: list[dict] = []
        search_url = f"{BASE_URL}/ricerca/anime"

        if not query or not query.strip():
            return []

        query = query.strip()

        try:
            with sync_playwright() as pw:
                browser, page = self._new_page(pw)
                try:
                    # ── 1. Naviga ─────────────────────────────────────────────
                    if not silent:
                        print(f"  [->] Navigazione {search_url}...")
                    try:
                        page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                    except Exception:
                        page.goto(search_url, wait_until="load", timeout=PAGE_TIMEOUT)

                    self._dismiss_cookies(page)
                    page.wait_for_timeout(1000)

                    # ── 2. Trova il campo di ricerca ──────────────────────────
                    INPUT_SELECTORS = [
                        "input[name=\'search_manga[title]\']",
                        f"#{SEARCH_INPUT_ID}",
                        "input.form-control.input-sm[type=\'text\']",
                        "input[name*=\'title\']",
                    ]
                    input_sel = None
                    for sel in INPUT_SELECTORS:
                        try:
                            page.wait_for_selector(sel, timeout=5_000)
                            input_sel = sel
                            break
                        except Exception:
                            continue

                    if not input_sel:
                        if not silent:
                            show_warning("Campo di ricerca non trovato.")
                        return []

                    if not silent:
                        val_before = page.input_value(input_sel)
                        print(f"  [dbg] Campo trovato: \'{input_sel}\' | valore: \'{val_before}\'")

                    # ── 3. Registra le POST AJAX *prima* di digitare ──────────
                    # FIX: page.on("response") intercetta TUTTE le risposte in
                    # tempo reale. Evita il bug del vecchio expect_response che
                    # catturava la POST vuota iniziale (472 chars) invece dei
                    # risultati reali.
                    received_responses: list[str] = []

                    def on_response(response):
                        if "/ricerca/anime" in response.url and response.request.method == "POST":
                            try:
                                body = response.text()
                                received_responses.append(body)
                                if not silent:
                                    print(
                                        f"  [dbg] POST intercettata: {len(body)} chars | "
                                        f"URL: {response.url}"
                                    )
                            except Exception as e:
                                if not silent:
                                    print(f"  [dbg] POST intercettata ma body non leggibile: {e}")

                    page.on("response", on_response)

                    # ── 4. Svuota, clicca e digita ────────────────────────────
                    page.click(input_sel)
                    page.fill(input_sel, "")
                    page.wait_for_timeout(200)

                    if not silent:
                        print(f"  [dbg] Digito \'{query}\' nel campo...")

                    page.type(input_sel, query, delay=150)

                    if not silent:
                        val_after = page.input_value(input_sel)
                        print(f"  [dbg] Valore campo dopo type(): \'{val_after}\'")

                    # Attendi che AnimeClick invii la POST AJAX (~500ms dalla digitazione)
                    page.wait_for_timeout(3000)

                    # ── 5. Prova il submit per sicurezza ──────────────────────
                    for s_sel in [
                        f"#{SEARCH_FORM_ID} button[type=\'submit\']",
                        f"#{SEARCH_FORM_ID} button",
                        "button[type=\'submit\']",
                    ]:
                        try:
                            page.click(s_sel, timeout=2_000)
                            if not silent:
                                print(f"  [ok] Submit cliccato: {s_sel}")
                            break
                        except Exception:
                            continue

                    # Aspetta ulteriori POST dopo il submit
                    page.wait_for_timeout(2000)

                    if not silent:
                        print(f"  [dbg] POST totali intercettate: {len(received_responses)}")
                        for idx, r in enumerate(received_responses):
                            has_q = query.lower() in r.lower()
                            print(f"  [dbg] POST #{idx+1}: {len(r)} chars | query presente: {has_q}")
                            print(f"  [dbg] Anteprima: {r[:200]}")

                    # ── 6. Scegli la risposta migliore ────────────────────────
                    json_html = ""

                    # Priorità 1: POST più lunga che contiene la query
                    best = max(
                        (r for r in received_responses if query.lower() in r.lower()),
                        key=len,
                        default=None,
                    )
                    if best:
                        json_html = _unwrap_json(best)
                        if not silent:
                            print(f"  [ok] Risposta scelta: {len(json_html)} chars (contiene query)")
                    elif received_responses:
                        # Priorità 2: POST più lunga in assoluto
                        best = max(received_responses, key=len)
                        json_html = _unwrap_json(best)
                        if not silent:
                            print(
                                f"  [!] Nessuna POST contiene la query. "
                                f"Uso la più lunga: {len(json_html)} chars"
                            )
                    else:
                        # Fallback: leggi il DOM aggiornato
                        if not silent:
                            print("  [!] Nessuna POST intercettata. Leggo il DOM...")
                        page.wait_for_timeout(2000)
                        json_html = _unwrap_json(page.content())
                        if not silent:
                            print(f"  [dbg] page.content(): {len(json_html)} chars")

                    # ── 7. Parse + filtro rilevanza ───────────────────────────
                    if json_html:
                        parsed = self._parse_search(BeautifulSoup(json_html, "html.parser"))
                        if parsed:
                            risultati = self._filter_by_relevance(parsed, query)
                            if not silent:
                                print(f"  [ok] Risultati finali: {len(risultati)}")

                finally:
                    browser.close()

        except Exception as exc:
            if not silent:
                show_error(f"Errore Playwright ({exc}). Provo HTTP puro...")
            fallback = self._http_search(query, silent=silent)
            if fallback:
                risultati = self._filter_by_relevance(fallback, query)

        return risultati
"""


# ══════════════════════════════════════════════════════════════════════════════
#  SCRIPT DI PATCH AUTOMATICO
#  Esegui questo script nella stessa cartella del file originale per
#  applicare il fix automaticamente.
# ══════════════════════════════════════════════════════════════════════════════

import re
import os
import shutil
from pathlib import Path


def apply_patch(target_path: str = "ricerca_scheda_anime_original.py") -> None:
    """Applica il fix al file originale."""
    src = Path(target_path)
    if not src.exists():
        print(f"[!] File non trovato: {target_path}")
        return

    # Backup
    backup = src.with_suffix(".py.bak")
    shutil.copy2(src, backup)
    print(f"[ok] Backup creato: {backup}")

    original = src.read_text(encoding="utf-8")
    original_lines = original.splitlines()

    # Trova inizio e fine del metodo search_anime
    start_idx = None
    end_idx = None
    for i, line in enumerate(original_lines):
        if re.match(r\'^\ {4}def search_anime\ *\(\', line):
            start_idx = i
        elif start_idx is not None and end_idx is None:
            if re.match(r\'^\ {4}def \', line):
                end_idx = i
                break

    if start_idx is None:
        print("[!] Metodo search_anime non trovato nel file.")
        return

    if end_idx is None:
        end_idx = len(original_lines)

    print(f"[ok] search_anime trovato: righe {start_idx+1}–{end_idx}")

    # Sostituisci
    new_lines = (
        original_lines[:start_idx]
        + PATCHED_METHOD.splitlines()
        + original_lines[end_idx:]
    )
    new_content = "\n".join(new_lines)
    src.write_text(new_content, encoding="utf-8")
    print(f"[ok] Patch applicata a: {target_path}")
    print(f"[ok] Righe prima: {len(original_lines)} | dopo: {len(new_lines)}")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "ricerca_scheda_anime.py"
    apply_patch(target)
