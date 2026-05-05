"""
settings_handler.py — Menu Impostazioni (Layer 0)
Data-driven: legge struttura da core.json → settings_menu
"""
from .core import Core


def run():
    _menu_impostazioni()


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
        {"key": s["key"], "icon": s.get("icon",""), "label": s["label"], "desc": s.get("description","")}
        for s in subsections
    ]

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()
        choice = ui.show_menu(title="⚙️  Impostazioni", items=items,
                              subtitle="Modifica le preferenze del progetto", show_version=False)
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


def _generali():
    core   = Core.get()
    ui     = core.ui
    config = core.config

    _FIELDS = [
        ("core",      "clear_screen",      "Pulisci schermo tra i menu",  "bool",   None),
        ("core",      "show_descriptions", "Mostra descrizioni nel menu", "bool",   None),
        ("core",      "theme",             "Tema colori",                 "choice", ["default"]),
        ("main_menu", "show_version",      "Mostra versione nel menu",    "bool",   None),
    ]

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()
        items = [
            {"key": str(i+1), "icon":"🔧", "label": label, "desc": f"Attuale: {config.get(sec,key)}"}
            for i,(sec,key,label,_,__) in enumerate(_FIELDS)
        ]
        choice = ui.show_menu(title="🔧  Impostazioni Generali", items=items,
                              subtitle="Impostazioni globali", show_version=False)
        if choice == "0":
            return
        idx = int(choice) - 1
        if not (0 <= idx < len(_FIELDS)):
            continue
        sec, key, label, tipo, opzioni = _FIELDS[idx]
        val = config.get(sec, key)
        if tipo == "bool":
            nuovo = not val
            config.set(sec, key, nuovo)
            ui.success(f"{label}: {val} → {nuovo}")
            core.logger.info(f"Settings.Generali: {sec}.{key} = {nuovo}")
        elif tipo == "choice" and opzioni:
            ui.info(f"Opzioni: {', '.join(opzioni)}")
            nuovo = ui.ask_input(f"Nuovo valore per '{label}'", default=str(val))
            if nuovo in opzioni:
                config.set(sec, key, nuovo)
                ui.success(f"{label}: {val} → {nuovo}")
            else:
                ui.error(f"Valore non valido. Opzioni: {', '.join(opzioni)}")
        else:
            nuovo = ui.ask_input(f"Nuovo valore per '{label}'", default=str(val))
            config.set(sec, key, nuovo)
            ui.success(f"{label}: {val} → {nuovo}")
        ui.pause()


def _moduli():
    core   = Core.get()
    ui     = core.ui
    config = core.config

    sections = config.get_enabled_sections()
    items = [{"key":s["key"],"icon":s.get("icon",""),"label":s["label"],"desc":s.get("description","")} for s in sections]

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()
        choice = ui.show_menu(title="🧩  Impostazioni Moduli", items=items,
                              subtitle="Seleziona sezione da configurare", show_version=False)
        if choice == "0":
            return
        selected = next((s for s in sections if s["key"] == choice), None)
        if not selected:
            ui.error("Sezione non trovata.")
            continue
        _modulo_section(selected["id"], selected["label"], selected.get("icon",""))


def _modulo_section(section_id: str, section_label: str, icon: str):
    core   = Core.get()
    ui     = core.ui
    config = core.config

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()
        prefs = config.get_section_prefs(section_id)
        if not prefs:
            ui.warning(f"Nessuna impostazione per '{section_label}'.")
            ui.pause()
            return
        keys  = list(prefs.keys())
        items = [{"key":str(i+1),"icon":"🔩","label":k,"desc":f"Attuale: {prefs[k]}"} for i,k in enumerate(keys)]
        choice = ui.show_menu(title=f"{icon}  {section_label} — Impostazioni", items=items,
                              subtitle=f"Preferenze {section_label}", show_version=False)
        if choice == "0":
            return
        idx = int(choice) - 1
        if not (0 <= idx < len(keys)):
            continue
        key = keys[idx]
        val = prefs[key]
        if isinstance(val, bool):
            nuovo = not val
            config.set(section_id, key, nuovo)
            ui.success(f"{key}: {val} → {nuovo}")
            core.logger.info(f"Settings.Moduli.{section_id}: {key} = {nuovo}")
        elif val is None:
            s = ui.ask_input(f"Nuovo valore per '{key}' (invio=None)", default="")
            nuovo = s if s else None
            config.set(section_id, key, nuovo)
            ui.success(f"{key}: {val} → {nuovo}")
            core.logger.info(f"Settings.Moduli.{section_id}: {key} = {nuovo}")
        elif isinstance(val, int):
            s = ui.ask_input(f"Nuovo valore per '{key}' (intero)", default=str(val))
            try:
                nuovo = int(s)
                config.set(section_id, key, nuovo)
                ui.success(f"{key}: {val} → {nuovo}")
                core.logger.info(f"Settings.Moduli.{section_id}: {key} = {nuovo}")
            except ValueError:
                ui.error("Inserire un numero intero.")
        else:
            nuovo = ui.ask_input(f"Nuovo valore per '{key}'", default=str(val))
            config.set(section_id, key, nuovo)
            ui.success(f"{key}: {val} → {nuovo}")
            core.logger.info(f"Settings.Moduli.{section_id}: {key} = {nuovo}")
        ui.pause()
