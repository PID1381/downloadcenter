import importlib

from scripts.core.logger import get_logger, log_debug

logger = get_logger(__name__)


def run_configured_handler(core, item):
    log_debug("[core/dispatcher] → run_configured_handler()")
    handler_path = item.get('handler', '')
    entry_fn = item.get('entry_fn', 'run')
    label = item.get('label', handler_path or 'Modulo')

    try:
        mod = importlib.import_module(handler_path)
    except ImportError:
        core.ui.error(label + ' non ancora implementato.')
        core.ui.pause()
        return

    fn = getattr(mod, entry_fn, None)
    if not callable(fn):
        core.ui.warning(
            f'{label}: codice avviabile mancante ({handler_path}.{entry_fn}). '
            'Provvediamo a implementare.'
        )
        core.ui.pause()
        return

    fn()
