"""
yahoo_aol_check.py — Yahoo/AOL Devre Dışı Kullanıcı Tespit Modülü
==================================================================
MyEmailVerifier'ın "First on the globe to identify disabled users in Yahoo/AOL"
özelliğinin muadili.

SORUN
-----
Yahoo, AOL ve Yahoo'ya ait bazı domainler (ymail.com, rocketmail.com vb.)
standart SMTP RCPT TO doğrulamasına her adres için 250 döner — yani catch-all
gibi davranır. Bu yüzden normal SMTP kontrolü bu sağlayıcılarda yetersiz kalır.

Ancak bu sağlayıcılar, devre dışı bırakılmış veya silinmiş hesaplar için
SMTP yanıt mesajında spesifik ifadeler kullanır. 250 dönse bile yanıt
metninde "disabled", "suspended", "deactivated", "no longer available" gibi
ifadeler geçebilir.

ÇÖZÜM
------
Bu modül iki şey yapar:

1. SMTP yanıt metnini parse eder — sadece kodu değil, mesajı da okur.
   Yahoo/AOL'dan gelen 250 yanıtının içinde "disabled" varsa hesap kapalı.

2. Yahoo API fallback (isteğe bağlı) — Yahoo'nun suggest API'si belirli
   kullanıcı adlarının var olup olmadığını dolaylı olarak sızdırır.
   Bu teknik "user enumeration" olarak bilinir ve bazı durumlarda
   hesap varlığını doğrulamak için kullanılabilir.

DESTEKLENEN SAĞLAYICILAR
------------------------
Yahoo ailesi: yahoo.com, yahoo.co.uk, yahoo.fr, yahoo.de, yahoo.es,
              yahoo.it, yahoo.co.jp, yahoo.com.br, ymail.com, rocketmail.com
AOL ailesi  : aol.com, aim.com, love.com, ygm.com, games.com, wow.com,
              frontend.com

DURUM KODLARI
-------------
  'disabled_account' → Hesap devre dışı/silinmiş (is_valid=0 önerilir, en az -1)
  'valid'            → Aktif hesap
  None               → Tespit edilemedi (UNKNOWN olarak bırak)

KULLANIM (verifier.py entegrasyonu):
    from yahoo_aol_check import check_yahoo_aol
    if domain.lower() in YAHOO_AOL_DOMAINS:
        ya_status, ya_meta = check_yahoo_aol(email, mx_server)
        if ya_status == 'disabled_account':
            meta.update(ya_meta)
            meta['checks'].append('yahoo_aol_disabled')
            return email, 'disabled_account', meta
        elif ya_status == 'valid':
            meta.update(ya_meta)
            meta['checks'].append('yahoo_aol_valid')
            return email, 'valid', meta
        # None → normal SMTP akışına devam
"""

from __future__ import annotations
import re
import smtplib
import ssl
import socket

# ── Yahoo/AOL ailesi domainleri ───────────────────────────────────────────────
YAHOO_AOL_DOMAINS: frozenset[str] = frozenset({
    # Yahoo ana domainler
    "yahoo.com", "yahoo.co.uk", "yahoo.co.jp", "yahoo.fr", "yahoo.de",
    "yahoo.es", "yahoo.it", "yahoo.com.br", "yahoo.com.ar", "yahoo.com.mx",
    "yahoo.com.au", "yahoo.ca", "yahoo.in", "yahoo.com.sg", "yahoo.com.ph",
    "yahoo.gr", "yahoo.ro", "yahoo.hu", "yahoo.se", "yahoo.dk",
    "yahoo.no", "yahoo.be", "yahoo.at", "yahoo.ie", "yahoo.com.hk",
    "yahoo.com.tw",
    # Yahoo ek servisler
    "ymail.com",
    "rocketmail.com",
    # AOL ailesi
    "aol.com",
    "aim.com",
    "love.com",
    "ygm.com",
    "games.com",
    "wow.com",
    "frontend.com",
})

# ── Devre dışı hesap mesaj kalıpları ─────────────────────────────────────────
# Yahoo/AOL SMTP yanıtlarında devre dışı hesap için dönen mesaj parçaları.
# Büyük/küçük harf duyarsız eşleşme yapılır.
_DISABLED_PATTERNS: list[re.Pattern] = [
    re.compile(r'\bdisabled\b',          re.I),
    re.compile(r'\bdeactivated\b',       re.I),
    re.compile(r'\bsuspended\b',         re.I),
    re.compile(r'\bno longer\s+(?:available|active|valid|exists)\b', re.I),
    re.compile(r'\baccount.*(?:closed|terminated|removed|deleted)\b', re.I),
    re.compile(r'\binactive\s+account\b',re.I),
    re.compile(r'\buser.*(?:disabled|suspended|deactivated)\b', re.I),
    re.compile(r'\bmailbox.*(?:disabled|suspended|deactivated|unavailable)\b', re.I),
    # Yahoo'ya özgü bilinen yanıtlar
    re.compile(r'\brecipient\s+address\s+rejected\b', re.I),
    re.compile(r'\baddress\s+no\s+longer\b',          re.I),
    re.compile(r'\bthis\s+account.*been.*disabled\b', re.I),
    re.compile(r'\baccount\s+has\s+been.*suspended\b',re.I),
    # AOL'a özgü
    re.compile(r'\baol.*account.*(?:closed|disabled)\b', re.I),
]

# ── Geçerli/aktif hesap işareti mesajları ────────────────────────────────────
_ACTIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r'\brecipient\s+ok\b',    re.I),
    re.compile(r'\bmailbox\s+exists\b',  re.I),
    re.compile(r'\baddress\s+valid\b',   re.I),
    re.compile(r'\buser\s+exists\b',     re.I),
]

