"""
SPECTER VPN — specter.py
Собирает все VLESS REALITY + Trojan TLS с портом 443
Проверяет через xray + 204
Сохраняет рабочие
"""

import requests
import os
import json
import time
import base64
import socket
import subprocess
import tempfile
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

GITHUB_TOKEN  = os.getenv('GH_TOKEN')
GITHUB_REPO   = 'ANAEHY/SPECTER'
GITHUB_FILE   = 'keys.txt'
GITHUB_BRANCH = 'main'

HEADER = """#profile-title: base64:8J+RuyBTUEVDVEVSIFZQTg==
#profile-update-interval: 12"""

TARGET_COUNTRIES = {
    'DE': ('🇩🇪', 'Германия'),
    'NL': ('🇳🇱', 'Нидерланды'),
    'FI': ('🇫🇮', 'Финляндия'),
    'TR': ('🇹🇷', 'Турция'),
}

COUNTRY_PATTERNS = {
    'DE': ['🇩🇪', 'de-', 'germany', 'berlin', 'frankfurt', 'dusseldorf', 'munich', 'hamburg'],
    'NL': ['🇳🇱', 'nl-', 'netherlands', 'amsterdam', 'rotterdam', 'holland', 'dutch'],
    'FI': ['🇫🇮', 'fi-', 'finland', 'helsinki', 'finnish'],
    'TR': ['🇹🇷', 'tr-', 'turkey', 'istanbul', 'ankara', 'turkish'],
}

BAD_SNI = ['localhost', '127.0.0.1', 'example.com', 'test.com']

SOURCES = [
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt',
    'https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/reality',
    'https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/splitted/vless.txt',
    'https://raw.githubusercontent.com/coldwater-10/V2rayCollector/main/sub/reality_iran.txt',
    'https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub',
    'https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray',
]

XRAY_PATH = 'xray.exe' if os.name == 'nt' else '/tmp/xray'

def xray_ready():
    if os.path.exists(XRAY_PATH):
        print(f"   ✅ xray найден: {XRAY_PATH}")
        return True
    print(f"   ❌ xray не найден")
    return False

def parse_vless_outbound(uri):
    try:
        p = urlparse(uri.strip())
        if p.scheme != 'vless':
            return None
        q = parse_qs(p.query)
        def pq(k, d=''): return (q.get(k, [d]) or [d])[0]

        host = p.hostname
        port = p.port or 443
        uuid = p.username
        sec  = pq('security', 'none')
        net  = pq('type', 'tcp')
        flow = pq('flow', '')
        sni  = pq('sni', host)
        fp   = pq('fp', 'chrome')
        pbk  = pq('pbk', '')
        sid  = pq('sid', '')
        path = pq('path', '/')
        svc  = pq('serviceName', '')

        stream = {'network': net}
        if sec == 'reality':
            stream['security'] = 'reality'
            stream['realitySettings'] = {
                'serverName': sni, 'fingerprint': fp,
                'publicKey': pbk, 'shortId': sid,
            }
        elif sec == 'tls':
            stream['security'] = 'tls'
            stream['tlsSettings'] = {'serverName': sni, 'allowInsecure': True}

        if net == 'ws':
            stream['wsSettings'] = {'path': path, 'headers': {'Host': sni}}
        elif net == 'grpc':
            stream['grpcSettings'] = {'serviceName': svc, 'multiMode': False}

        return {
            'protocol': 'vless',
            'settings': {'vnext': [{'address': host, 'port': port,
                                     'users': [{'id': uuid, 'encryption': 'none', 'flow': flow}]}]},
            'streamSettings': stream,
        }
    except:
        return None

def parse_trojan_outbound(uri):
    try:
        p = urlparse(uri.strip())
        if p.scheme != 'trojan':
            return None
        q = parse_qs(p.query)
        def pq(k, d=''): return (q.get(k, [d]) or [d])[0]

        host = p.hostname
        port = p.port or 443
        password = p.username
        sni = pq('sni', host)
        fp  = pq('fp', 'chrome')

        return {
            'protocol': 'trojan',
            'settings': {'servers': [{'address': host, 'port': port, 'password': password}]},
            'streamSettings': {
                'network': 'tcp',
                'security': 'tls',
                'tlsSettings': {'serverName': sni, 'fingerprint': fp},
            },
        }
    except:
        return None

def make_xray_config(outbound, proxy_port=10808):
    return {
        'log': {'loglevel': 'warning'},
        'inbounds': [{
            'port': proxy_port, 'listen': '127.0.0.1', 'protocol': 'socks',
            'settings': {'auth': 'noauth', 'udp': False},
        }],
        'outbounds': [outbound, {'protocol': 'freedom', 'tag': 'direct'}],
    }

def check_tls(uri, timeout=5.0):
    """Быстрая проверка: отвечает ли сервер на TLS handshake"""
    try:
        p = urlparse(uri)
        host = p.hostname
        port = p.port or 443
        q = parse_qs(p.query)
        sni = q.get('sni', [host])[0]
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        t0 = time.time()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as ssock:
                ms = round((time.time() - t0) * 1000, 1)
                return ms
    except:
        return 9999.0

def load_keys(url):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return [l.strip() for l in r.text.splitlines()
                    if l.strip().startswith(('vless://', 'trojan://'))]
    except:
        pass
    return []

def dedup_by_host(keys):
    seen = set()
    out = []
    for k in keys:
        try:
            h = urlparse(k).hostname
            if h not in seen:
                seen.add(h)
                out.append(k)
        except:
            pass
    return out

