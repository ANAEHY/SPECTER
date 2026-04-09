# -*- coding: utf-8 -*-
import sys, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import json
import time
import base64
import socket
import subprocess
import tempfile
import re
import statistics
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================
# GITHUB
# =====================
GITHUB_TOKEN  = os.getenv('GH_TOKEN')
GITHUB_REPO   = 'ANAEHY/SPECTER'
GITHUB_FILE   = 'keys.txt'
GITHUB_BRANCH = 'main'

HEADER = """#profile-title: base64:8J+RuyBTUEFDVEVSIFZQTg==
#profile-update-interval: 12"""

# =====================
# COUNTRY MAPS
# =====================
COUNTRY_RU = {
    "DE": "Germany", "FR": "France",  "NL": "Netherlands", "IT": "Italy",
    "ES": "Spain",   "PL": "Poland",  "BE": "Belgium",     "AT": "Austria",
    "CH": "Swiss",   "SE": "Sweden",  "NO": "Norway",      "DK": "Denmark",
    "FI": "Finland", "GB": "Britain", "US": "USA",         "CA": "Canada",
    "AU": "Australia","JP": "Japan",  "KR": "Korea",       "SG": "Singapore",
    "RU": "Russia",  "UA": "Ukraine", "TR": "Turkey",      "IL": "Israel",
    "AE": "UAE",     "IN": "India",   "BR": "Brazil",
}

FLAG_MAP = {
    "DE": "DE", "FR": "FR", "NL": "NL", "IT": "IT", "ES": "ES",
    "PL": "PL", "BE": "BE", "AT": "AT", "CH": "CH", "SE": "SE",
    "NO": "NO", "DK": "DK", "FI": "FI", "GB": "GB", "US": "US",
    "CA": "CA", "AU": "AU", "JP": "JP", "KR": "KR", "SG": "SG",
    "RU": "RU", "UA": "UA", "TR": "TR", "IL": "IL", "AE": "AE",
    "IN": "IN", "BR": "BR",
}

# =====================
# XRAY
# =====================
XRAY_PATH = 'xray.exe' if os.name == 'nt' else '/tmp/xray'

