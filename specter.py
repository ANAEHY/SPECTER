import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import os
import json
import time
import base64
import socket
import subprocess
import tempfile
import platform
import random
import re
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# =====================
# GITHUB
# =====================
GITHUB_TOKEN = os.getenv('GH_TOKEN')
GITHUB_REPO = 'ANAEHY/SPECTER'
GITHUB_FILE = 'keys.txt'
GITHUB_BRANCH = 'main'

HEADER = """#profile-title: base64:8J+RuyBTUEVDVEVSIFZQTg==
#profile-update-interval: 12"""

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
            if platform.machine().lower() in ('aarch64', 'arm64'):
                arch = 'linux-arm64-v8a'
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
# SNI → OPERATORS (2025-2026)
# =====================
SNI_OPERATORS = {
    'stats.vk-portal.net':          'МТС·Мега·Теле2·Йота·РТК',
    'sun6-21.userapi.com':          'МТС·Мега·Теле2·Йота·РТК',
    'sun6-20.userapi.com':          'МТС·Мега·Теле2·РТК',
    'sun6-22.userapi.com':          'МТС·Мега·Теле2·РТК',
    'queuev4.vk.com':               'МТС·Мега·Теле2·Йота·РТК',
    'login.vk.com':                 'МТС·Мега·Теле2·РТК',
    'eh.vk.com':                    'МТС·Мега·Теле2·Йота·РТК',
    'vk.com':                       'МТС·Мега·Теле2·Йота',
    'www.vk.com':                   'МТС·Мега·Теле2·Йота',
    'ok.ru':                        'МТС·Мега',
    'yandex.ru':                    'МТС·Мега·Теле2',
    'sba.yandex.net':               'МТС·Мега',
    'yastatic.net':                 'МТС·Мега·Теле2·РТК',
    'avatars.mds.yandex.net':       'МТС·Мега·Теле2·РТК',
    'dzen.ru':                      'Мега·Теле2',
    'www.ozon.ru':                  'МТС·Мега·Теле2',
    'st.ozone.ru':                  'МТС·Мега·Теле2·Йота·РТК',
    'www.wildberries.ru':           'МТС·Мега·Теле2·РТК',
    'alfabank.ru':                  'МТС·Мега·Теле2·Йота',
    'online.sberbank.ru':           'МТС·Мега·Теле2·РТК',
    'www.tbank.ru':                 'МТС·Мега',
    'id.tbank.ru':                  'МТС·Мега',
    '2gis.ru':                      'МТС·Мега·Теле2',
    'sntr.avito.ru':                'МТС·Мега·Теле2',
    'hh.ru':                        'МТС·Мега·Теле2',
    'rbc.ru':                       'МТС·Мега·РТК',
    'www.rbc.ru':                   'МТС·Мега·РТК',
    'lenta.ru':                     'МТС·Мега·Теле2',
    'www.t2.ru':                    'Теле2',
    'msk.t2.ru':                    'Теле2',
    'login.mts.ru':                 'МТС',
    'moscow.megafon.ru':            'Мега',
}

COUNTRY_RU = {
    "🇩🇪": "Германия",    "🇺🇸": "США",          "🇬🇧": "Великобритания",
    "🇫🇷": "Франция",     "🇳🇱": "Нидерланды",   "🇸🇬": "Сингапур",
    "🇯🇵": "Япония",      "🇰🇷": "Корея",        "🇨🇦": "Канада",
    "🇦🇺": "Австралия",   "🇷🇺": "Россия",       "🇫🇮": "Финляндия",
    "🇸🇪": "Швеция",      "🇳🇴": "Норвегия",     "🇩🇰": "Дания",
    "🇨🇭": "Швейцария",   "🇦🇹": "Австрия",      "🇧🇪": "Бельгия",
    "🇮🇪": "Ирландия",    "🇵🇱": "Польша",       "🇨🇿": "Чехия",
    "🇭🇺": "Венгрия",     "🇷🇴": "Румыния",      "🇧🇬": "Болгария",
    "🇹🇷": "Турция",      "🇮🇱": "Израиль",      "🇦🇪": "ОАЭ",
    "🇮🇳": "Индия",       "🇨🇳": "Китай",        "🇭🇰": "Гонконг",
    "🇹🇼": "Тайвань",     "🇧🇷": "Бразилия",     "🇦🇷": "Аргентина",
    "🇲🇽": "Мексика",     "🇿🇦": "ЮАР",          "🇮🇸": "Исландия",
    "🇵🇹": "Португалия",  "🇪🇸": "Испания",      "🇮🇹": "Италия",
    "🇬🇷": "Греция",      "🇲🇩": "Молдова",      "🇱🇹": "Литва",
    "🇱🇻": "Латвия",      "🇪🇪": "Эстония",      "🌐": "Anycast",
}