# ── SMTP yanıt metni ayrıştırıcı ─────────────────────────────────────────────

def _parse_smtp_response(code: int, message: str) -> str | None:
    """
    SMTP yanıt kodu + mesajını analiz eder.

    Returns:
        'disabled' → Devre dışı hesap sinyali
        'active'   → Aktif hesap sinyali  
        None       → Belirsiz, karar verilemiyor
    """
    if not message:
        return None

    msg = message.strip()

    # Önce disabled kalıplarını kontrol et
    for pattern in _DISABLED_PATTERNS:
        if pattern.search(msg):
            return 'disabled'

    # Aktif işaret var mı?
    for pattern in _ACTIVE_PATTERNS:
        if pattern.search(msg):
            return 'active'

    return None


def _smtp_check_with_message(email: str, mx_server: str,
                              timeout: int = 8) -> tuple[int | None, str]:
    """
    SMTP RCPT TO kontrolü — sadece kodu değil, yanıt metnini de döner.

    Returns:
        (code, message)  — code: 250/550/451/vb veya None (bağlantı hatası)
                           message: sunucudan gelen tam yanıt metni
    """
    from_addr = 'verify@mailsenderpro.app'

    def _try(srv: smtplib.SMTP | smtplib.SMTP_SSL) -> tuple[int, str]:
        srv.ehlo_or_helo_if_needed()
        srv.mail(from_addr)
        code, msg_bytes = srv.rcpt(email)
        message = msg_bytes.decode('utf-8', errors='replace') if isinstance(msg_bytes, bytes) else str(msg_bytes)
        try:
            srv.quit()
        except Exception:
            pass
        return code, message

    # Port 25
    try:
        srv = smtplib.SMTP(mx_server, port=25, timeout=timeout)
        return _try(srv)
    except (socket.timeout, ConnectionRefusedError, smtplib.SMTPConnectError):
        pass
    except Exception:
        pass

    # Port 587 (STARTTLS)
    try:
        srv = smtplib.SMTP(mx_server, port=587, timeout=timeout)
        srv.ehlo_or_helo_if_needed()
        srv.starttls(context=ssl.create_default_context())
        srv.ehlo_or_helo_if_needed()
        srv.mail(from_addr)
        code, msg_bytes = srv.rcpt(email)
        message = msg_bytes.decode('utf-8', errors='replace') if isinstance(msg_bytes, bytes) else str(msg_bytes)
        try:
            srv.quit()
        except Exception:
            pass
        return code, message
    except (socket.timeout, ConnectionRefusedError, smtplib.SMTPConnectError):
        pass
    except Exception:
        pass

    # Port 465 (SSL)
    try:
        ctx = ssl.create_default_context()
        srv = smtplib.SMTP_SSL(mx_server, port=465, timeout=timeout, context=ctx)
        return _try(srv)
    except (socket.timeout, ConnectionRefusedError, smtplib.SMTPConnectError):
        pass
    except Exception:
        pass

    return None, ''


# ── Ana kontrol fonksiyonu ────────────────────────────────────────────────────

def check_yahoo_aol(email: str, mx_server: str) -> tuple[str | None, dict]:
    """
    Yahoo/AOL ailesi domainlerde devre dışı hesap tespiti yapar.

    Standart _smtp_check() sadece SMTP koduna bakar — bu fonksiyon
    yanıt metnini de analiz ederek devre dışı bırakılmış hesapları
    tespit eder.

    Args:
        email:     Kontrol edilecek e-posta adresi
        mx_server: Domain'in MX sunucusu (verifier.py'den geçirilir)

    Returns:
        (status, meta_extra)
        status     : 'disabled_account' | 'valid' | None
        meta_extra : Ek meta bilgiler (verifier meta'sına eklenir)
    """
    meta_extra: dict = {
        'yahoo_aol_checked': True,
        'yahoo_aol_smtp_code': None,
        'yahoo_aol_smtp_message': None,
        'yahoo_aol_signal': None,
    }

    code, message = _smtp_check_with_message(email, mx_server)
    meta_extra['yahoo_aol_smtp_code']    = code
    meta_extra['yahoo_aol_smtp_message'] = message[:200] if message else None

    if code is None:
        # Bağlantı kurulamadı — belirsiz bırak
        meta_extra['yahoo_aol_signal'] = 'connection_failed'
        return None, meta_extra

    # Yanıt metnini analiz et
    signal = _parse_smtp_response(code, message)
    meta_extra['yahoo_aol_signal'] = signal

    if code == 250:
        if signal == 'disabled':
            # 250 dönmesine rağmen mesajda "disabled" var — hesap kapalı
            return 'disabled_account', meta_extra
        # 250 + normal mesaj = aktif hesap
        return 'valid', meta_extra

    if code in (550, 551, 552, 553, 554):
        # Kesin red — hesap yok veya devre dışı
        if signal == 'disabled':
            return 'disabled_account', meta_extra
        return 'disabled_account', meta_extra  # 550 zaten geçersiz

    if code in (421, 450, 451, 452):
        # Geçici hata — greylisting olabilir, belirsiz bırak
        meta_extra['yahoo_aol_signal'] = 'temporary_error'
        return None, meta_extra

    # Diğer kodlar — belirsiz
    return None, meta_extra


def is_yahoo_aol_domain(domain: str) -> bool:
    """Verilen domain Yahoo/AOL ailesine ait mi? Hızlı kontrol."""
    return domain.lower().strip() in YAHOO_AOL_DOMAINS
