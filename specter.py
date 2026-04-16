import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import os
import json
import time
import base64
import socket
import subprocess
import tempfile
import platform
import re
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================
# GITHUB
# =====================
GITHUB_TOKEN = os.getenv('GH_TOKEN')
GITHUB_REPO = 'ANAEHY/SPECTER'
GITHUB_FILE = 'keys.txt'
GITHUB_BRANCH = 'main'

HEADER = """#profile-title: base64:4pqhIFNQRUNURVIgVlBO
#profile-update-interval: 12"""

# =====================
# COUNTRY FLAGS
# =====================
COUNTRY_RU = {
    # Европа
    "🇩🇪": "Германия", "🇫🇷": "Франция", "🇳🇱": "Нидерланды", "🇮🇹": "Италия",
    "🇪🇸": "Испания", "🇵🇱": "Польша", "🇧🇪": "Бельгия", "🇦🇹": "Австрия",
    "🇨🇭": "Швейцария", "🇸🇪": "Швеция", "🇳🇴": "Норвегия", "🇩🇰": "Дания",
    "🇫🇮": "Финляндия", "🇬🇧": "Британия", "🇵🇹": "Португалия", "🇮🇪": "Ирландия",
    "🇨🇿": "Чехия", "🇸🇰": "Словакия", "🇭🇺": "Венгрия", "🇷🇴": "Румыния",
    "🇧🇬": "Болгария", "🇭🇷": "Хорватия", "🇸🇮": "Словения", "🇷🇸": "Сербия",
    "🇬🇷": "Греция", "🇱🇹": "Литва", "🇱🇻": "Латвия", "🇪🇪": "Эстония",
    "🇲🇩": "Молдова", "🇧🇾": "Беларусь", "🇲🇰": "Северная Македония",
    "🇦🇱": "Албания", "🇧🇦": "Босния", "🇲🇪": "Черногория", "🇽🇰": "Косово",
    "🇱🇺": "Люксембург", "🇲🇹": "Мальта", "🇨🇾": "Кипр", "🇮🇸": "Исландия",
    "🇱🇮": "Лихтенштейн", "🇲🇨": "Монако", "🇸🇲": "Сан-Марино",
    # СНГ / Кавказ / ЦА
    "🇷🇺": "Россия", "🇺🇦": "Украина", "🇰🇿": "Казахстан", "🇺🇿": "Узбекистан",
    "🇦🇿": "Азербайджан", "🇦🇲": "Армения", "🇬🇪": "Грузия",
    "🇹🇯": "Таджикистан", "🇹🇲": "Туркменистан", "🇰🇬": "Кыргызстан",
    # Ближний Восток
    "🇹🇷": "Турция", "🇮🇱": "Израиль", "🇦🇪": "ОАЭ", "🇸🇦": "Саудовская Аравия",
    "🇶🇦": "Катар", "🇰🇼": "Кувейт", "🇧🇭": "Бахрейн", "🇴🇲": "Оман",
    "🇮🇶": "Ирак", "🇮🇷": "Иран", "🇯🇴": "Иордания", "🇱🇧": "Ливан",
    # Азия
    "🇮🇳": "Индия", "🇯🇵": "Япония", "🇰🇷": "Корея", "🇸🇬": "Сингапур",
    "🇨🇳": "Китай", "🇭🇰": "Гонконг", "🇹🇼": "Тайвань", "🇲🇾": "Малайзия",
    "🇮🇩": "Индонезия", "🇵🇭": "Филиппины", "🇹🇭": "Таиланд", "🇻🇳": "Вьетнам",
    "🇵🇰": "Пакистан", "🇧🇩": "Бангладеш", "🇱🇰": "Шри-Ланка", "🇳🇵": "Непал",
    "🇲🇲": "Мьянма", "🇰🇭": "Камбоджа", "🇱🇦": "Лаос", "🇲🇳": "Монголия",
    # Северная Америка
    "🇺🇸": "США", "🇨🇦": "Канада", "🇲🇽": "Мексика",
    # Центральная и Южная Америка
    "🇧🇷": "Бразилия", "🇦🇷": "Аргентина", "🇨🇱": "Чили", "🇨🇴": "Колумбия",
    "🇵🇪": "Перу", "🇪🇨": "Эквадор", "🇻🇪": "Венесуэла", "🇺🇾": "Уругвай",
    "🇧🇴": "Боливия", "🇵🇾": "Парагвай", "🇨🇷": "Коста-Рика", "🇵🇦": "Панама",
    # Африка
    "🇿🇦": "ЮАР", "🇳🇬": "Нигерия", "🇪🇬": "Египет", "🇰🇪": "Кения",
    "🇲🇦": "Марокко", "🇹🇳": "Тунис", "🇬🇭": "Гана", "🇸🇳": "Сенегал",
    "🇪🇹": "Эфиопия", "🇩🇿": "Алжир", "🇹🇿": "Танзания", "🇺🇬": "Уганда",
    # Океания
    "🇦🇺": "Австралия", "🇳🇿": "Новая Зеландия",
    # Прочее
    "🌐": "Anycast",
}