CODE_TO_FLAG = {
    "DE": "🇩🇪", "US": "🇺🇸", "GB": "🇬🇧", "FR": "🇫🇷", "NL": "🇳🇱",
    "SG": "🇸🇬", "JP": "🇯🇵", "KR": "🇰🇷", "CA": "🇨🇦", "AU": "🇦🇺",
    "RU": "🇷🇺", "FI": "🇫🇮", "SE": "🇸🇪", "NO": "🇳🇴", "DK": "🇩🇰",
    "CH": "🇨🇭", "AT": "🇦🇹", "BE": "🇧🇪", "IE": "🇮🇪", "PL": "🇵🇱",
    "CZ": "🇨🇿", "HU": "🇭🇺", "RO": "🇷🇴", "BG": "🇧🇬", "HR": "🇭🇷",
    "RS": "🇷🇸", "UA": "🇺🇦", "TR": "🇹🇷", "IL": "🇮🇱", "AE": "🇦🇪",
    "IN": "🇮🇳", "CN": "🇨🇳", "HK": "🇭🇰", "TW": "🇹🇼", "BR": "🇧🇷",
    "AR": "🇦🇷", "MX": "🇲🇽", "ZA": "🇿🇦", "IS": "🇮🇸", "PT": "🇵🇹",
    "ES": "🇪🇸", "IT": "🇮🇹", "GR": "🇬🇷", "MD": "🇲🇩", "LT": "🇱🇹",
    "LV": "🇱🇻", "EE": "🇪🇪",
}

BAD_PATTERNS = ['compass/cdn', 'microsoft', 'booking', 'tradingview', 'jkvpn', 'pabloping', 'hediiigate', 'oboob']

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
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt', 'lte': False, 'top_n': 8},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt', 'lte': False, 'top_n': 8},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt', 'lte': True, 'top_n': 8},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt', 'lte': True, 'top_n': 8},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt', 'lte': True, 'top_n': 8},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt', 'lte': True, 'top_n': 8},
]

def is_cloudflare(config):
    return any(p in config.lower() for p in ['cloudflare', 'cf-ip', '1.1.1.1', '104.', '172.67.', '141.193.'])

def is_bad_key(config):
    config_lower = config.lower()
    return any(p in config_lower for p in BAD_PATTERNS)

def get_sni(uri):
    try:
        q = parse_qs(urlparse(uri).query)
        return (q.get('sni', [''])[0] or q.get('host', [''])[0] or '').lower()
    except:
        return ''

def get_operators_label(sni):
    for key, ops in SNI_OPERATORS.items():
        if key in sni:
            return ops
    return 'Универсальный'

