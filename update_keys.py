import requests
import random
import re
import os
import base64
from collections import defaultdict
from urllib.parse import urlparse, urlunparse, quote, unquote, parse_qs

# ===== GITHUB НАСТРОЙКИ =====
GITHUB_TOKEN  = os.getenv('GITHUB_TOKEN')
GITHUB_REPO   = 'ANAEHY/SPECTER'
GITHUB_FILE   = 'keys.txt'
GITHUB_BRANCH = 'main'

# ===== ИСТОЧНИКИ =====
PRIORITY_SOURCES = [
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt'
]

SNI_CIDR_SOURCES = [
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt'
]

HEADER = """#profile-title: base64:8J+RuyBTUEVDVEVSIFZQTg==
#profile-update-interval: 12"""

# ══════════════════════════════════════════════════════════════════
#  SNI → ОПЕРАТОРЫ (актуально 2025-2026, источник: 4pda)
# ══════════════════════════════════════════════════════════════════

SNI_OPERATORS = {
    'stats.vk-portal.net':          'МТС·Мега·Теле2·Йота·РТК',
    'sun6-21.userapi.com':          'МТС·Мега·Теле2·Йота·РТК',
    'sun6-20.userapi.com':          'МТС·Мега·Теле2·РТК',
    'sun6-22.userapi.com':          'МТС·Мега·Теле2·РТК',
    'queuev4.vk.com':               'МТС·Мега·Теле2·Йота·РТК',
    'login.vk.com':                 'МТС·Мега·Теле2·РТК',
    'eh.vk.com':                    'МТС·Мега·Теле2·Йота·РТК',
    'eh.vk.ru':                     'МТС·Мега·Теле2·Йота·РТК',
    'vk.com':                       'МТС·Мега·Теле2·Йота',
    'www.vk.com':                   'МТС·Мега·Теле2·Йота',
    'tunnel.vk-apps.com':           'МТС·Мега·Теле2·Йота',
    'akashi.vk-portal.net':         'МТС',
    'ok.ru':                        'МТС·Мегафон',
    'yandex.ru':                    'МТС·Мега·Теле2',
    'sba.yandex.net':               'МТС·Мегафон',
    'speller.yandex.net':           'МТС·Мега·Теле2·Йота·РТК',
    'egress.yandex.net':            'МТС·Мега·Теле2·РТК',
    'yastatic.net':                 'МТС·Мега·Теле2·РТК',
    'csp.yandex.net':               'МТС·Мега·Теле2·РТК',
    'avatars.mds.yandex.net':       'МТС·Мега·Теле2·РТК',
    'api-maps.yandex.ru':           'МТС·Мега·Теле2·РТК',
    'dzen.ru':                      'Мегафон·Теле2',
    'www.kinopoisk.ru':             'МТС·Мега·Теле2·Йота·РТК',
    'goya.rutube.ru':               'МТС·Мега·Теле2·РТК',
    'st.ozone.ru':                  'МТС·Мега·Теле2·Йота·РТК',
    'www.ozon.ru':                  'МТС·Мега·Теле2',
    'splitter.wb.ru':               'МТС·Мега·Теле2·Йота·РТК',
    'www.wildberries.ru':           'МТС·Мега·Теле2·РТК',
    'alfabank.ru':                  'МТС·Мега·Теле2·Йота',
    'online.sberbank.ru':           'МТС·Мега·Теле2·РТК',
    'www.tbank.ru':                 'МТС·Мега·Теле2',
    'id.tbank.ru':                  'МТС·Мега·Теле2',
    'nspk.ru':                      'МТС·Мега·Теле2·РТК',
    '2gis.ru':                      'МТС·Мега·Теле2',
    'sntr.avito.ru':                'МТС·Мега·Теле2',
    'hh.ru':                        'МТС·Мега·Теле2',
    'rbc.ru':                       'МТС·Мега·РТК',
    'www.rbc.ru':                   'МТС·Мега·РТК',
    'lenta.ru':                     'МТС·Мега·Теле2',
    'max.ru':                       'МТС·Мега·Теле2',
    'ads.x5.ru':                    'МТС·Мега·Теле2',
    'storage.yandexcloud.net':      'МТС·Мега·Теле2·РТК',
    'www.t2.ru':                    'Теле2',
    'msk.t2.ru':                    'Теле2',
    'login.mts.ru':                 'МТС',
    'moscow.megafon.ru':            'Мегафон',
}

BAD_PATTERNS = [
    'compass/cdn', 'microsoft', 'booking', 'tradingview',
    'jkvpn', 'pabloping', 'hediiigate', 'oboob'
]

# ══════════════════════════════════════════════════════════════════
#  СЛОВАРИ СТРАН
# ══════════════════════════════════════════════════════════════════

