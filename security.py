"""
security.py — Güvenlik yardımcıları
=====================================
Bu modül uygulamanın güvenlik katmanlarını sağlar:
- IP tabanlı rate limiting (hafıza içi dict ile çalışır)
- CSRF token üretimi ve doğrulaması (Double-Submit Cookie yöntemi)
- Tablo adı / sütun adı doğrulama (SQL injection saldırılarına karşı)
- Dosya yükleme güvenlik kontrolü (uzantı + boyut)
- Opsiyonel erişim şifresi middleware'i
"""
import time, re, threading, secrets, os
from functools import wraps
from flask import request, jsonify, session

# ── Rate Limiter (Madde 6: MySQL tabanlı — process-restart ve multi-worker güvenli) ──
#
# Strateji: rate_limit_log tablosuna her istek bir satır yazar; pencere içindeki
# satır sayısını COUNT ile kontrol eder. Bellek yerine MySQL kullandığından:
#   - Uygulama yeniden başlasa da sayaç sıfırlanmaz
#   - Birden fazla worker/process aynı limiti paylaşır
#   - Eski satırlar 10 dakikada bir otomatik temizlenir (TTL mantığı)
#
# DB bağlantısı kurulamazsa sessizce bellek tabanlı fallback'e geçer —
# rate limiting hiçbir zaman isteği engellemez bile olsa uygulama çökmez.

import time as _time
import threading as _threading

# Fallback: DB yoksa bellek tabanlı
_fallback_store: dict = {}
_fallback_lock = _threading.Lock()
_last_cleanup: float = 0.0
_CLEANUP_INTERVAL = 600  # saniye


def _get_ip() -> str:
    from flask import request as _req
    forwarded = _req.headers.get('X-Forwarded-For', '')
    return forwarded.split(',')[0].strip() if forwarded else (_req.remote_addr or 'unknown')


def _db_rate_check(ip: str, endpoint: str, max_calls: int, window_seconds: int) -> bool:
    """
    MySQL rate_limit_log tablosunu kullanarak istek sayısını kontrol eder.
    Döner: True → izin ver, False → limit aşıldı.
    """
    global _last_cleanup
    try:
        import database as _db
        conn = _db.get_connection()
        try:
            with conn.cursor() as cur:
                # Pencere içindeki istek sayısı
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM rate_limit_log "
                    "WHERE ip=%s AND endpoint=%s "
                    "AND hit_at >= NOW(3) - INTERVAL %s SECOND",
                    (ip, endpoint, window_seconds)
                )
                row = cur.fetchone()
                count = row['cnt'] if row else 0

                if count >= max_calls:
                    return False  # limit aşıldı

                # İstek kaydı ekle
                cur.execute(
                    "INSERT INTO rate_limit_log (ip, endpoint) VALUES (%s, %s)",
                    (ip, endpoint)
                )
            conn.commit()

            # Periyodik temizlik: 10 dk'dan eski satırları sil
            now = _time.time()
            if now - _last_cleanup > _CLEANUP_INTERVAL:
                _last_cleanup = now
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM rate_limit_log WHERE hit_at < NOW(3) - INTERVAL 600 SECOND"
                        )
                    conn.commit()
                except Exception:
                    pass
        finally:
            conn.close()
        return True
    except Exception:
        # DB erişim hatası → bellek tabanlı fallback
        return _fallback_rate_check(ip, endpoint, max_calls, window_seconds)


def _fallback_rate_check(ip: str, endpoint: str, max_calls: int, window_seconds: int) -> bool:
    """Bellek tabanlı fallback — sadece DB erişilemediğinde kullanılır."""
    key = f"{ip}:{endpoint}"
    now = _time.time()
    cutoff = now - window_seconds
    with _fallback_lock:
        timestamps = [t for t in _fallback_store.get(key, []) if t > cutoff]
        if len(timestamps) >= max_calls:
            return False
        timestamps.append(now)
        _fallback_store[key] = timestamps
    return True


