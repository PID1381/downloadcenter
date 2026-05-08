def run():
    from .core import Core
    _menu(Core.get())

def _menu(core):
    sm = core.config.get_settings_menu()
    subs = sm.get('subsections', [
        {'key':'1','label':'Generali','icon':'','desc':'Impostazioni globali'},
        {'key':'2','label':'Moduli','icon':'','desc':'URL moduli e YT-DLP'},
    ])
    items = [{'key':s['key'],'icon':s.get('icon',''),'label':s['label'],
              'desc':s.get('description', s.get('desc',''))} for s in subs]
    while True:
        c = core.ui.show_menu('Impostazioni', items, 'Modifica le preferenze del progetto')
        if c == '0': return
        elif c == '1': _generali(core)
        elif c == '2': _moduli(core)
        else: core.ui.error('Voce non valida')

def _generali(core):
    while True:
        cfg = core.config
        rows = [
            ('Versione progetto', cfg.get_version()),
            ('Download DIR', cfg.get_download_dir()),
            ('Link DIR', cfg.get_link_dir()),
            ('Export DIR', cfg.get_export_dir()),
            ('Debug mode', 'ON' if cfg.is_debug() else 'OFF'),
            ('Headless browser', 'ON' if cfg.is_headless() else 'OFF'),
        ]
        core.ui.show_info_table('Impostazioni Generali', rows)
        items = [
            {'key':'1','icon':'','label':'Cambia percorsi DIR','desc':''},
            {'key':'2','icon':'','label':'Toggle DEBUG mode','desc':''},
            {'key':'3','icon':'','label':'Toggle Headless browser','desc':''},
            {'key':'4','icon':'','label':'Reset default','desc':''},
        ]
        c = core.ui.show_menu('Generali', items, show_version=False)
        if c == '0': return
        elif c == '1': _cambia_dir(core)
        elif c == '2':
            v = not cfg.is_debug()
            cfg.set('core','debug_mode', v)
            core.ui.success('Debug: '+('ON' if v else 'OFF'))
            core.logger.info('debug_mode -> '+str(v))
        elif c == '3':
            v = not cfg.is_headless()
            cfg.set('core','headless_browser', v)
            core.ui.success('Headless: '+('ON' if v else 'OFF'))
        elif c == '4': _reset_defaults(core)

def _cambia_dir(core):
    items = [
        {'key':'1','icon':'','label':'Download DIR','desc':''},
        {'key':'2','icon':'','label':'Link DIR','desc':''},
        {'key':'3','icon':'','label':'Export DIR','desc':''},
    ]
    mapping = {'1':'download_dir','2':'link_dir','3':'export_dir'}
    labels  = {'1':'Download DIR','2':'Link DIR','3':'Export DIR'}
    while True:
        c = core.ui.show_menu('Cambia percorsi', items, show_version=False)
        if c == '0': return
        if c in mapping:
            p = core.ui.ask_input(labels[c]+' [invio=annulla]')
            if p:
                core.config.set_dir(mapping[c], p)
                core.ui.success(labels[c]+' impostato: '+p)
                core.logger.info(mapping[c]+' -> '+p)

def _reset_defaults(core):
    c = core.ui.ask_input('Digita SI per confermare il reset')
    if c.upper() != 'SI': core.ui.info('Annullato.'); return
    from .settings_core import DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT
    from .file_manager import FileManager
    core.config.set('core','download_dir', DOWNLOAD_DIR_DEFAULT)
    core.config.set('core','link_dir', LINK_DIR_DEFAULT)
    core.config.set('core','export_dir', EXPORT_DIR_DEFAULT)
    core.config.set('core','headless_browser', True)
    core.config.set('core','debug_mode', False)
    for d in [DOWNLOAD_DIR_DEFAULT, LINK_DIR_DEFAULT, EXPORT_DIR_DEFAULT]:
        FileManager.ensure_folder(d)
    core.ui.success('Impostazioni ripristinate ai default.')
    core.logger.info('Reset default impostazioni')

def _moduli(core):
    items = [
        {'key':'1','icon':'','label':'Cambio URL moduli','desc':''},
        {'key':'2','icon':'','label':'Impostazioni YT-DLP','desc':''},
    ]
    while True:
        c = core.ui.show_menu('Moduli', items, show_version=False)
        if c == '0': return
        elif c == '1': _cambio_url(core)
        elif c == '2': _ytdlp(core)

def _cambio_url(core):
    modules = core.url_manager.get_all_modules()
    mlist = list(modules.keys())
    items = [{'key':str(i+1),'icon':'','label':m,'desc':modules[m].get('base_url','')}
             for i, m in enumerate(mlist)]
    while True:
        c = core.ui.show_menu('URL Moduli', items, show_version=False)
        if c == '0': return
        try: idx = int(c)-1
        except: core.ui.error('Voce non valida'); continue
        if 0 <= idx < len(mlist):
            mod = mlist[idx]
            cur = core.url_manager.get_url(mod) or ''
            url = core.ui.ask_input('Nuovo URL per '+mod, cur)
            if url:
                core.url_manager.set_url(mod, 'base_url', url)
                core.ui.success('URL aggiornato: '+url)
                core.logger.info('url '+mod+' -> '+url)
                items[idx]['desc'] = url

def _ytdlp(core):
    cfg = core.config
    yd = cfg.get_section_prefs('ytdlp') or {
        'format':'bestvideo+bestaudio/best','merge_output':'mkv',
        'write_subs':False,'sub_lang':'it','embed_subs':True,
        'embed_thumbnail':False,'rate_limit':'','proxy':'','extra_args':'',
    }
    keys = list(yd.keys())
    while True:
        items = [{'key':str(i+1),'icon':'','label':k,'desc':str(yd[k])} for i,k in enumerate(keys)]
        c = core.ui.show_menu('YT-DLP', items, show_version=False)
        if c == '0': return
        try: idx = int(c)-1
        except: core.ui.error('Voce non valida'); continue
        if 0 <= idx < len(keys):
            k = keys[idx]; v = yd[k]
            if isinstance(v, bool):
                yd[k] = not v
                core.ui.success(k+': '+str(yd[k]))
            else:
                nv = core.ui.ask_input(k, str(v))
                yd[k] = nv
            cfg.set_section('ytdlp', yd)
