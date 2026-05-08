_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

class BrowserManager:
    def __init__(self):
        self._pw = None; self._browser = None
    def launch(self, headless=True, slow_mo=0):
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=headless, slow_mo=slow_mo)
            return True
        except: self._pw = None; return False
    def new_page(self):
        if not self._browser: return None
        try:
            ctx = self._browser.new_context(user_agent=_UA)
            return ctx.new_page()
        except: return None
    def close(self):
        try:
            if self._browser: self._browser.close()
            if self._pw: self._pw.stop()
        except: pass
        self._browser = None; self._pw = None