def install_xray() -> bool:
    if os.path.exists(XRAY_PATH):
        return True
    try:
        if os.name == 'nt':
            url = 'https://github.com/XTLS/Xray-core/releases/download/v1.8.6/Xray-windows-64.zip'
            r = requests.get(url, timeout=60, stream=True)
            with open('xray.zip', 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            import zipfile
            with zipfile.ZipFile('xray.zip') as z: z.extractall('.')
            os.remove('xray.zip')
        else:
            r   = requests.get('https://api.github.com/repos/XTLS/Xray-core/releases/latest', timeout=15)
            ver = r.json()['tag_name']
            url = f'https://github.com/XTLS/Xray-core/releases/download/{ver}/Xray-linux-64.zip'
            r   = requests.get(url, timeout=60, stream=True)
            with open('/tmp/xray.zip', 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            import zipfile
            with zipfile.ZipFile('/tmp/xray.zip') as z: z.extract('xray', '/tmp/')
            os.chmod(XRAY_PATH, 0o755)
            os.remove('/tmp/xray.zip')
        return True
    except Exception as e:
        print(f"[XRAY install error] {e}")
        return False

# =====================
# PROTOCOL PRIORITY
# Чем меньше число - тем лучше для РФ
# =====================
PROTO_PRIORITY = {
    'reality': 0,   # лучший для РФ
    'tls_ws':  1,   # websocket tls
    'tls':     2,   # обычный tls
    'ws':      3,   # ws без tls
    'grpc':    4,
    'other':   9,
}

def get_proto_priority(uri: str) -> int:
    try:
        q   = parse_qs(urlparse(uri).query)
        sec = q.get('security', ['none'])[0].lower()
        net = q.get('type',     ['tcp'])[0].lower()
        if sec == 'reality':
            return PROTO_PRIORITY['reality']
        if sec == 'tls' and net == 'ws':
            return PROTO_PRIORITY['tls_ws']
        if sec == 'tls':
            return PROTO_PRIORITY['tls']
        if net == 'ws':
            return PROTO_PRIORITY['ws']
        if net == 'grpc':
            return PROTO_PRIORITY['grpc']
        return PROTO_PRIORITY['other']
    except Exception:
        return PROTO_PRIORITY['other']

def proto_label(uri: str) -> str:
    try:
        q   = parse_qs(urlparse(uri).query)
        sec = q.get('security', ['none'])[0].lower()
        net = q.get('type',     ['tcp'])[0].lower()
        return f"{sec}/{net}"
    except Exception:
        return "?"

# =====================
# COUNTRY DETECTION
# =====================
def extract_country(uri: str) -> str:
    patterns = {
        'DE': ['de-','germany','berlin','frankfurt'],
        'FR': ['fr-','france','paris'],
        'NL': ['nl-','netherlands','amsterdam','rotterdam'],
        'IT': ['it-','italy','rome','milan'],
        'ES': ['es-','spain','madrid'],
        'PL': ['pl-','poland','warsaw'],
        'GB': ['gb-','uk','london','britain','england'],
        'US': ['us-','usa','new york','nyc'],
        'CA': ['ca-','canada','toronto'],
        'JP': ['jp-','japan','tokyo'],
        'RU': ['ru-','russia','moscow','spb'],
        'NL': ['nl-','netherlands','amsterdam'],
        'SE': ['se-','sweden','stockholm'],
        'FI': ['fi-','finland','helsinki'],
        'NO': ['no-','norway','oslo'],
    }
    text = uri.lower()
    for code, pats in patterns.items():
        if any(p in text for p in pats):
            return code
    return 'XX'

def get_country_label(uri: str) -> str:
    code = extract_country(uri)
    name = COUNTRY_RU.get(code, 'Unknown')
    return f"[{code}] {name}"

# =====================
# VLESS PARSING
# =====================
def parse_vless(uri: str) -> dict | None:
    try:
        p    = urlparse(uri)
        q    = parse_qs(p.query)
        h    = p.hostname
        pt   = p.port or 443
        u    = p.username
        sec  = q.get('security',    ['none'])[0]
        net  = q.get('type',        ['tcp'])[0]
        flow = q.get('flow',        [''])[0]
        sni  = q.get('sni',         [h])[0]
        fp   = q.get('fp',          ['chrome'])[0]
        pbk  = q.get('pbk',         [''])[0]
        sid  = q.get('sid',         [''])[0]
        path = q.get('path',        ['/'])[0]
        svc  = q.get('serviceName', [''])[0]

        stream = {'network': net}
        if sec == 'reality':
            stream['security'] = 'reality'
            stream['realitySettings'] = {
                'serverName': sni, 'fingerprint': fp,
                'publicKey': pbk,  'shortId': sid,
            }
        elif sec == 'tls':
            stream['security'] = 'tls'
            stream['tlsSettings'] = {'serverName': sni, 'allowInsecure': True}

        if net == 'ws':
            stream['wsSettings']   = {'path': path}
        elif net == 'grpc':
            stream['grpcSettings'] = {'serviceName': svc, 'multiMode': False}
        elif net == 'tcp':
            stream['tcpSettings']  = {}

        return {
            'protocol': 'vless',
            'settings': {
                'vnext': [{
                    'address': h, 'port': pt,
                    'users':   [{'id': u, 'encryption': 'none', 'flow': flow}],
                }]
            },
            'streamSettings': stream,
        }
    except Exception:
        return None

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

# =====================
# XRAY 204 CHECK
# =====================
GENERATE_204_URLS = [
    'https://www.gstatic.com/generate_204',
    'https://www.google.com/generate_204',
    'https://cp.cloudflare.com/generate_204',
]

def check_xray_204(uri: str, timeout: float = 6.0) -> float:
    """
    Полная проверка через xray + GET 204.
    Возвращает avg latency ms или 9999.
    """
    outbound = parse_vless(uri)
    if not outbound:
        return 9999

    port = get_free_port()
    cfg  = {
        'log':       {'loglevel': 'none'},
        'inbounds':  [{'port': port, 'listen': '127.0.0.1',
                       'protocol': 'socks',
                       'settings': {'auth': 'noauth', 'udp': True}}],
        'outbounds': [outbound, {'protocol': 'freedom', 'tag': 'direct'}],
    }

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(cfg, tmp); tmp.close()

    err_log = tempfile.NamedTemporaryFile(
        mode='w', suffix='.err', delete=False, encoding='utf-8')
    err_log.close()

    proc = None
    try:
        proc = subprocess.Popen(
            [XRAY_PATH, 'run', '-c', tmp.name],
            stdout=subprocess.DEVNULL,
            stderr=open(err_log.name, 'w', encoding='utf-8'),
        )

        # Ждём реального поднятия порта (до 4 сек)
        deadline = time.time() + 4.0
        port_up  = False
        while time.time() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    port_up = True; break
            except OSError:
                time.sleep(0.1)

        if not port_up:
            return 9999

        proxies = {
            'http':  f'socks5h://127.0.0.1:{port}',
            'https': f'socks5h://127.0.0.1:{port}',
        }

        # Параллельно шлём 3 запроса generate_204
        latencies = []

        def fetch_204(url):
            try:
                t0 = time.time()
                r  = requests.get(url, proxies=proxies,
                                  timeout=timeout, allow_redirects=False)
                ms = round((time.time() - t0) * 1000, 1)
                return ms if r.status_code == 204 else None
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=3) as ex:
            for f in as_completed([ex.submit(fetch_204, u) for u in GENERATE_204_URLS]):
                r = f.result()
                if r is not None:
                    latencies.append(r)

        if len(latencies) < 1:
            return 9999

        return round(statistics.mean(latencies), 1)

    except Exception:
        return 9999
    finally:
        if proc:
            try: proc.kill(); proc.wait(timeout=2)
            except Exception: pass
        try: os.unlink(tmp.name)
        except Exception: pass
        try: os.unlink(err_log.name)
        except Exception: pass

# =====================
# TCP FALLBACK CHECK
# =====================
def check_tcp(uri: str, timeout: float = 3.0) -> float:
    """TCP connect fallback если xray недоступен."""
    try:
        p    = urlparse(uri)
        host = p.hostname
        port = p.port or 443
        t0   = time.time()
        with socket.create_connection((host, port), timeout=timeout):
            rtt = round((time.time() - t0) * 1000, 1)
        if rtt > 600:
            return 9999
        return rtt
    except Exception:
        return 9999

# =====================
# UNIFIED CHECK
# =====================
def check_one(uri: str, use_xray: bool) -> float:
    """
    Если xray есть - проверяем через 204.
    Иначе - TCP connect.
    """
    host = urlparse(uri).hostname or '?'
    proto = proto_label(uri)

    if use_xray:
        ms = check_xray_204(uri)
        if ms < 9999:
            print(f"      [OK 204] {host} {proto} {ms:.0f}ms")
            return ms
        else:
            print(f"      [DEAD]   {host} {proto}")
            return 9999
    else:
        ms = check_tcp(uri)
        if ms < 9999:
            print(f"      [OK TCP] {host} {proto} {ms:.0f}ms")
            return ms
        else:
            print(f"      [DEAD]   {host} {proto}")
            return 9999

# =====================
# CHECK ALL KEYS
# =====================
def check_all(keys: list[str], use_xray: bool, workers: int = 10) -> list[tuple[str, float]]:
    """
    Проверяем ВСЕ ключи без ограничений.
    Сортировка: сначала priority протокола, потом latency.
    """
    results = []

    def worker(uri):
        ms = check_one(uri, use_xray)
        return (uri, ms) if ms < 9999 else (None, 9999)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(worker, k): k for k in keys}
        done = alive = 0
        for future in as_completed(futures):
            uri, ms = future.result()
            done += 1
            if uri:
                results.append((uri, ms))
                alive += 1
            if done % 25 == 0 or done == len(keys):
                print(f"   [{done}/{len(keys)}] alive: {alive}", flush=True)

    # Сортировка: сначала по приоритету протокола, потом по latency
    results.sort(key=lambda x: (get_proto_priority(x[0]), x[1]))
    return results

