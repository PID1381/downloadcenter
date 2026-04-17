"""
Core UI Module v2.1
Centralizzazione di tutte le operazioni di interfaccia utente.

Changelog v2.1:
- show_header() ora ritorna il titolo (str) invece di None
- ask_choice() supporta firma estesa: header / message / choices / default
- ask_choice() modalita' 2: se header!=None, ridisegna lo schermo prima del box
- Piena retrocompatibilita' con firma semplice (prompt, options)
"""
import os
from typing import Dict, List, Optional


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
    def show_header(title: str, breadcrumb: str = "") -> str:
        """Pulisce lo schermo, stampa l'header e ritorna il titolo."""
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
        """
        Metodo unificato per la scelta da menu.

        Modalita' 1 - firma semplice (retrocompatibile):
            ui.ask_choice(prompt="Scegli (0-2): ", options=["0","1","2"])

        Modalita' 2 - firma estesa (nuovi handler):
            ui.ask_choice(
                header="TITOLO SEZIONE",
                message="Scegli",
                choices={"1": "Voce A", "0": "Torna"},
                default="0",
            )
        """
        # --- Modalita' 2: dizionario choices ---
        if choices is not None:
            valid = list(choices.keys())

            # Se header e' fornito, ridisegna schermo + header prima del box
            if header is not None:
                UIManager.show_header(header)

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
                UIManager.show_error(f"Scegli tra: {', '.join(valid)}")

        # --- Modalita' 1: lista options (retrocompatibile) ---
        valid = options or []
        while True:
            c = input(f"  {prompt}").strip()
            if c in valid:
                return c
            UIManager.show_error(f"Scegli tra: {', '.join(valid)}")

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