COUNTRY_RU = {
    "🇩🇪": "Германия",    "🇺🇸": "США",          "🇬🇧": "Великобритания",
    "🇫🇷": "Франция",     "🇳🇱": "Нидерланды",   "🇸🇬": "Сингапур",
    "🇯🇵": "Япония",      "🇰🇷": "Корея",        "🇨🇦": "Канада",
    "🇦🇺": "Австралия",   "🇷🇺": "Россия",       "🇫🇮": "Финляндия",
    "🇸🇪": "Швеция",      "🇳🇴": "Норвегия",     "🇩🇰": "Дания",
    "🇨🇭": "Швейцария",   "🇦🇹": "Австрия",      "🇧🇪": "Бельгия",
    "🇮🇪": "Ирландия",    "🇵🇱": "Польша",       "🇨🇿": "Чехия",
    "🇭🇺": "Венгрия",     "🇷🇴": "Румыния",      "🇧🇬": "Болгария",
    "🇭🇷": "Хорватия",    "🇷🇸": "Сербия",       "🇺🇦": "Украина",
    "🇹🇷": "Турция",      "🇮🇱": "Израиль",      "🇦🇪": "ОАЭ",
    "🇮🇳": "Индия",       "🇨🇳": "Китай",        "🇭🇰": "Гонконг",
    "🇹🇼": "Тайвань",     "🇧🇷": "Бразилия",     "🇦🇷": "Аргентина",
    "🇲🇽": "Мексика",     "🇿🇦": "ЮАР",          "🇮🇸": "Исландия",
    "🇵🇹": "Португалия",  "🇪🇸": "Испания",      "🇮🇹": "Италия",
    "🇬🇷": "Греция",      "🇲🇩": "Молдова",      "🇱🇹": "Литва",
    "🇱🇻": "Латвия",      "🇪🇪": "Эстония",      "🌐": "Anycast",
}

COUNTRY_NAMES_EN = {
    "germany": "Германия",       "united states": "США",        "united kingdom": "Великобритания",
    "france": "Франция",         "netherlands": "Нидерланды",   "singapore": "Сингапур",
    "japan": "Япония",           "korea": "Корея",              "canada": "Канада",
    "australia": "Австралия",    "russia": "Россия",            "finland": "Финляндия",
    "sweden": "Швеция",          "norway": "Норвегия",          "denmark": "Дания",
    "switzerland": "Швейцария",  "austria": "Австрия",          "belgium": "Бельгия",
    "ireland": "Ирландия",       "poland": "Польша",            "czech": "Чехия",
    "hungary": "Венгрия",        "romania": "Румыния",          "bulgaria": "Болгария",
    "croatia": "Хорватия",       "serbia": "Сербия",            "ukraine": "Украина",
    "turkey": "Турция",          "israel": "Израиль",           "india": "Индия",
    "china": "Китай",            "hong kong": "Гонконг",        "taiwan": "Тайвань",
    "brazil": "Бразилия",        "argentina": "Аргентина",      "mexico": "Мексика",
    "spain": "Испания",          "italy": "Италия",             "greece": "Греция",
    "iceland": "Исландия",       "portugal": "Португалия",      "estonia": "Эстония",
    "lithuania": "Литва",        "latvia": "Латвия",            "moldova": "Молдова",
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

# ══════════════════════════════════════════════════════════════════
#  ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════

def get_flag_and_country(fragment: str):
    decoded = unquote(fragment)
    flag_match = re.search(r'([\U0001F1E0-\U0001F1FF]{2}|\U0001F310)', decoded)
    if flag_match:
        flag = flag_match.group(1)
        if flag in COUNTRY_RU:
            return flag, COUNTRY_RU[flag]
    decoded_lower = decoded.lower()
    for eng, rus in COUNTRY_NAMES_EN.items():
        if eng in decoded_lower:
            for code, name in COUNTRY_RU.items():
                if name == rus and code in CODE_TO_FLAG:
                    return CODE_TO_FLAG[code], rus
            return "🌐", rus
    return "🌐", "Сервер"

def get_sni(line: str) -> str:
    try:
        parsed = urlparse(line.strip())
        q = parse_qs(parsed.query)
        return (q.get('sni', [''])[0] or q.get('host', [''])[0]).lower()
    except:
        return ''

def get_operators_label(sni: str) -> str:
    for key, ops in SNI_OPERATORS.items():
        if key in sni:
            return ops
    return 'Универсальный'

def rename_key(line: str, label: str) -> str:
    line = line.strip()
    if not line or line.startswith('#'):
        return line
    for proto in ["vless://", "vmess://", "trojan://", "ss://", "ssr://", "hysteria2://", "tuic://"]:
        if line.lower().startswith(proto):
            break
    else:
        return line
    try:
        parsed = urlparse(line)
        flag, country = get_flag_and_country(parsed.fragment)
        new_name = f"{flag} {country} - {label}"
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                           parsed.params, parsed.query, quote(new_name)))
    except:
        return line

