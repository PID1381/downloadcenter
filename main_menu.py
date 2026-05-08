import sys, importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.core import Core, run_startup_checks

def main():
    core = Core.get()
    core.logger.section('AVVIO DOWNLOAD CENTER 3.0')
    run_startup_checks()
    while True:
        sections = core.config.get_enabled_sections()
        sm = core.config.get_settings_menu()
        items = [{'key':s['key'],'icon':s.get('icon',''),'label':s['label'],
                  'desc':s.get('description','')} for s in sections]
        if sm:
            items.append({'key':sm['key'],'icon':sm.get('icon',''),
                          'label':sm['label'],'desc':'Configura il progetto'})
        choice = core.ui.show_menu('DOWNLOAD CENTER 3.0', items)
        if choice == '0':
            core.ui.show_exit(); core.logger.info('USCITA'); break
        if sm and choice == sm.get('key','S'):
            try: importlib.import_module(sm['handler']).run()
            except Exception as e: core.ui.error(str(e)); core.ui.pause()
            continue
        sec = next((s for s in sections if s['key']==choice), None)
        if not sec: core.ui.error('Voce non valida.'); continue
        try: importlib.import_module(sec['handler']).run()
        except ImportError:
            core.ui.error(sec['label']+' non ancora implementato.')
            core.ui.pause()
        except Exception as e:
            core.logger.error(str(e)); core.ui.error(str(e)); core.ui.pause()

if __name__ == '__main__': main()