CODE_TO_FLAG = {
    # Европа
    "DE": "🇩🇪", "FR": "🇫🇷", "NL": "🇳🇱", "IT": "🇮🇹", "ES": "🇪🇸",
    "PL": "🇵🇱", "BE": "🇧🇪", "AT": "🇦🇹", "CH": "🇨🇭", "SE": "🇸🇪",
    "NO": "🇳🇴", "DK": "🇩🇰", "FI": "🇫🇮", "GB": "🇬🇧", "PT": "🇵🇹",
    "IE": "🇮🇪", "CZ": "🇨🇿", "SK": "🇸🇰", "HU": "🇭🇺", "RO": "🇷🇴",
    "BG": "🇧🇬", "HR": "🇭🇷", "SI": "🇸🇮", "RS": "🇷🇸", "GR": "🇬🇷",
    "LT": "🇱🇹", "LV": "🇱🇻", "EE": "🇪🇪", "MD": "🇲🇩", "BY": "🇧🇾",
    "MK": "🇲🇰", "AL": "🇦🇱", "BA": "🇧🇦", "ME": "🇲🇪", "XK": "🇽🇰",
    "LU": "🇱🇺", "MT": "🇲🇹", "CY": "🇨🇾", "IS": "🇮🇸",
    # СНГ / Кавказ / ЦА
    "RU": "🇷🇺", "UA": "🇺🇦", "KZ": "🇰🇿", "UZ": "🇺🇿", "AZ": "🇦🇿",
    "AM": "🇦🇲", "GE": "🇬🇪", "TJ": "🇹🇯", "TM": "🇹🇲", "KG": "🇰🇬",
    # Ближний Восток
    "TR": "🇹🇷", "IL": "🇮🇱", "AE": "🇦🇪", "SA": "🇸🇦", "QA": "🇶🇦",
    "KW": "🇰🇼", "BH": "🇧🇭", "OM": "🇴🇲", "IQ": "🇮🇶", "IR": "🇮🇷",
    "JO": "🇯🇴", "LB": "🇱🇧",
    # Азия
    "IN": "🇮🇳", "JP": "🇯🇵", "KR": "🇰🇷", "SG": "🇸🇬", "CN": "🇨🇳",
    "HK": "🇭🇰", "TW": "🇹🇼", "MY": "🇲🇾", "ID": "🇮🇩", "PH": "🇵🇭",
    "TH": "🇹🇭", "VN": "🇻🇳", "PK": "🇵🇰", "BD": "🇧🇩", "LK": "🇱🇰",
    "NP": "🇳🇵", "MM": "🇲🇲", "KH": "🇰🇭", "LA": "🇱🇦", "MN": "🇲🇳",
    # Северная Америка
    "US": "🇺🇸", "CA": "🇨🇦", "MX": "🇲🇽",
    # Южная Америка
    "BR": "🇧🇷", "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴", "PE": "🇵🇪",
    "EC": "🇪🇨", "VE": "🇻🇪", "UY": "🇺🇾", "BO": "🇧🇴", "PY": "🇵🇾",
    "CR": "🇨🇷", "PA": "🇵🇦",
    # Африка
    "ZA": "🇿🇦", "NG": "🇳🇬", "EG": "🇪🇬", "KE": "🇰🇪", "MA": "🇲🇦",
    "TN": "🇹🇳", "GH": "🇬🇭", "SN": "🇸🇳", "ET": "🇪🇹", "DZ": "🇩🇿",
    "TZ": "🇹🇿", "UG": "🇺🇬",
    # Океания
    "AU": "🇦🇺", "NZ": "🇳🇿",
}

# =====================
# XRAY - REAL 204 PROVERKA
# =====================
XRAY_PATH = 'xray.exe' if os.name == 'nt' else '/tmp/xray'

