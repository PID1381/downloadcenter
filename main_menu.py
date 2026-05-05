"""
main_menu.py — Entry point Download Center 3.0
SECTION REGISTRY: scripts/core/core.json → sections[]
SETTINGS MENU:    scripts/core/core.json → settings_menu
"""
import sys, os, importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.core import Core


def main():
    core   = Core.get()
    logger = core.logger
    config = core.config
    ui     = core.ui

    logger.info("=" * 60)
    logger.info("  DOWNLOAD CENTER 3.0 — AVVIO")
    logger.info("=" * 60)

    while True:
        if config.get("core", "clear_screen", True):
            ui.clear_screen()

        sections  = config.get_enabled_sections()
        show_desc = config.get("core", "show_descriptions", True)
        sm        = config.get_settings_menu()

        items = [
            {"key":s["key"],"icon":s["icon"],"label":s["label"],
             "desc":s["description"] if show_desc else ""}
            for s in sections
        ]
        if sm:
            items.append({
                "key":  sm["key"],
                "icon": sm.get("icon","⚙️"),
                "label":sm["label"],
                "desc": "Configura il progetto" if show_desc else ""
            })

        choice = ui.show_menu(
            title        = "DOWNLOAD CENTER 3.0",
            items        = items,
            show_version = config.get("main_menu", "show_version", True)
        )

        if choice == "0":
            logger.info("DOWNLOAD CENTER 3.0 — CHIUSURA")
            ui.show_exit()
            break

        if sm and choice == sm["key"]:
            logger.info("→ Impostazioni")
            try:
                mod = importlib.import_module(sm["handler"])
                getattr(mod, sm["entry_fn"])()
            except Exception as e:
                ui.error(f"Errore Impostazioni: {e}")
                logger.error(f"Impostazioni error: {e}")
                ui.pause()
            continue

        selected = next((s for s in sections if s["key"] == choice), None)
        if not selected:
            ui.error("Sezione non trovata.")
            continue

        config.set("core", "last_section", selected["id"])
        logger.section(selected["label"])

        try:
            mod = importlib.import_module(selected["handler"])
            getattr(mod, selected["entry_fn"])()
        except ImportError as e:
            ui.error(f"Sezione '{selected['label']}' non ancora implementata.")
            logger.error(f"ImportError {selected['handler']}: {e}")
            ui.pause()
        except Exception as e:
            ui.error(f"Errore in '{selected['label']}': {e}")
            logger.error(f"Errore {selected['id']}: {e}")
            ui.pause()


if __name__ == "__main__":
    main()
