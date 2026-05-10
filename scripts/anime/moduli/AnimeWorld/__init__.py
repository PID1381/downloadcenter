import os as _os, sys as _sys
# ── PATH GUARD (BUG-006/007B) ─────────────────────────────────────────────
_BASE_DIR = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
if _BASE_DIR not in _sys.path:
    _sys.path.insert(0, _BASE_DIR)
# ──────────────────────────────────────────────────────────────────────────

# AnimeWorld
