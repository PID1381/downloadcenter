import os
from typing import Dict, List, Optional
from .settings_core import Colors, Box, PROJECT_VERSION
from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)


def _vis(s):
    log_debug("[core/ui] → _vis()")
    r=0; i=0; n=len(s)
    while i < n:
        if ord(s[i])==27 and i+1<n and s[i+1]=='[':
            i+=2
            while i<n and s[i] not in 'mABCDEFGHJKST': i+=1
            i+=1
        else: r+=1; i+=1
    return r

def _pad(s, w):
    log_debug("[core/ui] → _pad()")
    return s + ' '*max(0, w-_vis(s))


def _trunc_plain(text: str, max_len: int) -> str:
    t = str(text or '')
    if max_len <= 0:
        return ''
    if len(t) <= max_len:
        return t
    if max_len == 1:
        return t[:1]
    return t[: max_len - 1] + '…'


def _terminal_cols(default: int = 80) -> int:
    try:
        return int(os.get_terminal_size().columns)
    except Exception:
        return default


def _calc_box_width(plain_lines: List[str], min_w: int = 52, max_w: Optional[int] = None) -> int:
    """Larghezza tabella in base al contenuto (con limiti min/max)."""
    if max_w is None:
        max_w = min(100, _terminal_cols() - 2)
    if not plain_lines:
        return min_w
    need = max(len(line) for line in plain_lines) + 2
    return max(min_w, min(max_w, need))