def install_xray():
    if os.path.exists(XRAY_PATH):
        return True
    try:
        if os.name == 'nt':
            url = 'https://github.com/XTLS/Xray-core/releases/download/v1.8.6/Xray-windows-64.zip'
            r = requests.get(url, timeout=60, stream=True)
            with open('xray.zip', 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            import zipfile
            with zipfile.ZipFile('xray.zip', 'r') as z:
                z.extractall('.')
            os.remove('xray.zip')
        else:
            arch = 'linux-64'
            r = requests.get('https://api.github.com/repos/XTLS/Xray-core/releases/latest', timeout=15)
            ver = r.json()['tag_name']
            url = f'https://github.com/XTLS/Xray-core/releases/download/{ver}/Xray-{arch}.zip'
            r = requests.get(url, timeout=60, stream=True)
            with open('/tmp/xray.zip', 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            import zipfile
            with zipfile.ZipFile('/tmp/xray.zip', 'r') as z:
                z.extract('xray', '/tmp/')
            os.chmod(XRAY_PATH, 0o755)
            os.remove('/tmp/xray.zip')
        return True
    except:
        return False

# =====================
# COUNTRY DETECTION
# =====================
def get_flag_and_country(fragment: str):
    decoded = unquote(fragment)
    flag_match = re.search(r'([\U0001F1E0-\U0001F1FF]{2})', decoded)
    if flag_match:
        flag = flag_match.group(1)
        if flag in COUNTRY_RU:
            return flag, COUNTRY_RU[flag]
    return "🌐", "Anycast"

def extract_country(config):
    patterns = {
        'DE': ['de-', 'germany', 'de:', 'berlin', 'frankfurt', 'de/', '🇩🇪', 'germany', 'german'],
        'FR': ['fr-', 'france', 'fr:', 'paris', 'fr/', '🇫🇷', 'france', 'french'],
        'NL': ['nl-', 'netherlands', 'nl:', 'amsterdam', 'rotterdam', 'nl/', '🇳🇱', 'netherlands', 'dutch'],
        'IT': ['it-', 'italy', 'it:', 'rome', 'milan', 'it/', '🇮🇹', 'italy', 'italian'],
        'ES': ['es-', 'spain', 'es:', 'madrid', 'es/', '🇪🇸', 'spain', 'spanish'],
        'PL': ['pl-', 'poland', 'pl:', 'warsaw', 'pl/', '🇵🇱', 'poland', 'polish'],
        'GB': ['gb-', 'uk', 'gb:', 'london', 'uk/', '🇬🇧', 'britain', 'british', 'england'],
        'US': ['us-', 'usa', 'us:', 'new york', 'nyc', 'la/', '🇺🇸', 'usa', 'america'],
        'CA': ['ca-', 'canada', 'ca:', 'toronto', 'ca/', '🇨🇦', 'canada'],
        'JP': ['jp-', 'japan', 'jp:', 'tokyo', 'jp/', '🇯🇵', 'japan', 'japanese'],
        'RU': ['ru-', 'russia', 'ru:', 'moscow', 'spb', 'ru/', '🇷🇺', 'russia'],
    }
    config_lower = config.lower()
    for country, pats in patterns.items():
        if any(pat in config_lower for pat in pats):
            return country
    return 'OTHER'

def get_country_from_url(uri):
    p = urlparse(uri)
    flag, country = get_flag_and_country(p.fragment)
    if country != "Anycast":
        return flag, country
    country_code = extract_country(uri)
    country_map = {
        'DE': ('🇩🇪', 'Германия'),
        'NL': ('🇳🇱', 'Нидерланды'),
        'FR': ('🇫🇷', 'Франция'),
        'IT': ('🇮🇹', 'Италия'),
        'ES': ('🇪🇸', 'Испания'),
        'PL': ('🇵🇱', 'Польша'),
        'GB': ('🇬🇧', 'Британия'),
        'US': ('🇺🇸', 'США'),
        'CA': ('🇨🇦', 'Канада'),
        'AU': ('🇦🇺', 'Австралия'),
        'JP': ('🇯🇵', 'Япония'),
        'KR': ('🇰🇷', 'Корея'),
        'RU': ('🇷🇺', 'Россия'),
    }
    if country_code in country_map:
        return country_map[country_code]
    return "🌐", "Anycast"

# =====================
# PARSING
# =====================
def parse_vless(uri):
    try:
        p = urlparse(uri)
        q = parse_qs(p.query)
        h, pt = p.hostname, p.port or 443
        u = p.username
        sec = q.get('security', ['none'])[0]
        net = q.get('type', ['tcp'])[0]
        flow = q.get('flow', [''])[0]
        sni = q.get('sni', [h])[0]
        fp = q.get('fp', ['chrome'])[0]
        pbk = q.get('pbk', [''])[0]
        sid = q.get('sid', [''])[0]
        path = q.get('path', ['/'])[0]
        
        stream = {'network': net}
        if sec == 'reality':
            stream['security'] = 'reality'
            stream['realitySettings'] = {'serverName': sni, 'fingerprint': fp, 'publicKey': pbk, 'shortId': sid}
        elif sec == 'tls':
            stream['security'] = 'tls'
            stream['tlsSettings'] = {'serverName': sni, 'allowInsecure': True}
        if net == 'ws':
            stream['wsSettings'] = {'path': path}
        
        return {'protocol': 'vless', 'settings': {'vnext': [{'address': h, 'port': pt, 'users': [{'id': u, 'encryption': 'none', 'flow': flow}]}]}, 'streamSettings': stream}
    except:
        return None

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

# =====================
# PROVERKA - XRAY + 204
# =====================
def check_xray(uri, timeout=8.0):
    outbound = parse_vless(uri)
    if not outbound:
        return 9999
    
    port = get_free_port()
    cfg = {
        'log': {'loglevel': 'none'},
        'inbounds': [{'port': port, 'listen': '127.0.0.1', 'protocol': 'socks', 'settings': {'auth': 'noauth'}}],
        'outbounds': [outbound, {'protocol': 'freedom'}],
    }
    
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(cfg, f)
    f.close()
    
    proc = None
    try:
        proc = subprocess.Popen([XRAY_PATH, 'run', '-c', f.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        
        proxies = {'http': f'socks5h://127.0.0.1:{port}', 'https': f'socks5h://127.0.0.1:{port}'}
        
        for url in ['https://www.gstatic.com/generate_204', 'https://www.google.com/generate_204']:
            try:
                t0 = time.time()
                r = requests.get(url, proxies=proxies, timeout=timeout, allow_redirects=False)
                if r.status_code == 204:
                    return round((time.time() - t0) * 1000, 1)
            except:
                continue
        return 9999
    except:
        return 9999
    finally:
        if proc:
            try: proc.kill()
            except: pass
        try: os.unlink(f.name)
        except: pass

def check_tcp(host, port, timeout=2.0):
    try:
        t0 = time.time()
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.time() - t0) * 1000, 1)
    except:
        return 9999

# =====================
# SOURCES
# =====================
IGARECK_SOURCES = [
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt', 'lte': False, 'top_n': 8, 'skip_check': False},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt', 'lte': False, 'top_n': 8, 'skip_check': False},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt', 'lte': True, 'top_n': 8, 'skip_check': False},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt', 'lte': True, 'top_n': 8, 'skip_check': False},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt', 'lte': True, 'top_n': 8, 'skip_check': False},
    # SNI - без проверки, берём все и переименовываем
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt', 'lte': True, 'top_n': None, 'skip_check': True},
]

