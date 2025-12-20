import requests
import re
import json
import time
import datetime
import pytz
import os
import sys
import hashlib
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from tqdm import tqdm
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_strmd_url():
    try:
        response = requests.get('https://strmd.link/', timeout=10)
        if response.status_code == 200:
            links = re.findall(r'href="(https://[^"]+)"', response.text)
            for link in links:
                if 'status.strmd.link' in link:
                    continue
                
                try:
                    r = requests.get(link, timeout=5)
                    if r.status_code == 200:
                        return link.rstrip('/')
                except Exception as e:
                    print(f"Mirror {link} failed: {e}")
    except Exception as e:
        print(f"Failed to get mirrors: {e}")

    return None

def fix_json(j):
    j = j.strip()
    j = j.lstrip('(').rstrip(')')
    parts = re.split(r'(?<!\\)"', j)
    for i in range(0, len(parts), 2):
        s = parts[i]
        # Replace unquoted keys with quoted keys
        s = re.sub(r'([^\s\[\]\{\}\:\,]+):', r'"\1":', s)
        parts[i] = s
    
    return '"'.join(parts)

def get_embed_url(strmd_url, source, source_id):
    response = requests.get(f"{strmd_url}/api/stream/{source}/{source_id}", timeout=10)
    
    if response.status_code == 200:
        data = response.text
        fixed_data = fix_json(data)
        try:
            json_data = json.loads(fixed_data)
            if len(json_data) > 0:
                return json_data[0]['embedUrl']
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON for watch URL: {e}")
            
    return None

def get_stream_url(watch_url, driver_path=None):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Enable performance logging to capture network requests
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    try:
        if driver_path:
            service = Service(executable_path=driver_path)
        else:
            service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"Failed to initialize Selenium driver: {e}")
        return None

    try:
        driver.get(watch_url)
        
        # Wait for requests to populate
        timeout = 20
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            logs = driver.get_log('performance')
            for entry in logs:
                try:
                    log = json.loads(entry['message'])['message']
                    if log['method'] == 'Network.requestWillBeSent':
                        url = log['params']['request']['url']
                        if '.m3u8' in url:
                            return url
                except (KeyError, json.JSONDecodeError):
                    continue
            time.sleep(0.5)
            
    except Exception as e:
        print(f"Error getting stream URL: {e}")
    finally:
        driver.quit()
        
    return None

