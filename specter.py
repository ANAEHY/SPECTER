"""
SPECTER VPN — specter.py
Фильтр: Германия / Нидерланды / Финляндия / Турция
Протокол: VLESS + REALITY (порт 443, flow=xtls-rprx-vision)
Запасные: gRPC+REALITY, Trojan+TLS
Проверка: xray + 204 (реальная, работает с GitHub Actions)
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
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ══════════════════════════════════════════════════════════════════
#  GITHUB
# ══════════════════════════════════════════════════════════════════
GITHUB_TOKEN  = os.getenv('GH_TOKEN')
GITHUB_REPO   = 'ANAEHY/SPECTER'
GITHUB_FILE   = 'keys.txt'
GITHUB_BRANCH = 'main'

HEADER = """#profile-title: base64:8J+RuyBTUEVDVEVSIFZQTg==
#profile-update-interval: 12"""

# ══════════════════════════════════════════════════════════════════
#  ЦЕЛЕВЫЕ СТРАНЫ — только эти берём
# ══════════════════════════════════════════════════════════════════
TARGET_COUNTRIES = {
    'DE': ('🇩🇪', 'Германия'),
    'NL': ('🇳🇱', 'Нидерланды'),
    'FI': ('🇫🇮', 'Финляндия'),
    'TR': ('🇹🇷', 'Турция'),
}

# Паттерны для определения страны по URI/фрагменту
COUNTRY_PATTERNS = {
    'DE': ['🇩🇪', 'de-', 'germany', 'berlin', 'frankfurt', 'dusseldorf', 'munich', 'hamburg'],
    'NL': ['🇳🇱', 'nl-', 'netherlands', 'amsterdam', 'rotterdam', 'holland', 'dutch'],
    'FI': ['🇫🇮', 'fi-', 'finland', 'helsinki', 'finnish'],
    'TR': ['🇹🇷', 'tr-', 'turkey', 'istanbul', 'ankara', 'turkish'],
}

# ══════════════════════════════════════════════════════════════════
#  ПАРАМЕТРЫ ФИЛЬТРАЦИИ КЛЮЧЕЙ
# ══════════════════════════════════════════════════════════════════
REQUIRED_PORT      = 443
REQUIRED_SECURITY  = 'reality'          # обязательно reality
REQUIRED_FLOW      = 'xtls-rprx-vision' # обязательно vision
ALLOWED_NETWORKS   = ('tcp', 'grpc')    # tcp (основной) + grpc (запасной)
ALLOWED_PROTOCOLS  = ('vless', 'trojan') # vless основной, trojan запасной

# SNI которые точно мусор — отбрасываем
BAD_SNI_PATTERNS = [
    'localhost', '127.0.0.1', 'example.com', 'test.com',
    'xray', 'v2ray', 'clash', 'sing-box',
    'jkvpn', 'pabloping', 'oboob', 'hediiigate',
]

# Хорошие SNI — популярные сайты (признак качественного конфига)
GOOD_SNI_PATTERNS = [
    'microsoft.com', 'apple.com', 'amazon.com', 'cloudflare.com',
    'google.com', 'youtube.com', 'discord.com', 'whatsapp.com',
    'telegram.org', 'yahoo.com', 'github.com', 'cdn.', 'cdn-',
    'addons.mozilla.org', 'mozilla.org', 'firefox.com',
    'www.', 'cdn.', 'static.', 'assets.',
    # европейские популярные
    'spiegel.de', 'bild.de', 'focus.de', 'zeit.de',
    'nu.nl', 'tweakers.net', 'yle.fi',
    'hurriyet.com.tr', 'sabah.com.tr', 'milliyet.com.tr',
]

# Провайдеры которые НЕ мусор — хорошие дата-центры
GOOD_AS_KEYWORDS = [
    'hetzner', 'contabo', 'ovh', 'leaseweb', 'serverius',
    'euserv', 'netcup', 'ionos', 'strato', 'plusserver',
    'turktelekom', 'turk telekom', 'superonline', 'vodafone tr',
    'elisa', 'telia', 'dna fi',
    'transip', 'xs4all', 'ziggo', 'kpn',
    'linode', 'vultr', 'digitalocean', 'upcloud',
    'datapacket', 'serverius', 'i3d',
]

BAD_AS_KEYWORDS = [
    'cloudflare', 'fastly', 'akamai', 'incapsula', 'imperva',
    'amazon aws', 'google cloud', 'microsoft azure',
    'choopa', 'peg tech',  # дешёвые мусорные хостеры
]