def load_keys(url):
    try:
        r = requests.get(url, timeout=15)
        return [l.strip() for l in r.text.splitlines() if l.strip().startswith('vless://')]
    except:
        return []

def dedup(keys):
    seen, out = set(), []
    for k in keys:
        try:
            p = urlparse(k)
            key = f"{p.hostname}:{p.port}"
            if key not in seen:
                seen.add(key); out.append(k)
        except:
            out.append(k)
    return out

def check_all(keys):
    results = []
    
    def worker(uri):
        ms = check_xray(uri, 6.0)
        if ms < 9999:
            return uri, ms
        
        try:
            p = urlparse(uri)
            ms = check_tcp(p.hostname, p.port or 443, 2.0)
            if ms < 9999:
                return uri, ms + 50
        except:
            pass
        
        return None, 9999
    
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(worker, k): k for k in keys}
        done, alive = 0, 0
        for f in as_completed(futures):
            uri, ms = f.result()
            done += 1
            if uri and ms < 9999:
                results.append((uri, ms))
                alive += 1
            if done % 20 == 0:
                print(f"   [{done}/{len(keys)}] alive: {alive}")
    
    results.sort(key=lambda x: x[1])
    return results

def rename_with_country(uri, lte):
    p = urlparse(uri)
    flag, country = get_country_from_url(uri)
    tag = f"LTE" if lte else "WiFi"
    new_name = f"{flag} {country} - {tag}"
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, quote(new_name)))

def get_flag_for_host(host):
    """Определяем страну хоста через ip-api.com"""
    try:
        r = requests.get(f'http://ip-api.com/json/{host}?fields=countryCode', timeout=4)
        if r.status_code == 200:
            code = r.json().get('countryCode', '')
            if code and code in CODE_TO_FLAG:
                flag = CODE_TO_FLAG[code]
                country = COUNTRY_RU.get(flag, code)
                return flag, country
    except:
        pass
    return "🌐", "Anycast"

