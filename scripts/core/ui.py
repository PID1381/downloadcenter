"""
Core UI Module v2.5
Changelog v2.5:
- colorama integrato: colori ANSI cross-platform (Windows + Unix)
- show_success → verde, show_error → rosso, show_warning → giallo, show_info → ciano
- show_header → titolo bright, breadcrumb dim
- ask_choice  → bordi bright, tasti ciano, prompt evidenziato
- Retrocompatibile v2.4 / v2.3 / v2.2 / v2.1
"""
import os
import unicodedata
from typing import Dict, List, Optional

# ── colorama: init con fallback graceful ─────────────────────────────────────
try:
    import colorama
    from colorama import Fore, Style, Back
    colorama.init(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False
    class _Dummy:
        def __getattr__(self, _): return ""
    Fore = Style = Back = _Dummy()


def visual_len(s: str) -> int:
    w = 0
    for ch in s:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("W", "F") else 1
    return w


def pad_to(s: str, width: int, fill: str = " ") -> str:
    return s + fill * max(0, width - visual_len(s))


class UIManager:
    WIDTH = 56

    @staticmethod
    def clear() -> None:
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except Exception:
            pass

    @staticmethod
    def show_header(title: str, breadcrumb: str = "") -> str:
        UIManager.clear()
        sep = Style.BRIGHT + "=" * UIManager.WIDTH + Style.RESET_ALL
        print(sep)
        print(f"  {Style.BRIGHT}{title}{Style.RESET_ALL}")
        print(sep)
        if breadcrumb:
            print(f"  {Style.DIM}{breadcrumb}{Style.RESET_ALL}")
        print()
        return title

    @staticmethod
    def show_success(msg: str) -> None:
        print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {msg}")

    @staticmethod
    def show_error(msg: str) -> None:
        print(f"  {Fore.RED}✗{Style.RESET_ALL} {msg}")

    @staticmethod
    def show_info(msg: str) -> None:
        print(f"  {Fore.CYAN}ℹ{Style.RESET_ALL} {msg}")

    @staticmethod
    def show_warning(msg: str) -> None:
        print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL} {msg}")

    @staticmethod
    def ask_yes_no(question: str) -> bool:
        while True:
            r = input(
                f"  {Style.BRIGHT}{question}{Style.RESET_ALL} (s/n): "
            ).strip().lower()
            if r in ("s", "si", "sì", "y", "yes"):
                return True
            if r in ("n", "no"):
                return False
            UIManager.show_error("Inserisci 's' o 'n'.")

    @staticmethod
    def ask_choice(
        prompt: str = "",
        options: Optional[List[str]] = None,
        *,
        header: Optional[str] = None,
        message: str = "Scegli un'opzione",
        choices: Optional[Dict[str, str]] = None,
        default: Optional[str] = None,
    ) -> str:
        if choices is not None:
            valid = list(choices.keys())
            _kw = max(visual_len(str(k)) for k in choices.keys())
            _lw = max(visual_len(str(v)) for v in choices.values())
            _inner  = _kw + _lw + 7
            _border = "  " + Style.BRIGHT + "+" + "─" * _inner + "+" + Style.RESET_ALL

            def _row(k, v):
                return (
                    "  " + Style.BRIGHT + "|" + Style.RESET_ALL
                    + "  " + Fore.CYAN + pad_to(str(k), _kw) + Style.RESET_ALL
                    + ".  " + pad_to(str(v), _lw)
                    + "  " + Style.BRIGHT + "|" + Style.RESET_ALL
                )

            def _print_box():
                print(_border)
                for key, label in choices.items():
                    print(_row(key, label))
                print(_border)

            _print_box()
            valid_str = "/".join(
                f"{Fore.CYAN}{v}{Style.RESET_ALL}{Style.BRIGHT}" for v in valid
            )
            prompt_str = (
                f"{Style.BRIGHT}{message} ({Style.RESET_ALL}"
                + valid_str
                + f"{Style.BRIGHT}){Style.RESET_ALL}: "
            )
            while True:
                raw = input(f"  {prompt_str}").strip()
                if raw == "" and default is not None:
                    return default
                if raw in valid:
                    return raw
                if header is not None:
                    UIManager.show_header(header)
                    _print_box()
                UIManager.show_error(f"Scegli tra: {', '.join(valid)}")

        valid_opts = options or []
        while True:
            c = input(f"  {Style.BRIGHT}{prompt}{Style.RESET_ALL}").strip()
            if c in valid_opts:
                return c
            UIManager.show_error(f"Scegli tra: {', '.join(valid_opts)}")

    @staticmethod
    def print_separator(char: str = "─") -> None:
        print(f"  {char * (UIManager.WIDTH - 2)}")

    @staticmethod
    def print_box(text: str) -> None:
        sep = Style.BRIGHT + "=" * UIManager.WIDTH + Style.RESET_ALL
        print(sep)
        print(f"  {Style.BRIGHT}{text}{Style.RESET_ALL}")
        print(sep)

    @staticmethod
    def wait_enter(msg: str = "Premi invio per continuare...") -> None:
        input(f"  {Style.DIM}{msg}{Style.RESET_ALL}")

    @staticmethod
    def show_sub_header(title: str) -> None:
        print()
        print("  " + Style.BRIGHT + "=" * 66 + Style.RESET_ALL)
        print("  " + Style.BRIGHT + title.center(66) + Style.RESET_ALL)
        print("  " + Style.BRIGHT + "=" * 66 + Style.RESET_ALL)
        print()

    @staticmethod
    def print_section_header(title: str, subtitle: str = "") -> None:
        W = UIManager.WIDTH
        sep = Style.BRIGHT + "=" * W + Style.RESET_ALL
        print()
        print(sep)
        print(f"  {Style.BRIGHT}{title}{Style.RESET_ALL}")
        if subtitle:
            print(f"  {Style.DIM}{subtitle}{Style.RESET_ALL}")
        print(sep)
        print()

    @staticmethod
    def print_table(
        headers: List[str],
        rows: List[List[str]],
        title: str = "",
        total_label: str = "",
        col_caps: Optional[List[int]] = None,
        indent: str = "  ",
    ) -> None:
        if not rows and not headers:
            print(f"{indent}(nessun dato da mostrare)")
            return
        n = len(headers)
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < n:
                    widths[i] = max(widths[i], len(str(cell)))
        if col_caps:
            widths = [
                min(w, col_caps[i]) if i < len(col_caps) else w
                for i, w in enumerate(widths)
            ]

        def _cell(val: str, w: int) -> str:
            val = str(val)
            if len(val) > w:
                val = val[:w - 2] + ".."
            return val.ljust(w)

        def _border(left, mid, right, fill):
            return (indent + Style.BRIGHT
                    + left + mid.join(fill * (w + 2) for w in widths) + right
                    + Style.RESET_ALL)

        def _row_str(vals):
            parts = [f" {_cell(str(v), widths[i])} " for i, v in enumerate(vals)]
            sep = Style.BRIGHT + "│" + Style.RESET_ALL
            return indent + sep + sep.join(parts) + sep

        W = UIManager.WIDTH
        if title:
            print()
            print(Style.BRIGHT + "=" * W + Style.RESET_ALL)
            print(f"  {Style.BRIGHT}{title}{Style.RESET_ALL}")
            print(Style.BRIGHT + "=" * W + Style.RESET_ALL)
            print()

        print(_border("┌", "┬", "┐", "─"))
        print(_row_str(headers))
        print(_border("├", "┼", "┤", "─"))
        for row in rows:
            padded = list(row) + [""] * (n - len(row))
            print(_row_str(padded[:n]))
        print(_border("└", "┴", "┘", "─"))

        if total_label:
            print()
            print(f"{indent}{total_label}")
        print()


ui = UIManager()