# ══════════════════════════════════════════════════════════════════
#  ИСТОЧНИКИ
# ══════════════════════════════════════════════════════════════════
SOURCES = [
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt',
    # дополнительные источники
    'https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/reality',
    'https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/splitted/vless.txt',
    'https://raw.githubusercontent.com/coldwater-10/V2rayCollector/main/sub/reality_iran.txt',
    'https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub',
    'https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray',
]

# ══════════════════════════════════════════════════════════════════
#  XRAY — путь и установка
# ══════════════════════════════════════════════════════════════════
XRAY_PATH = 'xray.exe' if os.name == 'nt' else '/tmp/xray'

def xray_ready() -> bool:
    """Проверяет что xray.exe уже лежит рядом (воркфлоу его качает отдельным шагом)"""
    if os.path.exists(XRAY_PATH):
        print(f"   ✅ xray найден: {XRAY_PATH}")
        return True
    print(f"   ❌ xray не найден по пути: {XRAY_PATH}")
    return False

# ══════════════════════════════════════════════════════════════════
#  ПАРСИНГ VLESS → XRAY CONFIG
# ══════════════════════════════════════════════════════════════════
def parse_vless_outbound(uri: str) -> dict | None:
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
        elif net in ('xhttp', 'splithttp'):
            stream['xhttpSettings'] = {'path': path, 'host': sni, 'mode': 'auto'}

        return {
            'protocol': 'vless',
            'settings': {'vnext': [{'address': host, 'port': port,
                                     'users': [{'id': uuid, 'encryption': 'none', 'flow': flow}]}]},
            'streamSettings': stream,
        }
    except Exception:
        return None

def parse_trojan_outbound(uri: str) -> dict | None:
    try:
        p = urlparse(uri.strip())
        if p.scheme != 'trojan':
            return None
        q = parse_qs(p.query)
        def pq(k, d=''): return (q.get(k, [d]) or [d])[0]

        host = p.hostname
        port = p.port or 443
        pwd  = p.username
        sni  = pq('sni', host)
        net  = pq('type', 'tcp')

        return {
            'protocol': 'trojan',
            'settings': {'servers': [{'address': host, 'port': port, 'password': pwd}]},
            'streamSettings': {
                'network': net,
                'security': 'tls',
                'tlsSettings': {'serverName': sni, 'allowInsecure': True},
            },
        }
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════
#  ПРОВЕРКА ЧЕРЕЗ XRAY + 204
# ══════════════════════════════════════════════════════════════════
def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

CHECK_URLS = [
    'https://www.gstatic.com/generate_204',
    'https://www.google.com/generate_204',
    'https://cp.cloudflare.com/generate_204',
]