def rename_sni(uri):
    """Переименовываем SNI-ключи: флаг + страна + Универсальный SNI"""
    p = urlparse(uri)
    flag, country = get_flag_for_host(p.hostname)
    new_name = f"{flag} {country} - Универсальный SNI"
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, quote(new_name)))

def save_github(content):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get('sha')
    data = {'message': 'Auto update', 'content': base64.b64encode(content.encode()).decode(), 'branch': GITHUB_BRANCH}
    if sha:
        data['sha'] = sha
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in (200, 201):
        print('\n[OK] Saved to GitHub')
    else:
        print(f'\n[ERROR] {r.status_code}')

# =====================
# MAIN
# =====================
print("=" * 50)
print("SPECTER - XRAY + 204 PROVERKA")
print("=" * 50)

xray_ok = install_xray()
print(f"[XRAY] {'OK' if xray_ok else 'NO - using TCP only'}")

all_keys = []
total = 0

for src in IGARECK_SOURCES:
    print(f"\n[{src['url'].split('/')[-1]}]")
    keys = dedup(load_keys(src['url']))
    print(f"   loaded: {len(keys)}")
    total += len(keys)
    if not keys:
        continue

    # ── SNI: без проверки, берём все, переименовываем ──
    if src.get('skip_check'):
        print(f"   skip_check: добавляем все {len(keys)} ключей без проверки")
        for uri in keys:
            all_keys.append((rename_sni(uri), uri))
        continue

    # ── Остальные источники: проверка по 204 ──
    checked = check_all(keys)
    print(f"   alive: {len(checked)}/{len(keys)}")
    
    top_n = src['top_n']
    top = checked[:top_n] if top_n else checked
    if top:
        print(f"   top: {', '.join(f'{ms}ms' for _, ms in top)}")
    
    for uri, _ in top:
        all_keys.append((rename_with_country(uri, src['lte']), uri))

COUNTRY_ORDER = {
    'Германия': 1, 'Нидерланды': 2, 'Франция': 3, 'Британия': 4, 'Швейцария': 5,
    'Швеция': 6, 'Норвегия': 7, 'Дания': 8, 'Финляндия': 9, 'Бельгия': 10,
    'Австрия': 11, 'Италия': 12, 'Испания': 13, 'Португалия': 14, 'Польша': 15,
    'Чехия': 16, 'Венгрия': 17, 'Румыния': 18, 'Болгария': 19, 'Сербия': 20,
    'Хорватия': 21, 'Греция': 22, 'Литва': 23, 'Латвия': 24, 'Эстония': 25,
    'США': 30, 'Канада': 31, 'Мексика': 32,
    'Австралия': 40, 'Новая Зеландия': 41,
    'Япония': 50, 'Корея': 51, 'Сингапур': 52, 'Гонконг': 53, 'Тайвань': 54,
    'Малайзия': 55, 'Индонезия': 56, 'Таиланд': 57, 'Вьетнам': 58, 'Индия': 59,
    'ОАЭ': 70, 'Израиль': 71, 'Турция': 72, 'Саудовская Аравия': 73, 'Катар': 74,
    'Казахстан': 80, 'Украина': 81, 'Россия': 90,
    'Anycast': 999,
}

def get_key_priority(key_str):
    """0 = SNI первые, 1 = WiFi, 2 = LTE"""
    decoded = unquote(urlparse(key_str).fragment)
    if 'SNI' in decoded:
        return 0
    if 'WiFi' in decoded:
        return 1
    return 2

def extract_country_order(key_str):
    try:
        fragment = unquote(urlparse(key_str).fragment) if urlparse(key_str).fragment else ''
        for country, order in COUNTRY_ORDER.items():
            if country.lower() in fragment.lower():
                return order
        return 998
    except:
        return 998

def extract_country_name(key_str):
    """Для алфавитной сортировки внутри одной страны"""
    try:
        return unquote(urlparse(key_str).fragment)
    except:
        return ''

all_keys.sort(key=lambda x: (
    get_key_priority(x[0]),       # SNI=0, WiFi=1, LTE=2
    extract_country_order(x[0]),  # порядок страны
    extract_country_name(x[0]),   # алфавит внутри страны
))
all_keys = [k[0] for k in all_keys]

wifi = sum(1 for k in all_keys if 'WiFi' in k)
lte = sum(1 for k in all_keys if 'LTE' in k)
sni = sum(1 for k in all_keys if 'SNI' in k)

print(f"\nTOTAL: {len(all_keys)} ({wifi} WiFi, {lte} LTE, {sni} SNI)")

content = HEADER + '\n' + '\n'.join(all_keys)
save_github(content)
