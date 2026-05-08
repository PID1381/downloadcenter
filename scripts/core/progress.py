import sys, time, threading

class ProgressAnimator:
    def __init__(self):
        self._spin_thr = None; self._spin_run = False
    def bar(self, cur, tot, width=40, pre='', suf=''):
        pct = cur/tot if tot else 0
        filled = int(width*pct)
        b = chr(0x2588)*filled + chr(0x2591)*(width-filled)
        return pre+'['+b+'] '+str(int(pct*100)).rjust(3)+'% '+suf
    def print_bar(self, cur, tot, **kw):
        s = self.bar(cur, tot, **kw)
        end = chr(10) if cur >= tot else chr(13)
        print(s, end=end, flush=True)
    def spinner_start(self, msg=''):
        self._spin_run = True
        frames = ['|','/','-','\\']
        def _run():
            i = 0
            while self._spin_run:
                print(chr(13)+'  '+frames[i%4]+' '+msg+'  ', end='', flush=True)
                i += 1; time.sleep(0.1)
            print(chr(13)+' '*40+chr(13), end='', flush=True)
        self._spin_thr = threading.Thread(target=_run, daemon=True)
        self._spin_thr.start()
    def spinner_stop(self):
        self._spin_run = False
        if self._spin_thr: self._spin_thr.join(timeout=1)
