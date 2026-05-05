"""
settings_handler.py — Menu Impostazioni (Layer 0)

Struttura:
  run()
    └─ _menu_impostazioni()
         ├─ 1. Generali   → _generali()
         │       ├─ tabella (versione, download_dir, link_dir, export_dir)
         │       ├─ 1. Cambia percorsi DIR     → _cambia_dir()
         │       ├─ 2. Avvia DEBUG mode        → toggle
         │       ├─ 3. On/Off Headless browser → toggle
         │       └─ 4. Reset impostazioni      → _reset_defaults()
         └─ 2. Moduli     → _moduli()
                 ├─ 1. Cambio URL moduli       → _cambio_url_moduli()
                 └─ 2. Impostazioni YT-DLP     → _ytdlp_settings()
"""
from .core import Core


def run():
    _menu_impostazioni()


# ── MENU PRINCIPALE IMPOSTAZIONI ─────────────────────────────────────────────
def _menu_impostazioni():
    core   = Core.get()
    ui     = core.ui
    config = core.config
    logger = core.logger

    sm = config.get_settings_menu()
    if not sm:
        ui.error("settings_menu non trovato in core.json")
        return

    subsections = sm.get("subsections", [])
    items = [
        {"key": s["key"], "icon": s.get("icon", ""), "label": s["label"],
         "desc": s.get("description", "")}
        for s in subsections
    ]

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()
        choice = ui.show_menu(title="⚙️  Impostazioni", items=items,
                              subtitle="Modifica le preferenze del progetto",
                              show_version=False)
        if choice == "0":
            logger.info("Impostazioni — uscita")
            return
        sub = next((s for s in subsections if s["key"] == choice), None)
        if not sub:
            ui.error("Voce non trovata.")
            continue
        logger.info(f"Impostazioni → {sub['label']}")
        if sub["key"] == "1":
            _generali()
        elif sub["key"] == "2":
            _moduli()
        else:
            ui.warning(f"Sotto-sezione '{sub['label']}' non ancora implementata.")
            ui.pause()


# ══════════════════════════════════════════════════════════════════════════════
# 1. GENERALI
# ══════════════════════════════════════════════════════════════════════════════
def _generali():
    core   = Core.get()
    ui     = core.ui
    config = core.config

    _ITEMS = [
        {"key": "1", "icon": "📁", "label": "Cambia percorsi DIR",
         "desc": "Modifica Download / Link / Export DIR"},
        {"key": "2", "icon": "🐛", "label": "Avvia DEBUG mode",
         "desc": "Abilita/disabilita log debug e dump HTML"},
        {"key": "3", "icon": "🌐", "label": "On/Off Headless browser",
         "desc": "Mostra/nasconde la finestra Playwright"},
        {"key": "4", "icon": "🔄", "label": "Reset impostazioni default",
         "desc": "Ripristina percorsi, headless=ON, debug=OFF"},
    ]

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()

        # Tabella info in cima
        ui.show_info_table("🔧 Impostazioni Generali", [
            ("Versione progetto",  config.get_version()),
            ("Download DIR",       config.get_download_dir()),
            ("Link DIR",           config.get_link_dir()),
            ("Export DIR",         config.get_export_dir()),
            ("Debug mode",         "ON" if config.is_debug() else "OFF"),
            ("Headless browser",   "ON" if config.is_headless() else "OFF"),
        ])

        choice = ui.show_menu(title="🔧 Generali — Azioni",
                              items=_ITEMS, show_version=False,
                              subtitle="Seleziona un'azione")
        if choice == "0":
            return
        if choice == "1":
            _cambia_dir()
        elif choice == "2":
            _toggle_debug()
        elif choice == "3":
            _toggle_headless()
        elif choice == "4":
            _reset_defaults()
        else:
            ui.error("Voce non valida.")


def _cambia_dir():
    core   = Core.get()
    ui     = core.ui
    config = core.config

    _DIR_ITEMS = [
        {"key": "1", "icon": "⬇️",  "label": "Download DIR",
         "desc": config.get_download_dir()},
        {"key": "2", "icon": "🔗", "label": "Link DIR",
         "desc": config.get_link_dir()},
        {"key": "3", "icon": "📤", "label": "Export DIR",
         "desc": config.get_export_dir()},
    ]
    _DIR_KEYS = {
        "1": ("download_dir", config.get_download_dir),
        "2": ("link_dir",     config.get_link_dir),
        "3": ("export_dir",   config.get_export_dir),
    }

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()

        # Aggiorna desc con valore corrente
        for item in _DIR_ITEMS:
            k, getter = _DIR_KEYS[item["key"]]
            item["desc"] = getter()

        choice = ui.show_menu(title="📁 Cambia percorsi DIR",
                              items=_DIR_ITEMS, show_version=False,
                              subtitle="Seleziona la DIR da modificare")
        if choice == "0":
            return
        if choice not in _DIR_KEYS:
            ui.error("Voce non valida.")
            continue

        cfg_key, getter = _DIR_KEYS[choice]
        attuale         = getter()
        nuovo           = ui.ask_input(f"Nuovo percorso (attuale: {attuale})",
                                       default=attuale)
        if nuovo and nuovo != attuale:
            import os
            os.makedirs(nuovo, exist_ok=True)
            config.set_dir(cfg_key, nuovo)
            core.logger.info(f"DIR aggiornata: {cfg_key} = {nuovo}")
            ui.success(f"Percorso aggiornato: {nuovo}")
        else:
            ui.info("Nessuna modifica.")
        ui.pause()


def _toggle_debug():
    core   = Core.get()
    config = core.config
    ui     = core.ui
    nuovo  = not config.is_debug()
    config.set("core", "debug_mode", nuovo)
    core.logger.info(f"DEBUG mode: {nuovo}")
    ui.success(f"DEBUG mode: {'ON' if nuovo else 'OFF'}")
    ui.pause()


