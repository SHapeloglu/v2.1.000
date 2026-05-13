"""
dnsbl_check.py — DNSBL / RBL IP Kara Liste Kontrolü
=====================================================
Bir IP adresinin bilinen DNS kara listelerinde (DNSBL/RBL) kayıtlı
olup olmadığını kontrol eder.

NASIL ÇALIŞIR
--------------
DNSBL sorgusu standart bir DNS A kaydı sorgusudur:
  - IP: 1.2.3.4  →  sorgu: 4.3.2.1.dnsbl.example.com
  - Yanıt 127.x.x.x dönerse IP listede → kara listede
  - NXDOMAIN dönerse IP listede değil → temiz

KULLANIM
--------
from dnsbl_check import check_ip, check_smtp_host

# IP ile direkt kontrol
result = check_ip('1.2.3.4')

# SMTP hostname ile kontrol (DNS çözümlemesi yapılır)
result = check_smtp_host('mail.example.com')

# Sonuç yapısı:
# {
#   'ip':        '1.2.3.4',
#   'listed':    True | False,
#   'hits':      [{'rbl': 'zen.spamhaus.org', 'response': '127.0.0.2', 'severity': 'critical'}],
#   'clean':     ['backscatterer.org', ...],
#   'checked_at': '2024-01-15 10:30:00',
#   'severity':  'critical' | 'high' | 'medium' | 'low' | 'clean'
# }

ENTEGRASYON
-----------
1. app.py → /api/senders/dnsbl-check endpoint'i (manuel kontrol)
2. mailer.py → send_one() / send_via_ses() öncesi uyarı logu
   (gönderimi engellemez — sadece uyarır, DB'ye kaydeder)
"""

from __future__ import annotations
import socket
import datetime
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── DNSBL Listesi ─────────────────────────────────────────────────────────────
# severity: critical → kesinlikle kara listede (gönderimi etkiler)
#           high     → önemli RBL, dikkat edilmeli
#           medium   → orta önem
#           low      → bilgi amaçlı
DNSBL_LISTS: list[dict] = [
    # ── Spamhaus (en kritik) ──────────────────────────────────────────────────
    {'rbl': 'zen.spamhaus.org',         'severity': 'critical',
     'desc': 'Spamhaus ZEN (SBL+XBL+PBL birleşik)'},
    {'rbl': 'sbl.spamhaus.org',         'severity': 'critical',
     'desc': 'Spamhaus SBL — spam kaynakları'},
    {'rbl': 'xbl.spamhaus.org',         'severity': 'critical',
     'desc': 'Spamhaus XBL — exploit/botnet'},
    {'rbl': 'pbl.spamhaus.org',         'severity': 'high',
     'desc': 'Spamhaus PBL — ISP dinamik IP\'leri'},

    # ── Barracuda ────────────────────────────────────────────────────────────
    {'rbl': 'b.barracudacentral.org',   'severity': 'critical',
     'desc': 'Barracuda Reputation Block List'},

    # ── SpamCop ──────────────────────────────────────────────────────────────
    {'rbl': 'bl.spamcop.net',           'severity': 'high',
     'desc': 'SpamCop Blocking List'},

    # ── SORBS ────────────────────────────────────────────────────────────────
    {'rbl': 'dnsbl.sorbs.net',          'severity': 'medium',
     'desc': 'SORBS birleşik listesi'},
    {'rbl': 'spam.dnsbl.sorbs.net',     'severity': 'high',
     'desc': 'SORBS spam kaynakları'},

    # ── NordSpam / Abusix ────────────────────────────────────────────────────
    {'rbl': 'all.s5h.net',              'severity': 'medium',
     'desc': 'Abusix Mail Intelligence'},

    # ── UCEProtect ───────────────────────────────────────────────────────────
    {'rbl': 'dnsbl-1.uceprotect.net',   'severity': 'high',
     'desc': 'UCEProtect Level 1 — bireysel IP'},
    {'rbl': 'dnsbl-2.uceprotect.net',   'severity': 'medium',
     'desc': 'UCEProtect Level 2 — subnet'},

    # ── MultiRBL / Composite ─────────────────────────────────────────────────
    {'rbl': 'dnsbl.justspam.org',       'severity': 'medium',
     'desc': 'JustSpam DNSBL'},
    {'rbl': 'ix.dnsbl.manitu.net',      'severity': 'low',
     'desc': 'Manitu NiX Spam'},
]

# Şiddet sıralaması (en kötü → en iyi)
_SEVERITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'clean': 4}

# Önbellak: {ip: (result_dict, expire_monotonic)}
_dnsbl_cache: dict = {}
_CACHE_TTL = 3600  # 1 saat


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def _reverse_ip(ip: str) -> str:
    """'1.2.3.4' → '4.3.2.1'"""
    return '.'.join(reversed(ip.split('.')))


def _check_single_rbl(reversed_ip: str, rbl_entry: dict, timeout: float = 3.0) -> dict | None:
    """
    Tek bir RBL için DNS sorgusu yapar.
    Listede ise {'rbl': ..., 'response': ..., 'severity': ...} döner.
    Temizse None döner.
    """
    query = f"{reversed_ip}.{rbl_entry['rbl']}"
    try:
        response = socket.getaddrinfo(query, None, socket.AF_INET)
        if response:
            ip_resp = response[0][4][0]
            # 127.x.x.x → gerçek DNSBL yanıtı
            if ip_resp.startswith('127.'):
                return {
                    'rbl':      rbl_entry['rbl'],
                    'desc':     rbl_entry['desc'],
                    'response': ip_resp,
                    'severity': rbl_entry['severity'],
                }
    except (socket.gaierror, socket.herror, OSError):
        pass  # NXDOMAIN veya timeout → temiz
    return None


