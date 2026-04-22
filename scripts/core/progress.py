"""
Core Progress Module v2.1
Animazioni di avanzamento centralizzate e thread-safe.

Changelog v2.1:
- animate() stile standard Download Center: |█░░| 4.8% ◑  (spinner ◐◓◑◒)
- Indentazione 6 spazi (allineata a download_diretto_anime.py)
- show_final() stampa barra 100% e va a capo
- Retrocompatibile con v2.0
"""
import threading
import time
from typing import Optional


class ProgressAnimator:
    _CHARS = ["◐", "◓", "◑", "◒"]

    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._prefix = "Progresso"
        self._step   = 0

    @staticmethod
    def animate(
        current: int,
        total: int,
        prefix: str = "Download",
        length: int = 40,
    ) -> None:
        """
        Barra progresso stile standard Download Center.
        Output: \r      Download: |█░░░░░░░░░░░░░░░| 4.8% ◑
        """
        if total <= 0:
            return
        percent = 100 * (current / float(total))
        filled  = int(length * current // total)
        anim    = ProgressAnimator._CHARS[int(time.time() * 4) % 4]
        bar     = "█" * filled + "░" * (length - filled)
        print(f"\r      {prefix}: |{bar}| {percent:.1f}% {anim}", end="", flush=True)

    @staticmethod
    def show_final(prefix: str = "Completato") -> None:
        """Stampa barra al 100% e va a capo."""
        bar = "█" * 40
        print(f"\r      {prefix}: |{bar}| 100.0% ✓", flush=True)

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
