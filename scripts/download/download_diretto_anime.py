'''
Download Diretto Anime - File Integrato
Scarica video da URL diretti con gestione resume, pausa e raggruppamento intelligente
Versione: 2.4.1 (FIXED PROGRESS BAR)
Data: 12 Aprile 2026
Legge percorso da: scripts/temp/prefs.json

NOVITA v2.4.1:
  - FIXED: Barra di progresso ripetuta
  - Aggiornamento progress bar ottimizzato
  - Stampa ogni 500KB per evitare flicker
  - Pulizia linea completa dopo il download
  - NUOVA FUNZIONE: Riprendi download interrotto
'''

import os
import sys
import requests
from pathlib import Path
from urllib.parse import urlparse
import re
from datetime import datetime
import json
import threading
import time
import signal

# CONFIGURAZIONE PERCORSI
_THIS_DIR = Path(__file__).parent.resolve()
_SCRIPTS_DIR = _THIS_DIR.parent
_TEMP_DIR = _SCRIPTS_DIR / "temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)
download_state_file = str(_TEMP_DIR / ".download_state.json")

# VARIABILI GLOBALI
pause_flag = False
exit_flag = False
progress_active = False

def signal_handler(sig, frame):
    global pause_flag
    pause_flag = True

def clear_screen():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except:
        pass

def clean_path(path_str):
    return path_str.strip().replace('"', '').replace("'", '')

def show_header(title):
    print()
    print("  " + "="*66)
    print("  " + title.center(66))
    print("  " + "="*66)
    print()

def show_success(message):
    print("  ✓ " + message)

def show_error(message):
    print("  ✗ " + message)

def show_info(message):
    print("  ℹ " + message)

def show_warning(message):
    print("  ⚠ " + message)

def format_size(bytes_val):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return "{:.2f} {}".format(bytes_val, unit)
        bytes_val /= 1024
    return "{:.2f} TB".format(bytes_val)

def animate_progress(current, total, prefix="Progresso", length=40):
    if total <= 0:
        return
    
    percent = 100 * (current / float(total))
    filled = int(length * current // total)
    chars = ['◐', '◓', '◑', '◒']
    anim = chars[int(time.time() * 4) % len(chars)]
    bar = '█' * filled + '░' * (length - filled)
    
    output = '  ' + prefix + ': |' + bar + '| {:.1f}% '.format(percent) + anim
    output += ' ' * 10
    
    print('\r' + output, end='', flush=True)

def get_valid_choice(prompt, valid_options):
    while True:
        choice = input("  " + prompt).strip().lower()
        if choice in valid_options:
            return choice
        show_error("Inserisci una delle seguenti opzioni: " + ", ".join(valid_options))

def ask_yes_no(question):
    response = get_valid_choice(question + " (s/n): ", ['s', 'si', 'sì', 'y', 'n', 'no'])
    return response in ('s', 'si', 'sì', 'y')

def get_video_links_from_input():
    show_header("📝 INSERIMENTO LINK VIDEO")
    print("  Inserisci i link video (uno per riga)")
    print("  Digita 'FINE' quando hai terminato")
    print("  Digita '0' per tornare al menu")
    print()
    links = []
    counter = 1
    
    while True:
        link = input("  Link " + str(counter) + ": ").strip()
        
        if link == "0":
            print()
            if links:
                print("  Inseriti %d link" % len(links))
                if ask_yes_no("Continua con questi link?"):
                    print()
                    return links
                else:
                    print()
                    links = []
                    counter = 1
                    continue
            else:
                show_info("Nessun link inserito - ritorno al menu")
                print()
                input("  Premi INVIO per continuare...")
                return None
        
        if link.upper() == 'FINE':
            if links:
                break
            else:
                show_error("Inserisci almeno un link")
                continue
        
        if link:
            if not link.startswith(('http://', 'https://')):
                link = 'https://' + link
            links.append(link)
            counter += 1
    
    return links

def get_file_path_from_input():
    show_header("📁 CARICAMENTO DA FILE")
    print("  Inserisci il percorso del file .txt")
    print("  Digita '0' per tornare al menu")
    print()
    
    while True:
        path = input("  Percorso file .txt: ").strip()
        
        if path == "0":
            show_info("Ritorno al menu")
            print()
            input("  Premi INVIO per continuare...")
            return None
        
        path = clean_path(path)
        
        if not path:
            show_error("Percorso vuoto")
            continue
        
        if os.path.isdir(path):
            show_error("E una cartella, non un file")
            continue
        
        if not os.path.isfile(path):
            show_error("File non trovato: " + path)
            if input("  Riprova? (s/n): ").strip().lower() not in ('s', 'si', 'y'):
                return None
            continue
        
        if not path.lower().endswith('.txt'):
            show_warning("Il file non ha estensione .txt")
            if not ask_yes_no("Continuare comunque?"):
                continue
        
        return path

def load_urls_from_file(file_path):
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'):
                    urls.append(url)
        return urls
    except FileNotFoundError:
        show_error("File non trovato: " + file_path)
        return []
    except Exception as e:
        show_error("Errore lettura file: " + str(e))
        return []

def get_download_dir_from_settings():
    possible_paths = [
        _TEMP_DIR / "prefs.json",
        _SCRIPTS_DIR / "prefs.json",
        _SCRIPTS_DIR / "config" / "settings.json",
        _SCRIPTS_DIR / "settings.json",
        _SCRIPTS_DIR / "config.json",
    ]
    for config_path in possible_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    download_dir = config.get('default_download_dir') or config.get('default_Download_dir') or config.get('download_dir')
                    if download_dir:
                        show_info("Download dir da: " + str(config_path))
                        return download_dir
            except Exception:
                pass
    return "."

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '', filename)
    sanitized = sanitized.strip()
    return sanitized[:200]

