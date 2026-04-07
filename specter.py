#!/usr/bin/env python3
"""
SPECTER VPN — April 2026 Edition
Фильтр: Работающие ключи в РФ
Страны: DE / NL / FI / TR
Протоколы: VLESS TCP REALITY, VLESS gRPC REALITY, Trojan TLS
"""

import requests
import os
import json
import time
import base64
import socket
import subprocess
import tempfile
import re
import ssl
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

GITHUB_TOKEN = os.getenv('GH_TOKEN')
GITHUB_REPO = 'ANAEHY/SPECTER'
GITHUB_FILE = 'keys.txt'
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
    'DE': ['de-', 'germany', 'berlin', 'frankfurt', 'dusseldorf', 'munich', 'hamburg', 'deutsch'],
    'NL': ['nl-', 'netherlands', 'amsterdam', 'rotterdam', 'holland', 'dutch'],
    'FI': ['fi-', 'finland', 'helsinki', 'finnish'],
    'TR': ['tr-', 'turkey', 'istanbul', 'ankara', 'turkish'],
}

GOOD_SNI = [
    'microsoft.com', 'apple.com', 'amazon.com', 'cloudflare.com',
    'google.com', 'youtube.com', 'discord.com', 'whatsapp.com',
    'telegram.org', 'yahoo.com', 'github.com', 'bbc.com', 'ft.com',
    'spiegel.de', 'bild.de', 'focus.de', 'zeit.de', 'dw.com',
    'nu.nl', 'tweakers.net', 'yle.fi', 'hs.fi',
    'hurriyet.com.tr', 'sabah.com.tr', 'milliyet.com.tr', 'ensonhaber.com',
]

BAD_SNI = [
    'localhost', '127.0.0.1', 'example.com', 'test.com',
    'xray', 'v2ray', 'clash', 'sing-box', 'nekobox',
    'jkvpn', 'pabloping', 'oboob', 'hediiigate',
]

SOURCES = [
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt',
    'https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/reality',
    'https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/splitted/vless.txt',
    'https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub',
]

@dataclass
class KeyInfo:
    uri: str
    scheme: str
    host: str
    port: int
    country: Optional[str]
    network: str
    security: str
    flow: str
    sni: str
    quality_score: int

def load_keys(url: str) -> list:
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            lines = r.text.strip().split('\n')
            return [l.strip() for l in lines if l.strip() and not l.startswith('#')]
    except:
        pass
    return []

def parse_key(uri: str) -> Optional[KeyInfo]:
    try:
        p = urlparse(uri.strip())
        if p.scheme not in ('vless', 'trojan'):
            return None
        
        q = parse_qs(p.query)
        
        host = p.hostname or ''
        port = p.port or 443
        
        if p.scheme == 'vless':
            security = q.get('security', ['none'])[0]
            network = q.get('type', ['tcp'])[0]
            flow = q.get('flow', [''])[0]
            sni = q.get('sni', [host])[0]
        else:  # trojan
            security = q.get('security', ['tls'])[0]
            network = q.get('type', ['tcp'])[0]
            flow = ''
            sni = q.get('sni', [host])[0]
        
        return KeyInfo(
            uri=uri, scheme=p.scheme, host=host, port=port,
            country=None, network=network, security=security,
            flow=flow, sni=sni, quality_score=0
        )
    except:
        return None

def detect_country(uri: str) -> Optional[str]:
    uri_lower = uri.lower()
    for cc, patterns in COUNTRY_PATTERNS.items():
        for pat in patterns:
            if pat in uri_lower:
                return cc
    return None

def calc_quality(ki: KeyInfo) -> int:
    score = 0
    
    if ki.port == 443:
        score += 30
    
    if ki.scheme == 'vless' and ki.security == 'reality':
        score += 25
    elif ki.scheme == 'trojan' and ki.security in ('tls', 'reality'):
        score += 20
    
    if ki.network in ('tcp', 'grpc'):
        score += 15
    
    sni_lower = ki.sni.lower()
    for good in GOOD_SNI:
        if good in sni_lower:
            score += 20
            break
    
    for bad in BAD_SNI:
        if bad in sni_lower:
            score -= 30
            break
    
    if ki.flow == 'xtls-rprx-vision':
        score += 10
    
    return max(0, score)