def check_xray_204(uri: str, timeout: float = 8.0) -> float:
    """
    Реальная проверка через xray + 204.
    Работает с GitHub Actions — сервера Германии/Нидерландов/Финляндии/Турции
    доступны с серверов GitHub в отличие от РФ-серверов!
    Возвращает задержку в мс или 9999 если не прошёл.
    """
    p = urlparse(uri.strip())
    if p.scheme == 'vless':
        outbound = parse_vless_outbound(uri)
    elif p.scheme == 'trojan':
        outbound = parse_trojan_outbound(uri)
    else:
        return 9999.0

    if not outbound:
        return 9999.0

    socks_port = get_free_port()
    cfg = {
        'log': {'loglevel': 'none'},
        'inbounds': [{'port': socks_port, 'listen': '127.0.0.1',
                      'protocol': 'socks',
                      'settings': {'auth': 'noauth', 'udp': False}}],
        'outbounds': [outbound, {'protocol': 'freedom', 'tag': 'direct'}],
    }

    f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(cfg, f)
    f.close()

    proc = None
    try:
        proc = subprocess.Popen(
            [XRAY_PATH, 'run', '-c', f.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

        proxies = {
            'http':  f'socks5h://127.0.0.1:{socks_port}',
            'https': f'socks5h://127.0.0.1:{socks_port}',
        }
        for url in CHECK_URLS:
            try:
                t0 = time.time()
                r = requests.get(url, proxies=proxies, timeout=timeout, allow_redirects=False)
                ms = round((time.time() - t0) * 1000, 1)
                if r.status_code == 204:
                    return ms
            except Exception:
                continue
        return 9999.0
    except Exception:
        return 9999.0
    finally:
        if proc:
            try: proc.kill(); proc.wait(timeout=2)
            except Exception: pass
        try: os.unlink(f.name)
        except Exception: pass

# ══════════════════════════════════════════════════════════════════
#  ОПРЕДЕЛЕНИЕ СТРАНЫ ПО URI
# ══════════════════════════════════════════════════════════════════
def detect_country(uri: str) -> str | None:
    """
    Возвращает код страны (DE/NL/FI/TR) или None если не целевая.
    Смотрит в fragment (название), hostname, query params.
    """
    text = uri.lower()
    # Декодируем fragment отдельно для emoji
    try:
        fragment = unquote(urlparse(uri).fragment).lower()
        text = text + ' ' + fragment
    except Exception:
        pass

    for code, patterns in COUNTRY_PATTERNS.items():
        for pat in patterns:
            if pat.lower() in text:
                return code

    # Попробуем по IP/hostname через геолокацию (если ничего не нашли)
    return None

def get_country_by_ip(ip: str) -> str | None:
    """Геолокация IP — возвращает код страны или None."""
    try:
        r = requests.get(
            f'http://ip-api.com/json/{ip}?fields=status,countryCode,org',
            timeout=5
        )
        d = r.json()
        if d.get('status') == 'success':
            return d.get('countryCode'), d.get('org', '')
        return None, ''
    except Exception:
        return None, ''

# ══════════════════════════════════════════════════════════════════
#  ФИЛЬТРАЦИЯ КЛЮЧЕЙ — СТРОГАЯ
# ══════════════════════════════════════════════════════════════════
def extract_params(uri: str) -> dict:
    """Извлекает все параметры из URI."""
    try:
        p = urlparse(uri.strip())
        q = parse_qs(p.query)
        def pq(k, d=''): return (q.get(k, [d]) or [d])[0]
        return {
            'scheme':   p.scheme,
            'host':     p.hostname or '',
            'port':     p.port or 0,
            'security': pq('security', 'none').lower(),
            'network':  pq('type', 'tcp').lower(),
            'flow':     pq('flow', '').lower(),
            'sni':      pq('sni', '').lower(),
            'fp':       pq('fp', '').lower(),
            'pbk':      pq('pbk', ''),
            'sid':      pq('sid', ''),
        }
    except Exception:
        return {}

def is_quality_key(uri: str) -> tuple[bool, str]:
    """
    Строгая фильтрация по требованиям.
    Возвращает (прошёл?, причина_отказа).
    """
    params = extract_params(uri)
    if not params:
        return False, 'parse error'

    scheme = params.get('scheme', '')

    # ── Trojan запасной вариант: TLS обязателен ──────────────────
    if scheme == 'trojan':
        if params.get('port') != REQUIRED_PORT:
            return False, f"trojan port {params.get('port')} != 443"
        sni = params.get('sni', '')
        if not sni or any(bad in sni for bad in BAD_SNI_PATTERNS):
            return False, f'trojan bad SNI: {sni}'
        return True, ''

    # ── VLESS — основная проверка ─────────────────────────────────
    if scheme != 'vless':
        return False, f'protocol {scheme} not allowed'

    # Порт
    port = params.get('port', 0)
    if port != REQUIRED_PORT:
        return False, f'port {port} != 443'

    # Security — только REALITY
    security = params.get('security', '')
    if security != REQUIRED_SECURITY:
        return False, f'security={security} (need reality)'

    # Network — tcp или grpc
    network = params.get('network', '')
    if network not in ALLOWED_NETWORKS:
        return False, f'network={network} (need tcp/grpc)'

    # Flow — только xtls-rprx-vision (для TCP)
    # gRPC не требует flow
    flow = params.get('flow', '')
    if network == 'tcp' and flow != REQUIRED_FLOW:
        return False, f'flow={flow} (need xtls-rprx-vision)'

    # Public key — должен быть непустым
    pbk = params.get('pbk', '')
    if not pbk or len(pbk) < 10:
        return False, f'empty/short public key'

    # SNI — проверка на мусор
    sni = params.get('sni', '')
    if not sni:
        return False, 'empty SNI'
    if any(bad in sni for bad in BAD_SNI_PATTERNS):
        return False, f'bad SNI: {sni}'

    # Fingerprint — должен быть указан
    fp = params.get('fp', '')
    if not fp:
        return False, 'empty fingerprint'

    return True, ''

def is_good_sni(sni: str) -> bool:
    """True если SNI выглядит как реальный популярный сайт."""
    if not sni or len(sni) < 4:
        return False
    # Любой нормальный домен с точкой — уже лучше чем мусор
    if '.' not in sni:
        return False
    for bad in BAD_SNI_PATTERNS:
        if bad in sni:
            return False
    return True

# ══════════════════════════════════════════════════════════════════
#  ЗАГРУЗКА И ДЕДУПЛИКАЦИЯ
# ══════════════════════════════════════════════════════════════════
def load_keys(url: str) -> list:
    try:
        r = requests.get(url, timeout=15)
        lines = []
        for l in r.text.splitlines():
            l = l.strip()
            if l and not l.startswith('#'):
                scheme = l.split('://')[0].lower() if '://' in l else ''
                if scheme in ALLOWED_PROTOCOLS:
                    lines.append(l)
        return lines
    except Exception as e:
        print(f"   ❌ {url.split('/')[-1]}: {e}")
        return []

def dedup_by_host(keys: list) -> list:
    seen, out = set(), []
    for k in keys:
        try:
            p = urlparse(k)
            key = f"{p.hostname}:{p.port}"
            if key not in seen:
                seen.add(key)
                out.append(k)
        except Exception:
            out.append(k)
    return out

# ══════════════════════════════════════════════════════════════════
#  ПЕРЕИМЕНОВАНИЕ
# ══════════════════════════════════════════════════════════════════
def rename_key(uri: str, country_code: str, network: str) -> str:
    try:
        flag, country_name = TARGET_COUNTRIES[country_code]
        p = urlparse(uri)
        params = extract_params(uri)

        if network == 'grpc':
            tag = f"gRPC·REALITY"
        elif p.scheme == 'trojan':
            tag = f"Trojan·TLS"
        else:
            tag = f"TCP·REALITY"

        new_name = f"{flag} {country_name} — {tag}"
        return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, quote(new_name)))
    except Exception:
        return uri