def process_match(match, strmd_url, driver_path):
    category = match.get('category', '')
    poster = 'https://raw.githubusercontent.com/woody-willis/strmd-sports/main/images/sports.png'
    category_name = category.lower()

    if category.lower().startswith('afl'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/afl.png?raw=true'
        category_name = 'AFL'
    elif category.lower().startswith('american-football'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/am-football.png?raw=true'
        category_name = 'American Football'
    elif category.lower().startswith('baseball'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/baseball.png?raw=true'
        category_name = 'Baseball'
    elif category.lower().startswith('basketball'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/basketball.png?raw=true'
        category_name = 'Basketball'
    elif category.lower().startswith('billiards'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/billiards.png?raw=true'
        category_name = 'Billiards'
    elif category.lower().startswith('cricket'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/cricket.png?raw=true'
        category_name = 'Cricket'
    elif category.lower().startswith('darts'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/darts.PNG?raw=true'
        category_name = 'Darts'
    elif category.lower().startswith('football'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/football.png?raw=true'
        category_name = 'Football'
    elif category.lower().startswith('fight'):
        poster = 'https://raw.githubusercontent.com/woody-willis/strmd-sports/main/images/fighting.png'
        category_name = 'Fighting'
    elif category.lower().startswith('golf'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/golf.png?raw=true'
        category_name = 'Golf'
    elif category.lower().startswith('hockey'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/hockey.png?raw=true'
        category_name = 'Hockey'
    elif category.lower().startswith('motor-sports'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/motor.png?raw=true'
        category_name = 'Motor Sports'
    elif category.lower().startswith('nba'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/nba.png?raw=true'
        category_name = 'NBA'
    elif category.lower().startswith('rugby'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/rugby.png?raw=true'
        category_name = 'Rugby'
    elif category.lower().startswith('tennis'):
        poster = 'https://github.com/woody-willis/strmd-sports/blob/main/images/tennis.png?raw=true'
        category_name = 'Tennis'
        
    if all(k in match for k in ('sources', 'date', 'id', 'title', 'category')):
        timestamp = match['date'] / 1000
        dt = datetime.datetime.fromtimestamp(timestamp, pytz.utc)
        dt_gb = dt.astimezone(pytz.timezone('Europe/London'))
        formatted_date = dt_gb.strftime('%I:%M %p %Z - (%d/%m/%Y)')
        
        watch_url = get_embed_url(strmd_url, match['sources'][0]['source'], match['sources'][0]['id'])
        if not watch_url:
            return None
        
        stream_url = get_stream_url(watch_url, driver_path)
        if not stream_url:
            return None
        
        epg_id = hashlib.md5(f"{match['id']}{match['date']}".encode()).hexdigest()

        return {
            'id': match['id'],
            'date': formatted_date,
            'time': match['date'],
            'title': match['title'],
            'posterImage': poster,
            'url': watch_url,
            'stream': stream_url,
            'Referer': 'https://embedsports.top/',
            'type': category_name,
            'epg': epg_id
        }
    return None

def discover_listings(strmd_url):
    max_retries = 3
    attempt = 0
    success = False
    all_matches = ""

    while attempt < max_retries and not success:
        attempt += 1
        try:
            response = requests.get(strmd_url + "/api/matches/all", timeout=30)
            if response.status_code == 200:
                all_matches = response.text
                success = True
            else:
                print(f"Attempt {attempt} failed with status {response.status_code}.")
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")

        if not success and attempt < max_retries:
            time.sleep(30)

    if not success:
        print(f"Failed after {max_retries} attempts.")
        sys.exit(1)
    
    try:
        all_matches_json = json.loads(all_matches)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to decode the JSON data. Error: {e}"}
    
    items = []

    # Install driver once
    try:
        driver_path = ChromeDriverManager().install()
    except Exception as e:
        print(f"Failed to install driver: {e}")
        return {"error": f"Failed to install driver: {e}"}

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_match = {executor.submit(process_match, match, strmd_url, driver_path): match for match in all_matches_json}
        
        for future in tqdm(as_completed(future_to_match), total=len(future_to_match), desc="Processing matches"):
            try:
                result = future.result()
                if result:
                    items.append(result)
            except Exception as e:
                print(f"Error processing match: {e}")
    return items

def generate_m3u8(items):
    m3u8 = '#EXTM3U url-tvg="https://raw.githubusercontent.com/woody-willis/strmd-sports/main/playlists/epg.xml"\n'
    for item in items:
        dt = datetime.datetime.fromtimestamp(item['time'] / 1000, pytz.utc)
        dt_ny = dt.astimezone(pytz.timezone('America/New_York'))
        formatted_time = dt_ny.strftime('%I:%M %p -')
        
        m3u8 += f'#EXTINF:-1 tvg-id="{item["epg"]}" tvg-name="{item["title"]}" tvg-logo="{item["posterImage"]}" group-title="{item["type"]}",'
        m3u8 += f'{formatted_time} {item["title"]} - {item["date"]}\n'
        m3u8 += f'{item["stream"]}\n'
    
    with open('playlists/playlist.m3u8', 'w') as f:
        f.write(m3u8)

def generate_proxy_m3u8(items):
    m3u8 = '#EXTM3U url-tvg="https://raw.githubusercontent.com/woody-willis/strmd-sports/main/playlists/epg.xml"\n'
    for item in items:
        dt = datetime.datetime.fromtimestamp(item['time'] / 1000, pytz.utc)
        dt_ny = dt.astimezone(pytz.timezone('America/New_York'))
        formatted_time = dt_ny.strftime('%I:%M %p -')
        
        m3u8 += f'#EXTINF:-1 tvg-id="{item["epg"]}" tvg-name="{item["title"]}" tvg-logo="{item["posterImage"]}" group-title="{item["type"]}",'
        m3u8 += f'{formatted_time} {item["title"]} - {item["date"]}\n'
        m3u8 += f'https://m3u8.ndaeasy.workers.dev?url={quote(item["stream"])}&data=UmVmZXJlcj1odHRwczovL2VtYmVkc3BvcnRzLnRvcHxPcmlnaW49aHR0cHM6Ly9lbWJlZHNwb3J0cy50b3B8VXNlci1BZ2VudD1Nb3ppbGxhLzUuMCAoTWFjaW50b3NoOyBJbnRlbCBNYWMgT1MgWCAxMF8xNV8wKSBBcHBsZVdlYktpdC81MzcuMzYgKEtIVE1MLCBsaWtlIEdlY2tvKSBDaHJvbWUvODQuMC40MTQ3LjM4IFNhZmFyaS81MzcuMzY%3D\n'
    
    with open('playlists/proxied_playlist.m3u8', 'w') as f:
        f.write(m3u8)

def generate_tivimate_m3u8(items):
    m3u8 = '#EXTM3U url-tvg="https://raw.githubusercontent.com/woody-willis/strmd-sports/main/playlists/epg.xml"\n'
    for item in items:
        dt = datetime.datetime.fromtimestamp(item['time'] / 1000, pytz.utc)
        dt_ny = dt.astimezone(pytz.timezone('America/New_York'))
        formatted_time = dt_ny.strftime('%I:%M %p -')
        
        m3u8 += f'#EXTINF:-1 tvg-id="{item["epg"]}" tvg-name="{item["title"]}" tvg-logo="{item["posterImage"]}" group-title="{item["type"]}",'
        m3u8 += f'{formatted_time} {item["title"]} - {item["date"]}\n'
        m3u8 += f'{item["stream"]}|Referer={item["Referer"]}\n'
    
    with open('playlists/tivimate_playlist.m3u8', 'w') as f:
        f.write(m3u8)

def generate_vlc(items):
    vlc = '#EXTM3U url-tvg="https://raw.githubusercontent.com/woody-willis/strmd-sports/main/playlists/epg.xml"\n'
    for item in items:
        dt = datetime.datetime.fromtimestamp(item['time'] / 1000, pytz.utc)
        dt_ny = dt.astimezone(pytz.timezone('America/New_York'))
        formatted_time = dt_ny.strftime('%I:%M %p -')
        
        vlc += f'#EXTINF:-1 tvg-id="{item["epg"]}" tvg-name="{item["title"]}" tvg-logo="{item["posterImage"]}" group-title="{item["type"]}",'
        vlc += f'{formatted_time} {item["title"]} - {item["date"]}\n'
        vlc += f'#EXTVLCOPT:http-referrer={item["Referer"]}\n'
        vlc += f'{item["stream"]}\n'
    
    with open('playlists/vlc_playlist.m3u8', 'w') as f:
        f.write(vlc)

def generate_kodipop(items):
    kodipop = '#EXTM3U url-tvg="https://raw.githubusercontent.com/woody-willis/strmd-sports/main/playlists/epg.xml"\n'
    for item in items:
        dt = datetime.datetime.fromtimestamp(item['time'] / 1000, pytz.utc)
        dt_ny = dt.astimezone(pytz.timezone('America/New_York'))
        formatted_time = dt_ny.strftime('%I:%M %p -')
        
        kodipop += f'#EXTINF:-1 tvg-id="{item["epg"]}" tvg-name="{item["title"]}" tvg-logo="{item["posterImage"]}" group-title="{item["type"]}",'
        kodipop += f'{formatted_time} {item["title"]} - {item["date"]}\n'
        kodipop += f'#KODIPROP:inputstream.adaptive.stream_headers=Referer={quote(item["Referer"])}\n'
        kodipop += f'{item["stream"]}\n'
    
    with open('playlists/kodi_playlist.m3u8', 'w') as f:
        f.write(kodipop)

def generate_epg(items):
    epg = '<?xml version="1.0" encoding="UTF-8"?>\n'
    epg += '<tv>\n'

    for item in items:
        epg += f'  <channel id="{item["epg"]}">\n'
        epg += f'    <display-name>{html_escape(item["title"] + " - " + item["date"])}</display-name>\n'
        epg += f'    <icon src="{html_escape(item["posterImage"])}" />\n'
        epg += '  </channel>\n'

    current_time = time.time() - 3600

    for item in items:
        start_time = datetime.datetime.fromtimestamp(current_time, pytz.utc).strftime('%Y%m%d%H%M%S +0000')
        end_time = datetime.datetime.fromtimestamp(current_time + (48 * 3600), pytz.utc).strftime('%Y%m%d%H%M%S +0000')

        dt = datetime.datetime.fromtimestamp(item['time'] / 1000, pytz.utc)
        
        pt_time = dt.astimezone(pytz.timezone('America/Los_Angeles')).strftime('%I:%M %p %Z')
        mt_time = dt.astimezone(pytz.timezone('America/Denver')).strftime('%I:%M %p %Z')
        et_time = dt.astimezone(pytz.timezone('America/New_York')).strftime('%I:%M %p %Z')
        
        formatted_date = dt.astimezone(pytz.timezone('America/New_York')).strftime('%m/%d/%Y')
        description = f"{pt_time} / {mt_time} / {et_time} - ({formatted_date})"

        epg += f'  <programme start="{start_time}" stop="{end_time}" channel="{item["epg"]}">\n'
        epg += f'    <title>{html_escape(item["title"] + " - " + item["date"])}</title>\n'
        epg += f'    <desc>{html_escape(description)}</desc>\n'
        epg += f'    <category lang="en">{html_escape(item["type"])}</category>\n'
        epg += '  </programme>\n'

    epg += '</tv>'

    with open('playlists/epg.xml', 'w') as f:
        f.write(epg)

def html_escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

def save_items_to_json(items):
    try:
        with open('playlists/streamed_su.json', 'w') as f:
            json.dump(items, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to write to file: {e}")
        sys.exit(1)

def filter_and_sort_events(items):
    current_time = time.time()
    four_hours_ago = current_time - (4 * 3600)

    upcoming_events = [item for item in items if (item['time'] / 1000) >= four_hours_ago]
    upcoming_events.sort(key=lambda x: x['time'])
    
    return upcoming_events

if __name__ == "__main__":
    strmd_url = get_strmd_url()
    if not strmd_url:
        print(json.dumps({"error": "No available strmd.link mirrors."}))
        sys.exit(1)
        
    items = discover_listings(strmd_url)
    
    if isinstance(items, dict) and 'error' in items:
        print(json.dumps(items))
        sys.exit(1)
        
    filtered_sorted_items = filter_and_sort_events(items)
    
    # Ensure playlists directory exists
    os.makedirs('playlists', exist_ok=True)
    
    generate_m3u8(filtered_sorted_items)
    generate_tivimate_m3u8(filtered_sorted_items)
    generate_vlc(filtered_sorted_items)
    generate_proxy_m3u8(filtered_sorted_items)
    generate_kodipop(filtered_sorted_items)
    generate_epg(filtered_sorted_items)
    save_items_to_json(filtered_sorted_items)
    
    print(json.dumps(filtered_sorted_items))