def check_connectivity(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def check_tls_handshake(host: str, port: int, timeout: float = 4.0) -> bool:
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                return ssock.do_handshake() is None
    except:
        return False

def check_http_response(host: str, port: int, path: str = '/', timeout: float = 5.0) -> int:
    try:
        import http.client
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request('GET', path, headers={'Host': 'www.google.com', 'User-Agent': 'Mozilla/5.0'})
        resp = conn.getresponse()
        conn.close()
        return resp.status
    except:
        return 0

print("=" * 65)
print("🔱 SPECTER VPN — АПРЕЛЬ 2026")
print("   Страны: 🇩🇪 DE / 🇳🇱 NL / 🇫🇮 FI / 🇹🇷 TR")
print("   Цель: Работающие ключи в РФ")
print("=" * 65)

print("\n📥 Загрузка источников...")
all_keys = []
for url in SOURCES:
    keys = load_keys(url)
    count = len(keys)
    all_keys.extend(keys)
    name = url.split('/')[-1][:35]
    print(f"   {name}: {count}")

print(f"\n📊 Всего загружено: {len(all_keys)}")

print("\n🔍 Этап 1: Парсинг и базовая фильтрация...")
parsed = []
for uri in all_keys:
    ki = parse_key(uri)
    if not ki:
        continue
    
    if ki.port != 443:
        continue
    
    ki.quality_score = calc_quality(ki)
    if ki.quality_score < 20:
        continue
    
    parsed.append(ki)

print(f"   После фильтрации: {len(parsed)}")

print("\n🗺️  Этап 2: Определение стран...")
for ki in parsed:
    if not ki.country:
        ki.country = detect_country(ki.uri)

country_stats = {}
for ki in parsed:
    if ki.country in TARGET_COUNTRIES:
        country_stats[ki.country] = country_stats.get(ki.country, 0) + 1

for cc, name in TARGET_COUNTRIES.items():
    flag, cname = TARGET_COUNTRIES[cc]
    print(f"   {flag} {cname}: {country_stats.get(cc, 0)}")

candidates = [ki for ki in parsed if ki.country in TARGET_COUNTRIES]
print(f"\n🎯 Кандидатов: {len(candidates)}")

print("\n🔬 Этап 3: Проверка работающих в РФ...")
print("   Метод: TLS handshake + HTTP response\n")

def verify_key(ki: KeyInfo) -> Optional[KeyInfo]:
    host, port = ki.host, ki.port
    
    t1 = check_connectivity(host, port, timeout=3.0)
    if not t1:
        return None
    
    if ki.security in ('tls', 'reality'):
        t2 = check_tls_handshake(host, port, timeout=4.0)
        if not t2:
            return None
    
    return ki

MAX_CHECK = 80
to_check = candidates[:MAX_CHECK]
print(f"   Проверяем {len(to_check)} ключей...\n")

working = []
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(verify_key, ki): ki for ki in to_check}
    done = 0
    for future in as_completed(futures):
        done += 1
        result = future.result()
        if result:
            working.append(result)
        if done % 15 == 0 or done == len(to_check):
            print(f"      [{done}/{len(to_check)}] рабочих: {len(working)}", flush=True)

print(f"\n✅ Рабочих: {len(working)}/{len(to_check)}")

by_type = {'tcp': [], 'grpc': [], 'trojan': []}
for ki in working:
    if ki.scheme == 'vless' and ki.network == 'tcp' and ki.security == 'reality':
        by_type['tcp'].append(ki)
    elif ki.scheme == 'vless' and ki.network == 'grpc' and ki.security == 'reality':
        by_type['grpc'].append(ki)
    elif ki.scheme == 'trojan':
        by_type['trojan'].append(ki)

by_type['tcp'].sort(key=lambda x: -x.quality_score)
by_type['grpc'].sort(key=lambda x: -x.quality_score)
by_type['trojan'].sort(key=lambda x: -x.quality_score)

print("\n📊 По типам:")
print(f"   ⚡ VLESS TCP REALITY: {len(by_type['tcp'])}")
print(f"   📡 VLESS gRPC REALITY: {len(by_type['grpc'])}")
print(f"   🔒 Trojan TLS: {len(by_type['trojan'])}")

final = []
PER_TYPE = 3

for ki in by_type['tcp'][:PER_TYPE]:
    final.append(ki)
for ki in by_type['grpc'][:PER_TYPE]:
    final.append(ki)
for ki in by_type['trojan'][:PER_TYPE]:
    final.append(ki)

def make_sub_link(ki: KeyInfo) -> str:
    frag = f"{ki.country} {TARGET_COUNTRIES[ki.country][1]} — "
    if ki.scheme == 'vless' and ki.network == 'tcp' and ki.security == 'reality':
        frag += "TCP·REALITY"
    elif ki.scheme == 'vless' and ki.network == 'grpc' and ki.security == 'reality':
        frag += "gRPC·REALITY"
    else:
        frag += "Trojan·TLS"
    
    return urlunparse((
        urlparse(ki.uri)._replace(fragment=quote(frag))
    ))

final_uris = [make_sub_link(ki) for ki in final]

def sort_uri(u):
    if 'TCP·REALITY' in u: return 0
    if 'gRPC·REALITY' in u: return 1
    return 2

final_uris.sort(key=sort_uri)

tcp_cnt = sum(1 for u in final_uris if 'TCP·REALITY' in u)
grpc_cnt = sum(1 for u in final_uris if 'gRPC·REALITY' in u)
trojan_cnt = sum(1 for u in final_uris if 'Trojan·TLS' in u)

print("\n" + "=" * 65)
print(f"🎯 ИТОГО: {len(final_uris)} серверов")
print(f"   ⚡ TCP·REALITY:  {tcp_cnt}")
print(f"   📡 gRPC·REALITY: {grpc_cnt}")
print(f"   🔒 Trojan·TLS:   {trojan_cnt}")
print("=" * 65)

if not final_uris:
    print("\n❌ Нет рабочих ключей!")
    sys.exit(0)

content = HEADER + '\n' + '\n'.join(final_uris)

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
    'message': '🔄 SPECTER — обновление ключей (апрель 2026)',
    'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
    'branch': GITHUB_BRANCH,
}
if sha:
    data['sha'] = sha

r = requests.put(url, headers=headers, json=data)
if r.status_code in (200, 201):
    print(f"\n✅ Сохранено → https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{GITHUB_FILE}")
else:
    print(f"\n❌ Ошибка: {r.status_code}")
