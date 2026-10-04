#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ SPECTER — живые VLESS-ключи + скорость

  1. load     источники → чистим дубли → разбираем ключи
  2. alive    НАСТОЯЩАЯ проверка: поднимаем xray и ходим в интернет через каждый ключ
              (нужно ≥2 успешных проб из 3). Один процесс xray на ~100 ключей → летает.
  3. enrich   для живых: страна выхода + замер скорости загрузки (Мбит/с)
  4. publish  сортировка по скорости, имена «🇩🇪 Германия - LTE - 🚀 245 Мбит/с», пуш keys.txt

Локально без токена: результат пишется в keys.local.txt (в GitHub ничего не уходит).
"""
from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ═══════════════════════════════ НАСТРОЙКИ ═══════════════════════════════

GITHUB_TOKEN = os.getenv('GH_TOKEN')
GITHUB_REPO = 'ANAEHY/SPECTER'
GITHUB_FILE = 'keys.txt'
GITHUB_BRANCH = 'main'

PROFILE_TITLE = '⚡ SPECTER VPN'
UPDATE_HOURS = 3                  # как часто клиент (Happ) перезапрашивает список; = частоте cron

SOURCE_BASE = 'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/'


@dataclass(frozen=True)
class Source:
    file: str
    tag: str                      # 'wifi' | 'lte' | 'sni'
    top: int | None               # сколько самых быстрых оставить (None = все живые)


SOURCES = [
    Source('BLACK_VLESS_RUS_mobile.txt',               'wifi', 8),
    Source('BLACK_VLESS_RUS.txt',                      'wifi', 8),
    Source('Vless-Reality-White-Lists-Rus-Mobile.txt', 'lte',  8),
    Source('Vless-Reality-White-Lists-Rus-Mobile-2.txt', 'lte', 8),
    Source('WHITE-CIDR-RU-checked.txt',                'lte',  8),
    Source('WHITE-SNI-RU-all.txt',                     'sni',  None),
]

# подпись в имени ключа и порядок групп в выдаче (SNI → WiFi → LTE)
TAGS = {'sni': ('Универсальный SNI', 0), 'wifi': ('WiFi', 1), 'lte': ('LTE', 2)}
GROUP_BY_TYPE = True              # True: сортировка по скорости внутри групп; False: одна общая по скорости

# ── проверка «живой / мёртвый» ──
BATCH_SIZE = 100                  # ключей на один процесс xray
BATCH_PARALLEL = 3                # процессов xray одновременно
PROBE_URLS = [
    'https://www.gstatic.com/generate_204',
    'https://cp.cloudflare.com/generate_204',
    'https://www.google.com/generate_204',
]
PROBE_NEED_OK = 2                 # из скольких проб должно пройти (из len(PROBE_URLS))
PROBE_TIMEOUT = (3, 6)            # (подключение, ожидание ответа), сек

# ── замер скорости (только для живых) ──
SPEED_URLS = [
    'https://speed.cloudflare.com/__down?bytes=100000000',
    'https://proof.ovh.net/files/100Mb.dat',
    'https://cachefly.cachefly.net/100mb.test',
]
SPEED_SECONDS = 4.0               # длительность замера на ключ
SPEED_WARMUP = 0.8                # первые секунды (TCP slow start) не считаем
SPEED_STREAMS = 3                 # параллельных потоков на ключ
SPEED_WORKERS = 4                 # ключей замеряем одновременно (больше — искажает цифры)
SPEED_MIN_MBPS = 1.0              # медленнее — считаем нерабочим
SPEED_PREPICK = 3                 # для источников с top: замеряем top*3 лучших по пингу

EXIT_GEO_URLS = [                 # узнаём страну ВЫХОДА (через сам ключ), сначала HTTPS-сервисы
    'https://ipwho.is/?fields=country_code',
    'https://api.country.is/',
    'https://ipapi.co/country/',
    'http://ip-api.com/line/?fields=countryCode',
]

MIN_KEYS_TO_PUBLISH = 5           # если живых меньше — не затираем keys.txt

UA = 'Mozilla/5.0 (SPECTER checker)'
XRAY_DIR = Path(tempfile.gettempdir()) / 'specter-xray'

# ═══════════════════════════════ СТРАНЫ ═══════════════════════════════

COUNTRY_RU = {
    # Европа
    'DE': 'Германия', 'FR': 'Франция', 'NL': 'Нидерланды', 'IT': 'Италия', 'ES': 'Испания',
    'PL': 'Польша', 'BE': 'Бельгия', 'AT': 'Австрия', 'CH': 'Швейцария', 'SE': 'Швеция',
    'NO': 'Норвегия', 'DK': 'Дания', 'FI': 'Финляндия', 'GB': 'Британия', 'PT': 'Португалия',
    'IE': 'Ирландия', 'CZ': 'Чехия', 'SK': 'Словакия', 'HU': 'Венгрия', 'RO': 'Румыния',
    'BG': 'Болгария', 'HR': 'Хорватия', 'SI': 'Словения', 'RS': 'Сербия', 'GR': 'Греция',
    'LT': 'Литва', 'LV': 'Латвия', 'EE': 'Эстония', 'MD': 'Молдова', 'BY': 'Беларусь',
    'MK': 'Северная Македония', 'AL': 'Албания', 'BA': 'Босния', 'ME': 'Черногория',
    'XK': 'Косово', 'LU': 'Люксембург', 'MT': 'Мальта', 'CY': 'Кипр', 'IS': 'Исландия',
    'LI': 'Лихтенштейн', 'MC': 'Монако', 'SM': 'Сан-Марино',
    # СНГ / Кавказ / ЦА
    'RU': 'Россия', 'UA': 'Украина', 'KZ': 'Казахстан', 'UZ': 'Узбекистан', 'AZ': 'Азербайджан',
    'AM': 'Армения', 'GE': 'Грузия', 'TJ': 'Таджикистан', 'TM': 'Туркменистан', 'KG': 'Кыргызстан',
    # Ближний Восток
    'TR': 'Турция', 'IL': 'Израиль', 'AE': 'ОАЭ', 'SA': 'Саудовская Аравия', 'QA': 'Катар',
    'KW': 'Кувейт', 'BH': 'Бахрейн', 'OM': 'Оман', 'IQ': 'Ирак', 'IR': 'Иран',
    'JO': 'Иордания', 'LB': 'Ливан',
    # Азия
    'IN': 'Индия', 'JP': 'Япония', 'KR': 'Корея', 'SG': 'Сингапур', 'CN': 'Китай',
    'HK': 'Гонконг', 'TW': 'Тайвань', 'MY': 'Малайзия', 'ID': 'Индонезия', 'PH': 'Филиппины',
    'TH': 'Таиланд', 'VN': 'Вьетнам', 'PK': 'Пакистан', 'BD': 'Бангладеш', 'LK': 'Шри-Ланка',
    'NP': 'Непал', 'MM': 'Мьянма', 'KH': 'Камбоджа', 'LA': 'Лаос', 'MN': 'Монголия',
    # Америка
    'US': 'США', 'CA': 'Канада', 'MX': 'Мексика',
    'BR': 'Бразилия', 'AR': 'Аргентина', 'CL': 'Чили', 'CO': 'Колумбия', 'PE': 'Перу',
    'EC': 'Эквадор', 'VE': 'Венесуэла', 'UY': 'Уругвай', 'BO': 'Боливия', 'PY': 'Парагвай',
    'CR': 'Коста-Рика', 'PA': 'Панама',
    # Африка
    'ZA': 'ЮАР', 'NG': 'Нигерия', 'EG': 'Египет', 'KE': 'Кения', 'MA': 'Марокко',
    'TN': 'Тунис', 'GH': 'Гана', 'SN': 'Сенегал', 'ET': 'Эфиопия', 'DZ': 'Алжир',
    'TZ': 'Танзания', 'UG': 'Уганда',
    # Океания
    'AU': 'Австралия', 'NZ': 'Новая Зеландия',
}

FLAG_RE = re.compile('[\U0001F1E6-\U0001F1FF]{2}')
T0 = time.time()


def log(msg: str = '') -> None:
    print(f'[{time.time() - T0:6.1f}s] {msg}', flush=True)


def cc_flag(cc: str) -> str:
    if not re.fullmatch(r'[A-Za-z]{2}', cc or ''):
        return '🌐'
    return ''.join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


def cc_name(cc: str) -> str:
    return COUNTRY_RU.get(cc.upper(), cc.upper()) if cc else 'Anycast'


def flag_to_cc(text: str) -> str:
    m = FLAG_RE.search(text or '')
    return ''.join(chr(ord(c) - 0x1F1E6 + 65) for c in m.group()) if m else ''


def fmt_speed(mbps: float) -> str:
    icon = '🚀' if mbps >= 100 else '⚡' if mbps >= 30 else '🐢'
    if mbps >= 1000:
        text = f'{mbps / 1000:.1f} Гбит/с'
    elif mbps >= 10:
        text = f'{mbps:.0f} Мбит/с'
    else:
        text = f'{mbps:.1f} Мбит/с'
    return f'{icon} {text}'


# ═══════════════════════════════ XRAY ═══════════════════════════════

def _asset_name() -> str:
    arm = platform.machine().lower() in ('arm64', 'aarch64')
    system = platform.system()
    if system == 'Windows':
        return 'Xray-windows-arm64-v8a.zip' if arm else 'Xray-windows-64.zip'
    if system == 'Darwin':
        return 'Xray-macos-arm64-v8a.zip' if arm else 'Xray-macos-64.zip'
    return 'Xray-linux-arm64-v8a.zip' if arm else 'Xray-linux-64.zip'


def ensure_xray() -> str:
    """Ищем xray (XRAY_PATH → PATH → кэш), иначе качаем свежий релиз."""
    exe = 'xray.exe' if os.name == 'nt' else 'xray'
    for cand in (os.getenv('XRAY_PATH'), shutil.which('xray'), str(XRAY_DIR / exe)):
        if cand and Path(cand).is_file():
            return cand
    XRAY_DIR.mkdir(parents=True, exist_ok=True)
    name = _asset_name()
    log(f'xray: качаю {name} …')
    zpath = XRAY_DIR / 'xray.zip'
    with requests.get(f'https://github.com/XTLS/Xray-core/releases/latest/download/{name}',
                      stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(zpath, 'wb') as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    with zipfile.ZipFile(zpath) as z:
        z.extract(exe, XRAY_DIR)
    zpath.unlink()
    target = XRAY_DIR / exe
    target.chmod(0o755)
    return str(target)


def xray_version(xray: str) -> str:
    try:
        out = subprocess.run([xray, 'version'], capture_output=True, text=True, timeout=10).stdout
        return out.splitlines()[0]
    except Exception:
        return '?'


class XrayError(RuntimeError):
    pass


def free_ports(n: int) -> list[int]:
    socks, ports = [], []
    try:
        for _ in range(n):
            s = socket.socket()
            s.bind(('127.0.0.1', 0))
            socks.append(s)
            ports.append(s.getsockname()[1])
    finally:
        for s in socks:
            s.close()
    return ports


# ═══════════════════════════════ ПАРСИНГ КЛЮЧЕЙ ═══════════════════════════════

HEX_RE = re.compile(r'^(?:[0-9a-fA-F]{2}){0,8}$')


@dataclass(eq=False)
class Node:
    uri: str                       # ключ без #имени (он же уникальный id)
    host: str
    port: int
    outbound: dict
    remark_cc: str = ''            # страна из исходного названия (запасной вариант)
    latency: float | None = None   # мс; None = мёртв / не проверялся
    speed: float = 0.0             # Мбит/с
    cc: str = ''                   # страна выхода


def parse_vless(raw: str) -> Node | None:
    """vless:// → outbound для xray. None = ключ битый или транспорт не поддерживается."""
    try:
        raw = raw.strip()
        u = urlparse(raw)
        if u.scheme != 'vless' or not u.username or not u.hostname:
            return None
        port = u.port or 443
        if not 0 < port < 65536:
            return None
        q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}

        net = (q.get('type') or 'tcp').lower()
        net = {'http': 'h2', 'splithttp': 'xhttp', 'raw': 'tcp'}.get(net, net)
        sec = (q.get('security') or 'none').lower()
        host_hdr = q.get('host', '')
        path = q.get('path') or '/'
        stream: dict = {'network': net}

        if net == 'ws':
            ws = {'path': path}
            if host_hdr:
                ws['host'] = host_hdr
            stream['wsSettings'] = ws
        elif net == 'grpc':
            g = {'serviceName': q.get('serviceName', ''), 'multiMode': q.get('mode') == 'multi'}
            if q.get('authority'):
                g['authority'] = q['authority']
            stream['grpcSettings'] = g
        elif net == 'httpupgrade':
            stream['httpupgradeSettings'] = {'path': path, 'host': host_hdr}
        elif net == 'xhttp':
            x = {'path': path, 'mode': q.get('mode') or 'auto'}
            if host_hdr:
                x['host'] = host_hdr
            if q.get('extra'):
                try:
                    extra = json.loads(q['extra'])
                    if isinstance(extra, dict):
                        x['extra'] = extra
                except ValueError:
                    pass
            stream['xhttpSettings'] = x
        elif net == 'h2':
            stream['httpSettings'] = {'path': path, 'host': [h for h in host_hdr.split(',') if h]}
        elif net == 'tcp':
            if q.get('headerType') == 'http':
                stream['tcpSettings'] = {'header': {'type': 'http', 'request': {
                    'path': path.split(','), 'headers': {'Host': host_hdr.split(',') if host_hdr else []}}}}
        else:
            return None                                  # kcp / quic / ... — не проверяем

        sni = q.get('sni') or host_hdr or u.hostname
        fp = q.get('fp') or 'chrome'
        if sec == 'reality':
            pbk, sid = q.get('pbk', ''), q.get('sid', '')
            if not pbk or not HEX_RE.match(sid):
                return None
            rs = {'serverName': sni, 'fingerprint': fp, 'publicKey': pbk,
                  'shortId': sid, 'spiderX': q.get('spx', '')}
            if q.get('pqv'):
                rs['mldsa65Verify'] = q['pqv']
            stream['security'] = 'reality'
            stream['realitySettings'] = rs
        elif sec == 'tls':
            ts = {'serverName': sni, 'fingerprint': fp}
            if q.get('alpn'):
                ts['alpn'] = q['alpn'].split(',')
            if (q.get('allowInsecure') or q.get('insecure') or '0').lower() in ('1', 'true'):
                ts['allowInsecure'] = True
            stream['security'] = 'tls'
            stream['tlsSettings'] = ts
        elif sec != 'none':
            return None

        user = {'id': unquote(u.username), 'encryption': q.get('encryption') or 'none'}
        if q.get('flow'):
            user['flow'] = q['flow']
        outbound = {'protocol': 'vless',
                    'settings': {'vnext': [{'address': u.hostname, 'port': port, 'users': [user]}]},
                    'streamSettings': stream}
        return Node(uri=raw.split('#', 1)[0], host=u.hostname, port=port, outbound=outbound,
                    remark_cc=flag_to_cc(unquote(u.fragment)))
    except Exception:
        return None