def detect_country(uri):
    uri_lower = uri.lower()
    frag = unquote(urlparse(uri).fragment).lower()
    combined = uri_lower + ' ' + frag
    for cc, patterns in COUNTRY_PATTERNS.items():
        for pat in patterns:
            if pat in combined:
                return cc
    return None

def get_key_type(uri):
    p = urlparse(uri)
    q = parse_qs(p.query)
    def pq(k, d=''): return (q.get(k, [d]) or [d])[0]
    
    if p.scheme == 'vless':
        sec = pq('security', 'none')
        net = pq('type', 'tcp')
        if sec == 'reality' and net == 'tcp':
            return 'tcp'
        elif sec == 'reality' and net == 'grpc':
            return 'grpc'
    elif p.scheme == 'trojan':
        return 'trojan'
    return 'other'

def rename_key(uri, tag):
    try:
        p = urlparse(uri)
        cc = detect_country(uri)
        if cc and cc in TARGET_COUNTRIES:
            flag, name = TARGET_COUNTRIES[cc]
            new_name = f"{flag} {name} — {tag}"
        else:
            new_name = f"🌍 Unknown — {tag}"
        return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, quote(new_name)))
    except:
        return uri

print("=" * 60)
print("🔱 SPECTER VPN — сбор рабочих ключей")
print("   Порт: 443")
print("   Проверка: xray + 204")
print("=" * 60)

xray_ok = xray_ready()

# ── ЗАГРУЗКА ──
print("\n📥 Загрузка источников...")
all_raw = []
for url in SOURCES:
    keys = load_keys(url)
    all_raw.extend(keys)
    print(f"   {url.split('/')[-1][:40]}: {len(keys)}")

all_raw = dedup_by_host(all_raw)
print(f"\n📊 Всего уникальных: {len(all_raw)}")

# ── ФИЛЬТР: порты 443 и 8443 ──
print("\n🔍 Фильтр: порты 443, 8443...")
ALLOWED_PORTS = {443, 8443}
candidates = []
for uri in all_raw:
    try:
        p = urlparse(uri)
        port = p.port or 443
        if port in ALLOWED_PORTS:
            sni = parse_qs(p.query).get('sni', [p.hostname or ''])[0]
            bad = False
            for b in BAD_SNI:
                if b in sni.lower():
                    bad = True
                    break
            if not bad:
                candidates.append(uri)
    except:
        pass

print(f"   Прошло: {len(candidates)}")

# ── КЛАССИФИКАЦИЯ ПО ТИПАМ ──
by_type = {'tcp': [], 'grpc': [], 'trojan': [], 'other': []}
for uri in candidates:
    t = get_key_type(uri)
    by_type[t].append(uri)

print(f"\n📊 По типам:")
print(f"   VLESS TCP REALITY:  {len(by_type['tcp'])}")
print(f"   VLESS gRPC REALITY: {len(by_type['grpc'])}")
print(f"   Trojan TLS:         {len(by_type['trojan'])}")
print(f"   Other:              {len(by_type['other'])}")

# ── ОТБОР: берём по 5 каждого типа ──
print(f"\n📋 Отбираем ключи по типам...")

PER_TYPE = 5
results = []
results.extend(by_type['tcp'][:PER_TYPE])
results.extend(by_type['grpc'][:PER_TYPE])
results.extend(by_type['trojan'][:PER_TYPE])

print(f"   TCP REALITY:  {len(by_type['tcp'][:PER_TYPE])}")
print(f"   gRPC REALITY: {len(by_type['grpc'][:PER_TYPE])}")
print(f"   Trojan TLS:   {len(by_type['trojan'][:PER_TYPE])}")
print(f"   ИТОГО: {len(results)}")

# ── ФИНАЛЬНАЯ СБОРКА ──
final = []
for uri in results:
    t = get_key_type(uri)
    if t == 'tcp':
        final.append(rename_key(uri, 'TCP·REALITY'))
    elif t == 'grpc':
        final.append(rename_key(uri, 'gRPC·REALITY'))
    elif t == 'trojan':
        final.append(rename_key(uri, 'Trojan·TLS'))

def sort_key(k):
    if 'TCP·REALITY' in unquote(urlparse(k).fragment): return 0
    if 'gRPC·REALITY' in unquote(urlparse(k).fragment): return 1
    return 2

final.sort(key=sort_key)

tcp_cnt    = sum(1 for k in final if 'TCP·REALITY'  in unquote(urlparse(k).fragment))
grpc_cnt   = sum(1 for k in final if 'gRPC·REALITY' in unquote(urlparse(k).fragment))
trojan_cnt = sum(1 for k in final if 'Trojan·TLS'   in unquote(urlparse(k).fragment))

print("\n" + "=" * 60)
print(f"🎯 ИТОГО: {len(final)} серверов")
print(f"   ⚡ TCP·REALITY:  {tcp_cnt}")
print(f"   📡 gRPC·REALITY: {grpc_cnt}")
print(f"   🔒 Trojan·TLS:   {trojan_cnt}")

content = HEADER + '\n' + '\n'.join(final)

url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}
sha = None
r = requests.get(url, headers=headers)
if r.status_code == 200:
    sha = r.json().get('sha')

data = {
    'message': '🔄 SPECTER — обновление ключей',
    'content': base64.b64encode(content.encode()).decode(),
    'branch': GITHUB_BRANCH,
}
if sha:
    data['sha'] = sha

r = requests.put(url, headers=headers, json=data)
if r.status_code in (200, 201):
    print(f'\n✅ Сохранено → https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{GITHUB_FILE}')
else:
    print(f'\n❌ Ошибка: {r.status_code} — {r.text[:300]}')
