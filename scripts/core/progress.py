import sys, time, threading

from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

_INTERRUPT_HINT = 'CTRL+C per interrompere'


class ProgressAnimator:
    def __init__(self):
        log_debug("[core/progress] → __init__()")
        self._spin_thr = None; self._spin_run = False; self._spin_clear = 40
    def bar(self, cur, tot, width=40, pre='', suf=''):
        log_debug("[core/progress] → bar()")
        pct = cur/tot if tot else 0
        filled = int(width*pct)
        b = chr(0x2588)*filled + chr(0x2591)*(width-filled)
        return pre+'['+b+'] '+str(int(pct*100)).rjust(3)+'% '+suf
    def print_bar(self, cur, tot, **kw):
        log_debug("[core/progress] → print_bar()")
        s = self.bar(cur, tot, **kw)
        end = chr(10) if cur >= tot else chr(13)
        print(s, end=end, flush=True)
    def spinner_start(self, msg=''):
        log_debug("[core/progress] → spinner_start()")
        msg = str(msg or '')
        if _INTERRUPT_HINT.lower() not in msg.lower():
            msg = (msg + ' ' if msg else '') + '(' + _INTERRUPT_HINT + ')'
        self._spin_clear = max(40, len(msg) + 8)
        self._spin_run = True
        frames = ['|','/','-','\\']
        def _run():
            log_debug("[core/progress] → _run()")
            i = 0
            while self._spin_run:
                print(chr(13)+'  '+frames[i%4]+' '+msg+'  ', end='', flush=True)
                i += 1; time.sleep(0.1)
            print(chr(13)+' '*self._spin_clear+chr(13), end='', flush=True)
        self._spin_thr = threading.Thread(target=_run, daemon=True)
        self._spin_thr.start()
    def spinner_stop(self):
        log_debug("[core/progress] → spinner_stop()")
        self._spin_run = False
        if self._spin_thr: self._spin_thr.join(timeout=1)