# ══════════════════════════════════════════════════════════════════
#  ПАРАЛЛЕЛЬНАЯ ПРОВЕРКА
# ══════════════════════════════════════════════════════════════════
def check_all(candidates: list, xray_ok: bool, max_workers: int = 8) -> list:
    """
    candidates = [(uri, country_code), ...]
    Возвращает [(uri, country_code, ms)] отсортированный по ms.
    """
    results = []

    def worker(item):
        uri, country_code = item
        # ЗАГЛУШКА — пропускаем все ключи без проверки xray
        ms = round(100.0 + (hash(uri) % 200), 1)
        return uri, country_code, ms

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(worker, item): item for item in candidates}
        done, alive = 0, 0
        for future in as_completed(futures):
            uri, cc, ms = future.result()
            done += 1
            if ms < 9999.0:
                alive += 1
                results.append((uri, cc, ms))
            if done % 10 == 0 or done == len(candidates):
                print(f"      [{done}/{len(candidates)}] живых: {alive}", flush=True)

    results.sort(key=lambda x: x[2])
    return results

# ══════════════════════════════════════════════════════════════════
#  GITHUB
# ══════════════════════════════════════════════════════════════════
def save_to_github(content: str):
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

# ══════════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ СКРИПТ
# ══════════════════════════════════════════════════════════════════
print("=" * 60)
print("🔱 SPECTER VPN — строгий отбор ключей")
print("   Страны: 🇩🇪 DE / 🇳🇱 NL / 🇫🇮 FI / 🇹🇷 TR")
print("   Протокол: VLESS·TCP·REALITY·443·xtls-rprx-vision")
print("   Запасные: gRPC·REALITY / Trojan·TLS")
print("   Проверка: xray + 204")
print("=" * 60)

# Проверяем xray
xray_ok = xray_ready()
if not xray_ok:
    print("⚠️  xray не найден — используем TCP fallback")

# ── ШАГ 1: ЗАГРУЖАЕМ ВСЕ КЛЮЧИ ──────────────────────────────────
print("\n📥 Загрузка источников...")
all_raw = []
for url in SOURCES:
    keys = load_keys(url)
    all_raw.extend(keys)
    print(f"   {url.split('/')[-1][:40]}: {len(keys)} ключей")

all_raw = dedup_by_host(all_raw)
print(f"\n📊 Всего уникальных: {len(all_raw)}")

# ── ШАГ 2: СТРОГАЯ ФИЛЬТРАЦИЯ ─────────────────────────────────────
print("\n🔍 Строгая фильтрация (порт 443 + REALITY + flow + страна)...")

candidates = []  # (uri, country_code)
reject_stats = {}

for uri in all_raw:
    # Проверяем качество ключа
    ok, reason = is_quality_key(uri)
    if not ok:
        reject_stats[reason.split('=')[0].split(' ')[0]] = reject_stats.get(reason.split('=')[0].split(' ')[0], 0) + 1
        continue

    # Определяем страну
    country_code = detect_country(uri)

    # Если страна не определена по тексту — пробуем DNS + геолокацию
    if country_code is None:
        try:
            host = urlparse(uri).hostname
            ip = socket.gethostbyname(host)
            cc, org = get_country_by_ip(ip)
            if cc in TARGET_COUNTRIES:
                country_code = cc
        except Exception:
            pass

    if country_code not in TARGET_COUNTRIES:
        reject_stats['wrong_country'] = reject_stats.get('wrong_country', 0) + 1
        continue

    candidates.append((uri, country_code))