def rename_lte_key(line: str) -> str:
    """Переименовывает LTE ключ С указанием операторов по SNI"""
    line = line.strip()
    if not line or line.startswith('#'):
        return line
    try:
        parsed = urlparse(line)
        flag, country = get_flag_and_country(parsed.fragment)
        sni = get_sni(line)
        ops = get_operators_label(sni)
        new_name = f"{flag} {country} - LTE [{ops}]"
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                           parsed.params, parsed.query, quote(new_name)))
    except:
        return line

def rename_block(configs: list, label: str) -> list:
    return [rename_key(line, label) for line in configs]

def is_cloudflare(config):
    return any(p in config.lower() for p in ['cloudflare', 'cf-ip', '1.1.1.1', '104.', '172.67.', '141.193.'])

def is_bad_key(config):
    config_lower = config.lower()
    return any(p in config_lower for p in BAD_PATTERNS)

def is_bad_sni_cidr(config):
    config_lower = config.lower()
    if 'anycast-ip' in config_lower: return True
    if any(p in config_lower for p in ['ee-', 'estonia', 'ee:', 'tallinn', '🇪🇪']): return 'EE_LAST'
    return False

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
        'BE': ['be-', 'belgium', 'be:', 'brussels', '🇧🇪'],
        'IE': ['ie-', 'ireland', 'ie:', 'dublin', '🇮🇪'],
        'PL': ['pl-', 'poland', 'pl:', 'warsaw', '🇵🇱'],
        'CZ': ['cz-', 'czech', 'cz:', 'prague', '🇨🇿'],
        'IT': ['it-', 'italy', 'it:', 'rome', 'milan', '🇮🇹'],
        'ES': ['es-', 'spain', 'es:', 'madrid', '🇪🇸'],
        'AU': ['au-', 'australia', 'au:', 'sydney', '🇦🇺'],
        'JP': ['jp-', 'japan', 'jp:', 'tokyo', '🇯🇵']
    }
    config_lower = config.lower()
    for country, pats in patterns.items():
        if any(pat in config_lower for pat in pats):
            return country
    return 'OTHER'

# ══════════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ В GITHUB
# ══════════════════════════════════════════════════════════════════

def save_to_github(content: str):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    sha = None
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        sha = resp.json().get('sha')
    encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    data = {'message': '🔄 Обновление ключей SPECTER VPN', 'content': encoded, 'branch': GITHUB_BRANCH}
    if sha:
        data['sha'] = sha
    resp = requests.put(url, headers=headers, json=data)
    if resp.status_code in [200, 201]:
        print(f'\n✅ Файл сохранён в GitHub!')
        print(f'🔗 https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{GITHUB_FILE}')
    else:
        print(f'\n❌ Ошибка сохранения: {resp.status_code} — {resp.text}')

# ══════════════════════════════════════════════════════════════════
#  ОСНОВНОЙ СКРИПТ
# ══════════════════════════════════════════════════════════════════

print("🚀 SPECTER VPN — сборка ключей")

# ── 1. ФИКСИРОВАННЫЕ БЛОКИ: 4DE / 4NL / 4FR / 3RU ───────────────
target_blocks = {'DE': 4, 'NL': 4, 'FR': 4, 'RU': 3}
collected_blocks = {country: [] for country in target_blocks}

print("\n📥 ФИКСИРОВАННЫЕ БЛОКИ 4/4/4/3:")
for source in PRIORITY_SOURCES:
    print(f"  {source.split('/')[-1]}")
    try:
        resp = requests.get(source, timeout=10)
        lines = [l.strip() for l in resp.text.splitlines()[3:] if l.strip()]
        valid_lines = [l for l in lines if not is_cloudflare(l) and not is_bad_key(l)]
        for country, target_count in target_blocks.items():
            if len(collected_blocks[country]) < target_count:
                country_lines = [l for l in valid_lines if extract_country(l) == country]
                needed = target_count - len(collected_blocks[country])
                if country_lines:
                    selected = random.sample(country_lines, min(needed, len(country_lines)))
                    for key in selected:
                        if key not in collected_blocks[country]:
                            collected_blocks[country].append(key)
                    print(f"     ✅ {country}: +{len(selected)}")
    except Exception as e:
        print(f"     ❌ {e}")

for country in collected_blocks:
    collected_blocks[country] = rename_block(collected_blocks[country], "WiFi")