def sanitize_folder_name(folder_name):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '', folder_name)
    sanitized = sanitized.strip()
    return sanitized[:200]

def get_safe_path(base_path):
    if os.path.exists(base_path):
        show_warning("'" + os.path.basename(base_path) + "' esiste già!")
        if ask_yes_no("Vuoi usarlo comunque?"):
            return base_path
        base = base_path
        counter = 1
        while os.path.exists(base + "_" + str(counter)):
            counter += 1
        new_path = base + "_" + str(counter)
        show_success("Nuovo percorso: " + os.path.basename(new_path))
        return new_path
    try:
        os.makedirs(base_path, exist_ok=True)
        return base_path
    except Exception as e:
        show_error("Errore creazione cartella: " + str(e))
        return None

class DownloadState:
    def __init__(self, state_file=None):
        if state_file is None:
            state_file = download_state_file
        self.state_file = state_file
        self.state = {}
    
    def load(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                return True
        except Exception:
            pass
        return False
    
    def save(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            pass
        return False
    
    def create_download_session(self, session_id, video_links, download_folder):
        try:
            files_dict = {}
            for link in video_links:
                filename = os.path.basename(urlparse(link).path)
                if not filename:
                    filename = "video_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".mp4"
                files_dict[filename] = {
                    'url': link,
                    'status': 'pending',
                    'size': 0,
                    'downloaded': 0,
                    'timestamp': datetime.now().isoformat()
                }
            self.state = {
                'session_id': session_id,
                'created_at': datetime.now().isoformat(),
                'download_folder': download_folder,
                'files': files_dict
            }
            self.save()
        except Exception:
            pass
    
    def start_download(self, filename):
        try:
            if 'files' in self.state and filename in self.state['files']:
                self.state['files'][filename]['status'] = 'in_progress'
                self.state['files'][filename]['start_time'] = datetime.now().isoformat()
                self.save()
        except Exception:
            pass
    
    def update_download_progress(self, filename, downloaded, total_size):
        try:
            if 'files' in self.state and filename in self.state['files']:
                self.state['files'][filename]['downloaded'] = downloaded
                self.state['files'][filename]['size'] = total_size
                self.state['files'][filename]['status'] = 'in_progress'
                self.save()
        except Exception:
            pass
    
    def mark_downloaded(self, filename):
        try:
            if 'files' in self.state and filename in self.state['files']:
                self.state['files'][filename]['status'] = 'completed'
                self.state['files'][filename]['completed_time'] = datetime.now().isoformat()
                self.save()
        except Exception:
            pass
    
    def mark_failed(self, filename):
        try:
            if 'files' in self.state and filename in self.state['files']:
                self.state['files'][filename]['status'] = 'failed'
                self.save()
        except Exception:
            pass
    
    def is_complete(self):
        try:
            if 'files' in self.state:
                for file_info in self.state['files'].values():
                    if isinstance(file_info, dict):
                        if file_info.get('status') != 'completed':
                            return False
                return True
        except Exception:
            pass
        return True
    
    def clear(self):
        try:
            self.state = {}
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        except Exception:
            pass

def download_video(video_url, save_path, filename, download_state=None):
    global pause_flag
    try:
        response = requests.head(video_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
        response.raise_for_status()
        
        if not filename:
            filename = os.path.basename(urlparse(video_url).path)
            if not filename:
                filename = "video_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".mp4"
        
        Path(save_path).mkdir(parents=True, exist_ok=True)
        full_path = os.path.join(save_path, filename)
        
        if os.path.exists(full_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(save_path, name + "_" + str(counter) + ext)):
                counter += 1
            full_path = os.path.join(save_path, name + "_" + str(counter) + ext)
            filename = name + "_" + str(counter) + ext
        
        temp_path = full_path + '.tmp'
        resume_position = 0
        
        if download_state:
            download_state.start_download(filename)
        
        resume_headers = {"User-Agent": "Mozilla/5.0"}
        if os.path.exists(temp_path):
            resume_position = os.path.getsize(temp_path)
            resume_headers['Range'] = 'bytes=' + str(resume_position) + '-'
        
        response = requests.get(video_url, headers=resume_headers, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = resume_position
        last_print = 0
        
        print()
        print("  ⬇ " + filename)
        print("    💡 Premi Ctrl+C per mettere in pausa")
        
        mode = 'ab' if os.path.exists(temp_path) else 'wb'
        
        with open(temp_path, mode) as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if downloaded - last_print >= 512000 or downloaded >= resume_position + total_size:
                        if total_size > 0:
                            total_with_resume = total_size + resume_position
                            animate_progress(downloaded, total_with_resume, "    Download")
                            if download_state:
                                download_state.update_download_progress(filename, downloaded, total_with_resume)
                        last_print = downloaded
                
                if pause_flag:
                    pause_flag = False
                    print()
                    return None
        
        print()
        os.rename(temp_path, full_path)
        show_success("Download completato")
        if download_state:
            download_state.mark_downloaded(filename)
        return True
    
    except KeyboardInterrupt:
        print()
        print()
        print("  ⏸ Pausa!")
        if download_state and filename:
            download_state.start_download(filename)
        return None
    except requests.exceptions.RequestException as e:
        show_error("Errore di connessione: " + str(e))
        if download_state and filename:
            download_state.mark_failed(filename)
        return False
    except Exception as e:
        show_error("Errore: " + str(e))
        if download_state and filename:
            download_state.mark_failed(filename)
        return False

def show_pause_menu():
    global exit_flag
    while True:
        show_header("⏸ DOWNLOAD IN PAUSA")
        print("  1. Riprendi")
        print("  2. Salta")
        print("  3. Termina")
        print()
        choice = get_valid_choice("Scelta (1-3): ", ['1', '2', '3'])
        if choice == '1':
            return 'resume'
        elif choice == '2':
            return 'skip'
        elif choice == '3':
            print()
            print("  1. Esci dallo script")
            print("  2. Riavvia")
            print()
            sub = get_valid_choice("Scelta (1-2): ", ['1', '2'])
            if sub == '1':
                exit_flag = True
                return 'exit'
            elif sub == '2':
                return 'restart'

def _process_downloads(video_links, mode_name="input"):
    global exit_flag, pause_flag
    
    if not video_links:
        show_error("Nessun link video disponibile.")
        return
    
    total_count = len(video_links)
    print()
    print("  Total: " + str(total_count) + " video")
    print()
    print("  " + "="*66)
    print("  T = Scarica TUTTI")
    print("  Esempi: 1,5,10 oppure 1-5")
    print("  E = Esci dal processo")
    print()
    
    while True:
        selection = input("  Cosa scaricare? ").strip()
        if not selection:
            show_error("Inserisci una selezione")
            continue
        
        if selection.upper() == 'E':
            show_header("🔄 SCEGLI COSA FARE")
            print("  1. Riavvia il download")
            print("  0. Torna al menu")
            print()
            choice = get_valid_choice("Scelta (1,0): ", ['1', '0'])
            if choice == '1':
                return _process_downloads(video_links, mode_name)
            else:
                return
        
        selected_videos = []
        if selection.upper() == 'T':
            selected_videos = video_links
            break
        else:
            try:
                parts = selection.split(',')
                for part in parts:
                    if '-' in part:
                        start, end = part.split('-')
                        start = int(start.strip()) - 1
                        end = int(end.strip())
                        selected_videos.extend(video_links[start:end])
                    else:
                        idx = int(part.strip()) - 1
                        if 0 <= idx < len(video_links):
                            selected_videos.append(video_links[idx])
                selected_videos = list(dict.fromkeys(selected_videos))
                if selected_videos:
                    break
                else:
                    show_error("Selezione non valida")
            except Exception:
                show_error("Formato non valido")
    
    if not selected_videos:
        return
    
    show_header("🎥 VIDEO SELEZIONATI")
    for idx, link in enumerate(selected_videos, 1):
        print("  " + str(idx) + ". " + link)
    print()
    
    base_path = get_download_dir_from_settings()
    main_folder = os.path.join(base_path, "Download file singolo-i")
    main_folder = get_safe_path(main_folder)
    if not main_folder:
        show_error("Impossibile creare cartella principale.")
        return
    
    link_groups = {}
    for link in selected_videos:
        url_parts = urlparse(link).path.strip('/').split('/')
        if len(url_parts) >= 2:
            penultima = url_parts[-2]
        else:
            penultima = "Generico"
        if penultima not in link_groups:
            link_groups[penultima] = []
        link_groups[penultima].append(link)
    
    show_info("Cartella principale: " + main_folder)
    
    for group_name, links in link_groups.items():
        sub_folder = sanitize_folder_name(group_name)
        download_folder = os.path.join(main_folder, sub_folder)
        download_folder = get_safe_path(download_folder)
        if not download_folder:
            show_error("Impossibile creare sottocartella per " + group_name + ".")
            continue
        
        show_info("Sottocartella per '" + group_name + "': " + download_folder)
        
        download_state = DownloadState()
        session_id = datetime.now().isoformat()
        download_state.create_download_session(session_id, links, download_folder)
        
        show_header("✔ CONFERMA DOWNLOAD")
        num_links = len(links)
        print("  Video: " + str(num_links))
        print("  Cartella: " + download_folder)
        print()
        
        if not ask_yes_no("Confermi?"):
            print()
            print("  Annullato")
            download_state.clear()
            continue
        
        show_header("📥 DOWNLOAD")
        total_ok = 0
        total_fail = 0
        for vid_idx, video_link in enumerate(links, 1):
            if exit_flag:
                break
            filename = os.path.basename(urlparse(video_link).path)
            if not filename:
                filename = "video_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".mp4"
            print()
            print("  [" + str(vid_idx) + "/" + str(num_links) + "]")
            while True:
                result = download_video(video_link, download_folder, filename, download_state)
                if result is True:
                    total_ok += 1
                    break
                elif result is False:
                    total_fail += 1
                    break
                elif result is None:
                    menu = show_pause_menu()
                    if menu == 'resume':
                        continue
                    elif menu == 'skip':
                        break
                    elif menu == 'exit':
                        exit_flag = True
                        break
                    elif menu == 'restart':
                        return _process_downloads(video_links, mode_name)
        if exit_flag:
            return
        if download_state.is_complete():
            download_state.clear()
            show_header("✅ DOWNLOAD COMPLETO")
        else:
            show_header("⚠️ DOWNLOAD PARZIALE")
            show_info("Stato salvato per ripresa.")
        show_success("Ok: " + str(total_ok))
        if total_fail > 0:
            show_error("Errori: " + str(total_fail))
        show_info("Cartella: " + download_folder)

def _internal_main_workflow(mode):
    global exit_flag, pause_flag
    
    if mode == '1':
        video_links = get_video_links_from_input()
        if video_links is None:
            return
        _process_downloads(video_links, "input manuale")
    
    elif mode == '2':
        file_path = get_file_path_from_input()
        if file_path is None:
            return
        
        print()
        print("  Caricamento file...")
        video_links = load_urls_from_file(file_path)
        
        if not video_links:
            show_error("Nessun URL trovato nel file")
            print()
            input("  Premi INVIO per tornare...")
            return
        
        show_success("Caricati %d URL dal file" % len(video_links))
        print()
        _process_downloads(video_links, "da file .txt")

def resume_interrupted_downloads():
    global exit_flag
    download_state = DownloadState()
    
    if not os.path.exists(download_state_file):
        show_header("❌ NESSUN DOWNLOAD INTERROTTO")
        show_info("File di stato non trovato: " + download_state_file)
        print()
        input("  Premi INVIO per tornare...")
        return
    
    if not download_state.load():
        show_header("❌ ERRORE CARICAMENTO STATO")
        show_error("Impossibile caricare il file di stato")
        print()
        input("  Premi INVIO per tornare...")
        return
    
    if 'files' not in download_state.state or not download_state.state['files']:
        show_header("❌ NESSUN DOWNLOAD IN SOSPESO")
        show_info("Nessun file trovato nello stato")
        print()
        if ask_yes_no("Vuoi cancellare il file di stato?"):
            download_state.clear()
            show_success("File di stato eliminato")
        print()
        input("  Premi INVIO per tornare...")
        return
    
    show_header("📋 DOWNLOAD INTERROTTO")
    print("  Sessione ID: " + str(download_state.state.get('session_id', 'N/A'))[:40])
    print("  Creato: " + str(download_state.state.get('created_at', 'N/A'))[:40])
    print("  Cartella: " + str(download_state.state.get('download_folder', 'N/A')))
    print()
    
    print("  FILE IN SOSPESO:")
    print()
    file_list = list(download_state.state['files'].items())
    for idx, (filename, info) in enumerate(file_list, 1):
        status = info.get('status', 'unknown')
        downloaded = info.get('downloaded', 0)
        total = info.get('size', 0)
        
        print("  " + str(idx) + ". " + filename)
        print("     Status: " + status)
        if total > 0:
            percent = (downloaded / total) * 100
            print("     Progresso: " + format_size(downloaded) + " / " + format_size(total) + " ({:.1f}%)".format(percent))
        print("     URL: " + info.get('url', 'N/A')[:60] + "...")
        print()
    
    print("  " + "="*66)
    print("  1. Riprendi download dai file in sospeso")
    print("  2. Cancella i download pendenti")
    print("  0. Torna al menu")
    print()
    
    choice = get_valid_choice("Scelta (0-2): ", ['0', '1', '2'])
    
    if choice == '0':
        return
    
    elif choice == '1':
        print()
        show_info("Ripresa download in corso...")
        
        download_folder = download_state.state.get('download_folder')
        if not os.path.exists(download_folder):
            show_error("Cartella di download non trovata: " + download_folder)
            print()
            input("  Premi INVIO per tornare...")
            return
        
        show_header("📥 RIPRESA DOWNLOAD")
        total_ok = 0
        total_fail = 0
        
        for idx, (filename, info) in enumerate(file_list, 1):
            if info.get('status') == 'completed':
                show_success("(già completato) " + filename)
                continue
            
            video_url = info.get('url')
            if not video_url:
                show_error("URL mancante per: " + filename)
                continue
            
            print()
            print("  [" + str(idx) + "/" + str(len(file_list)) + "]")
            
            while True:
                result = download_video(video_url, download_folder, filename, download_state)
                if result is True:
                    total_ok += 1
                    break
                elif result is False:
                    total_fail += 1
                    break
                elif result is None:
                    menu = show_pause_menu()
                    if menu == 'resume':
                        continue
                    elif menu == 'skip':
                        break
                    elif menu == 'exit':
                        exit_flag = True
                        break
                    elif menu == 'restart':
                        return resume_interrupted_downloads()
            
            if exit_flag:
                return
        
        if download_state.is_complete():
            download_state.clear()
            show_header("✅ DOWNLOAD COMPLETO")
        else:
            show_header("⚠️ DOWNLOAD PARZIALE")
            show_info("Stato salvato per ripresa.")
        
        show_success("Ok: " + str(total_ok))
        if total_fail > 0:
            show_error("Errori: " + str(total_fail))
        
        print()
        input("  Premi INVIO per tornare...")
    
    elif choice == '2':
        print()
        show_warning("Sei sicuro di voler cancellare i download pendenti?")
        if ask_yes_no("Continua?"):
            download_state.clear()
            show_success("Download pendenti eliminati")
            show_info("File di stato rimosso: " + download_state_file)
        print()
        input("  Premi INVIO per tornare...")

def main():
    global exit_flag, pause_flag
    signal.signal(signal.SIGINT, signal_handler)
    try:
        while True:
            clear_screen()
            show_header("⬇ DOWNLOAD DIRETTO LINK VIDEO")
            print("  1. Scarica singolo file")
            print("  2. Da cartella di file .txt")
            print("  3. Riprendi download interrotto")
            print("  0. Torna al menu")
            print()
            mode = get_valid_choice("Scelta (0-3): ", ['0', '1', '2', '3'])
            if mode == '0':
                return
            elif mode == '3':
                resume_interrupted_downloads()
            else:
                _internal_main_workflow(mode)
    except KeyboardInterrupt:
        print()
        print()
        print("  ⏸ Programma interrotto!")
        sys.exit(0)
    except Exception as e:
        print()
        print()
        print("  ✗ ERRORE CRITICO: " + str(e))
        import traceback
        traceback.print_exc()
        input("  Premi INVIO per chiudere...")
        sys.exit(1)

def scarica_singolo(prefs):
    signal.signal(signal.SIGINT, signal_handler)
    _internal_main_workflow('1')

def scarica_da_cartella(prefs):
    signal.signal(signal.SIGINT, signal_handler)
    _internal_main_workflow('2')

if __name__ == "__main__":
    main()
