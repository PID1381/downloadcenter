"""
scripts/core/logger.py  —  PATCHED (upgrade-3)
Livello di logging condizionato a cfg.is_debug().
"""
import logging


def _get_cfg():
    """Import lazy per evitare import circolari."""
    from scripts.core.config import cfg  # noqa: PLC0415
    return cfg


def setup_logger(name: str = "app") -> logging.Logger:
    """
    Restituisce un logger configurato.
    Il livello è DEBUG solo se cfg.is_debug() == True,
    altrimenti INFO.
    """
    cfg = _get_cfg()

    # ── PATCH: livello dipendente da is_debug() ──────────────────
    level = logging.DEBUG if cfg.is_debug() else logging.INFO
    # ─────────────────────────────────────────────────────────────

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger


# Logger di default del modulo
log = setup_logger("app")
