"""
Core Progress Module v2.0
Animazioni di avanzamento centralizzate e thread-safe.
"""
import threading
import time
from typing import Optional


class ProgressAnimator:
    """Gestione animazioni progress bar."""
    _CHARS = ["◐", "◓", "◑", "◒"]

    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._prefix = "Progresso"
        self._step   = 0

    @staticmethod
    def animate(current: int, total: int, prefix: str = "Progresso",
                length: int = 40) -> None:
        if total <= 0: return
        percent = 100 * (current / float(total))
        filled  = int(length * current // total)
        anim    = ProgressAnimator._CHARS[int(time.time() * 4) % 4]
        bar     = "█" * filled + "░" * (length - filled)
        print(f"\r  {prefix}: |{bar}| {percent:.1f}% {anim}", end="", flush=True)

    @staticmethod
    def show_final(prefix: str = "Completato") -> None:
        ProgressAnimator.animate(100, 100, prefix)
        print()

    def start(self, prefix: str = "Lavoro in corso") -> None:
        self._active = True
        self._prefix = prefix
        self._step   = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._active = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def _loop(self) -> None:
        while self._active:
            val = min(self._step * 0.15, 95)
            ProgressAnimator.animate(int(val), 100, self._prefix)
            self._step += 1
            time.sleep(0.1)

    def update(self, current: int, total: int) -> None:
        ProgressAnimator.animate(current, total, self._prefix)


progress = ProgressAnimator()