# ── 2. 16 УНИКАЛЬНЫХ СЛУЧАЙНЫХ СТРАН ─────────────────────────────
print("\n📥 16 УНИКАЛЬНЫХ СТРАН:")
random_countries = defaultdict(list)
used_countries = set(collected_blocks.keys())

for source in PRIORITY_SOURCES:
    try:
        resp = requests.get(source, timeout=10)
        lines = [l.strip() for l in resp.text.splitlines()[3:] if l.strip()]
        valid_lines = [l for l in lines if not is_cloudflare(l) and not is_bad_key(l)]
        for line in valid_lines:
            country = extract_country(line)
            if country not in used_countries and country != 'OTHER' and len(random_countries[country]) < 1:
                random_countries[country].append(line)
    except:
        pass

random_countries_list = list(random_countries.keys())
random.shuffle(random_countries_list)
selected_random = random_countries_list[:16]
for country in selected_random:
    random_countries[country] = rename_block(random_countries[country][:1], "WiFi")

# ── 3. SNI/CIDR → LTE (с определением оператора!) ────────────────
print("\n📥 SNI/CIDR (умная сортировка по операторам):")
sni_cidr_configs = []
sni_cidr_ee = []

for source in SNI_CIDR_SOURCES:
    source_name = source.split('/')[-1]
    try:
        resp = requests.get(source, timeout=10)
        lines = [l.strip() for l in resp.text.splitlines()[3:] if l.strip()]
        if 'SNI-RU-all' in source_name:
            lines = lines[2:]
        filtered_lines = []
        for line in lines:
            if is_cloudflare(line) or is_bad_key(line):
                continue
            bad_result = is_bad_sni_cidr(line)
            if bad_result == 'EE_LAST':
                sni_cidr_ee.append(line)
            elif not bad_result:
                filtered_lines.append(line)
        selected = filtered_lines[:10] if 'CIDR' in source_name else filtered_lines
        sni_cidr_configs.extend(selected)
        print(f"     ✅ {source_name}: +{len(selected)}")
    except Exception as e:
        print(f"     ❌ {e}")

# Применяем умное переименование с операторами
sni_cidr_renamed = [rename_lte_key(line) for line in sni_cidr_configs]
sni_cidr_ee_renamed = [rename_lte_key(line) for line in sni_cidr_ee]

# Статистика по операторам
ops_stat = defaultdict(int)
for line in sni_cidr_configs:
    sni = get_sni(line)
    ops = get_operators_label(sni)
    ops_stat[ops] += 1

print(f"\n📊 Статистика LTE по операторам:")
for ops, count in sorted(ops_stat.items(), key=lambda x: -x[1])[:8]:
    print(f"     {ops}: {count} ключей")

# ── 4. ДОПОЛНИТЕЛЬНЫЕ ИСТОЧНИКИ (по 3 из каждого) ───────────────
EXTRA_SOURCES = [
    'https://raw.githubusercontent.com/whoahaow/rjsxrd/main/githubmirror/bypass/bypass-all.txt',
    'https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt',
]
EXTRA_GOOD_SNI = list(SNI_OPERATORS.keys())

print("\n📥 ДОПОЛНИТЕЛЬНЫЕ ИСТОЧНИКИ (по 3 ключа):")
extra_configs = []
for source in EXTRA_SOURCES:
    source_name = source.split('/')[-1]
    try:
        resp = requests.get(source, timeout=10)
        lines = [l.strip() for l in resp.text.splitlines() if l.strip() and l.strip().startswith('vless://')]
        good_lines = []
        for line in lines:
            if is_cloudflare(line) or is_bad_key(line):
                continue
            sni = get_sni(line)
            if any(good in sni for good in EXTRA_GOOD_SNI):
                good_lines.append(line)
        selected = random.sample(good_lines, min(3, len(good_lines))) if good_lines else []
        extra_configs.extend(selected)
        print(f"     ✅ {source_name}: найдено {len(good_lines)} хороших, берём {len(selected)}")
    except Exception as e:
        print(f"     ❌ {source_name}: {e}")

extra_renamed = [rename_lte_key(line) for line in extra_configs]

# ── 5. ФИНАЛЬНАЯ СБОРКА ───────────────────────────────────────────
final_configs = []
for country in ['DE', 'NL', 'FR', 'RU']:
    final_configs.extend(collected_blocks[country])
for country in selected_random:
    final_configs.extend(random_countries[country][:1])
final_configs.extend(sni_cidr_renamed[:25])
final_configs.extend(sni_cidr_ee_renamed[:3])
final_configs.extend(extra_renamed)
final_configs = final_configs[:66]

content = HEADER + '\n' + '\n'.join(final_configs)
print(f"\n🎯 ИТОГО: {len(final_configs)} серверов")

# ── 6. СОХРАНЯЕМ В GITHUB ────────────────────────────────────────
save_to_github(content)