# =====================
# SOURCES
# =====================
IGARECK_SOURCES = [
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt',               'lte': False, 'top_n': 10},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt',                      'lte': False, 'top_n': 10},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt',  'lte': True,  'top_n': 10},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt','lte': True,  'top_n': 10},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt',                'lte': True,  'top_n': 10},
    {'url': 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt',                     'lte': True,  'top_n': 10},
]

def load_keys(url: str) -> list[str]:
    try:
        r = requests.get(url, timeout=15)
        # берём ВСЕ vless:// строки без ограничений
        return [l.strip() for l in r.text.splitlines()
                if l.strip().startswith('vless://')]
    except Exception:
        return []

def dedup(keys: list[str]) -> list[str]:
    """Дедупликация по host:port."""
    seen, out = set(), []
    for k in keys:
        try:
            p   = urlparse(k)
            key = f"{p.hostname}:{p.port}"
            if key not in seen:
                seen.add(key); out.append(k)
        except Exception:
            out.append(k)
    return out

def rename_key(uri: str, lte: bool) -> str:
    p      = urlparse(uri)
    code   = extract_country(uri)
    name   = COUNTRY_RU.get(code, 'Unknown')
    proto  = proto_label(uri)
    tag    = "LTE" if lte else "WiFi"
    label  = f"[{code}] {name} {proto} - {tag}"
    return urlunparse((p.scheme, p.netloc, p.path, p.params,
                       p.query, quote(label)))

