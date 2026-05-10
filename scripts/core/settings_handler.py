"""
DC3 — scripts/core/settings_handler.py
════════════════════════════════════════════════════════════════════════
Gestione menu Impostazioni.

Sezioni:
  1. Generali  → percorsi DIR, debug, headless, reset default
  2. Moduli    → cambio URL moduli (con test connessione), YT-DLP

Dipendenze interne:
  core.config       → get/set preferenze
  core.url_manager  → get/set URL moduli
  core.ui           → output + input
  core.logger       → log eventi
  settings_core     → costanti DIR default
  file_manager      → FileManager.ensure_folder
════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import requests as _rq

# ─────────────────────────────────────────────────────────────────────
# COSTANTI TEST CONNESSIONE
# ─────────────────────────────────────────────────────────────────────
_CONN_TIMEOUT = 10          # secondi
_CONN_UA      = "DC3-URL-checker/1.0"


# ═════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

def run() -> None:
    """Entry point chiamato dal dispatcher principale."""
    from .core import Core
    _menu(Core.get())


# ═════════════════════════════════════════════════════════════════════
# MENU PRINCIPALE IMPOSTAZIONI
# ═════════════════════════════════════════════════════════════════════

def _menu(core) -> None:
    sm   = core.config.get_settings_menu()
    subs = sm.get("subsections", [
        {"key": "1", "label": "Generali", "icon": "", "desc": "Impostazioni globali"},
        {"key": "2", "label": "Moduli",   "icon": "", "desc": "URL moduli e YT-DLP"},
    ])
    items = [
        {
            "key":  s["key"],
            "icon": s.get("icon", ""),
            "label": s["label"],
            "desc":  s.get("description", s.get("desc", "")),
        }
        for s in subs
    ]
    while True:
        c = core.ui.show_menu("Impostazioni", items, "Modifica le preferenze del progetto")
        if   c == "0": return
        elif c == "1": _generali(core)
        elif c == "2": _moduli(core)
        else:          core.ui.error("Voce non valida")


# ═════════════════════════════════════════════════════════════════════
# SEZIONE 1 — GENERALI
# ═════════════════════════════════════════════════════════════════════

def _generali(core) -> None:
    while True:
        cfg  = core.config
        info_rows = [
            ("Versione progetto",  cfg.get_version()),
            ("Download DIR",       cfg.get_download_dir()),
            ("Link DIR",           cfg.get_link_dir()),
            ("Export DIR",         cfg.get_export_dir()),
            ("Debug mode",         "ON" if cfg.is_debug()    else "OFF"),
            ("Headless browser",   "ON" if cfg.is_headless() else "OFF"),
        ]

        items = [
            {"key": "1", "icon": "", "label": "Cambia percorsi DIR",    "desc": ""},
            {"key": "2", "icon": "", "label": "Toggle DEBUG mode",       "desc": ""},
            {"key": "3", "icon": "", "label": "Toggle Headless browser", "desc": ""},
            {"key": "4", "icon": "", "label": "Reset default",           "desc": ""},
        ]
        c = core.ui.show_menu("Generali", items, show_version=False, info_rows=info_rows)

        if   c == "0": return
        elif c == "1": _cambia_dir(core)
        elif c == "2":
            v = not cfg.is_debug()
            cfg.set("core", "debug_mode", v)
            core.ui.success("Debug: " + ("ON" if v else "OFF"))
            core.logger.info("debug_mode -> " + str(v))
        elif c == "3":
            v = not cfg.is_headless()
            cfg.set("core", "headless_browser", v)
            core.ui.success("Headless: " + ("ON" if v else "OFF"))
            core.logger.info("headless_browser -> " + str(v))
        elif c == "4":
            _reset_defaults(core)


def _cambia_dir(core) -> None:
    items = [
        {"key": "1", "icon": "", "label": "Download DIR", "desc": ""},
        {"key": "2", "icon": "", "label": "Link DIR",     "desc": ""},
        {"key": "3", "icon": "", "label": "Export DIR",   "desc": ""},
    ]
    mapping = {"1": "download_dir", "2": "link_dir", "3": "export_dir"}
    labels  = {"1": "Download DIR", "2": "Link DIR",  "3": "Export DIR"}

    while True:
        c = core.ui.show_menu("Cambia percorsi", items, show_version=False)
        if c == "0":
            return
        if c in mapping:
            p = core.ui.ask_input(labels[c] + " [invio=annulla]")
            if p:
                core.config.set_dir(mapping[c], p)
                core.ui.success(labels[c] + " impostato: " + p)
                core.logger.info(mapping[c] + " -> " + p)


def _reset_defaults(core) -> None:
    c = core.ui.ask_input("Digita SI per confermare il reset")
    if c.upper() != "SI":
        core.ui.info("Annullato.")
        return

    from .settings_core import DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT
    from .file_manager  import FileManager

    core.config.set("core", "download_dir",      DOWNLOAD_DIR_DEFAULT)
    core.config.set("core", "link_dir",          LINK_DIR_DEFAULT)
    core.config.set("core", "export_dir",        EXPORT_DIR_DEFAULT)
    core.config.set("core", "headless_browser",  True)
    core.config.set("core", "debug_mode",        False)

    for d in [DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT]:
        FileManager.ensure_folder(d)

    core.ui.success("Impostazioni ripristinate ai default.")
    core.logger.info("Reset default impostazioni")


# ═════════════════════════════════════════════════════════════════════
# SEZIONE 2 — MODULI
# ═════════════════════════════════════════════════════════════════════

def _moduli(core) -> None:
    items = [
        {"key": "1", "icon": "", "label": "Cambio URL moduli",   "desc": ""},
        {"key": "2", "icon": "", "label": "Impostazioni YT-DLP", "desc": ""},
    ]
    while True:
        c = core.ui.show_menu("Moduli", items, show_version=False)
        if   c == "0": return
        elif c == "1": _cambio_url(core)
        elif c == "2": _ytdlp(core)


# ─────────────────────────────────────────────────────────────────────
# CAMBIO URL — con test connessione HTTP
# ─────────────────────────────────────────────────────────────────────

def _cambio_url(core) -> None:
    """
    Permette di modificare il base_url di ogni modulo registrato
    in url_manager.

    Dopo il salvataggio esegue un test di connessione HTTP e informa
    l'utente sull'esito. Il salvataggio avviene SEMPRE, indipendentemente
    dall'esito del test.

    Casi gestiti dal test:
      ✅  HTTP < 400          → raggiungibile
      ⚠️  HTTP ≥ 400          → raggiunto ma risponde con errore
      ⚠️  ConnectionError     → dominio non trovato / rifiutato
      ⚠️  Timeout             → nessuna risposta entro _CONN_TIMEOUT s
      ⚠️  SSLError            → certificato non valido
      ⚠️  Altro               → errore generico
    """
    modules = core.url_manager.get_all_modules()
    mlist   = list(modules.keys())

    # Costruisce items con label = nome modulo, desc = URL corrente
    items = [
        {
            "key":   str(i + 1),
            "icon":  "",
            "label": m,
            "desc":  (modules[m].get("base_url", "⚠  non configurato") if isinstance(modules[m], dict) else str(modules[m])),
        }
        for i, m in enumerate(mlist)
    ]

    while True:
        c = core.ui.show_menu("URL Moduli", items, show_version=False)
        if c == "0":
            return

        try:
            idx = int(c) - 1
        except ValueError:
            core.ui.error("Voce non valida")
            continue

        if not (0 <= idx < len(mlist)):
            core.ui.error("Voce non valida")
            continue

        modulo_key   = mlist[idx]
        url_corrente = core.url_manager.get_url(modulo_key, "base_url") or ""

        # ── Inserimento nuovo URL ────────────────────────────
        core.ui.show_info_table(
            f"URL — {modulo_key}",
            [("URL corrente", url_corrente or "(non impostato)")]
        )
        nuovo_url = core.ui.ask_input(
            "Nuovo URL (es: https://www.animeworld.so) — Invio per annullare",
            url_corrente,
        )

        if not nuovo_url or nuovo_url.strip() == url_corrente.strip():
            core.ui.info("Nessuna modifica.")
            continue

        # Normalizza: rimuovi slash finale, assicura schema https://
        nuovo_url = nuovo_url.strip().rstrip("/")
        if not nuovo_url.startswith(("http://", "https://")):
            nuovo_url = "https://" + nuovo_url

        # ── Salvataggio ──────────────────────────────────────
        core.url_manager.set_url(modulo_key, "base_url", nuovo_url)
        core.logger.info(f"url {modulo_key} -> {nuovo_url}")
        core.ui.success(f"URL salvato: {nuovo_url}")

        # Aggiorna la desc nel menu per la prossima iterazione
        items[idx]["desc"] = nuovo_url

        # ── Test connessione ─────────────────────────────────
        core.ui.info("Test connessione in corso...")
        _test_connessione(core, nuovo_url)


def _test_connessione(core, url: str) -> None:
    """
    Esegue una GET sull'URL e stampa l'esito tramite core.ui.
    Non solleva eccezioni — tutti i casi sono gestiti internamente.
    """
    try:
        resp = _rq.get(
            url,
            timeout=_CONN_TIMEOUT,
            headers={"User-Agent": _CONN_UA},
            allow_redirects=True,
        )
        if resp.status_code < 400:
            core.ui.success(f"Raggiungibile (HTTP {resp.status_code}).")
        else:
            core.ui.error(
                f"Raggiunto ma risponde con HTTP {resp.status_code}.\n"
                f"  Verifica che l'indirizzo sia corretto. (URL salvato comunque)"
            )

    except _rq.exceptions.SSLError:
        core.ui.error(
            "Errore certificato SSL.\n"
            "  Prova con http:// invece di https://. (URL salvato comunque)"
        )

    except _rq.exceptions.ConnectionError:
        core.ui.error(
            "Connessione rifiutata o dominio non trovato.\n"
            "  Verifica il dominio aggiornato del sito. (URL salvato comunque)"
        )

    except _rq.exceptions.Timeout:
        core.ui.error(
            f"Nessuna risposta entro {_CONN_TIMEOUT}s.\n"
            f"  Il sito potrebbe essere lento o irraggiungibile. (URL salvato comunque)"
        )

    except Exception as exc:
        core.ui.error(
            f"Test connessione fallito: {exc}\n"
            f"  (URL salvato comunque)"
        )


# ─────────────────────────────────────────────────────────────────────
# YT-DLP
# ─────────────────────────────────────────────────────────────────────

def _ytdlp(core) -> None:
    """
    Impostazioni YT-DLP.
    I valori bool vengono togglati; i valori stringa vengono modificati
    con ask_input. Tutto viene persistito in config come sezione 'ytdlp'.
    """
    cfg = core.config
    yd  = cfg.get_section_prefs("ytdlp") or {
        "format":           "bestvideo+bestaudio/best",
        "merge_output":     "mkv",
        "write_subs":       False,
        "sub_lang":         "it",
        "embed_subs":       True,
        "embed_thumbnail":  False,
        "rate_limit":       "",
        "proxy":            "",
        "extra_args":       "",
    }
    keys = list(yd.keys())

    while True:
        items = [
            {"key": str(i + 1), "icon": "", "label": k, "desc": str(yd[k])}
            for i, k in enumerate(keys)
        ]
        c = core.ui.show_menu("YT-DLP", items, show_version=False)

        if c == "0":
            return

        try:
            idx = int(c) - 1
        except ValueError:
            core.ui.error("Voce non valida")
            continue

        if not (0 <= idx < len(keys)):
            core.ui.error("Voce non valida")
            continue

        k = keys[idx]
        v = yd[k]

        if isinstance(v, bool):
            yd[k] = not v
            core.ui.success(f"{k}: {yd[k]}")
            core.logger.info(f"ytdlp.{k} -> {yd[k]}")
        else:
            nv = core.ui.ask_input(k, str(v))
            if nv is not None:
                yd[k] = nv
                core.logger.info(f"ytdlp.{k} -> {nv}")

        cfg.set_section("ytdlp", yd)
        # Aggiorna la desc nel menu
        items[idx]["desc"] = str(yd[k])