def rate_limit(max_calls: int, window_seconds: int = 60):
    """
    IP tabanlı istek hızı sınırlayıcı decorator.
    MySQL rate_limit_log tablosunu kullanır; DB yoksa bellek tabanlı fallback.
    Proxy arkasında X-Forwarded-For header'ını da kontrol eder.
    """
    def decorator(f):
        endpoint_name = f.__name__

        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = _get_ip()
            allowed = _db_rate_check(ip, endpoint_name, max_calls, window_seconds)
            if not allowed:
                from flask import Response as _Resp, request as _req
                import json as _json
                accepts = _req.headers.get('Accept', '')
                if 'text/event-stream' in accepts:
                    msg = _json.dumps({
                        'type': 'error',
                        'message': f'Çok fazla istek. Lütfen {window_seconds} saniye bekleyin.'
                    })
                    return _Resp(f'data: {msg}\n\n', mimetype='text/event-stream', status=429)
                return jsonify({
                    'success': False,
                    'message': f'Çok fazla istek. Lütfen {window_seconds} saniye bekleyin.'
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ── CSRF Koruması (Double-Submit Cookie) ─────────────────────────────
def generate_csrf_token() -> str:
    """
    Session başına benzersiz CSRF token üretir.
    Token session'da saklanır; form/JS isteği ile X-CSRF-Token header'ında gönderilir.
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def csrf_protect(f):
    """
    State-changing endpoint'leri (POST/PUT/DELETE) CSRF'ye karşı korur.
    İstemci her mutasyon isteğinde X-CSRF-Token header'ı göndermeli.
    GET/HEAD/OPTIONS isteklerinde kontrol yapılmaz.
    Webhook endpoint'leri bu decorator'ı KULLANMAMALI (dış kaynak POST atar).
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return f(*args, **kwargs)
        token_in_session = session.get('csrf_token', '')
        token_in_header  = request.headers.get('X-CSRF-Token', '')
        token_in_form    = request.form.get('csrf_token', '')
        token_provided   = token_in_header or token_in_form
        if not token_in_session or not secrets.compare_digest(token_in_session, token_provided):
            return jsonify({'success': False, 'message': 'Geçersiz CSRF token.'}), 403
        return f(*args, **kwargs)
    return wrapped


# ── Dosya Yükleme Güvenliği ───────────────────────────────────────────
_ALLOWED_EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm', '.csv'}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # 50 MB
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_excel_upload(file_storage) -> tuple[bool, str]:
    """
    Excel/CSV yüklemesini uzantı ve boyut açısından doğrular.
    Döner: (geçerli_mi, hata_mesajı)
    """
    if not file_storage or not file_storage.filename:
        return False, 'Dosya seçilmedi.'
    filename = file_storage.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXCEL_EXTENSIONS:
        return False, f'Desteklenmeyen dosya türü: {ext}. İzin verilenler: {", ".join(_ALLOWED_EXCEL_EXTENSIONS)}'
    # Boyut kontrolü — stream'i okumadan önce seek
    file_storage.stream.seek(0, 2)   # sona git
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)      # başa dön
    if size > _MAX_UPLOAD_BYTES:
        return False, f'Dosya çok büyük ({size // (1024*1024)} MB). Maksimum: {_MAX_UPLOAD_BYTES // (1024*1024)} MB'
    return True, ''


def validate_attachment(file_storage) -> tuple[bool, str]:
    """
    E-posta eki dosyasını boyut açısından doğrular.
    """
    if not file_storage or not file_storage.filename:
        return True, ''   # Ek isteğe bağlı — yoksa hata değil
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > _MAX_ATTACHMENT_BYTES:
        return False, f'Ek dosyası çok büyük ({size // (1024*1024)} MB). Maksimum: {_MAX_ATTACHMENT_BYTES // (1024*1024)} MB'
    return True, ''


def safe_attachment_filename(filename: str) -> str:
    """
    Path traversal saldırılarına karşı dosya adını temizler.
    werkzeug.utils.secure_filename eşdeğeri — sadece temel ismi alır.
    """
    # Dizin ayırıcıları ve tehlikeli karakterleri kaldır
    filename = os.path.basename(filename.replace('\\', '/'))
    # Sadece güvenli karakterlere izin ver
    filename = re.sub(r'[^\w\.\-]', '_', filename)
    return filename or 'attachment'


# ── Tablo / Sütun Adı Doğrulama (SQL Injection önleme) ───────────────
_SAFE_IDENT = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$')


def safe_identifier(name: str) -> str:
    """
    Tablo veya sütun adının güvenli olup olmadığını doğrular.
    Geçersizse ValueError fırlatır.
    """
    if not name or not _SAFE_IDENT.match(name):
        raise ValueError(
            f"Geçersiz tablo/sütun adı: '{name}'. "
            "Sadece harf, rakam ve _ kullanılabilir."
        )
    return name


# ── Opsiyonel Erişim Şifresi Middleware ──────────────────────────────
def require_local_or_auth(f):
    """
    .env'deki APP_ACCESS_PASSWORD değişkeni tanımlıysa şifre kontrolü yapar.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        pwd = os.getenv('APP_ACCESS_PASSWORD', '').strip()
        if not pwd:
            return f(*args, **kwargs)
        provided = (
            request.headers.get('X-Access-Password', '') or
            request.args.get('pwd', '') or
            (request.json.get('pwd', '') if request.is_json else '')
        )
        if not secrets.compare_digest(pwd, provided):
            return jsonify({'success': False, 'message': 'Yetkisiz erişim.'}), 401
        return f(*args, **kwargs)
    return wrapped
