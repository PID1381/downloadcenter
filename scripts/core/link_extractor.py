import urllib.request
from pathlib import Path
from typing import Dict, List
from .settings_core import VARIE_DIR
from .file_manager import FileManager
from scripts.core.logger import get_logger, log_debug
logger = get_logger(__name__)

_inst = None

class EstrazioneLink:
    def __init__(self):
        log_debug("[core/link_extractor] → __init__()")
        pass
    @classmethod
    def get(cls):
        log_debug("[core/link_extractor] → get()")
        global _inst
        if _inst is None: _inst = cls()
        return _inst
    def run(self, module_id, anime_url, titolo):
        log_debug("[core/link_extractor] → run()")
        from .core import Core
        core = Core.get()
        core.progress.spinner_start('Recupero link in corso...')
        try:
            fn = getattr(self, '_extract_'+module_id, self._extract_generic)
            links = fn(anime_url)
        finally:
            core.progress.spinner_stop()
        if not links:
            core.ui.warning('Nessun link estratto da '+anime_url)
            core.ui.pause(); return []
        grouped = self._group_by_pattern(links)
        sel = self._show_and_select(grouped, core)
        if sel:
            path = self._save_to_file(sel, titolo, module_id)
            core.ui.success('Salvato: '+path)
            core.logger.info('Link salvati: '+path)
        return sel
    def _extract_animeworld(self, url):
        log_debug("[core/link_extractor] → _extract_animeworld()")
        return []
    def _extract_animeunity(self, url):
        log_debug("[core/link_extractor] → _extract_animeunity()")
        try:
            from scripts.anime.moduli.AnimeUnity.handlers_animeunity import get_episodes
            return get_episodes(url) or []
        except Exception:
            return []
    def _extract_generic(self, url):
        log_debug("[core/link_extractor] → _extract_generic()")
        try:
            req = urllib.request.Request(url,
                headers={'User-Agent':'Mozilla/5.0 Chrome/120'})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode('utf-8', errors='ignore')
            urls=[]; start=0
            while True:
                idx=html.find('http', start)
                if idx==-1: break
                end=idx
                while end<len(html) and html[end] not in ' \t\n\r<>"': end+=1
                c=html[idx:end]
                if c.startswith('http'): urls.append(c)
                start=end
            return list(set(urls))
        except: return []
    def _group_by_pattern(self, links):
        log_debug("[core/link_extractor] → _group_by_pattern()")
        from urllib.parse import urlparse

        groups = {}
        for lnk in links:
            try:
                p = urlparse(lnk)
                parts = p.path.strip('/').split('/')
                key = p.netloc+('/'+parts[0] if parts else '')
            except: key = 'altri'
            groups.setdefault(key, []).append(lnk)
        return groups
    def _show_and_select(self, grouped, core):
        log_debug("[core/link_extractor] → _show_and_select()")
        if not grouped: return []
        keys = list(grouped.keys())
        letters = [chr(65+i) for i in range(len(keys))]
        items = [{'key':letters[i],'icon':'','label':keys[i],
                  'desc':'tot:'+str(len(grouped[keys[i]]))}
                 for i in range(len(keys))]
        c = core.ui.show_menu('Gruppi link', items, show_version=False)
        if c == '0': return []
        if c.upper() not in letters:
            core.ui.error('Voce non valida'); return []
        idx = ord(c.upper())-65
        sel_group = grouped[keys[idx]]
        items2 = [{'key':str(i+1),'icon':'','label':lnk[:70]}
                  for i,lnk in enumerate(sel_group)]
        c2 = core.ui.show_menu('Seleziona link', items2, show_version=False)
        if c2 == '0': return []
        return self._parse_selection(c2, sel_group)
    def _parse_selection(self, scelta, links):
        log_debug("[core/link_extractor] → _parse_selection()")
        s = scelta.strip()
        if s.lower() == 'tutti': return list(links)
        if '-' in s:
            try: a,b = s.split('-',1); return links[int(a)-1:int(b)]
            except: return []
        try: return [links[int(s)-1]]
        except: return []
    def _save_to_file(self, links, titolo, module_id):
        log_debug("[core/link_extractor] → _save_to_file()")
        return self.save_links_file(titolo, module_id, links)

    def save_links_file(self, titolo, module_id, lines, suffix=''):
        """Salva righe di testo in varie/Link/<titolo>/."""
        log_debug("[core/link_extractor] → save_links_file()")
        if not lines:
            return ''
        safe = FileManager.sanitize_folder_name(titolo)
        d = Path(VARIE_DIR) / 'Link' / safe
        d.mkdir(parents=True, exist_ok=True)
        name = safe + '_' + module_id + (('_' + suffix) if suffix else '') + '.txt'
        path = d / name
        body = titolo + ' - ' + module_id + chr(10) + chr(10) + chr(10).join(lines)
        path.write_text(body, encoding='utf-8')
        return str(path)