# ═══════════════════════════════ XRAY BATCH ═══════════════════════════════

class XrayBatch:
    """Один процесс xray = N локальных HTTP-прокси; i-й прокси ходит строго через i-й ключ.
    Всё, что не попало под правило, уходит в blackhole — ложно-живых не будет."""

    def __init__(self, xray: str, nodes: list[Node]):
        self.xray, self.nodes = xray, nodes
        self.ports = free_ports(len(nodes))
        self.proc: subprocess.Popen | None = None
        self._files: list[str] = []
        self._log = None

    def _config(self) -> dict:
        outs: list[dict] = [{'tag': 'block', 'protocol': 'blackhole'}]
        ins, rules = [], []
        for i, (n, port) in enumerate(zip(self.nodes, self.ports)):
            outs.append({**n.outbound, 'tag': f'o{i}'})
            ins.append({'tag': f'i{i}', 'listen': '127.0.0.1', 'port': port,
                        'protocol': 'http', 'settings': {}})
            rules.append({'type': 'field', 'inboundTag': [f'i{i}'], 'outboundTag': f'o{i}'})
        return {'log': {'loglevel': 'none'}, 'inbounds': ins, 'outbounds': outs,
                'routing': {'domainStrategy': 'AsIs', 'rules': rules}}

    def _tail(self) -> str:
        try:
            return Path(self._files[1]).read_text(errors='replace').strip()[-300:] or 'xray завершился'
        except Exception:
            return 'xray завершился'

    def __enter__(self) -> 'XrayBatch':
        fd, cfg = tempfile.mkstemp(prefix='specter-', suffix='.json')
        with os.fdopen(fd, 'w') as f:
            json.dump(self._config(), f)
        self._files = [cfg, cfg + '.log']
        self._log = open(self._files[1], 'wb')
        try:
            self.proc = subprocess.Popen([self.xray, 'run', '-c', cfg], stdout=self._log,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            deadline = time.time() + 20
            while True:
                if self.proc.poll() is not None:
                    raise XrayError(self._tail())
                try:
                    socket.create_connection(('127.0.0.1', self.ports[-1]), 0.3).close()
                    break
                except OSError:
                    if time.time() > deadline:
                        raise XrayError('xray не открыл порты за 20 с')
                    time.sleep(0.05)
        except BaseException:
            self.close()
            raise
        return self

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def close(self) -> None:
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.kill()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                pass
        if self._log:
            self._log.close()
        for p in self._files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def __exit__(self, *exc) -> None:
        self.close()


def session_for(port: int) -> requests.Session:
    s = requests.Session()
    s.trust_env = False                      # не слушаем системные HTTP(S)_PROXY
    s.headers['User-Agent'] = UA
    s.proxies = {'http': f'http://127.0.0.1:{port}', 'https': f'http://127.0.0.1:{port}'}
    return s


# ═══════════════════════════════ ШАГ 1: ЖИВОЙ ИЛИ НЕТ ═══════════════════════════════

def probe_alive(port: int) -> float | None:
    """Пинг в мс, если через ключ реально открылись ≥PROBE_NEED_OK адресов из PROBE_URLS, иначе None."""
    ok: list[float] = []
    fails = 0
    with session_for(port) as s:
        for url in PROBE_URLS:
            t = time.perf_counter()
            try:
                r = s.get(url, timeout=PROBE_TIMEOUT, allow_redirects=False)
                if r.status_code == 204:
                    ok.append((time.perf_counter() - t) * 1000)
                else:
                    fails += 1
            except requests.RequestException:
                fails += 1
            if len(ok) >= PROBE_NEED_OK or fails > len(PROBE_URLS) - PROBE_NEED_OK:
                break
    return round(min(ok), 1) if len(ok) >= PROBE_NEED_OK else None


def _alive_chunk(xray: str, nodes: list[Node]) -> int:
    """Проверяет пачку ключей одним xray. Если xray не стартовал (битый ключ) — делим пополам."""
    try:
        with XrayBatch(xray, nodes) as batch:
            with ThreadPoolExecutor(len(nodes)) as ex:
                futs = {ex.submit(probe_alive, p): n for p, n in zip(batch.ports, nodes)}
                results = {futs[f]: f.result() for f in futs}
            if not batch.running():
                raise XrayError('xray упал во время проверки')
        for n, ms in results.items():
            n.latency = ms
        return sum(ms is not None for ms in results.values())
    except XrayError:
        if len(nodes) == 1:
            return 0
        mid = len(nodes) // 2
        return _alive_chunk(xray, nodes[:mid]) + _alive_chunk(xray, nodes[mid:])


def check_alive(xray: str, nodes: list[Node]) -> int:
    chunks = [nodes[i:i + BATCH_SIZE] for i in range(0, len(nodes), BATCH_SIZE)]
    alive = done = 0
    with ThreadPoolExecutor(BATCH_PARALLEL) as ex:
        for fut in as_completed([ex.submit(_alive_chunk, xray, c) for c in chunks]):
            alive += fut.result()
            done += 1
            log(f'  пачка {done}/{len(chunks)} · живых пока {alive}')
    return alive


# ═══════════════════════════════ ШАГ 2: СТРАНА И СКОРОСТЬ ═══════════════════════════════

def parse_cc(text: str) -> str:
    t = text.strip()
    if re.fullmatch(r'[A-Z]{2}', t):
        return t
    try:
        d = json.loads(t)
    except ValueError:
        return ''
    if isinstance(d, dict):
        for k in ('countryCode', 'country_code', 'country'):
            v = d.get(k)
            if isinstance(v, str) and re.fullmatch(r'[A-Za-z]{2}', v):
                return v.upper()
    return ''


def exit_country(port: int) -> str:
    with session_for(port) as s:
        for url in EXIT_GEO_URLS:
            try:
                r = s.get(url, timeout=(3, 4))
                if r.ok:
                    cc = parse_cc(r.text)
                    if cc:
                        return cc
            except requests.RequestException:
                continue
    return ''


def _download(port: int, url: str) -> float:
    """Один поток загрузки → Мбит/с (после прогрева)."""
    got = got_base = 0
    t_base = t_last = None
    start = time.perf_counter()
    try:
        with session_for(port) as s, s.get(url, stream=True, timeout=(3, 6),
                                           headers={'Accept-Encoding': 'identity'}) as r:
            if r.status_code != 200:
                return 0.0
            for chunk in r.iter_content(1 << 16):
                now = time.perf_counter()
                got += len(chunk)
                t_last = now
                if t_base is None and now - start >= SPEED_WARMUP:
                    t_base, got_base = now, got
                if now - start >= SPEED_SECONDS:
                    break
    except requests.RequestException:
        pass
    if t_last is None:
        return 0.0
    if t_base is None or t_last - t_base < 0.25:      # поток закончился/оборвался до конца прогрева
        t_base, got_base = start, 0
    dt = t_last - t_base
    return (got - got_base) * 8 / dt / 1e6 if dt > 0 else 0.0


def speed_test(port: int) -> float:
    """Суммарная скорость SPEED_STREAMS параллельных потоков, Мбит/с."""
    for url in SPEED_URLS:
        with ThreadPoolExecutor(SPEED_STREAMS) as ex:
            total = sum(ex.map(lambda _: _download(port, url), range(SPEED_STREAMS)))
        if total > 0:
            return round(total, 1)
    return 0.0


def enrich(xray: str, nodes: list[Node]) -> None:
    chunks = [nodes[i:i + BATCH_SIZE] for i in range(0, len(nodes), BATCH_SIZE)]
    done = 0
    for chunk in chunks:
        try:
            with XrayBatch(xray, chunk) as batch:
                with ThreadPoolExecutor(16) as ex:
                    for n, cc in zip(chunk, ex.map(exit_country, batch.ports)):
                        n.cc = cc or n.remark_cc
                with ThreadPoolExecutor(SPEED_WORKERS) as ex:
                    futs = {ex.submit(speed_test, p): n for p, n in zip(batch.ports, chunk)}
                    for f in as_completed(futs):
                        futs[f].speed = f.result()
                        done += 1
                        if done % 10 == 0 or done == len(nodes):
                            log(f'  замерено {done}/{len(nodes)}')
        except XrayError as e:
            log(f'  ✗ xray не поднялся ({e}) — пачка пропущена')


# ═══════════════════════════════ ИСТОЧНИКИ И ПУБЛИКАЦИЯ ═══════════════════════════════

def fetch_source(src: Source) -> list[str]:
    err = ''
    for _ in range(3):
        try:
            r = requests.get(SOURCE_BASE + src.file, timeout=20, headers={'User-Agent': UA})
            if 400 <= r.status_code < 500:
                err = f'HTTP {r.status_code} (источник удалён или переименован?)'
                break
            r.raise_for_status()
            return [ln.strip() for ln in r.text.splitlines() if ln.strip().startswith('vless://')]
        except requests.RequestException as e:
            err = str(e)
            time.sleep(1)
    log(f'  ✗ {src.file}: {err[:90]}')
    return []


def key_name(src: Source, n: Node) -> str:
    return f'{cc_flag(n.cc)} {cc_name(n.cc)} - {TAGS[src.tag][0]} - {fmt_speed(n.speed)}'


def build_header() -> str:
    title = base64.b64encode(PROFILE_TITLE.encode()).decode()
    return f'#profile-title: base64:{title}\n#profile-update-interval: {UPDATE_HOURS}'


def publish(content: str, count: int) -> bool:
    if not GITHUB_TOKEN:
        if os.getenv('GITHUB_ACTIONS'):
            log('✗ нет секрета GH_TOKEN — публиковать некуда')
            return False
        Path('keys.local.txt').write_text(content, encoding='utf-8')
        log('GH_TOKEN не задан → сохранено в keys.local.txt')
        return True
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'Accept': 'application/vnd.github+json'}
    r = None
    for _ in range(3):
        sha = None
        g = requests.get(url, headers=headers, params={'ref': GITHUB_BRANCH}, timeout=30)
        if g.status_code == 200:
            info = g.json()
            sha = info.get('sha')
            try:
                if base64.b64decode(info.get('content', '')).decode('utf-8').strip() == content.strip():
                    log('keys.txt не изменился — коммит пропущен')
                    return True
            except Exception:
                pass
        data = {'message': f'Auto update · {count} keys', 'branch': GITHUB_BRANCH,
                'content': base64.b64encode(content.encode('utf-8')).decode()}
        if sha:
            data['sha'] = sha
        r = requests.put(url, headers=headers, json=data, timeout=60)
        if r.status_code in (200, 201):
            log('✓ keys.txt сохранён в GitHub')
            return True
        if r.status_code != 409:                       # 409 = sha устарел → пробуем ещё раз
            break
    log(f'✗ GitHub: {r.status_code if r is not None else "?"} {r.text[:200] if r is not None else ""}')
    return False