def extract_country(config):
    patterns = {
        'DE': ['de-', 'germany', 'de:', 'berlin', 'frankfurt', 'de/', '🇩🇪'],
        'NL': ['nl-', 'netherlands', 'nl:', 'amsterdam', 'rotterdam', 'nl/', '🇳🇱'],
        'FR': ['fr-', 'france', 'fr:', 'paris', 'fr/', '🇫🇷'],
        'RU': ['ru-', 'russia', 'ru:', 'moscow', 'spb', 'ru/', '🇷🇺'],
        'FI': ['fi-', 'finland', 'fi:', 'helsinki', '🇫🇮'],
        'US': ['us-', 'usa', 'us:', 'newyork', '🇺🇸'],
        'SG': ['sg-', 'singapore', 'sg:', '🇸🇬'],
        'GB': ['gb-', 'uk', 'gb:', 'london', '🇬🇧'],
        'CA': ['ca-', 'canada', 'ca:', 'toronto', '🇨🇦'],
        'SE': ['se-', 'sweden', 'se:', 'stockholm', '🇸🇪'],
        'NO': ['no-', 'norway', 'no:', 'oslo', '🇳🇴'],
        'DK': ['dk-', 'denmark', 'dk:', 'copenhagen', '🇩🇰'],
        'CH': ['ch-', 'switzerland', 'ch:', 'zurich', '🇨🇭'],
        'AT': ['at-', 'austria', 'at:', 'vienna', '🇦🇹'],
        'JP': ['jp-', 'japan', 'jp:', 'tokyo', '🇯🇵']
    }
    config_lower = config.lower()
    for country, pats in patterns.items():
        if any(pat in config_lower for pat in pats):
            return country
    return 'OTHER'

def get_flag_and_country(fragment: str):
    decoded = unquote(fragment)
    flag_match = re.search(r'([\U0001F1E0-\U0001F1FF]{2}|\U0001F310)', decoded)
    if flag_match:
        flag = flag_match.group(1)
        if flag in COUNTRY_RU:
            return flag, COUNTRY_RU[flag]
    return "🌐", "Сервер"

def rename_key(line: str, label: str) -> str:
    line = line.strip()
    if not line or line.startswith('#'):
        return line
    try:
        parsed = urlparse(line)
        flag, country = get_flag_and_country(parsed.fragment)
        if country == "Сервер":
            country_code = extract_country(line)
            if country_code in CODE_TO_FLAG:
                flag = CODE_TO_FLAG[country_code]
                country = COUNTRY_RU.get(flag, "Сервер")
        new_name = f"{flag} {country} - {label}"
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, quote(new_name)))
    except:
        return line

def rename_lte_key(line: str) -> str:
    line = line.strip()
    if not line or line.startswith('#'):
        return line
    try:
        parsed = urlparse(line)
        flag, country = get_flag_and_country(parsed.fragment)
        if country == "Сервер":
            country_code = extract_country(line)
            if country_code in CODE_TO_FLAG:
                flag = CODE_TO_FLAG[country_code]
                country = COUNTRY_RU.get(flag, "Сервер")
        sni = get_sni(line)
        ops = get_operators_label(sni)
        new_name = f"{flag} {country} - LTE [{ops}]"
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, quote(new_name)))
    except:
        return line

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

def save_github(content):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get('sha')
    data = {'message': '🔄 Обновление ключей SPECTER VPN', 'content': base64.b64encode(content.encode()).decode(), 'branch': GITHUB_BRANCH}
    if sha:
        data['sha'] = sha
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in (200, 201):
        print('\n[OK] Saved to GitHub')
    else:
        print(f'\n[ERROR] {r.status_code}: {r.text[:100]}')

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
    
    checked = check_all(keys)
    print(f"   alive: {len(checked)}/{len(keys)}")
    
    top = checked[:src['top_n']]
    if top:
        print(f"   top: {', '.join(f'{ms}ms' for _, ms in top)}")
    
    for uri, _ in top:
        if src['lte']:
            all_keys.append(rename_lte_key(uri))
        else:
            all_keys.append(rename_key(uri, "WiFi"))

wifi = sum(1 for k in all_keys if 'WiFi' in k)
lte = sum(1 for k in all_keys if 'LTE' in k)

print(f"\nTOTAL: {len(all_keys)} ({wifi} WiFi, {lte} LTE)")

ops_stat = defaultdict(int)
for line in all_keys:
    if 'LTE' in line:
        sni = get_sni(line)
        ops = get_operators_label(sni)
        ops_stat[ops] += 1

print(f"\n[LTE Operators]:")
for ops, count in sorted(ops_stat.items(), key=lambda x: -x[1]):
    print(f"   {ops}: {count}")

content = HEADER + '\n' + '\n'.join(all_keys)
save_github(content)