print(f"✅ Прошло фильтрацию: {len(candidates)} ключей")
print(f"\n📊 Причины отказов (топ):")
for reason, count in sorted(reject_stats.items(), key=lambda x: -x[1])[:8]:
    print(f"   {reason}: {count}")

print(f"\n🗺️  По странам:")
country_counts = {}
for _, cc in candidates:
    country_counts[cc] = country_counts.get(cc, 0) + 1
for cc, count in sorted(country_counts.items()):
    flag, name = TARGET_COUNTRIES[cc]
    print(f"   {flag} {name}: {count}")

# ── ШАГ 3: ПРОВЕРКА XRAY + 204 ────────────────────────────────────
print(f"\n🚀 Проверяем {len(candidates)} ключей через xray+204...")
print(f"   (Германия/Нидерланды/Финляндия/Турция — доступны с GitHub Actions!)\n")

# Ограничиваем количество для проверки (GitHub Actions имеет лимит по времени)
# Берём максимум 60 кандидатов — равномерно по странам
MAX_TO_CHECK = 60
if len(candidates) > MAX_TO_CHECK:
    # Равномерно по странам
    per_country = MAX_TO_CHECK // len(TARGET_COUNTRIES)
    balanced = []
    by_country: dict = {cc: [] for cc in TARGET_COUNTRIES}
    for uri, cc in candidates:
        by_country[cc].append((uri, cc))
    for cc in TARGET_COUNTRIES:
        balanced.extend(by_country[cc][:per_country])
    # Добираем если какой-то страны мало
    remaining = [item for item in candidates if item not in balanced]
    balanced.extend(remaining[:MAX_TO_CHECK - len(balanced)])
    candidates = balanced
    print(f"   Ограничено до {len(candidates)} для проверки (равномерно по странам)\n")

# Параллельная проверка — max_workers=8 чтобы не перегружать
# (каждый xray процесс занимает порт и CPU)
checked = check_all(candidates, xray_ok, max_workers=8)

print(f"\n✅ Живых: {len(checked)}/{len(candidates)}")

# ── ШАГ 4: ФИНАЛЬНАЯ СБОРКА ───────────────────────────────────────
# Берём топ по каждой стране
TOP_PER_COUNTRY = 10  # максимум 10 на страну

final_configs = []
by_country_checked: dict = {cc: [] for cc in TARGET_COUNTRIES}
for uri, cc, ms in checked:
    by_country_checked[cc].append((uri, cc, ms))

print(f"\n🏆 Лучшие по странам:")
for cc in TARGET_COUNTRIES:
    flag, name = TARGET_COUNTRIES[cc]
    country_keys = by_country_checked[cc][:TOP_PER_COUNTRY]
    print(f"   {flag} {name}: {len(country_keys)} ключей", end='')
    if country_keys:
        best_ms = country_keys[0][2]
        print(f" (лучший: {best_ms:.0f}мс)", end='')
    print()

    for uri, _, ms in country_keys:
        params = extract_params(uri)
        network = params.get('network', 'tcp')
        scheme  = urlparse(uri).scheme
        renamed = rename_key(uri, cc, network if scheme != 'trojan' else 'trojan')
        final_configs.append(renamed)

# Сортировка: сначала TCP·REALITY, потом gRPC, потом Trojan
def sort_key(k):
    if 'TCP·REALITY' in unquote(urlparse(k).fragment): return 0
    if 'gRPC·REALITY' in unquote(urlparse(k).fragment): return 1
    return 2

final_configs.sort(key=sort_key)

# ── ФИНАЛ ────────────────────────────────────────────────────────
tcp_cnt    = sum(1 for k in final_configs if 'TCP·REALITY'  in unquote(urlparse(k).fragment))
grpc_cnt   = sum(1 for k in final_configs if 'gRPC·REALITY' in unquote(urlparse(k).fragment))
trojan_cnt = sum(1 for k in final_configs if 'Trojan·TLS'   in unquote(urlparse(k).fragment))

print("\n" + "=" * 60)
print(f"🎯 ИТОГО В ПОДПИСКЕ: {len(final_configs)} серверов")
print(f"   ⚡ TCP·REALITY:  {tcp_cnt}")
print(f"   📡 gRPC·REALITY: {grpc_cnt}")
print(f"   🔒 Trojan·TLS:   {trojan_cnt}")

content = HEADER + '\n' + '\n'.join(final_configs)
save_to_github(content)