def _toggle_headless():
    core   = Core.get()
    config = core.config
    ui     = core.ui
    nuovo  = not config.is_headless()
    config.set("core", "headless_browser", nuovo)
    core.logger.info(f"Headless browser: {nuovo}")
    ui.success(f"Headless browser: {'ON' if nuovo else 'OFF'}")
    ui.pause()


def _reset_defaults():
    core   = Core.get()
    config = core.config
    ui     = core.ui
    from .settings_core import DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT
    import os

    confirm = ui.ask_input(
        "Reset a valori default? Digita SI per confermare", default="NO"
    )
    if confirm.upper() != "SI":
        ui.info("Reset annullato.")
        ui.pause()
        return

    config.set("core", "download_dir",     DOWNLOAD_DIR_DEFAULT)
    config.set("core", "link_dir",         LINK_DIR_DEFAULT)
    config.set("core", "export_dir",       EXPORT_DIR_DEFAULT)
    config.set("core", "headless_browser", True)
    config.set("core", "debug_mode",       False)

    for d in (DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT):
        os.makedirs(d, exist_ok=True)

    core.logger.info("Reset impostazioni default eseguito.")
    ui.success("Impostazioni ripristinate ai valori default.")
    ui.pause()


# ══════════════════════════════════════════════════════════════════════════════
# 2. MODULI
# ══════════════════════════════════════════════════════════════════════════════
def _moduli():
    core   = Core.get()
    ui     = core.ui
    config = core.config

    _ITEMS = [
        {"key": "1", "icon": "🔗", "label": "Cambio URL moduli",
         "desc": "Modifica l'URL base di ogni modulo"},
        {"key": "2", "icon": "🎬", "label": "Impostazioni YT-DLP",
         "desc": "Preferenze per il modulo YT-DLP"},
    ]

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()
        choice = ui.show_menu(title="🧩 Impostazioni Moduli",
                              items=_ITEMS, show_version=False,
                              subtitle="Seleziona configurazione")
        if choice == "0":
            return
        if choice == "1":
            _cambio_url_moduli()
        elif choice == "2":
            _ytdlp_settings()
        else:
            ui.error("Voce non valida.")


def _cambio_url_moduli():
    core   = Core.get()
    ui     = core.ui
    config = core.config
    um     = core.url_manager

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()

        modules = um.get_all_modules()
        if not modules:
            ui.warning("Nessun modulo configurato in urls_config.json.")
            ui.pause()
            return

        items = [
            {"key": str(i + 1), "icon": "🔗",
             "label": name,
             "desc": data.get("base_url", "(non impostato)")}
            for i, (name, data) in enumerate(modules.items())
        ]
        module_names = list(modules.keys())

        choice = ui.show_menu(title="🔗 Cambio URL moduli",
                              items=items, show_version=False,
                              subtitle="Seleziona modulo da modificare")
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(module_names)):
                raise ValueError
        except ValueError:
            ui.error("Voce non valida.")
            continue

        mod_name  = module_names[idx]
        mod_data  = modules[mod_name]
        url_keys  = [k for k in mod_data.keys() if "url" in k.lower()]
        if not url_keys:
            url_keys = ["base_url"]

        for ukey in url_keys:
            attuale = mod_data.get(ukey, "")
            nuovo   = ui.ask_input(f"{mod_name} → {ukey}", default=attuale)
            if nuovo and nuovo != attuale:
                um.set_url(mod_name, ukey, nuovo)
                core.logger.info(f"URL aggiornato: {mod_name}.{ukey} = {nuovo}")
                ui.success(f"{mod_name}.{ukey} aggiornato.")
            else:
                ui.info("Nessuna modifica.")
        ui.pause()


def _ytdlp_settings():
    core   = Core.get()
    ui     = core.ui
    config = core.config

    # Prefs YT-DLP nel prefs.json (sezione "ytdlp")
    _DEFAULTS = {
        "format":          "bestvideo+bestaudio/best",
        "merge_output":    "mp4",
        "write_subs":      False,
        "sub_lang":        "it",
        "embed_subs":      False,
        "embed_thumbnail": False,
        "rate_limit":      "",
        "proxy":           "",
        "extra_args":      "",
    }

    # Assicura sezione ytdlp in prefs
    for k, v in _DEFAULTS.items():
        if config.get("ytdlp", k) is None:
            config.set("ytdlp", k, v)

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()

        prefs = {k: config.get("ytdlp", k, v) for k, v in _DEFAULTS.items()}
        items = [
            {"key": str(i + 1), "icon": "🔩",
             "label": k, "desc": f"Attuale: {prefs[k]}"}
            for i, k in enumerate(prefs.keys())
        ]
        choice = ui.show_menu(title="🎬 Impostazioni YT-DLP",
                              items=items, show_version=False,
                              subtitle="Modifica preferenze YT-DLP")
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            keys = list(prefs.keys())
            if not (0 <= idx < len(keys)):
                raise ValueError
        except ValueError:
            ui.error("Voce non valida.")
            continue

        key = keys[idx]
        val = prefs[key]

        if isinstance(val, bool):
            nuovo = not val
            config.set("ytdlp", key, nuovo)
            ui.success(f"{key}: {val} → {nuovo}")
            core.logger.info(f"YT-DLP: {key} = {nuovo}")
        else:
            nuovo = ui.ask_input(f"Nuovo valore per '{key}'", default=str(val))
            config.set("ytdlp", key, nuovo)
            ui.success(f"{key}: {val} → {nuovo}")
            core.logger.info(f"YT-DLP: {key} = {nuovo}")
        ui.pause()
