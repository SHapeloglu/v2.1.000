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

# ── Rate Limiter ──────────────────────────────────────────────────────
_rate_store: dict = {}
_rate_lock = threading.Lock()


def _clean_old(timestamps: list, window: int) -> list:
    cutoff = time.time() - window
    return [t for t in timestamps if t > cutoff]


def rate_limit(max_calls: int, window_seconds: int = 60):
    """
    IP tabanlı istek hızı sınırlayıcı decorator.
    Proxy arkasında X-Forwarded-For header'ını da kontrol eder.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Proxy arkasında gerçek IP'yi al
            forwarded = request.headers.get('X-Forwarded-For', '')
            ip = forwarded.split(',')[0].strip() if forwarded else (request.remote_addr or 'unknown')
            now = time.time()
            with _rate_lock:
                timestamps = _clean_old(_rate_store.get(ip, []), window_seconds)
                if len(timestamps) >= max_calls:
                    from flask import Response as _Resp
                    import json as _json
                    accepts = request.headers.get('Accept', '')
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
                timestamps.append(now)
                _rate_store[ip] = timestamps
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
