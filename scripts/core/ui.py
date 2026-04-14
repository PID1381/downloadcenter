"""
Core UI Module v2.0
Centralizzazione di tutte le operazioni di interfaccia utente.
"""
import os
from typing import List


class UIManager:
    """Gestione centralizzata UI."""
    WIDTH = 56

    @staticmethod
    def clear() -> None:
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except Exception:
            pass

    @staticmethod
    def show_header(title: str, breadcrumb: str = "") -> None:
        UIManager.clear()
        print("=" * UIManager.WIDTH)
        print(f"  {title}")
        print("=" * UIManager.WIDTH)
        if breadcrumb:
            print(f"  {breadcrumb}")
        print()

    @staticmethod
    def show_success(msg: str) -> None: print(f"  ✓ {msg}")

    @staticmethod
    def show_error(msg: str) -> None:   print(f"  ✗ {msg}")

    @staticmethod
    def show_info(msg: str) -> None:    print(f"  ℹ {msg}")

    @staticmethod
    def show_warning(msg: str) -> None: print(f"  ⚠ {msg}")

    @staticmethod
    def ask_yes_no(question: str) -> bool:
        while True:
            r = input(f"  {question} (s/n): ").strip().lower()
            if r in ("s", "si", "sì", "y", "yes"): return True
            if r in ("n", "no"):                         return False
            UIManager.show_error("Inserisci 's' o 'n'.")

    @staticmethod
    def ask_choice(prompt: str, options: List[str]) -> str:
        while True:
            c = input(f"  {prompt}").strip().lower()
            if c in options: return c
            UIManager.show_error(f"Scegli tra: {', '.join(options)}")

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


ui = UIManager()
