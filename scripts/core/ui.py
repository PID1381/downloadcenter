"""
Core UI Module v2.2
Centralizzazione di tutte le operazioni di interfaccia utente.

Changelog v2.2:
- print_table(headers, rows, ...) con box-drawing standard ┌─┬┐
- print_section_header(title, subtitle="")
- Retrocompatibile con v2.1
"""
import os
from typing import Dict, List, Optional


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
        print("=" * UIManager.WIDTH)
        print(f"  {title}")
        print("=" * UIManager.WIDTH)
        if breadcrumb:
            print(f"  {breadcrumb}")
        print()
        return title

    @staticmethod
    def show_success(msg: str) -> None:
        print(f"  ✓ {msg}")

    @staticmethod
    def show_error(msg: str) -> None:
        print(f"  ✗ {msg}")

    @staticmethod
    def show_info(msg: str) -> None:
        print(f"  ℹ {msg}")

    @staticmethod
    def show_warning(msg: str) -> None:
        print(f"  ⚠ {msg}")

    @staticmethod
    def ask_yes_no(question: str) -> bool:
        while True:
            r = input(f"  {question} (s/n): ").strip().lower()
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
            print("  +--------------------------------------+")
            for key, label in choices.items():
                print(f"  |  {key}.  {label:<34}|")
            print("  +--------------------------------------+")
            prompt_str = f"{message} ({'/'.join(valid)}): "
            while True:
                raw = input(f"  {prompt_str}").strip()
                if raw == "" and default is not None:
                    return default
                if raw in valid:
                    return raw
                if header is not None:
                    UIManager.show_header(header)
                    print("  +--------------------------------------+")
                    for key, label in choices.items():
                        print(f"  |  {key}.  {label:<34}|")
                    print("  +--------------------------------------+")
                UIManager.show_error(f"Scegli tra: {', '.join(valid)}")
        valid_opts = options or []
        while True:
            c = input(f"  {prompt}").strip()
            if c in valid_opts:
                return c
            UIManager.show_error(f"Scegli tra: {', '.join(valid_opts)}")

    @staticmethod
    def print_separator(char: str = "─") -> None:
        print(f"  {char * (UIManager.WIDTH - 2)}")

    @staticmethod
    def print_box(text: str) -> None:
        print("=" * UIManager.WIDTH)
        print(f"  {text}")
        print("=" * UIManager.WIDTH)

    @staticmethod
    def wait_enter(msg: str = "Premi invio per continuare...") -> None:
        input(f"  {msg}")

    @staticmethod
    def show_sub_header(title: str) -> None:
        print()
        print("  " + "=" * 66)
        print("  " + title.center(66))
        print("  " + "=" * 66)
        print()

    # ── NUOVO v2.2 ──────────────────────────────────────────────────────────

    @staticmethod
    def print_section_header(title: str, subtitle: str = "") -> None:
        """Header sezione con separatori == standard."""
        W = UIManager.WIDTH
        print()
        print("=" * W)
        print(f"  {title}")
        if subtitle:
            print(f"  {subtitle}")
        print("=" * W)
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
        """
        Tabella con box-drawing standard ┌─┬┐ — layout uniforme Download Center.

        Args:
            headers:     Intestazioni colonne
            rows:        Righe dati (lista di liste di stringhe)
            title:       Titolo sopra la tabella (header ======)
            total_label: Riga riepilogo sotto la tabella
            col_caps:    Larghezze massime per colonna (opzionale)
            indent:      Indentazione sinistra (default "  ")
        """
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
            return indent + left + mid.join(fill * (w + 2) for w in widths) + right

        def _row_str(vals):
            parts = [f" {_cell(str(v), widths[i])} " for i, v in enumerate(vals)]
            return indent + "│" + "│".join(parts) + "│"

        W = UIManager.WIDTH
        if title:
            print()
            print("=" * W)
            print(f"  {title}")
            print("=" * W)
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