# ═══════════════════════════════ MAIN ═══════════════════════════════

def main() -> int:
    log('⚡ SPECTER · живые ключи + скорость')
    xray = ensure_xray()
    log(f'xray: {xray_version(xray)}')

    # 1) загрузка
    log('1/3 источники')
    parsed: dict[str, Node | None] = {}
    per_source: list[tuple[Source, list[Node]]] = []
    for src in SOURCES:
        raws = fetch_source(src)
        nodes, seen, bad = [], set(), 0
        for raw in raws:
            uri = raw.split('#', 1)[0]
            if uri in seen:
                continue
            seen.add(uri)
            if uri not in parsed:
                parsed[uri] = parse_vless(raw)
            if parsed[uri]:
                nodes.append(parsed[uri])
            else:
                bad += 1
        per_source.append((src, nodes))
        log(f'  {src.file:<44}{len(raws):>5} → {len(nodes)}' + (f'  (не разобрано: {bad})' if bad else ''))

    uniq = [n for n in parsed.values() if n]
    if not uniq:
        log('✗ ключей нет — выходим')
        return 1

    # 2) живые?
    log(f'2/3 проверка {len(uniq)} ключей через xray')
    t = time.time()
    alive = check_alive(xray, uniq)
    log(f'  живых {alive}/{len(uniq)} ({alive * 100 // len(uniq)}%) за {time.time() - t:.0f} с')
    for src, nodes in per_source:
        if nodes:
            log(f'    {src.file:<44}{sum(n.latency is not None for n in nodes):>4}/{len(nodes)}')

    # 3) страна выхода + скорость (только лучшие по пингу кандидаты)
    candidates: dict[str, Node] = {}
    for src, nodes in per_source:
        live = sorted((n for n in nodes if n.latency is not None), key=lambda n: n.latency)
        for n in (live if src.top is None else live[:src.top * SPEED_PREPICK]):
            candidates[n.uri] = n
    log(f'3/3 страна и скорость: {len(candidates)} кандидатов')
    t = time.time()
    enrich(xray, list(candidates.values()))
    log(f'  готово за {time.time() - t:.0f} с')

    # итог: топ по скорости в каждом источнике → общая сортировка
    rows: list[tuple[Source, Node]] = []
    for src, nodes in per_source:
        good = sorted((n for n in nodes if n.speed >= SPEED_MIN_MBPS), key=lambda n: -n.speed)
        rows += [(src, n) for n in (good if src.top is None else good[:src.top])]
    rows.sort(key=lambda r: (TAGS[r[0].tag][1] if GROUP_BY_TYPE else 0, -r[1].speed))

    if len(rows) < MIN_KEYS_TO_PUBLISH:
        log(f'✗ живых ключей всего {len(rows)} (< {MIN_KEYS_TO_PUBLISH}) — keys.txt не трогаю')
        return 1

    lines = [f'{n.uri}#{quote(key_name(src, n), safe="")}' for src, n in rows]
    content = build_header() + '\n' + '\n'.join(lines) + '\n'

    by_tag = {tag: sum(1 for s, _ in rows if s.tag == tag) for tag in TAGS}
    for tag, cnt in by_tag.items():
        if cnt == 0 and any(s.tag == tag and nodes for s, nodes in per_source):
            log(f'⚠ {TAGS[tag][0]}: живых не нашлось. Если это ключи под белые списки РФ — '
                f'с зарубежного раннера их часто не проверить (нужен раннер в РФ)')
    log(f'ИТОГО {len(rows)} ключей: WiFi {by_tag["wifi"]} · LTE {by_tag["lte"]} · SNI {by_tag["sni"]}')
    for src, n in rows[:5]:
        log(f'  {key_name(src, n)}')

    return 0 if publish(content, len(rows)) else 1


if __name__ == '__main__':
    sys.exit(main())
