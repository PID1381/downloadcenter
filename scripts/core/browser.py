"""
Core Browser Module v2.0
Gestione centralizzata del browser Playwright.
"""
from typing import List, Optional

_COOKIE_SELECTORS = [
    "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#cookie-accept", ".cc-btn.cc-allow",
    "button[id*='accept']", "button[class*='accept']",
    "button[class*='cookie']", "a[id*='accept']",
]
_COOKIE_TEXTS = ["continua", "accetta", "accept", "ok", "agree", "accetto"]


class BrowserManager:
    """Browser Playwright centralizzato."""

    def __init__(self):
        self._cookie_dismissed = False

    def new_page(self, playwright, headless: Optional[bool] = None):
        """Crea nuova pagina con impostazioni da config."""
        from .config import config
        hl      = headless if headless is not None else config.is_headless()
        timeout = config.get_timeout() * 1_000
        browser = playwright.chromium.launch(headless=hl)
        ctx = browser.new_context(
            locale="it-IT",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.set_default_timeout(timeout)
        return browser, page

    def dismiss_cookies(self, page) -> None:
        """Chiude banner cookie con selettori CSS e testo."""
        if self._cookie_dismissed:
            return
        js = """([sel, txt]) => {
            for (const s of sel) {
                try { const e = document.querySelector(s);
                  if (e && e.offsetParent !== null) { e.click(); return 'css:' + s; }
                } catch(e) {}
            }
            const all = document.querySelectorAll(
                'button, a, input[type=button], input[type=submit], [role=button]');
            for (const e of all) {
                const t = (e.innerText || e.value || e.textContent || '').trim().toLowerCase();
                if (txt.includes(t) && e.offsetParent !== null) { e.click(); return 'text:' + t; }
            }
            return null;
        }"""
        try:
            clicked = page.evaluate(js, [_COOKIE_SELECTORS, _COOKIE_TEXTS])
            if clicked:
                self._cookie_dismissed = True
                page.wait_for_timeout(300)
                return
        except Exception:
            pass
        for sel in _COOKIE_SELECTORS:
            try:
                page.click(sel, timeout=600)
                self._cookie_dismissed = True
                page.wait_for_timeout(300)
                return
            except Exception:
                continue

    def reset_cookie_state(self) -> None:
        self._cookie_dismissed = False

    def wait_for_results(self, page, selectors: List[str],
                         timeout: int = 3_000) -> bool:
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=timeout)
                page.wait_for_timeout(800)
                return True
            except Exception:
                continue
        return False

    def fetch_html(self, url: str, wait_selector: Optional[str] = None,
                   headless: Optional[bool] = None) -> str:
        """Fetch HTML completo da URL con Playwright."""
        from playwright.sync_api import sync_playwright
        from .ui import ui
        self.reset_cookie_state()
        html = ""
        try:
            with sync_playwright() as pw:
                browser, page = self.new_page(pw, headless=headless)
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    self.dismiss_cookies(page)
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=8_000)
                        except Exception:
                            pass
                    page.wait_for_timeout(1_500)
                    self.dismiss_cookies(page)
                    html = page.content()
                finally:
                    browser.close()
        except Exception as e:
            ui.show_error(f"Errore browser: {e}")
        return html


class PageHelper:
    """Utilities statiche per operazioni su pagina."""

    @staticmethod
    def wait_for_element(page, selector: str, timeout: int = 5_000) -> bool:
        try:
            page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    @staticmethod
    def extract_text(page, selector: str) -> str:
        try:
            el = page.query_selector(selector)
            return el.inner_text() if el else ""
        except Exception:
            return ""

    @staticmethod
    def extract_links(page, selector: str) -> List[str]:
        try:
            return [el.get_attribute("href") or ""
                    for el in page.query_selector_all(selector)]
        except Exception:
            return []


browser_mgr = BrowserManager()
