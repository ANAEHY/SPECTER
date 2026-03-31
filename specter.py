"""
SPECTER VPN - REALNAYA PROVERKA 204
Xray + GET 204 proverka dlya RF
"""

import os
import time
import json
import socket
import requests
import subprocess
import tempfile
from urllib.parse import urlparse, parse_qs, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================
# KONFIGURACIYA
# =====================
REPO_URL = 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main'
SOURCES = [
    ('BLACK_VLESS_RUS_mobile.txt', False, 8),
    ('BLACK_VLESS_RUS.txt', False, 8),
    ('Vless-Reality-White-Lists-Rus-Mobile.txt', True, 8),
    ('Vless-Reality-White-Lists-Rus-Mobile-2.txt', True, 8),
    ('WHITE-CIDR-RU-checked.txt', True, 8),
    ('WHITE-SNI-RU-all.txt', True, 8),
]

HEADER = """#profile-title: base64:8J+RuyBTUEFDVERSIFZQTg==
#profile-update-interval: 12"""

# =====================
# XRAY (standalone)
# =====================
XRAY_NAME = 'xray.exe' if os.name == 'nt' else 'xray'
XRAY_PATH = os.path.join(os.getcwd(), XRAY_NAME)

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def check_key_xray(uri, timeout=8.0):
    """Proverka cherez xray + GET 204"""
    outbound = parse_vless(uri)
    if not outbound:
        return 9999
    
    port = get_free_port()
    cfg = {
        'log': {'loglevel': 'error'},
        'inbounds': [{'port': port, 'listen': '127.0.0.1',
            'protocol': 'socks', 'settings': {'auth': 'noauth'}}],
        'outbounds': [outbound, {'protocol': 'freedom'}],
    }
    
    cfg_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(cfg, cfg_file)
    cfg_file.close()
    
    proc = None
    try:
        proc = subprocess.Popen([XRAY_PATH, 'run', '-c', cfg_file.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        try: os.unlink(cfg_file.name)
        except: pass

def check_key_tcp(uri, timeout=2.0):
    """Fallback TCP proverka"""
    try:
        p = urlparse(uri)
        t0 = time.time()
        with socket.create_connection((p.hostname, p.port or 443), timeout=timeout):
            return round((time.time() - t0) * 1000, 1)
    except:
        return 9999

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

# =====================
# MAIN LOGIKA
# =====================
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
        except: out.append(k)
    return out

def get_operator(uri):
    try:
        sni = (parse_qs(urlparse(uri).query).get('sni', [''])[0] or '').lower()
        ops = {'vk.com': 'MTC.Mega.Tele2', 'yandex.ru': 'MTC.Mega.Tele2', 'ok.ru': 'MTC.Mega', 'ozon.ru': 'MTC.Mega.Tele2', 'wildberries.ru': 'MTC.Mega.Tele2'}
        for k, v in ops.items():
            if k in sni: return v
        return 'Universal'
    except: return 'Universal'

def check_all(keys, workers=10):
    results = []
    def worker(uri):
        ms = check_key_xray(uri, 6.0)
        if ms < 9999: return uri, ms
        ms = check_key_tcp(uri, 2.0)
        return (uri, ms + 50) if ms < 9999 else (None, 9999)
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(worker, k): k for k in keys}
        for f in as_completed(futures):
            uri, ms = f.result()
            if uri and ms < 9999: results.append((uri, ms))
    results.sort(key=lambda x: x[1])
    return results

def rename(uri, lte):
    p = urlparse(uri)
    tag = f"LTE [{get_operator(uri)}]" if lte else "WiFi"
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, tag))

# =====================
# MAIN
# =====================
print("=" * 50)
print("SPECTER - PROVERKA KLUCHEY")
print("=" * 50)

all_keys, total = [], 0
for fn, lte, top_n in SOURCES:
    print(f"\n[{fn}]")
    keys = dedup(load_keys(f"{REPO_URL}/{fn}"))
    print(f"   zagruzeno: {len(keys)}")
    total += len(keys)
    if not keys: continue
    checked = check_all(keys)
    print(f"   zhivyh: {len(checked)}/{len(keys)}")
    for uri, ms in checked[:top_n]:
        all_keys.append(rename(uri, lte))
    if checked[:top_n]:
        print(f"   top: {', '.join(f'{ms}ms' for _, ms in checked[:top_n])}")

wifi = sum(1 for k in all_keys if 'WiFi' in k)
lte = sum(1 for k in all_keys if 'LTE' in k)

print(f"\nITOGO: {len(all_keys)} ({wifi} WiFi, {lte} LTE)")

with open('keys.txt', 'w', encoding='utf-8') as f:
    f.write(HEADER + '\n' + '\n'.join(all_keys))

print("\n[OK] keys.txt sohranen")