# =====================
# GITHUB SAVE
# =====================
def save_github(content: str):
    if not GITHUB_TOKEN:
        print("[SKIP] GH_TOKEN not set")
        return
    url     = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}',
               'Accept': 'application/vnd.github.v3+json'}
    sha = None
    r   = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get('sha')
    data = {'message': 'Auto update',
            'content': base64.b64encode(content.encode()).decode(),
            'branch':  GITHUB_BRANCH}
    if sha:
        data['sha'] = sha
    r = requests.put(url, headers=headers, json=data)
    print('[OK] Saved to GitHub' if r.status_code in (200, 201)
          else f'[ERROR] GitHub {r.status_code}: {r.text[:200]}')

# =====================
# SORT ORDER
# =====================
COUNTRY_ORDER = {
    'DE':1,  'NL':2,  'FR':3,  'IT':4,  'ES':5,
    'PL':6,  'GB':7,  'US':8,  'CA':9,  'AU':10,
    'JP':11, 'KR':12, 'RU':13, 'XX':99,
}

def final_sort_key(uri: str) -> tuple:
    proto_p   = get_proto_priority(uri)
    country_p = COUNTRY_ORDER.get(extract_country(uri), 50)
    return (proto_p, country_p)

# =====================
# MAIN
# =====================
def main():
    print("=" * 55)
    print("  SPECTER - ALL KEYS CHECK + PROTOCOL SORT")
    print("=" * 55)
    print("  Priority: reality > tls/ws > tls > ws > grpc")
    print("=" * 55)

    use_xray = install_xray()
    mode = "xray+204" if use_xray else "TCP only"
    print(f"\n[MODE] {mode}\n")

    all_results = []   # (renamed_uri, proto_priority)

    for src in IGARECK_SOURCES:
        name = src['url'].split('/')[-1]
        print(f"\n{'='*55}")
        print(f"[{name}]")

        # Грузим ВСЕ ключи
        raw = dedup(load_keys(src['url']))
        print(f"   total keys: {len(raw)}")

        if not raw:
            print("   -> skip (empty)")
            continue

        # Проверяем ВСЕ
        checked = check_all(raw, use_xray, workers=10)
        print(f"   alive: {len(checked)}/{len(raw)}")

        # Берём топ N
        top = checked[:src['top_n']]
        if top:
            protos = [proto_label(u) for u, _ in top]
            print(f"   top protos: {', '.join(protos)}")
            lats   = [f"{ms:.0f}" for _, ms in top]
            print(f"   top ms:     {', '.join(lats)}")

        for uri, ms in top:
            renamed = rename_key(uri, src['lte'])
            all_results.append((renamed, get_proto_priority(uri)))

    print(f"\n{'='*55}")

    # Финальная сортировка: reality первые, потом остальные
    all_results.sort(key=lambda x: (x[1], final_sort_key(x[0])))
    final_keys = [r[0] for r in all_results]

    # Статистика по протоколам
    proto_stats: dict[str, int] = {}
    for uri, _ in all_results:
        pl = proto_label(uri)
        proto_stats[pl] = proto_stats.get(pl, 0) + 1

    print(f"TOTAL: {len(final_keys)} keys")
    for proto, cnt in sorted(proto_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {proto}: {cnt}")

    if not final_keys:
        print("[WARN] No alive keys")
        return

    content = HEADER + '\n' + '\n'.join(final_keys)
    save_github(content)

if __name__ == '__main__':
    main()