def _menu_item_row(key: str, label: str, desc: str, width: int, C) -> str:
    """Una riga menu troncata per stare nel box."""
    prefix = f"  {C.CYAN_BOLD}{key}{C.RESET}.  "
    prefix_vis = _vis(prefix)
    desc_plain = (desc or '').strip()
    if desc_plain:
        desc_vis_budget = min(28, max(12, width // 3))
        desc_txt = '  ' + C.GRAY + _trunc_plain(desc_plain, desc_vis_budget) + C.RESET
        desc_vis = _vis(desc_txt)
    else:
        desc_txt = ''
        desc_vis = 0
    label_max = max(8, width - prefix_vis - desc_vis)
    label_txt = C.WHITE + _trunc_plain(label, label_max) + C.RESET
    row = prefix + label_txt + desc_txt
    if _vis(row) > width:
        row = prefix + C.WHITE + _trunc_plain(label, max(6, width - prefix_vis)) + C.RESET
    return _pad(row, width)

class UIManager:
    WIDTH = 56
    @staticmethod
    def clear():
        log_debug("[core/ui] → clear()")
        try: os.system('cls' if os.name=='nt' else 'clear')
        except: pass
    @staticmethod
    def clear_screen():
        log_debug("[core/ui] → clear_screen()")
        UIManager.clear()
    @staticmethod
    def show_header(title, breadcrumb=''):
        log_debug("[core/ui] → show_header()")
        UIManager.clear()
        print('='*UIManager.WIDTH)
        print('  '+title)
        print('='*UIManager.WIDTH)
        if breadcrumb: print('  '+breadcrumb)
        print(); return title
    @staticmethod
    def show_menu(title, items, subtitle='', show_version=True, info_rows=None):
        log_debug("[core/ui] → show_menu()")
        UIManager.clear()
        C = Colors
        B = Box

        plain: List[str] = []
        vs_plain = (' v' + PROJECT_VERSION) if show_version else ''
        plain.append(' ' + str(title) + vs_plain + ' ')
        if subtitle:
            plain.append(' ' + str(subtitle) + ' ')
        if info_rows:
            for ir_lb, ir_val in info_rows:
                plain.append('  ' + str(ir_lb).ljust(24) + str(ir_val))
        for it in items:
            k = str(it.get('key', '?'))
            ic = str(it.get('icon', ' '))
            lb = str(it.get('label', ''))
            ds = str(it.get('desc', '') or '')
            line = f"  {k}.  {ic}  {lb}"
            if ds:
                line += f"  {ds}"
            plain.append(line)
        plain.append('  0.  ↩  Esci / Indietro')

        W = _calc_box_width(plain, min_w=52, max_w=min(100, _terminal_cols() - 2))

        def hl(l, r):
            return C.CYAN + l + B.H * W + r + C.RESET

        def vr(s):
            return C.CYAN + B.V + C.RESET + _pad(s, W) + C.CYAN + B.V + C.RESET

        print()
        print(hl(B.TL, B.TR))
        vs = (C.DIM + C.CYAN + ' v' + PROJECT_VERSION + C.RESET) if show_version else ''
        ti = ' ' + C.BOLD + C.WHITE + _trunc_plain(title, W - len(vs_plain) - 4) + C.RESET + vs + ' '
        lp = max(0, (W - _vis(ti)) // 2)
        rp = max(0, W - _vis(ti) - lp)
        print(C.CYAN + B.V + C.RESET + ' ' * lp + ti + ' ' * rp + C.CYAN + B.V + C.RESET)
        if subtitle:
            si = ' ' + C.DIM + C.GRAY + _trunc_plain(subtitle, W - 4) + C.RESET + ' '
            l2 = max(0, (W - _vis(si)) // 2)
            r2 = max(0, W - _vis(si) - l2)
            print(C.CYAN + B.V + C.RESET + ' ' * l2 + si + ' ' * r2 + C.CYAN + B.V + C.RESET)
        print(hl(B.ML, B.MR))
        if info_rows:
            for ir_lb, ir_val in info_rows:
                lb = _trunc_plain(str(ir_lb), 24).ljust(24)
                val = _trunc_plain(str(ir_val), max(8, W - 28))
                ir_row = '  ' + C.GRAY + lb + C.RESET + C.WHITE + val + C.RESET
                print(vr(ir_row))
            print(hl(B.ML, B.MR))
        for it in items:
            k = str(it.get('key', '?'))
            lb = str(it.get('label', ''))
            ds = str(it.get('desc', '') or '')
            print(vr(_menu_item_row(k, lb, ds, W, C)))
        print(hl(B.ML, B.MR))
        er = (
            '  ' + C.RED_BOLD + '0' + C.RESET + '.  ' + chr(0x21a9) + '  '
            + C.RED_BOLD + 'Esci / Indietro' + C.RESET
        )
        print(vr(er))
        print(hl(B.BL, B.BR))
        print()
        return input('  ' + C.CYAN_BOLD + 'Scelta' + C.RESET + ': ').strip().upper()
    @staticmethod
    def show_success(m):
        log_debug("[core/ui] → show_success()")
        print('  '+Colors.GREEN+chr(0x2713)+' '+str(m)+Colors.RESET)
    @staticmethod
    def show_error(m):
        log_debug("[core/ui] → show_error()")
        print('  '+Colors.RED+chr(0x2717)+' '+str(m)+Colors.RESET)
    @staticmethod
    def show_info(m):
        log_debug("[core/ui] → show_info()")
        print('  '+Colors.BLUE+chr(0x2139)+' '+str(m)+Colors.RESET)
    @staticmethod
    def show_warning(m):
        log_debug("[core/ui] → show_warning()")
        print('  '+Colors.YELLOW+chr(0x26a0)+' '+str(m)+Colors.RESET)
    @staticmethod
    def success(m):
        log_debug("[core/ui] → success()")
        UIManager.show_success(m)
    @staticmethod
    def error(m):
        log_debug("[core/ui] → error()")
        UIManager.show_error(m)
    @staticmethod
    def info(m):
        log_debug("[core/ui] → info()")
        UIManager.show_info(m)
    @staticmethod
    def warning(m):
        log_debug("[core/ui] → warning()")
        UIManager.show_warning(m)
    @staticmethod
    def ask_input(prompt, default=''):
        log_debug("[core/ui] → ask_input()")
        hint=(' ['+default+']') if default else ''
        raw=input('  '+prompt+hint+': ').strip()
        return raw if raw else default
    @staticmethod
    def pause(msg='Premi INVIO per continuare...'):
        log_debug("[core/ui] → pause()")
        input('  '+msg)
    @staticmethod
    def wait_enter(msg='Premi invio per continuare...'):
        log_debug("[core/ui] → wait_enter()")
        UIManager.pause(msg)
    @staticmethod
    def ask_yes_no(q):
        log_debug("[core/ui] → ask_yes_no()")
        while True:
            r=input('  '+q+' (s/n): ').strip().lower()
            if r in ('s','si','y','yes'): return True
            if r in ('n','no'): return False
            UIManager.show_error("Inserisci 's' o 'n'.")
    @staticmethod
    def ask_choice(prompt='', options=None, *, header=None,
                   message="Scegli un'opzione", choices=None, default=None):
        log_debug("[core/ui] → ask_choice()")
        if choices:
            valid=list(choices.keys())
            print('  +'+'-'*38+'+')
            for k, v in choices.items(): print('  |  '+k+'.  '+v.ljust(34)+'|')
            print('  +'+'-'*38+'+')
            while True:
                raw=input('  '+message+' ('+'/'.join(valid)+'): ').strip()
                if raw=='' and default is not None: return default
                if raw in valid: return raw
                UIManager.show_error('Scegli tra: '+', '.join(valid))
        valid_opts=options or []
        while True:
            c=input('  '+prompt).strip()
            if c in valid_opts: return c
            UIManager.show_error('Scegli tra: '+', '.join(valid_opts))
    @staticmethod
    def print_separator(ch=chr(0x2500)): print('  '+ch*(UIManager.WIDTH-2))
    @staticmethod
    def print_box(t):
        log_debug("[core/ui] → print_box()")
        print('='*UIManager.WIDTH); print('  '+t); print('='*UIManager.WIDTH)
    @staticmethod
    def show_sub_header(t):
        log_debug("[core/ui] → show_sub_header()")
        print(); print('  '+'='*66); print('  '+t.center(66)); print('  '+'='*66); print()
    @staticmethod
    def show_info_table(title, rows):
        log_debug("[core/ui] → show_info_table()")
        C=Colors; B=Box; W=B.WIDTH
        print(); print(C.CYAN+B.TL+B.H*W+B.TR+C.RESET)
        t=' '+C.BOLD+C.WHITE+title+C.RESET+' '
        lp=max(0,(W-_vis(t))//2); rp=max(0,W-_vis(t)-lp)
        print(C.CYAN+B.V+C.RESET+' '*lp+t+' '*rp+C.CYAN+B.V+C.RESET)
        print(C.CYAN+B.ML+B.H*W+B.MR+C.RESET)
        for lb, val in rows:
            row='  '+C.GRAY+str(lb).ljust(24)+C.RESET+C.WHITE+str(val)+C.RESET
            print(C.CYAN+B.V+C.RESET+_pad(row, W)+C.CYAN+B.V+C.RESET)
        print(C.CYAN+B.BL+B.H*W+B.BR+C.RESET); print()
    @staticmethod
    def show_exit():
        log_debug("[core/ui] → show_exit()")
        C=Colors; B=Box; W=B.WIDTH
        print(); print(C.CYAN+B.TL+B.H*W+B.TR+C.RESET)
        t=' '+C.BOLD+C.CYAN+'Arrivederci!'+C.RESET+' '
        lp=max(0,(W-_vis(t))//2); rp=max(0,W-_vis(t)-lp)
        print(C.CYAN+B.V+C.RESET+' '*lp+t+' '*rp+C.CYAN+B.V+C.RESET)
        print(C.CYAN+B.BL+B.H*W+B.BR+C.RESET); print()
    @staticmethod
    def print_startup_header():
        log_debug("[core/ui] → print_startup_header()")
        C=Colors; B=Box; W=B.WIDTH
        print(C.CYAN+B.TL+B.H*W+B.TR+C.RESET)
        t=' '+C.BOLD+C.WHITE+'DOWNLOAD CENTER 3.0  -  Controlli pre-avvio'+C.RESET+' '
        lp=max(0,(W-_vis(t))//2); rp=max(0,W-_vis(t)-lp)
        print(C.CYAN+B.V+C.RESET+' '*lp+t+' '*rp+C.CYAN+B.V+C.RESET)
        print(C.CYAN+B.ML+B.H*W+B.MR+C.RESET)
    @staticmethod
    def print_startup_footer():
        log_debug("[core/ui] → print_startup_footer()")
        C=Colors; B=Box; W=B.WIDTH
        print(C.CYAN+B.ML+B.H*W+B.MR+C.RESET)
        m='  '+C.GREEN_BOLD+'Controlli completati.'+C.RESET
        print(C.CYAN+B.V+C.RESET+_pad(m, W)+C.CYAN+B.V+C.RESET)
        print(C.CYAN+B.BL+B.H*W+B.BR+C.RESET)
        input('  Premi INVIO per continuare... ')
    @staticmethod
    def print_section_label(lbl):
        log_debug("[core/ui] → print_section_label()")
        C=Colors; B=Box; W=B.WIDTH
        t='  '+C.BOLD+C.CYAN+lbl+C.RESET
        print(C.CYAN+B.V+C.RESET+_pad(t, W)+C.CYAN+B.V+C.RESET)
    @staticmethod
    def print_check_row(lbl, ok, warn=False):
        log_debug("[core/ui] → print_check_row()")
        C=Colors; B=Box; W=B.WIDTH
        if ok is True: st=C.GREEN_BOLD+'OK  '+C.RESET
        elif ok is False: st=C.RED_BOLD+'FAIL'+C.RESET
        else: st=C.YELLOW+'WARN'+C.RESET
        row='  '+st+'  '+lbl
        print(C.CYAN+B.V+C.RESET+_pad(row, W)+C.CYAN+B.V+C.RESET)

ui = UIManager()