def _resolve_hostname_to_ip(hostname: str, timeout: float = 5.0) -> str | None:
    """Hostname'i IPv4 adresine çevirir."""
    try:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        result = socket.gethostbyname(hostname)
        socket.setdefaulttimeout(old_timeout)
        return result
    except Exception:
        return None


def _is_private_ip(ip: str) -> bool:
    """Özel/loopback IP'leri DNSBL'e gönderme."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


# =============================================================================
# ANA KONTROL FONKSİYONLARI
# =============================================================================

def check_ip(
    ip:           str,
    lists:        list[dict] | None = None,
    max_workers:  int  = 10,
    timeout:      float = 3.0,
    use_cache:    bool = True,
) -> dict:
    """
    Verilen IP adresini DNSBL listelerinde kontrol eder.

    Args:
        ip:          IPv4 adresi
        lists:       Kontrol edilecek RBL listesi (None = DNSBL_LISTS)
        max_workers: Paralel DNS sorgusu sayısı
        timeout:     Her DNS sorgusu için timeout (saniye)
        use_cache:   Önbellekten oku/yaz

    Returns:
        {
            'ip':         str,
            'listed':     bool,
            'hits':       list[{rbl, desc, response, severity}],
            'clean':      list[str],   — temiz bulunan RBL adları
            'checked_at': str,
            'severity':   str,         — en kötü hit'in severity'si
            'cached':     bool,
        }
    """
    import time as _time

    ip = ip.strip()
    lists = lists or DNSBL_LISTS

    # Önbellak kontrolü
    if use_cache:
        entry = _dnsbl_cache.get(ip)
        if entry:
            result, expire_ts = entry
            if _time.monotonic() < expire_ts:
                result_copy = dict(result)
                result_copy['cached'] = True
                return result_copy

    # Özel IP kontrolü
    if _is_private_ip(ip):
        return {
            'ip': ip, 'listed': False, 'hits': [], 'clean': [],
            'checked_at': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'severity': 'clean', 'cached': False,
            'note': 'Özel/loopback IP — DNSBL kontrolü atlandı',
        }

    reversed_ip = _reverse_ip(ip)
    hits:  list[dict] = []
    clean: list[str]  = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_map = {
            ex.submit(_check_single_rbl, reversed_ip, rbl, timeout): rbl
            for rbl in lists
        }
        for future in as_completed(future_map):
            rbl_entry = future_map[future]
            try:
                result = future.result()
                if result:
                    hits.append(result)
                else:
                    clean.append(rbl_entry['rbl'])
            except Exception:
                clean.append(rbl_entry['rbl'])

    # En kötü severity'yi bul
    if hits:
        worst = min(hits, key=lambda h: _SEVERITY_RANK.get(h['severity'], 99))
        severity = worst['severity']
    else:
        severity = 'clean'

    checked_at = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    output = {
        'ip':         ip,
        'listed':     len(hits) > 0,
        'hits':       sorted(hits, key=lambda h: _SEVERITY_RANK.get(h['severity'], 99)),
        'clean':      sorted(clean),
        'checked_at': checked_at,
        'severity':   severity,
        'cached':     False,
    }

    # Önbelleğe yaz
    if use_cache:
        import time as _time2
        _dnsbl_cache[ip] = (output, _time2.monotonic() + _CACHE_TTL)

    return output


def check_smtp_host(
    smtp_host:   str,
    **kwargs
) -> dict:
    """
    SMTP hostname'ini DNS'e çözümleyip DNSBL kontrolü yapar.

    Returns:
        check_ip() çıktısı + 'hostname' alanı
    """
    ip = _resolve_hostname_to_ip(smtp_host)
    if not ip:
        return {
            'ip': None, 'hostname': smtp_host,
            'listed': False, 'hits': [], 'clean': [],
            'checked_at': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'severity': 'clean', 'cached': False,
            'error': f"'{smtp_host}' için IP çözümlenemedi",
        }
    result = check_ip(ip, **kwargs)
    result['hostname'] = smtp_host
    return result


def check_sender_row(sender_row: dict) -> dict | None:
    """
    Bir sender kaydının SMTP sunucusunu DNSBL'e karşı kontrol eder.
    sender_row['smtp_server'] varsa kontrol eder, yoksa None döner.
    """
    smtp_host = (sender_row.get('smtp_server') or '').strip()
    if not smtp_host:
        return None
    return check_smtp_host(smtp_host)


def summarize(result: dict) -> str:
    """
    DNSBL sonucunu tek satır özet olarak döner (log için).
    Örn: "1.2.3.4 — 2 kara listede! (critical: zen.spamhaus.org)"
    """
    if not result.get('listed'):
        return f"{result.get('ip')} — tüm DNSBL listelerinde temiz"
    hits = result.get('hits', [])
    worst = hits[0] if hits else {}
    return (
        f"{result.get('ip')} — {len(hits)} kara listede! "
        f"({worst.get('severity')}: {worst.get('rbl')})"
    )
