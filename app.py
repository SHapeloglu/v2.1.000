"""
app.py — MailSender Pro Flask Uygulaması
=========================================
Tüm HTTP route'ları ve API endpoint'leri bu dosyada tanımlıdır.

BÖLÜMLER:
  1. Başlangıç        — Flask kurulumu, secret_key, .env yükleme
  2. Güvenlik         — HTTP güvenlik header'ları, HTTPS yönlendirme
  3. Auth             — login_required / admin_required decorator'ları,
                        giriş/çıkış route'ları, context_processor
  4. Sayfa route'ları — HTML sayfaları render eden GET route'lar
  5. DB API           — Veritabanı bağlantı ayarları endpoint'leri
  6. Senders API      — Gönderici CRUD + test + SES kota endpoint'leri
  7. Rules API        — Gönderim kuralı CRUD endpoint'leri
  8. Send API         — Tek mail, Excel toplu, DB toplu gönderim (SSE stream)
  9. Tablo API        — Excel→DB aktarım, tablo listeleme/önizleme
 10. Suppression API  — Suppression listesi CRUD + purge endpoint'leri
 11. Şablon API       — Konu/mesaj şablonu CRUD endpoint'leri
 12. Kullanıcı API    — Kullanıcı yönetimi (admin) + şifre değiştirme
 13. Kuyruk API       — Hosting modu kuyruk yönetimi endpoint'leri
 14. Unsubscribe API  — Token doğrulama ve abonelik iptali
 15. EC2 API          — AWS EC2 durdurma (auto-stop) endpoint'leri
 16. Uygulama başlatma — auto_migrate, before_request hook'ları

ÖNEMLİ NOTLAR:
  - SEND_MODE=local    → SSE (Server-Sent Events) ile canlı akış
  - SEND_MODE=hosting  → Kuyruk sistemi, worker.py cPanel cron ile çalışır
  - rate_limit()       → Kötüye kullanıma karşı IP başına istek sınırı
  - @login_required    → Oturumu olmayan kullanıcıyı login sayfasına yönlendirir
  - @admin_required    → Sadece admin rolündeki kullanıcılara izin verir
"""
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session
import os, io, time, json, pathlib, datetime, functools, re
import pandas as pd
from dotenv import load_dotenv, set_key   # .env okuma ve güncelleme
# Gönderim fonksiyonları
from mailer import (send_one, plain_to_html, render_template_str,
                    smtp_connect, build_message, send_via_ses, send_via_api,
                    test_sender, test_api_sender)
from security import (rate_limit, safe_identifier, csrf_protect,
                       generate_csrf_token, validate_excel_upload,
                       validate_attachment, safe_attachment_filename)  # Güvenlik yardımcıları
from version import VERSION_SHORT, VERSION          # Uygulama versiyon bilgisi

# .env dosyasının tam yolu — set_key() ile güncelleme için kullanılır
ENV_PATH = pathlib.Path(__file__).parent / '.env'
load_dotenv(ENV_PATH)  # Ortam değişkenlerini yükle

app = Flask(__name__)
# Session şifreleme anahtarı — .env'de SECRET_KEY tanımlı olmalı
# Tanımlı değilse rastgele üretilir (yeniden başlatmada oturumlar sıfırlanır)
_secret = os.getenv('SECRET_KEY', '')
if not _secret:
    import warnings
    warnings.warn(
        "SECRET_KEY tanımlanmamış! .env dosyasına SECRET_KEY ekleyin. "
        "Tanımsız bırakılırsa her yeniden başlatmada oturumlar sıfırlanır.",
        RuntimeWarning, stacklevel=2
    )
    _secret = os.urandom(32)
app.secret_key = _secret
# Oturum süresi: 8 saat — uzun süreli açık bağlantı riskini azaltır
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=8)

# ── Güvenlik Header'ları ───────────────────────────────────────────────
@app.after_request
def add_security_headers(response):
    """
    Her HTTP yanıtına güvenlik header'ları ekler.
    Bu header'lar yaygın web saldırılarına karşı ilk savunma hattını oluşturur.
    """
    # Tarayıcının MIME türünü tahmin etmesini engelle (MIME sniffing saldırısı)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Clickjacking koruması
    response.headers['X-Frame-Options'] = 'DENY'
    # XSS filtresi (eski tarayıcılar için)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer bilgisini kısıtla
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # HTTPS kullanıyorsan HSTS aktif olur (HTTP'de zararsız)
    if os.getenv('FORCE_HTTPS', 'false').lower() == 'true':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # Content-Security-Policy — XSS son savunma hattı
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    # Cache: API yanıtları önbelleğe alınmasın
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
    return response

# ── HTTPS Yönlendirme (FORCE_HTTPS=true ise) ─────────────────────────
@app.before_request
def force_https_redirect():
    """
    FORCE_HTTPS=true ise tüm HTTP isteklerini HTTPS'ye yönlendirir.
    Proxy arkasında çalışırken X-Forwarded-Proto header'ını kontrol eder.
    301 yönlendirme: tarayıcı bir sonraki istekte doğrudan HTTPS kullanır.
    """
    if os.getenv('FORCE_HTTPS', 'false').lower() == 'true':
        # request.is_secure: doğrudan TLS bağlantısı
        # X-Forwarded-Proto: proxy/load balancer'dan geçen HTTPS isteği
        if not request.is_secure and request.headers.get('X-Forwarded-Proto', 'http') != 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)  # Kalıcı yönlendirme

# ── Veritabanı modülü geç yükleme (lazy import) ─────────────────────
# database.py'yi modül seviyesinde import etmek yerine her çağrıda içe aktarır.
# Bu sayede DB bağlantısı olmadan uygulama başlayabilir (DB ayarları henüz yoksa).
def db():
    """database modülünü döner. Geç yükleme sayesinde DB olmadan da uygulama çalışır."""
    import database
    return database


# ══════════════════════════════════════════════════════════════════════
#  AUTH — Giriş / Çıkış / Decorator
# ══════════════════════════════════════════════════════════════════════

def login_required(f):
    """
    Oturum açılmamış kullanıcıları engeller.
    - API isteği (/api/*) ise 401 JSON yanıtı döner
    - Sayfa isteği ise /auth/login'e yönlendirir, ?next=<url> ile geri dönmeyi sağlar
    functools.wraps: orijinal fonksiyon adını ve docstring'ini korur.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        """Decorator sarmalayıcısı — orijinal fonksiyonu çağırır."""
        if not session.get('user_id'):
            # API çağrıları için JSON hata yanıtı
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Oturum acilmamis.'}), 401
            # Sayfa çağrıları için login'e yönlendir, başarılı girişten sonra buraya dön
            return redirect('/auth/login?next=' + request.path)
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """
    Sadece admin rolündeki kullanıcılara izin verir.
    Oturum yoksa login'e, oturum varsa ama admin değilse 403 döner.
    Kullanıcı yönetimi sayfaları ve endpoint'leri için kullanılır.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        """Admin yetkisi kontrolü yapar, yetersizse 403 döner."""
        if not session.get('user_id'):
            return redirect('/auth/login')
        if session.get('user_role') != 'admin':
            return jsonify({'success': False, 'message': 'Admin yetkisi gerekli.'}), 403
        return f(*args, **kwargs)
    return decorated

def ensure_admin_exists():
    """
    Hiç kullanıcı yoksa varsayılan admin hesabı oluşturur.
    Uygulama her başlangıcında auto_migrate() tarafından çağrılır.
    İlk kullanımda admin/admin123 oluşturulur — kullanıcı hemen değiştirmeli!
    DB bağlantısı yoksa sessizce atlanır (kritik değil).
    """
    try:
        if db().user_count() == 0:
            db().user_create('admin', 'admin123', role='admin')
            print("UYARI: admin/admin123 olusturuldu - HEMEN degistirin!")
            print("UYARI: Guvenlik icin ilk giriste sifrenizi degistirin.")
    except Exception:
        pass  # DB henüz yapılandırılmamışsa atla

@app.route('/auth/login', methods=['GET'])
def login_page():
    """
    Login sayfasını gösterir.
    Zaten oturum açıksa ana sayfaya yönlendirir.
    setup_mode: hiç kullanıcı yoksa True (ilk kurulum notu gösterilir).
    """
    if session.get('user_id'):
        return redirect('/')  # Zaten oturum açık — yeniden giriş gerekmez
    try:
        setup_mode = db().user_count() == 0  # İlk kurulum kontrolü
    except Exception:
        setup_mode = True  # DB erişilemiyorsa setup modunu göster
    return render_template('login.html', setup_mode=setup_mode)

@app.route('/auth/login', methods=['POST'])
@rate_limit(10, 60)  # Brute-force koruması: dakikada 10 deneme
def login_post():
    """
    JSON ile gönderilen kullanıcı adı/şifre çiftini doğrular.
    Başarılıysa session'ı doldurur ve yönlendirme URL'si döner.
    session.permanent=True: tarayıcı kapanınca oturum sona ermez.
    """
    data     = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    # Boş alan kontrolü
    if not username or not password:
        return jsonify({'success': False, 'message': 'Kullanici adi ve sifre gerekli.'})

    # DB'de doğrulama — başarısızsa None döner
    user = db().user_authenticate(username, password)
    if not user:
        return jsonify({'success': False, 'message': 'Kullanici adi veya sifre hatali.'})

    # Session fixation koruması — yeni oturumda eski session verilerini temizle
    old_csrf = session.get('csrf_token')  # CSRF token'ı koru (yenisi üretilecek)
    session.clear()
    if old_csrf:
        session['csrf_token'] = old_csrf
    # Oturumu doldur — bu veriler @login_required ve @admin_required tarafından kullanılır
    session.permanent = True
    session['user_id']   = user['id']       # Birincil anahtar
    session['username']  = user['username'] # Sidebar'da göstermek için
    session['user_role'] = user['role']     # 'admin' veya 'editor'
    session['user_theme'] = user.get('theme', 'charcoal')  # DB'den kullanıcı teması

    # Login öncesi ziyaret etmek istediği sayfa varsa oraya yönlendir
    next_url = request.args.get('next', '/')
    return jsonify({'success': True, 'redirect': next_url})

@app.route('/auth/logout')
def logout():
    """Oturumu tamamen temizler ve login sayfasına yönlendirir."""
    session.clear()  # Tüm session verilerini sil
    return redirect('/auth/login')

# ── Audit Log Yardımcıları ─────────────────────────────────────────────────
def _client_ip() -> str:
    """İstemci IP adresini döner. Proxy arkasında X-Forwarded-For header'ı kullanılır."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

def _audit(action: str, target_type: str = '', target_id=None, detail: str = ''):
    """
    Kullanıcı eylemini audit_log tablosuna kaydeder.
    session'dan kullanıcı bilgisini otomatik alır.
    action örnekleri: 'user_create', 'sender_update', 'excel_upload', 'bulk_start'
    """
    try:
        db().audit(
            user_id     = session.get('user_id'),
            username    = session.get('username', ''),
            action      = action,
            target_type = target_type,
            target_id   = str(target_id) if target_id is not None else '',
            detail      = detail,
            ip_address  = _client_ip(),
        )
    except Exception as e:
        print(f"[_audit] {e}")  # Audit hatası uygulamayı durdurmamalı


@app.context_processor
def inject_user():
    """
    Tüm Jinja2 şablonlarına 'current_user', 'app_version' ve 'help' enjekte eder.
    'help': mevcut endpoint'e göre help_content.HELP'ten otomatik seçilir.
    None ise base.html ? butonu gösterilmez.
    """
    from help_content import HELP
    endpoint  = request.endpoint or ''
    help_data = HELP.get(endpoint)
    return {
        'current_user': {
            'id':       session.get('user_id'),
            'username': session.get('username', ''),
            'role':     session.get('user_role', ''),
            'theme':    session.get('user_theme', 'charcoal'),
        },
        'app_version': VERSION_SHORT,
        'help':        help_data,
        'csrf_token':  generate_csrf_token(),   # Tüm şablonlarda {{ csrf_token }} ile erişilir
    }

# ══════════════════════════════════════════════════════════════════════
#  SAYFA ROUTE'LARI
# ══════════════════════════════════════════════════════════════════════

@app.route('/')
@login_required
def index():
    """
    Ana sayfa — DB yapılandırılmışsa bulk-send'e, yoksa DB ayarları sayfasına yönlendirir.
    İlk kurulumda kullanıcıyı otomatik olarak DB ayarlarına götürür.
    """
    # Zorunlu DB değişkenleri var mı?
    db_configured = all([os.getenv('DB_HOST'), os.getenv('DB_USER'), os.getenv('DB_NAME')])
    if not db_configured:
        return redirect(url_for('settings_db'))   # DB ayarları yapılmamış → ayarlar sayfası
    return redirect(url_for('bulk_send_page'))    # Her şey tamam → toplu gönderim

@app.route('/single-send')
@login_required
def single_send_page():
    """Tek mail gönderim sayfasını render eder."""
    return render_template('pages/single-send.html')

@app.route('/bulk-send')
@login_required
def bulk_send_page():
    """Toplu mail gönderim sayfasını render eder."""
    return render_template('pages/bulk-send.html')

@app.route('/send-log')
@login_required
def send_log_page():
    """Gönderim geçmişi sayfasını render eder."""
    return render_template('pages/send-log.html')

@app.route('/settings')
@login_required
def settings_page():
    """Ayarlar ana sayfasını ilk sekmeye yönlendirir."""
    return redirect(url_for('settings_smtp'))

@app.route('/settings/senders')
@login_required
def settings_senders():
    """Gönderici listesi sayfasını render eder."""
    return redirect(url_for('settings_smtp'))

@app.route('/settings/senders/smtp')
@login_required
def settings_smtp():
    """SMTP gönderici ayarları sayfasını render eder."""
    return render_template('pages/settings/smtp.html')

@app.route('/settings/senders/ses')
@login_required
def settings_ses():
    """AWS SES gönderici ayarları sayfasını render eder."""
    return render_template('pages/settings/ses.html')

@app.route('/settings/senders/api')
@login_required
def settings_api_senders():
    """API gönderici ayarları sayfasını render eder."""
    return render_template('pages/settings/api.html')

@app.route('/settings/rules')
@login_required
def settings_rules():
    """Gönderim kuralları sayfasını render eder."""
    return render_template('pages/settings/rules.html')

@app.route('/settings/db')
@login_required
def settings_db():
    """Veritabanı ayarları sayfasını render eder."""
    return render_template('pages/settings/db.html')

@app.route('/settings/users')
@admin_required   # Sadece admin erişebilir — editor rolündekiler 403 alır
def settings_users():
    """Kullanıcı yönetimi sayfasını render eder (admin only)."""
    return render_template('pages/settings/users.html')

@app.route('/settings/subscription')
@login_required
def settings_subscription():
    """Abonelik ve suppression ayarları sayfasını render eder."""
    return render_template('pages/settings/subscription.html')

@app.route('/settings/theme')
@login_required
def settings_theme():
    """Tema ayarları sayfasını render eder."""
    return render_template('pages/settings/theme.html')

@app.route('/unsubscribe')
def unsubscribe_page():
    """
    Unsubscribe onay sayfası — @login_required YOK, herkes erişebilir.
    Mail içindeki link buraya gelir: /unsubscribe?token=<jwt-token>
    Token geçerliyse e-posta suppression listesine eklenir.
    """
    token = request.args.get('token', '')
    return render_template('unsubscribe.html', token=token)

# ══════════════════════════════════════════════════════════════════════
#  API ROUTE'LARI
# ══════════════════════════════════════════════════════════════════════

# ─── DB API ───────────────────────────────────────────────────────────
@app.route('/api/db-config', methods=['GET'])
@login_required
def get_db_config():
    """
    Mevcut DB ayarlarını döner.
    SECRET_KEY değerini değil, yalnızca var olup olmadığını bildirir (güvenlik).
    """
    return jsonify({
        'DB_HOST': os.getenv('DB_HOST',''),
        'DB_PORT': os.getenv('DB_PORT','3306'),
        'DB_USER': os.getenv('DB_USER',''),
        'DB_NAME': os.getenv('DB_NAME',''),
        'HAS_SECRET_KEY': bool(os.getenv('SECRET_KEY','')),  # True/False — değer asla döndürülmez
    })

@app.route('/api/db-config', methods=['POST'])
@login_required
@csrf_protect
@rate_limit(5, 60)
def save_db_config():
    """
    DB bağlantı ayarlarını .env dosyasına kaydeder.
    Kaydedildikten sonra bağlantıyı test eder ve init_db() ile tabloları oluşturur.
    load_dotenv(override=True): yeni değerleri hemen os.environ'a uygular.
    """
    data = request.json
    keys = ['DB_HOST','DB_PORT','DB_USER','DB_PASSWORD','DB_NAME','SECRET_KEY']

    ENV_PATH.touch(exist_ok=True)  # .env dosyası yoksa boş oluştur
    for k in keys:
        if data.get(k):
            set_key(str(ENV_PATH), k, str(data[k]))  # .env'ye yaz

    load_dotenv(ENV_PATH, override=True)  # Yeni değerleri belleğe al

    # Bağlantı testi
    ok, msg = db().test_connection()
    if not ok:
        return jsonify({'success': False, 'message': f'Kaydedildi fakat bağlantı hatası: {msg}'})

    # Bağlantı başarılı — tabloları oluştur (IF NOT EXISTS, güvenli)
    ok2, msg2 = db().init_db()
    return jsonify({'success': True, 'message': f'Bağlantı başarılı! {msg2}'})

@app.route('/api/db-test', methods=['POST'])
@login_required
def test_db():
    """DB bağlantısını test eder, sonucu JSON olarak döner."""
    ok, msg = db().test_connection()
    return jsonify({'success': ok, 'message': msg})

# ─── Senders API ──────────────────────────────────────────────────────
@app.route('/api/senders', methods=['GET'])
@login_required
def list_senders():
    """
    Tüm göndericileri döner.
    Güvenlik: şifre alanı maskelenerek '••••••••' olarak gönderilir.
    Datetime alanları okunabilir formata çevrilir.
    """
    rows = db().get_senders()
    for r in rows:
        r['password'] = '••••••••'  # Şifreyi asla düz metin gönderme
        if isinstance(r.get('created_at'), datetime.datetime):
            r['created_at'] = r['created_at'].strftime('%d.%m.%Y %H:%M')
        if isinstance(r.get('updated_at'), datetime.datetime):
            r['updated_at'] = r['updated_at'].strftime('%d.%m.%Y %H:%M')
    return jsonify({'success': True, 'data': rows})

@app.route('/api/senders/stats', methods=['GET'])
@login_required
def sender_stats():
    """DB log'dan her gönderici için aylık ve toplam istatistik döner."""
    stats = db().get_sender_monthly_stats()
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/ses-quota/<int:sender_id>', methods=['GET'])
@login_required
@rate_limit(10, 60)
def ses_quota(sender_id):
    """AWS SES'ten canlı kota ve gönderim istatistiği çeker."""
    sender_row = db().get_sender(sender_id)
    if not sender_row:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'})
    if sender_row.get('sender_mode') != 'ses':
        return jsonify({'success': False, 'message': 'Bu gönderici SES modunda değil.'})
    try:
        from mailer import _resolve_aws_credentials
        import boto3
        aws_key, aws_secret, aws_region = _resolve_aws_credentials(sender_row)
        if not aws_key or not aws_secret:
            return jsonify({'success': False, 'message': 'AWS credentials eksik.'})
        session = boto3.Session(
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region,
        )
        client = session.client('ses')
        quota = client.get_send_quota()
        stats = client.get_send_statistics()
        # Son 24 saatteki gönderim
        sent_last_24h = sum(
            int(dp.get('DeliveryAttempts', 0))
            for dp in stats.get('SendDataPoints', [])
        )
        return jsonify({
            'success': True,
            'max_24h':       int(quota.get('Max24HourSend', 0)),
            'sent_24h':      int(quota.get('SentLast24Hours', 0)),
            'max_per_sec':   float(quota.get('MaxSendRate', 0)),
            'sent_last_24h': sent_last_24h,
        })
    except Exception as e:
        msg = str(e)
        if 'AuthFailure' in msg or 'InvalidClientTokenId' in msg:
            msg = 'AWS credentials geçersiz veya yetersiz yetki.'
        return jsonify({'success': False, 'message': msg})

@app.route('/api/senders', methods=['POST'])
@login_required
@csrf_protect
@rate_limit(20, 60)
def create_sender():
    """
    Yeni gönderici oluşturur.
    Her mod için farklı zorunlu alan seti doğrulanır:
      - smtp: smtp_server, smtp_port, username, password
      - ses:  aws_access_key, aws_secret_key
      - api:  api_host, api_endpoint, api_auth_token
    """
    data = request.json
    mode = data.get('sender_mode', 'smtp')

    # Tüm modlarda zorunlu alanlar
    for f in ['name', 'email']:
        if not data.get(f):
            return jsonify({'success': False, 'message': f'{f} zorunludur.'})

    # Moda özgü zorunlu alan kontrolü
    if mode == 'smtp':
        for f in ['smtp_server', 'smtp_port', 'username', 'password']:
            if not data.get(f):
                return jsonify({'success': False, 'message': f'SMTP modu için {f} zorunludur.'})
    elif mode == 'ses':
        for f in ['aws_access_key', 'aws_secret_key']:
            if not data.get(f):
                return jsonify({'success': False, 'message': f'AWS SES modu için {f} zorunludur.'})
    elif mode == 'api':
        for f in ['api_host', 'api_endpoint', 'api_auth_token']:
            if not data.get(f):
                return jsonify({'success': False, 'message': f'API modu için {f} zorunludur.'})
    else:
        return jsonify({'success': False, 'message': f'Geçersiz mod: {mode}'})

    # Varsayılan değerleri ekle (form göndermediyse)
    data.setdefault('use_ssl', 1)
    data.setdefault('is_active', 1)
    data.setdefault('aws_region', 'us-east-1')
    ok, result = db().save_sender(data)
    if ok:
        _audit('sender_create', 'sender', result,
               detail=f"mode={data.get('sender_mode')} name={data.get('name')} email={data.get('email')}")
    return jsonify({'success': ok, 'message': 'Kaydedildi.' if ok else result, 'id': result if ok else None})

@app.route('/api/senders/<int:sid>', methods=['PUT'])
@login_required
@csrf_protect
def update_sender(sid):
    """Mevcut göndericinin alanlarını günceller."""
    data = request.json
    mode = data.get('sender_mode', 'smtp')

    for f in ['name', 'email']:
        if not data.get(f):
            return jsonify({'success': False, 'message': f'{f} zorunludur.'})

    if mode == 'smtp':
        for f in ['smtp_server', 'smtp_port', 'username']:
            if not data.get(f):
                return jsonify({'success': False, 'message': f'SMTP modu için {f} zorunludur.'})

    data.setdefault('use_ssl', 1)
    data.setdefault('is_active', 1)
    data.setdefault('aws_region', 'us-east-1')
    ok, result = db().save_sender(data, sender_id=sid)
    if ok:
        _audit('sender_update', 'sender', sid,
               detail=f"name={data.get('name')} email={data.get('email')}")
    return jsonify({'success': ok, 'message': 'Güncellendi.' if ok else result})

@app.route('/api/senders/<int:sid>', methods=['DELETE'])
@login_required
@csrf_protect
def remove_sender(sid):
    """Göndericivi siler."""
    row = db().get_sender(sid)
    ok, msg = db().delete_sender(sid)
    if ok:
        name = row['name'] if row else str(sid)
        _audit('sender_delete', 'sender', sid, detail=f"name={name}")
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/senders/<int:sid>/test', methods=['POST'])
@login_required
@rate_limit(10, 60)
def test_sender_route(sid):
    """
    Gönderici bağlantısını canlı olarak test eder.
    - API modu: test_api_sender() → HTTP isteği gönderir
    - SMTP/SES: test_sender()     → Bağlantı kurup oturumu test eder
    """
    row = db().get_sender(sid)
    if not row:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'})
    if row.get('sender_mode') == 'api':
        ok, msg = test_api_sender(row)  # API endpoint'e ping at
    else:
        ok, msg = test_sender(row)      # SMTP bağlantısını test et
    return jsonify({'success': ok, 'message': msg})


# ─── Brevo Kota Sorgulama ──────────────────────────────────────────────────────
@app.route('/api/senders/<int:sid>/brevo-quota', methods=['GET'])
@login_required
def brevo_quota(sid):
    """
    Brevo hesap kotasini ve kredi bilgisini sorgular.
    Brevo API /v3/account endpoint'ini kullanir.
    Sadece api_host'u api.brevo.com olan gondericiler icin calisir.
    """
    # Brevo /v3/account endpoint'i ile hesap planı ve e-posta kredi bilgisini çeker
    import http.client, json as _json, ssl as _ssl
    row = db().get_sender(sid)
    if not row:
        return jsonify({'success': False, 'message': 'Gonderici bulunamadi.'})
    if row.get('sender_mode') != 'api':
        return jsonify({'success': False, 'message': 'Bu gonderici API modunda degil.'})
    host = (row.get('api_host') or '').strip()
    host = host.removeprefix('https://').removeprefix('http://').rstrip('/')
    if 'brevo.com' not in host and 'sendinblue.com' not in host:
        return jsonify({'success': False, 'message': "Bu gonderici Brevo API'si degil. (api_host: api.brevo.com olmali)"})
    auth_token = (row.get('api_auth_token') or '').strip()
    if not auth_token:
        return jsonify({'success': False, 'message': 'API auth token eksik.'})
    try:
        ctx = _ssl.create_default_context()
        conn = http.client.HTTPSConnection('api.brevo.com', timeout=10, context=ctx)
        conn.request('GET', '/v3/account', headers={
            'accept':  'application/json',
            'api-key': auth_token,
        })
        resp = conn.getresponse()
        body = resp.read().decode('utf-8')
        conn.close()
        if resp.status != 200:
            return jsonify({'success': False, 'message': f'Brevo API hatasi ({resp.status}): {body[:200]}'})
        data = _json.loads(body)
        plan_list = data.get('plan', [])
        email_credits = None
        plan_name     = None
        credits_used  = None
        for p in plan_list:
            if p.get('type') in ('payAsYouGo', 'free', 'subscription'):
                email_credits = p.get('credits')
                credits_used  = p.get('creditsUsed')
                plan_name     = p.get('type')
                break
        return jsonify({
            'success':       True,
            'company':       data.get('companyName', ''),
            'email':         data.get('email', ''),
            'first_name':    data.get('firstName', ''),
            'last_name':     data.get('lastName', ''),
            'plan':          plan_list,
            'email_credits': email_credits,
            'credits_used':  credits_used,
            'plan_name':     plan_name,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Baglanti hatasi: {e}'})


# ─── Rules API ────────────────────────────────────────────────────────
@app.route('/api/rules', methods=['GET'])
@login_required
def list_rules():
    """Tüm gönderim kurallarını listeler."""
    rows = db().get_rules()
    for r in rows:
        if isinstance(r.get('created_at'), datetime.datetime):
            r['created_at'] = r['created_at'].strftime('%d.%m.%Y %H:%M')
    return jsonify({'success': True, 'data': rows})

@app.route('/api/rules', methods=['POST'])
@login_required
@csrf_protect
def create_rule():
    """Yeni gönderim kuralı oluşturur."""
    data = request.json
    for f in ['name','sender_id','min_interval_h']:
        if data.get(f) is None:
            return jsonify({'success': False, 'message': f'{f} zorunludur.'})
    data.setdefault('is_active', 1)
    ok, result = db().save_rule(data)
    return jsonify({'success': ok, 'message': 'Kaydedildi.' if ok else result, 'id': result if ok else None})

@app.route('/api/rules/<int:rid>', methods=['PUT'])
@login_required
@csrf_protect
def update_rule(rid):
    """Mevcut gönderim kuralını günceller."""
    data = request.json
    data.setdefault('is_active', 1)
    ok, result = db().save_rule(data, rule_id=rid)
    return jsonify({'success': ok, 'message': 'Güncellendi.' if ok else result})

@app.route('/api/rules/<int:rid>', methods=['DELETE'])
@login_required
@csrf_protect
def remove_rule(rid):
    """Gönderim kuralını siler."""
    ok, msg = db().delete_rule(rid)
    return jsonify({'success': ok, 'message': msg})

# ─── Single Send API ──────────────────────────────────────────────────
@app.route('/api/send', methods=['POST'])
@login_required
@rate_limit(30, 60)
def send_single():
    """
    Tek e-posta gönderir (multipart/form-data).
    Gönderim moduna göre send_via_ses / send_via_api / send_one çağrılır.
    Her gönderim sonucu send_log tablosuna kaydedilir (sent/failed).
    Ek dosya varsa (attachment) isteğe bağlı olarak eklenir.
    """
    sender_id = request.form.get('sender_id')
    recipient = request.form.get('recipient','').strip()
    subject   = request.form.get('subject','').strip()
    body      = request.form.get('body','').strip()
    html_mode = request.form.get('html_mode') == 'true'

    if not all([sender_id, recipient, subject, body]):
        return jsonify({'success': False, 'message': 'Tüm alanları doldurun.'})

    row = db().get_sender(int(sender_id))
    if not row:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'})

    # html_mode=false ise düz metni HTML'e çevir (satır sonları <br> olur)
    body_html = body if html_mode else plain_to_html(body)
    include_unsubscribe = request.form.get('include_unsubscribe') == 'true'

    # Ek dosya varsa belleğe al: (dosya_adı, bytes)
    attachment = None
    if 'attachment' in request.files:
        f = request.files['attachment']
        if f.filename:
            valid_att, err_att = validate_attachment(f)
            if not valid_att:
                return jsonify({'success': False, 'message': err_att})
            attachment = (safe_attachment_filename(f.filename), f.read())

    try:
        if row.get('sender_mode') == 'ses':
            # AWS SES ile gönder
            try:
                send_via_ses(row, recipient, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
                ok, err = True, None
            except Exception as e:
                ok, err = False, str(e)
        elif row.get('sender_mode') == 'api':
            # Üçüncü taraf mail API'si ile gönder
            try:
                recip_name = request.form.get('recipient_name', '').strip()
                send_via_api(row, recipient, subject, body_html, recipient_name=recip_name, include_unsubscribe=include_unsubscribe)
                ok, err = True, None
            except Exception as e:
                ok, err = False, str(e)
        else:
            # SMTP ile gönder
            ok, err = send_one(row, recipient, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)

        # Sonucu logla — başarı veya hata fark etmeksizin
        status = 'sent' if ok else 'failed'
        db().log_send(row['id'], None, recipient, subject, status, err)

        if ok:
            return jsonify({'success': True, 'message': 'E-posta gönderildi! ✓'})
        else:
            return jsonify({'success': False, 'message': f'Hata: {err}'})

    except Exception as e:
        # Beklenmeyen hata — logla ve kullanıcıya bildir
        db().log_send(row['id'], None, recipient, subject, 'failed', str(e))
        return jsonify({'success': False, 'message': f'Beklenmeyen hata: {str(e)}'})

# ─── Excel Preview API ────────────────────────────────────────────────
@app.route('/api/preview-excel', methods=['POST'])
@login_required
def preview_excel():
    """Excel dosyasını okuyup önizleme bilgilerini döndürür"""
    try:
        if 'excel' not in request.files:
            return jsonify({'success': False, 'message': 'Dosya yok'})
        
        file = request.files['excel']
        valid, err = validate_excel_upload(file)
        if not valid:
            return jsonify({'success': False, 'message': err})

        df = pd.read_excel(file)
        columns = df.columns.tolist()
        
        preview = []
        for _, row in df.head(5).iterrows():
            row_dict = {}
            for col in columns:
                val = row[col]
                if pd.isna(val):
                    row_dict[col] = ''
                else:
                    row_dict[col] = str(val)
            preview.append(row_dict)
        
        return jsonify({
            'success': True,
            'columns': columns,
            'preview': preview,
            'total': len(df)
        })
        
    except Exception as e:
        import traceback
        print(f"[preview_excel] {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Dosya okunamadı. Geçerli bir Excel/CSV dosyası yükleyin.'})

# ─── Bulk Send API (Excel'den) ────────────────────────────────────────
@app.route('/api/count-excel-rows', methods=['POST'])
@login_required
def count_excel_rows():
    """Excel dosyasındaki geçerli e-posta satır sayısını döndürür"""
    excel_file = request.files.get('excel')
    email_col  = request.form.get('email_col', '').strip()
    if not excel_file or not email_col:
        return jsonify({'success': False, 'count': 0})
    valid, err = validate_excel_upload(excel_file)
    if not valid:
        return jsonify({'success': False, 'count': 0, 'message': err})
    try:
        df = pd.read_excel(excel_file)
        df = df.replace({pd.NA: None, float('nan'): None})
        count = sum(1 for _, row in df.iterrows()
                    if is_valid_email(str(row.get(email_col) or '')))
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'count': 0, 'message': str(e)})


@app.route('/api/count-table-rows', methods=['GET'])
@login_required
def count_table_rows():
    """DB tablosundaki geçerli e-posta satır sayısını döndürür"""
    table_name = request.args.get('table_name', '').strip()
    email_col  = request.args.get('email_col', '').strip()
    if not table_name or not email_col:
        return jsonify({'success': False, 'count': 0})
    try:
        ok, result = db().get_table_rows(table_name)
        if not ok:
            return jsonify({'success': False, 'count': 0})
        count = sum(1 for r in result if is_valid_email(str(r.get(email_col) or '')))
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'count': 0, 'message': str(e)})


@app.route('/api/send-bulk', methods=['POST'])
@login_required
@rate_limit(20, 60)
def send_bulk():
    """
    Excel dosyasından toplu gönderim yapar (Server-Sent Events ile canlı akış).
    SSE stream formatı:
      data: {"type":"start", "total": N}
      data: {"type":"progress", "i":1, "email":"...", "status":"ok"|"error"|"skipped"}
      data: {"type":"done", "ok":N, "err":N, "skipped":N}
    batch_offset/batch_limit: parçalı gönderim için başlangıç ve limit.
    """
    try:
        excel_file  = request.files.get('excel')
        sender_id   = request.form.get('sender_id')
        rule_id     = request.form.get('rule_id') or None
        email_col   = request.form.get('email_col')
        var_cols    = request.form.get('var_cols', '').split(',') if request.form.get('var_cols') else []
        subject_tpl = request.form.get('subject', '').strip()
        body_tpl    = request.form.get('body', '').strip()
        html_mode   = request.form.get('html_mode') == 'true'
        delay_ms    = int(request.form.get('delay_ms', 500))
        include_unsubscribe = request.form.get('include_unsubscribe') == 'true'
        source      = request.form.get('source', 'excel')  # 'excel' | 'paste'

        # Yapıştır (paste) modunda excel_file yoktur — paste_emails JSON listesi gelir
        paste_emails_raw = request.form.get('paste_emails')
        if source == 'paste' and paste_emails_raw:
            try:
                paste_emails = json.loads(paste_emails_raw)
            except Exception:
                paste_emails = []
        else:
            paste_emails = []

        # Zorunlu alan kontrolü — paste modunda email_col gerekmez
        if source == 'paste':
            if not all([sender_id, subject_tpl, body_tpl]):
                return jsonify({'success': False, 'message': 'Gerekli alanlar eksik'})
            if not paste_emails:
                return jsonify({'success': False, 'message': 'E-posta listesi boş'})
        else:
            if not all([excel_file, sender_id, email_col, subject_tpl, body_tpl]):
                return jsonify({'success': False, 'message': 'Gerekli alanlar eksik'})
        
        batch_offset = int(request.form.get('batch_offset', 0))
        batch_limit  = int(request.form.get('batch_limit', 0))

        # MX kontrolü aktif mi? Form'dan al (varsayılan: aktif)
        use_mx_check = request.form.get('mx_check', 'true') == 'true'

        valid_rows   = []
        invalid_rows = []   # format veya MX hatası olan satırlar

        # Domain cache'i bu batch için sıfırla (yeni gönderim = temiz cache)
        with _mx_lock:
            _mx_cache.clear()

        if source == 'paste':
            # Paste modu: JSON listeden gelen adresler — Excel dosyası okunmaz
            # email_col yoktur, 'email' sabit anahtarını kullanırız
            for em in paste_emails:
                em = str(em).strip()
                if not em:
                    continue
                ok, reason = is_valid_email_with_mx(em, use_mx=use_mx_check)
                if ok:
                    valid_rows.append({'email': em})  # Dict formatı stream() ile uyumlu
                else:
                    invalid_rows.append((em, reason))
            email_col = 'email'  # stream() içinde row.get(email_col) ile erişilir
        else:
            # Excel modu: Dosyayı oku ve satırları işle
            df = pd.read_excel(excel_file)
            df = df.replace({pd.NA: None, float('nan'): None})
            for _, row in df.iterrows():
                email = row.get(email_col)
                if not email:
                    continue
                email_str = str(email).strip()
                ok, reason = is_valid_email_with_mx(email_str, use_mx=use_mx_check)
                if ok:
                    valid_rows.append(row)
                else:
                    invalid_rows.append((email_str, reason))
        
        # Parçalı gönderim: sadece ilgili dilimi al
        if batch_limit > 0:
            valid_rows = valid_rows[batch_offset:batch_offset + batch_limit]
        
        sender_row = db().get_sender(int(sender_id))
        if not sender_row:
            return jsonify({'success': False, 'message': 'Gönderici bulunamadı'})
        
        rule_row = db().get_rule(int(rule_id)) if rule_id else None
        min_interval_h = int(rule_row['min_interval_h']) if rule_row else 0
        
        attachment = None
        if 'attachment' in request.files:
            att = request.files['attachment']
            if att.filename:
                valid_att2, err_att2 = validate_attachment(att)
                if not valid_att2:
                    return jsonify({'success': False, 'message': err_att2})
                attachment = (safe_attachment_filename(att.filename), att.read())
        
        _uid = session.get('user_id')
        _uname = session.get('username', 'unknown')
        _bulk_file = getattr(excel_file, 'filename', 'excel') if excel_file else 'excel'
        _ip = _client_ip()  # request context dışında kullanılamaz, önceden yakala

        def stream():
            """SSE (Server-Sent Events) akışı — anlık ilerleme gönderir."""
            total = len(valid_rows) + len(invalid_rows)
            if total == 0:
                yield sse({'type': 'error', 'message': 'Geçerli e-posta bulunamadı'})
                return

            # Toplu gönderim başlangıcını logla
            db().audit(_uid, _uname, 'bulk_start', 'bulk', _bulk_file,
                       detail=f"total={total} sender_id={sender_id} invalid={len(invalid_rows)}",
                       ip_address=_ip)
            yield sse({'type': 'start', 'total': total})

            ok_c = err_c = skip_c = 0

            # Geçersiz formatlı adresleri önce skipped olarak raporla
            for inv_i, (inv_email, inv_reason) in enumerate(invalid_rows, 1):
                skip_c += 1
                db().log_send(sender_row['id'], rule_id and int(rule_id), inv_email,
                              subject_tpl, 'skipped', inv_reason, user_id=_uid, username=_uname)
                yield sse({'type': 'progress', 'i': inv_i, 'total': total,
                           'email': inv_email, 'status': 'skipped', 'reason': inv_reason})
            
            for i, row in enumerate(valid_rows, len(invalid_rows) + 1):
                email = str(row[email_col]).strip()

                # MX kontrolü gönderim öncesinde (valid_rows oluşturulurken) zaten yapıldı.
                # Burada tekrar yapmak SSE bağlantısını gereksiz yere bloke eder.

                # Değişken kolonları topla: {{AdSoyad}}, {{Şehir}} vb. şablon değişkenleri
                # pd.isna() DataFrame satırlarında çalışır; dict (paste modu) için try/except
                variables = {}
                for col in var_cols:
                    if col in row:
                        val = row[col]
                        try:
                            is_na = pd.isna(val)
                        except (TypeError, ValueError):
                            is_na = val is None
                        variables[col] = '' if is_na else str(val)
                
                allowed, reason = db().can_send(sender_row['id'], email, min_interval_h)
                if not allowed:
                    skip_c += 1
                    db().log_send(sender_row['id'], rule_id and int(rule_id), email, subject_tpl, 'skipped', reason, user_id=_uid, username=_uname)
                    yield sse({'type': 'progress', 'i': i, 'total': total, 'email': email, 'status': 'skipped', 'reason': reason})
                    yield from heartbeat_sleep(delay_ms)
                    continue
                
                subject = render_template_str(subject_tpl, variables)
                body = render_template_str(body_tpl, variables)
                body_html = body if html_mode else plain_to_html(body)
                
                try:
                    if sender_row.get('sender_mode') == 'ses':
                        send_via_ses(sender_row, email, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
                    elif sender_row.get('sender_mode') == 'api':
                        variables_for_name = variables if variables else {}
                        recipient_name = variables_for_name.get('name') or variables_for_name.get('ad') or ''
                        send_via_api(sender_row, email, subject, body_html, recipient_name=recipient_name, include_unsubscribe=include_unsubscribe)
                    else:
                        ok, err = send_one(sender_row, email, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
                        if not ok:
                            raise Exception(err)
                    
                    ok_c += 1
                    db().log_send(sender_row['id'], rule_id and int(rule_id), email, subject, 'sent', user_id=_uid, username=_uname)
                    yield sse({'type': 'progress', 'i': i, 'total': total, 'email': email, 'status': 'ok'})
                    
                except Exception as e:
                    err_c += 1
                    db().log_send(sender_row['id'], rule_id and int(rule_id), email, subject, 'failed', str(e), user_id=_uid, username=_uname)
                    yield sse({'type': 'progress', 'i': i, 'total': total, 'email': email, 'status': 'error', 'error': str(e)})
                
                yield from heartbeat_sleep(delay_ms)
            
            db().audit(_uid, _uname, 'bulk_done', 'bulk', _bulk_file,
                       detail=f"ok={ok_c} err={err_c} skipped={skip_c} total={total}",
                       ip_address=_ip)
            yield sse({'type': 'done', 'ok': ok_c, 'err': err_c, 'skipped': skip_c, 'total': total})

        return Response(stream(), 
                       mimetype='text/event-stream',
                       headers={
                           'Cache-Control': 'no-cache, no-store, must-revalidate',
                           'Pragma': 'no-cache',
                           'Expires': '0',
                           'X-Accel-Buffering': 'no'
                       })
        
    except Exception as e:
        import traceback
        print("[send_bulk ERROR] " + str(e) + "\n" + traceback.format_exc())
        return jsonify({'success': False, 'message': f'Sunucu hatası: {str(e)}'})

# ─── Bulk Send API (DB tablosundan) ─────────────────────────────────
# Excel yerine MySQL tablosunu kaynak olarak kullanır.
# SES, SMTP ve API modlarını destekler (isim rağmen tüm modlar çalışır).
@app.route('/api/send-bulk-ses', methods=['POST'])
@login_required
@rate_limit(20, 60)
def send_bulk_ses():
    """
    DB tablosundan toplu gönderim yapar (SSE stream).
    Kaynak: get_table_rows() ile MySQL tablosundan tüm satırlar okunur.
    Tablo sütunları otomatik olarak değişken map'e eklenir: {{sütun_adı}}
    """
    sender_id   = request.form.get('sender_id')
    rule_id     = request.form.get('rule_id') or None
    subject_tpl = request.form.get('subject','').strip()
    body_tpl    = request.form.get('body','').strip()
    html_mode   = request.form.get('html_mode') == 'true'
    table_name  = request.form.get('table_name','').strip()
    email_col   = request.form.get('email_col','').strip()
    delay_ms    = int(request.form.get('delay_ms', 500))
    include_unsubscribe = request.form.get('include_unsubscribe') == 'true'

    if not all([sender_id, table_name, email_col, subject_tpl, body_tpl]):
        return jsonify({'success': False, 'message': 'Gerekli alanlar eksik.'})

    sender_row = db().get_sender(int(sender_id))
    if not sender_row:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'})

    rule_row = db().get_rule(int(rule_id)) if rule_id else None
    min_interval_h = int(rule_row['min_interval_h']) if rule_row else 0

    attachment = None
    if 'attachment' in request.files:
        att = request.files['attachment']
        if att.filename:
            valid_att3, err_att3 = validate_attachment(att)
            if not valid_att3:
                return jsonify({'success': False, 'message': err_att3})
            attachment = (safe_attachment_filename(att.filename), att.read())

    batch_offset = int(request.form.get('batch_offset', 0))
    batch_limit  = int(request.form.get('batch_limit', 0))

    _uid2   = session.get('user_id')
    _uname2 = session.get('username', 'unknown')
    _ip2       = _client_ip()  # request context dışında kullanılamaz, önceden yakala
    _only_valid  = request.form.get('only_valid', 'false') == 'true'   # stream() dışında yakala
    _use_mx2     = request.form.get('mx_check', 'true') == 'true'      # stream() dışında yakala

    def stream():
        """SSE (Server-Sent Events) akışı — anlık ilerleme gönderir."""
        try:
            ok, result = db().get_table_rows(table_name, only_valid=_only_valid)
            if not ok:
                yield sse({'type':'error','message':result}); return
            rows = result
        except Exception as e:
            yield sse({'type':'error','message':f'Tablo okunamadı: {e}'}); return

        use_mx_check2 = _use_mx2
        # Domain cache'i temizle
        with _mx_lock:
            _mx_cache.clear()
        valid = []
        invalid_db = []
        for r in rows:
            em = str(r.get(email_col) or '').strip()
            ok2, reason2 = is_valid_email_with_mx(em, use_mx=use_mx_check2)
            if ok2:
                valid.append(r)
            elif em:
                invalid_db.append((em, reason2))
        if batch_limit > 0:
            valid = valid[batch_offset:batch_offset + batch_limit]
        total = len(valid)
        if total == 0:
            yield sse({'type':'error','message':'Geçerli e-posta bulunamadı.'}); return

        db().audit(_uid2, _uname2, 'bulk_start', 'bulk', table_name,
                   detail=f"total={total} sender_id={sender_id} source=db",
                   ip_address=_ip2)
        yield sse({'type':'start','total':total})

        ok_c = err_c = skip_c = 0

        for i, row in enumerate(valid,1):
            email = str(row[email_col]).strip()
            variables = {k: ('' if v is None else str(v)) for k,v in row.items()}

            allowed, reason = db().can_send(sender_row['id'], email, min_interval_h)
            if not allowed:
                skip_c += 1
                db().log_send(sender_row['id'], rule_id and int(rule_id), email, subject_tpl, 'skipped', reason, user_id=_uid2, username=_uname2)
                yield sse({'type':'progress','i':i,'total':total,'email':email,'status':'skipped','reason':reason})
                yield from heartbeat_sleep(delay_ms)
                continue

            subj      = render_template_str(subject_tpl, variables)
            body      = render_template_str(body_tpl, variables)
            body_html = body if html_mode else plain_to_html(body)

            try:
                if sender_row.get('sender_mode') == 'api':
                    recipient_name = str(variables.get('name', '') or variables.get('ad', ''))
                    send_via_api(sender_row, email, subj, body_html, recipient_name=recipient_name, include_unsubscribe=include_unsubscribe)
                else:
                    send_via_ses(sender_row, email, subj, body_html, attachment, include_unsubscribe=include_unsubscribe)
                ok_c += 1
                db().log_send(sender_row['id'], rule_id and int(rule_id), email, subj, 'sent', user_id=_uid2, username=_uname2)
                yield sse({'type':'progress','i':i,'total':total,'email':email,'status':'ok'})
            except Exception as e:
                err_c += 1
                db().log_send(sender_row['id'], rule_id and int(rule_id), email, subj, 'failed', str(e), user_id=_uid2, username=_uname2)
                yield sse({'type':'progress','i':i,'total':total,'email':email,'status':'error','error':str(e)})

            yield from heartbeat_sleep(delay_ms)

        db().audit(_uid2, _uname2, 'bulk_done', 'bulk', table_name,
                   detail=f"ok={ok_c} err={err_c} skipped={skip_c} total={total}",
                   ip_address=_ip2)
        yield sse({'type':'done','ok':ok_c,'err':err_c,'skipped':skip_c,'total':total})

    return Response(stream(),
                   mimetype='text/event-stream',
                   headers={
                       'Cache-Control': 'no-cache, no-store, must-revalidate',
                       'Pragma': 'no-cache',
                       'Expires': '0',
                       'X-Accel-Buffering': 'no'
                   })

# ─── Tablo API'leri ───────────────────────────────────────────────────
@app.route('/api/list-tables', methods=['GET'])
@login_required
def list_tables():
    """Kullanıcı tablolarını (sistem tabloları hariç) satır sayısı ve sütunlarıyla listeler."""
    ok, result = db().list_user_tables()
    return jsonify({'success': ok, 'tables': result if ok else [], 'message': result if not ok else ''})

@app.route('/api/table-preview', methods=['POST'])
@login_required
def table_preview():
    """Tablonun ilk 5 satırını önizleme olarak döner."""
    data = request.json
    table_name = data.get('table_name')
    ok, result = db().get_table_preview(table_name)
    return jsonify({'success': ok, **({'columns': result['columns'], 'preview': result['preview'], 'total': result['total']} if ok else {'message': result})})

@app.route('/api/check-table-exists', methods=['POST'])
@login_required
def check_table_exists():
    """Tablonun varlığını kontrol eder."""
    data = request.json
    table_name = data.get('table_name')
    ok, result = db().table_exists(table_name)
    return jsonify({'exists': ok and result})

@app.route('/api/import-excel-to-db', methods=['POST'])
@login_required
def import_excel_to_db():
    """
    Excel dosyasını MySQL tablosuna aktarır.
    action: 'new' | 'overwrite' | 'append' | 'append_dedupe'
    column_names: {excel_kolon_adı: db_kolon_adı} eşleştirme haritası (JSON)
    """
    try:
        excel_file   = request.files['excel']
        table_name   = request.form.get('table_name')
        column_names = json.loads(request.form.get('column_names', '{}'))  # JSON string → dict
        action       = request.form.get('action', 'new')

        valid, err = validate_excel_upload(excel_file)
        if not valid:
            return jsonify({'success': False, 'message': err})

        original_filename = safe_attachment_filename(excel_file.filename)
        df = pd.read_excel(excel_file)
        ok, count, msg = db().import_excel_to_table(df, table_name, column_names, action)
        if ok:
            _audit('excel_upload', 'excel', table_name,
                   detail=f"file={original_filename} action={action} rows={count}")
        return jsonify({'success': ok, 'message': msg, 'count': count})
    except Exception as e:
        import traceback
        print(f"[import_excel_to_db] {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Dosya aktarım hatası. Dosya formatını kontrol edin.'})

# ─── Suppression List API ─────────────────────────────────────────────
@app.route('/api/suppression', methods=['GET'])
@login_required
def get_suppression():
    """Suppression listesini sayfalı olarak döner."""
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    search   = request.args.get('search')
    reason   = request.args.get('reason')
    rows, total = db().get_suppression_list(page, per_page, search, reason)
    return jsonify({'success': True, 'data': rows, 'total': total, 'page': page})

@app.route('/api/suppression', methods=['POST'])
@login_required
@csrf_protect
@rate_limit(30, 60)
def add_suppression():
    """Manuel suppression ekleme. Tek adres veya virgülle ayrılmış liste kabul eder."""
    data   = request.json or {}
    emails = data.get('emails', data.get('email', ''))
    reason = data.get('reason', 'manual').strip()
    if reason not in ('unsubscribe', 'bounce', 'complaint', 'invalid', 'manual'):
        reason = 'manual'
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.replace(';', ',').split(',') if e.strip()]
    if not emails:
        return jsonify({'success': False, 'message': 'En az bir e-posta gerekli.'})
    added, skipped = 0, 0
    for email in emails:
        if '@' not in email:
            skipped += 1
            continue
        ok = db().add_to_suppression(email.lower(), reason, source='manual')
        if ok: added += 1
        else:  skipped += 1
    _audit('suppression_add', 'suppression', None,
           detail=f"added={added} skipped={skipped} reason={reason}")
    return jsonify({
        'success': True,
        'message': f'{added} adres eklendi' + (f', {skipped} atlandı' if skipped else '') + '.',
        'added': added, 'skipped': skipped,
    })


@app.route('/api/suppression', methods=['DELETE'])
@login_required
@csrf_protect
def remove_suppression():
    """Suppression listesinden adres kaldırır."""
    email = request.json.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': 'E-posta gerekli.'})
    ok, msg = db().delete_suppression(email)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/suppression/stats', methods=['GET'])
@login_required
def suppression_stats():
    """Suppression listesi istatistiklerini döner."""
    stats = db().get_suppression_stats()
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/suppression/purge-table', methods=['POST'])
@login_required
@rate_limit(5, 60)
def purge_table():
    """Seçili tablodan suppression listesindeki adresleri siler."""
    data       = request.json
    table_name = data.get('table_name', '').strip()
    email_col  = data.get('email_col', '').strip()
    if not table_name or not email_col:
        return jsonify({'success': False, 'message': 'Tablo adı ve e-posta sütunu gerekli.'})
    ok, count, msg = db().purge_suppressed_from_table(table_name, email_col)
    return jsonify({'success': ok, 'message': msg, 'count': count})


@app.route('/api/suppression/purge-all', methods=['POST'])
@login_required
@admin_required
@csrf_protect
@rate_limit(3, 60)
def purge_all_tables():
    """
    Tüm kullanıcı tablolarından suppression listesindeki adresleri siler.
    E-posta kolonu tahmin edilir: 'mail', 'email', 'eposta', 'e_posta' içeren sütun adı.
    E-posta kolonu bulunamayan tablolar atlanır (log mesajıyla bildirilir).
    """ 
    try:
        ok, tables_result = db().list_user_tables()
        if not ok:
            return jsonify({'success': False, 'message': f'Tablolar listelenemedi: {tables_result}'})

        total_deleted = 0
        results = []
        for tbl in tables_result:
            table_name = tbl['name']
            # E-posta kolonu tahmin et
            email_col = next(
                (c for c in tbl.get('columns', []) if any(k in c.lower() for k in ['mail', 'email', 'eposta', 'e_posta'])),
                None
            )
            if not email_col:
                results.append(f"{table_name}: e-posta sütunu bulunamadı, atlandı")
                continue
            ok, count, msg = db().purge_suppressed_from_table(table_name, email_col)
            if ok and count > 0:
                total_deleted += count
                results.append(f"{table_name}: {count} kayıt silindi")

        msg = f"Toplam {total_deleted} kayıt silindi." + (f" ({'; '.join(results)})" if results else "")
        return jsonify({'success': True, 'message': msg, 'total': total_deleted})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ─── Tablo is_valid Sayım Endpoint'i ─────────────────────────────────────────
@app.route('/api/table-valid-count', methods=['POST'])
@login_required
def table_valid_count():
    """
    Tablodaki is_valid kolon dağılımını döner.
    Bulk-send sayfasında 'sadece geçerli adreslere gönder' toggle'ı için kullanılır.
    """
    data = request.json or {}
    table_name = data.get('table_name', '').strip()
    if not table_name:
        return jsonify({'success': False, 'message': 'table_name gerekli.'})
    counts = db().get_table_valid_counts(table_name)
    if counts is None:
        return jsonify({'success': False, 'message': 'is_valid kolonu bulunamadı.'})
    return jsonify({
        'success':  True,
        'valid':    counts['valid'],
        'invalid':  counts['invalid'],
        'risky':    counts['risky'],
        'unchecked':counts['unchecked'],
        'total':    counts['total'],
    })


# ══════════════════════════════════════════════════════════════════════
#  DOMAIN BLOKLAMA ENDPOINTLERİ
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/suppression/domains', methods=['GET'])
@login_required
def get_suppression_domains():
    """Domain bloklama listesini döner."""
    search = request.args.get('search', '').strip() or None
    rows = db().get_suppression_domains(search)
    return jsonify({'success': True, 'data': rows})


@app.route('/api/suppression/domains', methods=['POST'])
@login_required
def add_suppression_domain():
    """
    Bir veya birden fazla domain'i bloklama listesine ekler.
    O domain'e ait tüm adreslere gönderim engellenir.
    Giriş: { "domains": "domain1.com\ndomain2.com", "reason": "manual", "note": "" }
    """
    data   = request.json or {}
    raw    = data.get('domains', data.get('domain', '')).strip()
    reason = data.get('reason', 'manual').strip() or 'manual'
    note   = data.get('note', '').strip()

    # Satır sonu veya virgülle ayrılmış domain listesi
    domains = [
        d.strip().lower().lstrip('@')
        for d in re.split(r'[,\n]+', raw)
        if d.strip()
    ]
    if not domains:
        return jsonify({'success': False, 'message': 'En az bir domain gerekli.'})

    added, skipped, errors = 0, 0, []
    for domain in domains:
        ok, msg = db().add_suppression_domain(domain, reason, note)
        if ok:
            added += 1
        else:
            skipped += 1
            errors.append(f"{domain}: {msg}")

    _audit('domain_block_add', 'suppression_domains', None,
           detail=f"added={added} skipped={skipped} domains={','.join(domains[:5])}")

    msg = f'{added} domain engellendi'
    if skipped:
        msg += f', {skipped} atlandı'
    if errors:
        msg += f'. Hatalar: {"; ".join(errors[:3])}'
    return jsonify({'success': True, 'message': msg + '.', 'added': added, 'skipped': skipped})


@app.route('/api/suppression/domains', methods=['DELETE'])
@login_required
def delete_suppression_domain():
    """Domain'i bloklama listesinden kaldırır."""
    data   = request.json or {}
    domain = data.get('domain', '').strip().lower().lstrip('@')
    if not domain:
        return jsonify({'success': False, 'message': 'Domain gerekli.'})
    ok, msg = db().delete_suppression_domain(domain)
    if ok:
        _audit('domain_block_remove', 'suppression_domains', None, detail=f"domain={domain}")
    return jsonify({'success': ok, 'message': msg})


@app.route('/api/suppression/domains/check', methods=['GET'])
@login_required
def check_domain_suppressed():
    """Bir domain'in bloklu olup olmadığını kontrol eder."""
    domain = request.args.get('domain', '').strip().lower().lstrip('@')
    if not domain:
        return jsonify({'success': False, 'message': 'Domain gerekli.'})
    rows = db().get_suppression_domains(search=domain)
    blocked = any(r['domain'] == domain for r in rows)
    return jsonify({'success': True, 'blocked': blocked, 'domain': domain})


# ══════════════════════════════════════════════════════════════════════
#  ŞABLON (KONU / MESAJ) ENDPOINTLERİ
# ══════════════════════════════════════════════════════════════════════

@app.route('/settings/templates')
@login_required
def settings_templates():
    """Şablon yönetim sayfasını render eder."""
    return render_template('pages/settings/templates.html')


@app.route('/api/templates', methods=['GET'])
@login_required
def api_template_list():
    """Tüm şablonları veya belirli tipteki şablonları döner."""
    tpl_type = request.args.get('type')  # 'subject' | 'body' | None
    rows = db().template_list(tpl_type)
    return jsonify({'success': True, 'data': rows})


@app.route('/api/templates/create', methods=['POST'])
@login_required
def api_template_create():
    """Yeni şablon oluşturur."""
    data    = request.json or {}
    tpl_type = data.get('type', '').strip()
    name    = data.get('name', '').strip()
    content = data.get('content', '').strip()

    # Zorunlu alan kontrolü
    if tpl_type not in ('subject', 'body'):
        return jsonify({'success': False, 'message': 'Geçersiz şablon tipi.'})
    if not name:
        return jsonify({'success': False, 'message': 'Şablon adı zorunludur.'})
    if not content:
        return jsonify({'success': False, 'message': 'İçerik boş olamaz.'})

    ok, result = db().template_create(tpl_type, name, content)
    if ok:
        return jsonify({'success': True, 'id': result, 'message': 'Şablon kaydedildi.'})
    return jsonify({'success': False, 'message': result})


@app.route('/api/templates/<int:tpl_id>', methods=['GET'])
@login_required
def api_template_get(tpl_id):
    """Tek şablonu döner."""
    row = db().template_get(tpl_id)
    if not row:
        return jsonify({'success': False, 'message': 'Şablon bulunamadı.'})
    return jsonify({'success': True, 'data': row})


@app.route('/api/templates/<int:tpl_id>', methods=['PUT'])
@login_required
def api_template_update(tpl_id):
    """Şablonu günceller."""
    data = request.json or {}
    ok, msg = db().template_update(
        tpl_id,
        name    = data.get('name'),
        content = data.get('content')
    )
    return jsonify({'success': ok, 'message': msg})


@app.route('/api/templates/<int:tpl_id>', methods=['DELETE'])
@login_required
def api_template_delete(tpl_id):
    """Şablonu siler."""
    ok, msg = db().template_delete(tpl_id)
    return jsonify({'success': ok, 'message': msg})


# ══════════════════════════════════════════════════════════════════════
#  KULLANICI YÖNETİM ENDPOINTLERİ
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/users', methods=['GET'])
@login_required
def api_user_list():
    """
    Tüm kullanıcıları listeler.
    @login_required: oturum gerekli.
    İçeride ek kontrol: sadece admin rolü kullanabilir (@admin_required kullanmak
    yerine JSON 403 döndürmek için manuel kontrol yapıldı).
    """
    if session.get('user_role') != 'admin':
        return jsonify({'success': False, 'message': 'Yetkisiz.'})
    return jsonify({'success': True, 'data': db().user_list()})

@app.route('/api/users/create', methods=['POST'])
@admin_required
@csrf_protect
def api_user_create():
    """Yeni kullanıcı oluşturur. Şifre minimum 6 karakter olmalı."""
    data = request.json or {}
    username = data.get('username','').strip()
    password = data.get('password','')
    email    = data.get('email','').strip()
    role     = data.get('role','editor')  # Varsayılan rol: editor

    if not username or not password:
        return jsonify({'success': False, 'message': 'Kullanici adi ve sifre zorunlu.'})
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Sifre en az 6 karakter olmali.'})

    ok, msg = db().user_create(username, password, email, role)
    if ok:
        _audit('user_create', 'user', username, detail=f"role={role} email={email}")
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/users/update', methods=['POST'])
@admin_required
@csrf_protect
def api_user_update():
    """Kullanıcı bilgilerini günceller."""
    data = request.json or {}
    uid  = data.get('uid')
    if not uid:
        return jsonify({'success': False, 'message': 'uid gerekli.'})
    kwargs = {}
    if data.get('email')     is not None: kwargs['email']     = data['email']
    if data.get('role')      is not None: kwargs['role']      = data['role']
    if data.get('is_active') is not None: kwargs['is_active'] = int(data['is_active'])
    if data.get('password'):
        if len(data['password']) < 6:
            return jsonify({'success': False, 'message': 'Sifre en az 6 karakter olmali.'})
        kwargs['password'] = data['password']
    ok, msg = db().user_update(int(uid), **kwargs)
    if ok:
        _audit('user_update', 'user', uid, detail=str({k:v for k,v in kwargs.items() if k != 'password'}))
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/users/delete', methods=['POST'])
@admin_required
@csrf_protect
def api_user_delete():
    """
    Kullanıcıyı siler.
    İki güvenlik katmanı:
      1. Uygulama katmanı: admin kendini silemez (bu kontrol)
      2. DB katmanı: son admin silinemez (database.user_delete içinde)
    """
    uid = (request.json or {}).get('uid')
    if not uid:
        return jsonify({'success': False, 'message': 'uid gerekli.'})
    # Kendi kendini silme koruması — sistemden kilitlenmeyi önler
    if int(uid) == session.get('user_id'):
        return jsonify({'success': False, 'message': 'Kendinizi silemezsiniz.'})
    ok, msg = db().user_delete(int(uid))
    if ok:
        _audit('user_delete', 'user', uid)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/users/change-password', methods=['POST'])
@login_required
@csrf_protect
def api_change_password():
    """
    Kullanıcı kendi şifresini değiştirir.
    Önce mevcut şifreyi doğrular (admin bile doğrulama atlamaz).
    Yeni şifre minimum 6 karakter.
    """
    data   = request.json or {}
    old_pw = data.get('old_password','')
    new_pw = data.get('new_password','')

    if not old_pw or not new_pw:
        return jsonify({'success': False, 'message': 'Eski ve yeni sifre gerekli.'})
    if len(new_pw) < 6:
        return jsonify({'success': False, 'message': 'Yeni sifre en az 6 karakter olmali.'})

    # Güvenlik: eski şifreyi doğrula — session'daki kullanıcı adını kullan
    user = db().user_authenticate(session['username'], old_pw)
    if not user:
        return jsonify({'success': False, 'message': 'Mevcut sifre yanlis.'})

    ok, msg = db().user_update(session['user_id'], password=new_pw)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/me', methods=['GET'])
@login_required
def api_me():
    """
    Giriş yapmış kullanıcının temel bilgilerini döner.
    Sidebar ve UI bileşenleri için kullanılır.
    """
    return jsonify({
        'id':       session.get('user_id'),
        'username': session.get('username'),
        'role':     session.get('user_role'),  # 'admin' | 'editor'
    })

@app.route('/api/me/theme', methods=['POST'])
@login_required
def api_set_theme():
    """Kullanıcının seçtiği temayı DB'ye ve session'a kaydeder."""
    theme = request.json.get('theme', '')
    ok, msg = db().user_set_theme(session['user_id'], theme)
    if ok:
        session['user_theme'] = theme
    return jsonify({'success': ok, 'message': msg})

# ══════════════════════════════════════════════════════════════════════
#  KUYRUK (HOSTING MODU) ENDPOINTLERİ
# ══════════════════════════════════════════════════════════════════════

def is_hosting_mode():
    """
    .env'deki SEND_MODE değerini kontrol eder.
    'hosting' → kuyruk sistemi aktif (worker.py cPanel cron ile çalışır)
    'local'   → SSE ile anlık gönderim (varsayılan)
    """
    return os.getenv('SEND_MODE', 'local').lower() == 'hosting'


@app.route('/api/queue/create', methods=['POST'])
@login_required
@rate_limit(10, 60)
def queue_create_endpoint():
    """Kuyruğa yeni gönderim görevi ekler."""
    if not is_hosting_mode():
        return jsonify({'success': False, 'message': 'Sadece hosting modunda kullanılabilir.'})

    sender_id  = request.form.get('sender_id')
    rule_id    = request.form.get('rule_id') or None
    name       = request.form.get('name', '').strip() or f"Görev {datetime.datetime.now().strftime('%d.%m %H:%M')}"
    source_type = request.form.get('source_type', 'db')
    email_col  = request.form.get('email_col', '').strip()
    var_cols   = request.form.get('var_cols', '')
    subject_tpl = request.form.get('subject', '').strip()
    body_tpl   = request.form.get('body', '').strip()
    html_mode  = request.form.get('html_mode') == 'true'
    include_unsub = request.form.get('include_unsubscribe') == 'true'
    delay_ms   = int(request.form.get('delay_ms', 500))
    batch_size = int(request.form.get('batch_size', 0))
    batch_wait = int(request.form.get('batch_wait_min', 60))
    table_name = request.form.get('table_name', '').strip()

    if not all([sender_id, email_col, subject_tpl, body_tpl]):
        return jsonify({'success': False, 'message': 'Zorunlu alanlar eksik.'})

    # Excel kaynağı: dosyayı binary olarak oku — worker.py DB'den çekecek
    source_excel = None
    if source_type == 'excel':
        ef = request.files.get('excel')
        if not ef:
            return jsonify({'success': False, 'message': 'Excel dosyası bulunamadı.'})
        source_excel = ef.read()  # LONGBLOB olarak send_queue.source_excel'e kaydedilir

    # Ek dosya: binary olarak sakla — worker.py her maile ekleyecek
    attachment_name = attachment_data = None
    if 'attachment' in request.files:
        att = request.files['attachment']
        if att.filename:
            attachment_name = att.filename
            attachment_data = att.read()

    try:
        qid = db().queue_create(
            name=name, sender_id=int(sender_id), rule_id=int(rule_id) if rule_id else None,
            source_type=source_type, email_col=email_col, var_cols=var_cols,
            subject_tpl=subject_tpl, body_tpl=body_tpl,
            html_mode=html_mode, include_unsub=include_unsub,
            delay_ms=delay_ms, batch_size=batch_size, batch_wait_min=batch_wait,
            source_table=table_name if source_type == 'db' else None,
            source_excel=source_excel,
            attachment_name=attachment_name, attachment_data=attachment_data,
        )
        return jsonify({'success': True, 'queue_id': qid,
                        'message': f'Görev kuyruğa eklendi (#{qid}). Worker en geç 5 dk içinde çalıştıracak.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/queue/list', methods=['GET'])
@login_required
def queue_list_endpoint():
    """
    Son 50 kuyruk görevini döner.
    Hosting modunda değilse boş liste döner (UI bu durumu ayrıca işler).
    """
    if not is_hosting_mode():
        return jsonify({'success': False, 'data': []})
    try:
        rows = db().queue_list(limit=50)
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/queue/progress/<int:qid>', methods=['GET'])
@login_required
def queue_progress_endpoint(qid):
    """
    Hosting modunda UI polling için görev ilerlemesini döner.
    Yanıt: durum, sayaçlar, son 20 log satırı.
    UI her 3 saniyede bu endpoint'i çeker.
    """
    try:
        row = db().queue_get_progress(qid)
        if not row:
            return jsonify({'success': False, 'message': 'Görev bulunamadı.'})
        return jsonify({'success': True, 'data': row})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/queue/cancel/<int:qid>', methods=['POST'])
@login_required
def queue_cancel_endpoint(qid):
    """Kuyruktaki görevi iptal eder."""
    try:
        ok = db().queue_cancel(qid)
        return jsonify({'success': ok, 'message': 'İptal edildi.' if ok else 'İptal edilemedi.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/queue/mode', methods=['GET'])
@login_required
def queue_mode():
    """UI'ın modu öğrenmesi için."""
    return jsonify({'mode': os.getenv('SEND_MODE', 'local')})


# ─── Unsubscribe Hosting DB Config ───────────────────────────────────
@app.route('/api/unsub-db-config', methods=['GET'])
@login_required
def get_unsub_db_config():
    """Unsubscribe uygulama ayarlarını .env'den okur."""
    return jsonify({
        'UNSUB_DB_HOST':     os.getenv('UNSUB_DB_HOST', ''),
        'UNSUB_DB_PORT':     os.getenv('UNSUB_DB_PORT', '3306'),
        'UNSUB_DB_USER':     os.getenv('UNSUB_DB_USER', ''),
        'UNSUB_DB_NAME':     os.getenv('UNSUB_DB_NAME', ''),
        'UNSUB_APP_URL':     os.getenv('UNSUB_APP_URL', ''),
    })

@app.route('/api/unsub-db-config', methods=['POST'])
@login_required
@rate_limit(5, 60)
def save_unsub_db_config():
    """Unsubscribe uygulama ayarlarını .env'e kaydeder."""
    data = request.json
    keys = ['UNSUB_DB_HOST','UNSUB_DB_PORT','UNSUB_DB_USER','UNSUB_DB_PASSWORD','UNSUB_DB_NAME','UNSUB_APP_URL']
    ENV_PATH.touch(exist_ok=True)
    for k in keys:
        if data.get(k) is not None:
            set_key(str(ENV_PATH), k, str(data[k]))
    load_dotenv(ENV_PATH, override=True)
    # Bağlantıyı test et
    try:
        import pymysql
        conn = pymysql.connect(
            host=os.getenv('UNSUB_DB_HOST'),
            port=int(os.getenv('UNSUB_DB_PORT', 3306)),
            user=os.getenv('UNSUB_DB_USER'),
            password=os.getenv('UNSUB_DB_PASSWORD',''),
            database=os.getenv('UNSUB_DB_NAME'),
            connect_timeout=5,
        )
        conn.close()
        return jsonify({'success': True, 'message': 'Bağlantı başarılı! Ayarlar kaydedildi.'})
    except Exception as e:
        return jsonify({'success': True, 'message': f'Ayarlar kaydedildi fakat bağlantı hatası: {e}'})

# ─── Unsubscribe API ──────────────────────────────────────────────────
@app.route('/api/unsubscribe', methods=['POST'])
@rate_limit(10, 60)  # Dakikada 10 istek — token brute-force koruması
def unsubscribe():
    """
    Unsubscribe token'ını doğrular ve e-postayı suppression listesine ekler.
    Token tek kullanımlıktır — verify_unsubscribe_token() işaretler.
    Başarılıysa e-posta adresi de yanıtta döner (onay sayfasında göstermek için).
    """
    data  = request.json
    token = data.get('token', '').strip()

    if not token:
        return jsonify({'success': False, 'message': 'Geçersiz istek: token eksik.'})

    # Token doğrula ve tüket — geçersizse None döner
    email = db().verify_unsubscribe_token(token)
    if not email:
        return jsonify({'success': False, 'message': 'Bu link geçersiz veya daha önce kullanılmış.'})

    # E-postayı suppression listesine ekle (reason: unsubscribe, kaynak: web-form)
    success = db().add_to_suppression(email, 'unsubscribe', 'web-form')
    if success:
        return jsonify({'success': True, 'message': 'Abonelikten çıkma işlemi başarılı.', 'email': email})
    else:
        return jsonify({'success': False, 'message': 'Bir hata oluştu, lütfen tekrar deneyin.'})

@app.route('/api/unsubscribe-preview', methods=['POST'])
@rate_limit(20, 60)
def unsubscribe_preview():
    """Token'a ait e-posta adresini token'ı tüketmeden döner (onay ekranında göstermek için)."""
    data = request.json
    token = data.get('token', '').strip()
    if not token:
        return jsonify({'email': None, 'message': 'Token eksik.'})
    email = db().peek_unsubscribe_token(token)
    if not email:
        return jsonify({'email': None, 'message': 'Geçersiz veya süresi dolmuş link.'})
    return jsonify({'email': email})

# ─── Log API ──────────────────────────────────────────────────────────
@app.route('/api/send-log/summary', methods=['GET'])
@login_required
def get_send_log_summary():
    """Tüm gönderim loglarının özet istatistiğini döner — özet kart için."""
    summary = db().get_log_summary()
    return jsonify({'success': True, 'data': summary})


@app.route('/api/send-log', methods=['GET'])
@login_required
def get_send_log():
    """Gönderim geçmişini filtreli ve sayfalı döner."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    sender_id = request.args.get('sender_id')
    status = request.args.get('status')
    search = request.args.get('search')
    
    rows, total = db().get_send_log(page, per_page, sender_id, status, search)
    for r in rows:
        if isinstance(r.get('sent_at'), datetime.datetime):
            r['sent_at'] = r['sent_at'].strftime('%d.%m.%Y %H:%M:%S')
    return jsonify({'success': True, 'data': rows, 'total': total, 'page': page})

@app.route('/api/send-log/clear', methods=['DELETE'])
@login_required
@admin_required
@csrf_protect
@rate_limit(5, 60)
def clear_send_log():
    """Tüm gönderim loglarını siler (geri alınamaz)."""
    sender_id = request.args.get('sender_id')  # opsiyonel: sadece belirli göndericinin logları
    ok, msg = db().clear_send_log(sender_id=int(sender_id) if sender_id else None)
    return jsonify({'success': ok, 'message': msg})

# ─── E-posta Format ve MX Doğrulama ──────────────────────────────────────────
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# MX sorgu cache — aynı domain'i tekrar sorgulamaz
# {domain: True/False} — process boyunca bellekte tutulur
# MAX_MX_CACHE_SIZE: çok uzun çalışan sunucularda bellek şişmesini önler
_mx_cache: dict = {}
_mx_lock = __import__('threading').Lock()
_MAX_MX_CACHE = 50_000  # Bu kadar domain önbelleğe alındıktan sonra temizlenir

def check_mx(domain: str, timeout: float = 1.0) -> bool:
    """
    Domain'in geçerli bir MX (mail exchange) kaydı olup olmadığını kontrol eder.

    Cache sistemi:
      - Aynı domain daha önce sorgulandıysa DNS'e tekrar gitmez
      - 84.000 adreslik listede genellikle ~5.000-10.000 farklı domain vardır
      - Cache sayesinde her domain yalnızca bir kez sorgulanır
      - Cache _MAX_MX_CACHE boyutunu aşarsa otomatik temizlenir (bellek koruması)

    Timeout: 1 saniye — yanıt gelmezse geçerli sayar (false negative riski
    almak yerine false positive tercih edilir, gönderim kesilmesin)

    Dönen değer:
      True  → MX kaydı var, domain mail alabiliyor
      False → MX kaydı yok, domain mail alamıyor (hard bounce garantisi)
    """
    domain = domain.strip().lower()
    with _mx_lock:
        if domain in _mx_cache:
            return _mx_cache[domain]
        # Cache çok büyüdüyse temizle (bellek koruması)
        if len(_mx_cache) >= _MAX_MX_CACHE:
            _mx_cache.clear()

    try:
        import socket
        # DNS MX sorgusu için dns.resolver kullan, yoksa socket fallback
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX', lifetime=timeout)
            result = len(answers) > 0
        except ImportError:
            # dnspython yüklü değilse socket ile A kaydı kontrolü yap
            # MX kadar kesin değil ama hiç yoktan iyi
            try:
                socket.setdefaulttimeout(timeout)
                socket.gethostbyname(domain)
                result = True
            except socket.gaierror:
                result = False
    except Exception:
        result = True  # Hata durumunda geçerli say — gönderimi kesme

    with _mx_lock:
        _mx_cache[domain] = result
    return result


def is_valid_email_with_mx(email: str, use_mx: bool = False) -> tuple[bool, str]:
    """
    E-posta format kontrolü + isteğe bağlı MX sorgusu.

    Dönen değer: (geçerli_mi, hata_sebebi)
      (True,  '')                        → geçerli
      (False, 'Geçersiz e-posta formatı') → format hatası
      (False, 'MX kaydı yok: domain.com') → domain mail alamıyor
    """
    if not is_valid_email(email):
        return False, 'Geçersiz e-posta formatı'
    if use_mx:
        domain = email.rsplit('@', 1)[1].lower()
        if not check_mx(domain):
            return False, f'MX kaydı yok: {domain}'
    return True, ''


# Rol bazlı adres önekleri — bu adresler genelde kişisel değil, açılma oranı düşük
_ROLE_PREFIXES = {
    'info', 'admin', 'administrator', 'support', 'help', 'helpdesk',
    'noreply', 'no-reply', 'donotreply', 'do-not-reply',
    'contact', 'sales', 'marketing', 'billing', 'accounts',
    'postmaster', 'webmaster', 'hostmaster', 'abuse',
    'newsletter', 'mail', 'email', 'office', 'reception',
}

# check_mx — yukarıda tanımlıdır (satır ~1793)


def is_role_based(email: str) -> bool:
    """
    Rol bazlı e-posta adresi mi kontrol eder.
    info@, admin@, noreply@ gibi adresler cold email için düşük değerli.
    """
    if '@' not in email:
        return False
    local = email.split('@')[0].lower().strip()
    return local in _ROLE_PREFIXES

def is_valid_email(email: str) -> bool:
    """
    E-posta adresinin formatını doğrular.
    Sadece @ varlığını değil, RFC uyumlu formatı kontrol eder.
    Yakalanan durumlar:
      - Çift nokta: info@unimet..com.tr
      - Nokta ile başlama/bitme: .user@domain.com
      - Domain'de TLD eksikliği: user@domain
      - Çok uzun adres: >254 karakter
      - Unicode/özel karakter içeren domain
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254:
        return False
    if not _EMAIL_RE.match(email):
        return False
    local, domain = email.rsplit('@', 1)
    if '..' in local or '..' in domain:
        return False
    if local.startswith('.') or local.endswith('.'):
        return False
    if domain.startswith('.') or domain.endswith('.'):
        return False
    return True


def sse(data: dict) -> str:
    """
    Server-Sent Events formatında veri satırı oluşturur.
    Tarayıcı EventSource API'si bu formatı otomatik parse eder.
    ensure_ascii=False: Türkçe karakterler bozulmadan gönderilir.
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def heartbeat_sleep(delay_ms: float):
    """
    Mail gönderimler arası beklemeyi Cloudflare/proxy timeout'una karşı
    SSE heartbeat'lerle parçalar.

    Cloudflare Pro/Business: 100 saniyelik upstream timeout uygular.
    Eğer SSE stream'de 30+ saniye veri gönderilmezse bağlantıyı keser
    ve istemci tarafında 502 hatası oluşur.

    Çözüm: Bekleme süresini HEARTBEAT_INTERVAL'lık dilimlere böl,
    her dilimin sonunda SSE comment satırı (': heartbeat') gönder.
    SSE comment'leri tarayıcı tarafından görmezden gelinir ama
    proxy'ye "bağlantı hâlâ aktif" sinyali verir.

    Kullanım: time.sleep(delay_ms/1000) yerine yield from heartbeat_sleep(delay_ms)
    """
    HEARTBEAT_INTERVAL = 8.0    # saniye — localhost dahil tüm ortamlarda bağlantıyı canlı tutar
    HEARTBEAT_MSG      = ": heartbeat\n\n"

    remaining = delay_ms / 1000.0
    while remaining > 0:
        chunk = min(remaining, HEARTBEAT_INTERVAL)
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0:          # son dilimde gereksiz heartbeat gönderme
            yield HEARTBEAT_MSG

# ─── EC2 Auto-Stop ────────────────────────────────────────────────────
def _get_instance_id() -> str:
    """
    EC2 instance metadata servisinden kendi instance ID'sini alır.
    IMDSv2 protokolü: önce PUT ile token al, sonra token'la instance-id sorg.
    IMDSv2 başarısız olursa eski IMDSv1 yolunu dener (fallback).
    """ 
    import urllib.request
    try:
        req = urllib.request.Request(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            method='PUT'
        )
        token = urllib.request.urlopen(req, timeout=2).read().decode()
        req2 = urllib.request.Request(
            'http://169.254.169.254/latest/meta-data/instance-id',
            headers={'X-aws-ec2-metadata-token': token}
        )
        return urllib.request.urlopen(req2, timeout=2).read().decode()
    except Exception:
        return urllib.request.urlopen(
            'http://169.254.169.254/latest/meta-data/instance-id', timeout=2
        ).read().decode()

def _get_ec2_region() -> str:
    """EC2 instance'ının bölgesini metadata API'den okur."""
    import urllib.request
    try:
        req = urllib.request.Request(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            method='PUT'
        )
        token = urllib.request.urlopen(req, timeout=2).read().decode()
        req2 = urllib.request.Request(
            'http://169.254.169.254/latest/meta-data/placement/region',
            headers={'X-aws-ec2-metadata-token': token}
        )
        return urllib.request.urlopen(req2, timeout=2).read().decode()
    except Exception:
        return os.getenv('AWS_REGION', 'us-east-1')

def stop_this_ec2(delay_seconds: int = 5):
    """
    Belirtilen saniye sonra EC2 instance'ını durdurur.
    Daemon thread kullanılır: Flask yanıtı döndükten sonra da çalışmaya devam eder.
    boto3.ec2.stop_instances(): instance'ı durdurur (siler değil — EBS verisi korunur).
    """ 
    import threading
    def _stop():
        """EC2 durdurma işlemini arka plan thread'de çalıştırır."""
        time.sleep(delay_seconds)
        try:
            import boto3
            instance_id = _get_instance_id()
            region = _get_ec2_region()
            ec2 = boto3.client('ec2', region_name=region)
            ec2.stop_instances(InstanceIds=[instance_id])
            print(f"[EC2 Auto-Stop] {instance_id} durduruldu.")
        except Exception as e:
            print(f"[EC2 Auto-Stop] Hata: {e}")
    threading.Thread(target=_stop, daemon=True).start()

@app.route('/api/ec2-stop', methods=['POST'])
@login_required
@admin_required
@csrf_protect
def ec2_stop():
    """EC2 instance'ını durdurur."""
    stop_this_ec2(delay_seconds=5)
    return jsonify({'success': True, 'message': 'EC2 5 saniye içinde duruyor...'})

@app.route('/api/ec2-instance-id', methods=['GET'])
@login_required
def ec2_instance_id():
    """EC2 instance ID'sini metadata API'den okur."""
    try:
        iid = _get_instance_id()
        return jsonify({'success': True, 'instance_id': iid})
    except Exception:
        return jsonify({'success': False, 'instance_id': None})

# ── İlk istek öncesi otomatik DB başlatma ────────────────────────────
# _db_migrated bayrağı: migration sadece bir kez çalışsın diye
_db_migrated = False

@app.before_request
def auto_migrate():
    """
    Her istekten önce çalışır (before_request hook).
    ensure_admin_exists(): hiç kullanıcı yoksa admin/admin123 oluşturur.
    DB migration sadece ilk istekte çalışır (_db_migrated bayrağı ile):
      - init_db(): tabloları oluşturur (IF NOT EXISTS)
      - migrate_db(): eksik kolonları ekler (API gönderici desteği)
    DB yapılandırılmamışsa migration sessizce atlanır.
    """
    ensure_admin_exists()  # Her istekte çalışır ama user_count()=0 dışında bir şey yapmaz
    global _db_migrated
    if not _db_migrated:
        _db_migrated = True  # Bir kez çalıştır bayrağını işaretle
        try:
            # Tüm DB ortam değişkenleri ayarlanmışsa migration'ı çalıştır
            if all([os.getenv('DB_HOST'), os.getenv('DB_USER'), os.getenv('DB_NAME')]):
                db().init_db()    # Yeni tabloları oluştur
                db().migrate_db() # Eksik kolonları ekle
        except Exception as e:
            print(f"[auto_migrate] {e}")  # Hata varsa uygulama yine de çalışsın


# ══════════════════════════════════════════════════════════════════════
#  E-POSTA DOĞRULAMA (Liste Temizleme) ENDPOINTLERİ
# ══════════════════════════════════════════════════════════════════════

@app.route('/settings/help')
@login_required
def settings_help():
    """Tam kullanım kılavuzu sayfası."""
    from help_content import GUIDE
    return render_template('pages/settings/help.html', guide=GUIDE)


@app.route('/settings/verify')
@login_required
def settings_verify():
    """Liste Temizleme ayarlar sayfası."""
    return render_template('pages/settings/verify.html')


@app.route('/api/verify/jobs', methods=['GET'])
@login_required
def api_verify_jobs():
    """Tüm doğrulama işlerini listeler (UI her 5sn poll eder)."""
    return jsonify({'success': True, 'data': db().verify_job_list()})


@app.route('/api/verify/start', methods=['POST'])
@login_required
def api_verify_start():
    """
    Yeni doğrulama işi kuyruğa ekler.
    İşi gerçekten çalıştıran worker.py'dir (cPanel cron, her 5 dakika).
    Sekme kapatılsa da iş arka planda devam eder.
    """
    try:
        data       = request.json or {}
        table_name = data.get('table_name', '').strip()
        email_col  = data.get('email_col', '').strip()
        mode       = data.get('mode', 'mx')
        threads    = int(data.get('threads', 10))
        job_name   = data.get('job_name', f"{table_name} — doğrulama").strip()

        if not table_name or not email_col:
            return jsonify({'success': False, 'message': 'Tablo ve e-posta kolonu zorunlu.'})
        if mode not in ('format', 'mx', 'smtp'):
            return jsonify({'success': False, 'message': 'Geçersiz mod.'})
        if not 1 <= threads <= 30:
            return jsonify({'success': False, 'message': 'Thread sayısı 1-30 arası olmalı.'})

        ok, job_id = db().verify_job_create(
            job_name=job_name,
            table_name=table_name,
            email_col=email_col,
            mode=mode,
            threads=threads,
            user_id=session.get('user_id'),
            username=session.get('username'),
        )
        if not ok:
            return jsonify({'success': False, 'message': str(job_id)})

        _audit('verify_start', 'verify', job_id,
               detail=f"table={table_name} col={email_col} mode={mode}")

        # Local modda (geliştirme ortamı) işi arka plan thread'de hemen başlat
        # Hosting modunda worker.py cron ile çalıştırır
        if not is_hosting_mode():
            import threading
            def _run():
                """Verify işini arka plan thread'de çalıştırır."""
                try:
                    from verifier import run_verify_job
                    run_verify_job(job_id=job_id, cancel_flags={})
                except Exception as e:
                    import traceback
                    print("[verify thread ERROR] " + str(e) + "\n" + traceback.format_exc())
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            msg = 'İş başlatıldı. Sayfa otomatik güncellenecek.'
        else:
            msg = 'İş kuyruğa alındı. worker.py en geç 5 dakika içinde başlatacak.'

        return jsonify({
            'success': True,
            'job_id':  job_id,
            'message': msg,
        })

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print("[api_verify_start ERROR] " + str(e) + "\n" + err)
        return jsonify({'success': False, 'message': f'Sunucu hatası: {str(e)}'})


@app.route('/api/verify/cancel/<int:job_id>', methods=['POST'])
@login_required
def api_verify_cancel(job_id):
    """
    İşi iptal eder.
    'running' veya 'pending' durumundaki işleri 'cancelled' yapar.
    Takılı kalmış (stuck) işleri de temizler.
    """
    db().verify_job_cancel(job_id)
    _audit('verify_cancel', 'verify', job_id)
    return jsonify({'success': True})

@app.route('/api/verify/export-clean', methods=['POST'])
@login_required
@rate_limit(10, 60)
def api_verify_export_clean():
    """
    Doğrulanmış adresleri yeni bir tabloya kopyalar.
    Kaynak tablodaki is_valid=1 (ve isteğe bağlı -1) satırları
    yeni isimli bir tabloya CREATE TABLE AS SELECT ile aktarır.
    """
    try:
        data           = request.json or {}
        source_table   = data.get('source_table', '').strip()
        new_table_name = data.get('new_table_name', '').strip()
        include_risky  = data.get('include_risky', False)

        if not source_table or not new_table_name:
            return jsonify({'success': False, 'message': 'Kaynak tablo ve yeni tablo adı zorunludur.'})

        ok, result = db().export_verified_table(
            source_table=source_table,
            new_table_name=new_table_name,
            include_risky=include_risky,
        )
        if not ok:
            return jsonify({'success': False, 'message': str(result)})

        _audit('verify_export', 'verify', None,
               detail=f"source={source_table} new={new_table_name} risky={include_risky} rows={result}")

        label = "geçerli+riskli" if include_risky else "geçerli"
        return jsonify({
            'success':    True,
            'row_count':  result,
            'table_name': new_table_name,
            'message':    f"'{new_table_name}' tablosu oluşturuldu — {result:,} {label} adres kopyalandı.",
        })

    except Exception as e:
        import traceback
        print("[api_verify_export_clean ERROR] " + str(e) + "\n" + traceback.format_exc())
        return jsonify({'success': False, 'message': f'Sunucu hatası: {str(e)}'})


@app.route('/api/verify/reset-stuck', methods=['POST'])
@login_required
def api_verify_reset_stuck():
    """
    10 dakikadan uzun süredir 'running' durumunda olan işleri
    'cancelled' yaparak temizler. Uygulama yeniden başladığında
    veya worker çöktüğünde askıda kalan işler için kullanılır.
    """
    conn = db().get_connection() if hasattr(db(), 'get_connection') else None
    try:
        import database as _db
        _conn = _db.get_connection()
        with _conn.cursor() as cur:
            cur.execute("""
                UPDATE email_verify_jobs
                SET status='cancelled', finished_at=UTC_TIMESTAMP()
                WHERE status IN ('running','pending')
                AND started_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 10 MINUTE)
            """)
            affected = cur.rowcount
        _conn.commit()
        return jsonify({'success': True, 'cancelled': affected,
                        'message': f'{affected} takılı iş temizlendi.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    return jsonify({'success': True, 'message': 'İptal edildi. Worker bir sonraki döngüde durduracak.'})


@app.route('/api/verify/smtp-skip', methods=['GET'])
@login_required
def api_verify_smtp_skip_get():
    """SMTP muaf domain listesini döner."""
    from verifier import _SMTP_SKIP_BASE
    user_domains  = db().smtp_skip_domains_get()
    return jsonify({
        'success':      True,
        'user_domains': user_domains,
        'base_domains': sorted(_SMTP_SKIP_BASE),
    })


@app.route('/api/verify/smtp-skip', methods=['POST'])
@login_required
@admin_required
def api_verify_smtp_skip_set():
    """SMTP muaf domain listesini günceller (admin only)."""
    data    = request.json or {}
    domains = data.get('domains', [])
    if not isinstance(domains, list):
        return jsonify({'success': False, 'message': 'domains listesi bekleniyor.'})
    ok = db().smtp_skip_domains_set(domains)
    if ok:
        # Önbelleği sıfırla
        from verifier import _get_smtp_skip_domains
        _get_smtp_skip_domains._ts = 0
        _audit('smtp_skip_update', 'setting', 'smtp_skip_domains',
               detail=f"{len(domains)} domain")
    return jsonify({'success': ok, 'message': 'Kaydedildi.' if ok else 'Kayıt hatası.'})


@app.route('/api/verify/jobs/<int:job_id>', methods=['GET'])
@login_required
def api_verify_job_detail(job_id):
    """Tek bir iş detayını döner (ilerleme izleme için)."""
    j = db().verify_job_get(job_id)
    if not j:
        return jsonify({'success': False, 'message': 'İş bulunamadı.'})
    return jsonify({'success': True, 'data': j})

# ══════════════════════════════════════════════════════════════════════
#  ŞİFRE SIFIRLAMA ROUTE'LARI
# ══════════════════════════════════════════════════════════════════════

@app.route('/auth/forgot-password', methods=['GET', 'POST'])
@rate_limit(3, 300)  # 5 dakikada 3 reset isteği — e-posta spam önleme
def forgot_password():
    """
    GET  → Şifremi unuttum formu
    POST → Kullanıcı adı veya e-posta ile reset maili gönder
    """
    if request.method == 'GET':
        return render_template('forgot_password.html')

    data     = request.json or {}
    identity = data.get('identity', '').strip()  # kullanıcı adı veya e-posta

    if not identity:
        return jsonify({'success': False, 'message': 'Kullanıcı adı veya e-posta gerekli.'})

    # Kullanıcıyı bul
    user = db().get_user_by_username(identity) or db().get_user_by_email(identity)

    # Güvenlik: kullanıcı bulunamasa bile aynı mesajı dön (kullanıcı tespitini önle)
    if not user or not user.get('email'):
        return jsonify({
            'success': True,
            'message': 'Kayıtlı e-posta adresiniz varsa sıfırlama bağlantısı gönderildi.'
        })

    # Token oluştur
    token = db().password_reset_create_token(user['id'], user['username'])

    # Reset URL'i oluştur
    base_url = request.host_url.rstrip('/')
    reset_url = f"{base_url}/auth/reset-password/{token}"

    # Mail gönder — sisteme tanımlı ilk aktif SMTP/SES göndericiyi kullan
    mail_error = None
    try:
        senders = db().get_senders(active_only=False)
        sender = next((s for s in (senders or []) if s.get('sender_mode') in ('smtp', 'ses') and s.get('is_active', 1)), None)
        if not sender:
            return jsonify({
                'success': False,
                'message': 'Sistem gönderici yapılandırılmamış. '
                           'Ayarlar > SMTP/SES bölümünde bir gönderici ekleyin, '
                           'ya da reset_password.py ile şifreyi komut satırından sıfırlayın.'
            })

        subject = "MailSender Pro — Şifre Sıfırlama"
        body = f"""<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
<h2 style="color:#6366f1">🔐 Şifre Sıfırlama</h2>
<p>Merhaba <strong>{user['username']}</strong>,</p>
<p>Şifrenizi sıfırlamak için aşağıdaki butona tıklayın:</p>
<p style="margin:24px 0">
  <a href="{reset_url}"
     style="background:#6366f1;color:#fff;padding:12px 24px;border-radius:8px;
            text-decoration:none;font-weight:600;display:inline-block">
    Şifremi Sıfırla →
  </a>
</p>
<p style="font-size:12px;color:#999">
  Bağlantı çalışmıyorsa aşağıdaki adresi tarayıcınıza yapıştırın:<br>
  <code style="font-size:11px;word-break:break-all">{reset_url}</code>
</p>
<p style="font-size:12px;color:#888">Bu bağlantı <strong>1 saat</strong> geçerlidir.<br>
Bu isteği siz yapmadıysanız bu maili görmezden gelin.</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="font-size:11px;color:#aaa">MailSender Pro · {request.host}</p>
</div>"""

        mode = sender.get('sender_mode', 'smtp')
        import traceback as _tb
        if mode == 'smtp':
            from mailer import send_one
            success, err = send_one(sender, user['email'], subject, body)
            if not success:
                mail_error = f"SMTP hatası: {err}"
        elif mode == 'ses':
            from mailer import send_via_ses
            send_via_ses(sender, user['email'], subject, body, include_unsubscribe=False)

    except Exception as e:
        import traceback as _tb
        mail_error = str(e)
        print(f"[forgot_password] HATA: {e}")
        print(_tb.format_exc())

    if mail_error:
        print(f"[forgot_password] mail gönderilemedi → {mail_error}")
        return jsonify({
            'success': False,
            'message': f'Mail gönderilemedi: {mail_error} — '
                       f'Alternatif: python reset_password.py {user["username"]} yenisifre'
        })

    return jsonify({
        'success': True,
        'message': f'Sıfırlama bağlantısı {user["email"]} adresine gönderildi. Spam klasörünü de kontrol edin.'
    })


@app.route('/auth/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    GET  → Yeni şifre belirleme formu (token geçerliyse göster)
    POST → Yeni şifreyi kaydet, tokeni kullanılmış yap
    """
    if request.method == 'GET':
        row = db().password_reset_verify_token(token)
        if not row:
            return render_template('reset_password.html',
                                   token=token, error='Bu bağlantı geçersiz veya süresi dolmuş.')
        return render_template('reset_password.html', token=token, error=None,
                               username=row['username'])

    # POST — yeni şifreyi kaydet
    data     = request.json or {}
    password = data.get('password', '')
    confirm  = data.get('confirm', '')

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Şifre en az 6 karakter olmalı.'})
    if password != confirm:
        return jsonify({'success': False, 'message': 'Şifreler eşleşmiyor.'})

    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    ok = db().password_reset_use_token(token, pw_hash)
    if not ok:
        return jsonify({'success': False, 'message': 'Bağlantı geçersiz veya süresi dolmuş.'})

    return jsonify({'success': True, 'message': 'Şifreniz güncellendi. Giriş yapabilirsiniz.'})


# ══════════════════════════════════════════════════════════════════════
#  AWS SES — SNS WEBHOOK, İTİBAR MONİTÖRÜ, OTOMATİK HIZ
#  Bu bölüm: bounce/complaint bildirimleri, hesap itibarı izleme,
#  otomatik gönderim hızı hesaplama ve konfigürasyon seti yönetimi.
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/ses/sns-webhook', methods=['POST'])
def ses_sns_webhook():
    """
    AWS SNS → SES Bounce/Complaint/Delivery bildirimleri burada alınır.
    SNS bu endpoint'e POST atar. İki aşama:
      1. SubscriptionConfirmation → SNS'i onaylama URL'ini ziyaret et
      2. Notification             → Bounce/Complaint parse et, suppression'a ekle

    SNS Topic Subscription URL olarak bu endpoint'i kaydedin:
      https://yourdomain.com/api/ses/sns-webhook
    Auth YOK — SNS imzası doğrulanır.
    """
    import json as _json

    raw = request.get_data(as_text=True)
    try:
        msg = _json.loads(raw)
    except Exception:
        return jsonify({'error': 'JSON parse hatası'}), 400

    msg_type = msg.get('Type', '')

    # ── Adım 1: SNS Subscription Confirmation ──────────────────────
    if msg_type == 'SubscriptionConfirmation':
        confirm_url = msg.get('SubscribeURL')
        if confirm_url:
            try:
                import urllib.request
                urllib.request.urlopen(confirm_url, timeout=10)
                print(f"[SNS] Subscription onaylandı: {confirm_url[:80]}")
            except Exception as e:
                print(f"[SNS] Onay hatası: {e}")
        return jsonify({'ok': True})

    # ── Adım 2: Notification ────────────────────────────────────────
    if msg_type != 'Notification':
        return jsonify({'ok': True})

    try:
        payload = _json.loads(msg.get('Message', '{}'))
    except Exception:
        return jsonify({'ok': True})

    notif_type = payload.get('notificationType', '')  # Bounce | Complaint | Delivery

    if notif_type == 'Bounce':
        bounce     = payload.get('bounce', {})
        btype      = bounce.get('bounceType', '')      # Permanent | Transient
        bsubtype   = bounce.get('bounceSubType', '')   # General | NoEmail | Suppressed
        recipients = [r.get('emailAddress', '')
                      for r in bounce.get('bouncedRecipients', [])]
        feedback_id = bounce.get('feedbackId', '')

        for email in recipients:
            if not email:
                continue
            # Kalıcı bounce → suppression'a ekle
            if btype == 'Permanent':
                db().add_to_suppression(email, 'bounce', source='ses_sns')
            db().ses_notification_save(
                notif_type='Bounce', recipient=email,
                bounce_type=btype, bounce_sub=bsubtype,
                feedback_id=feedback_id, raw_json=raw[:4000]
            )
        print(f"[SNS] Bounce: {btype}/{bsubtype} → {recipients}")

    elif notif_type == 'Complaint':
        complaint   = payload.get('complaint', {})
        recipients  = [r.get('emailAddress', '')
                       for r in complaint.get('complainedRecipients', [])]
        feedback_id = complaint.get('feedbackId', '')

        for email in recipients:
            if not email:
                continue
            # Şikayet → her zaman suppression'a ekle
            db().add_to_suppression(email, 'complaint', source='ses_sns')
            db().ses_notification_save(
                notif_type='Complaint', recipient=email,
                feedback_id=feedback_id, raw_json=raw[:4000]
            )
        print(f"[SNS] Complaint → {recipients}")

    elif notif_type == 'Delivery':
        delivery    = payload.get('delivery', {})
        recipients  = delivery.get('recipients', [])
        for email in recipients:
            db().ses_notification_save(
                notif_type='Delivery', recipient=email, raw_json=None
            )

    return jsonify({'ok': True})


@app.route('/api/ses/reputation/<int:sender_id>', methods=['GET'])
@login_required
def ses_reputation(sender_id):
    """Son 7 günün bounce/complaint oranını döner."""
    days  = int(request.args.get('days', 7))
    stats = db().ses_reputation_stats(sender_id=sender_id, days=days)
    return jsonify({'success': True, 'data': stats})


@app.route('/api/ses/reputation', methods=['GET'])
@login_required
def ses_reputation_all():
    """Tüm SES göndericilerin toplam itibar istatistiği."""
    days  = int(request.args.get('days', 7))
    stats = db().ses_reputation_stats(days=days)
    return jsonify({'success': True, 'data': stats})


@app.route('/api/ses/auto-delay/<int:sender_id>', methods=['GET'])
@login_required
def ses_auto_delay(sender_id):
    """
    SES gönderim limitine göre önerilen delay_ms değerini hesaplar.
    max_send_rate → saniyede gönderilebilecek max mail
    Güvenlik marjı %80 → delay_ms = 1000 / (max_rate * 0.8)
    """
    sender_row = db().get_sender(sender_id)
    if not sender_row or sender_row.get('sender_mode') != 'ses':
        return jsonify({'success': False, 'message': 'SES gönderici bulunamadı.'})
    try:
        from mailer import _resolve_aws_credentials
        import boto3
        aws_key, aws_secret, aws_region = _resolve_aws_credentials(sender_row)
        session = boto3.Session(
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region,
        )
        client    = session.client('ses')
        quota     = client.get_send_quota()
        max_rate  = float(quota.get('MaxSendRate', 1))
        # %80 marj ile hesapla, minimum 200ms
        safe_rate = max_rate * 0.8
        delay_ms  = max(200, int(1000 / safe_rate)) if safe_rate > 0 else 1000
        return jsonify({
            'success':   True,
            'max_rate':  max_rate,
            'delay_ms':  delay_ms,
            'note':      f'SES limitiniz {max_rate}/sn — güvenli delay: {delay_ms}ms'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/ses/configuration-sets/<int:sender_id>', methods=['GET'])
@login_required
def ses_configuration_sets(sender_id):
    """SES hesabındaki mevcut ConfigurationSet'leri listeler."""
    sender_row = db().get_sender(sender_id)
    if not sender_row or sender_row.get('sender_mode') != 'ses':
        return jsonify({'success': False, 'message': 'SES gönderici bulunamadı.'})
    try:
        from mailer import _resolve_aws_credentials
        import boto3
        aws_key, aws_secret, aws_region = _resolve_aws_credentials(sender_row)
        session = boto3.Session(
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region,
        )
        client = session.client('ses')
        resp   = client.list_configuration_sets(MaxItems=50)
        names  = [cs['Name'] for cs in resp.get('ConfigurationSets', [])]
        return jsonify({'success': True, 'configuration_sets': names})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ══════════════════════════════════════════════════════════════════════
#  WEBHOOK ENDPOINTLERİ — Bounce/Complaint otomatik suppression
# ══════════════════════════════════════════════════════════════════════

def _webhook_add_suppression(email: str, reason: str, source: str, detail: str = ''):
    """Webhook'tan gelen bounce/complaint için suppression ekler ve loglar."""
    if not email or '@' not in email:
        return
    email = email.strip().lower()
    db().add_to_suppression(email, reason, source=source)
    print(f"[webhook] Suppression eklendi: {email} ({reason}) [{source}] {detail}")


@app.route('/webhook/brevo', methods=['POST'])
def webhook_brevo():
    """
    Brevo (Sendinblue) webhook endpoint'i.
    Brevo Dashboard → Settings → Webhooks → URL: https://siteniz.com/webhook/brevo
    Events: hard_bounce, soft_bounce, spam, unsubscribe

    Güvenlik — iki yöntem desteklenir (birlikte veya ayrı kullanılabilir):

    1. Basic Authentication (önerilen — Brevo panelinde kolayca ayarlanır):
       .env'ye ekleyin:
         BREVO_WEBHOOK_USER=webhook
         BREVO_WEBHOOK_PASS=guclu-bir-sifre-belirleyin
       Brevo panelinde Authentication Method: Basic
         Username: webhook  (BREVO_WEBHOOK_USER ile aynı)
         Password: guclu-bir-sifre-belirleyin  (BREVO_WEBHOOK_PASS ile aynı)

    2. HMAC İmza Doğrulama (alternatif):
       .env'ye ekleyin: BREVO_WEBHOOK_SECRET=gizli-anahtar
       Brevo bu anahtarla her isteği imzalar, sistem doğrular.

    İkisi de tanımlı değilse webhook kimlik doğrulamasız çalışır (güvensiz).
    """
    import base64

    # ── Yöntem 1: Basic Authentication ────────────────────────────────
    wb_user = os.getenv('BREVO_WEBHOOK_USER', '').strip()
    wb_pass = os.getenv('BREVO_WEBHOOK_PASS', '').strip()
    if wb_user and wb_pass:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Basic '):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                provided_user, provided_pass = decoded.split(':', 1)
                if provided_user != wb_user or provided_pass != wb_pass:
                    return jsonify({'error': 'Unauthorized'}), 401
            except Exception:
                return jsonify({'error': 'Unauthorized'}), 401
        else:
            return jsonify({'error': 'Unauthorized'}), 401

    # ── Yöntem 2: HMAC İmza Doğrulama (Basic yoksa kontrol edilir) ───
    elif os.getenv('BREVO_WEBHOOK_SECRET', ''):
        import hmac, hashlib
        secret = os.getenv('BREVO_WEBHOOK_SECRET', '')
        sig = request.headers.get('X-Brevo-Signature', '')
        expected = hmac.new(secret.encode(), request.data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return jsonify({'error': 'Invalid signature'}), 401

    events = request.json
    if not isinstance(events, list):
        events = [events]

    processed = 0
    for ev in events:
        event_type = ev.get('event', '')
        email      = ev.get('email', '')
        msg_id     = ev.get('message-id', ev.get('MessageId', ''))

        if event_type in ('hard_bounce', 'blocked'):
            _webhook_add_suppression(email, 'bounce', 'brevo',
                detail=f"type={event_type} msg_id={msg_id}")
            processed += 1
        elif event_type in ('spam', 'complaint'):
            _webhook_add_suppression(email, 'complaint', 'brevo',
                detail=f"msg_id={msg_id}")
            processed += 1
        elif event_type == 'unsubscribe':
            _webhook_add_suppression(email, 'unsubscribe', 'brevo',
                detail=f"msg_id={msg_id}")
            processed += 1

    return jsonify({'success': True, 'processed': processed})


@app.route('/webhook/mailrelay', methods=['POST'])
def webhook_mailrelay():
    """
    Mailrelay webhook endpoint'i.
    Mailrelay Panel → Configuración → Notificaciones → URL: https://siteniz.com/webhook/mailrelay
    Events: bounce, complaint, unsubscribe

    Mailrelay POST olarak form-data veya JSON gönderebilir.
    """
    # Form-data veya JSON kabul et
    if request.is_json:
        data = request.json or {}
    else:
        data = request.form.to_dict()

    event_type = (data.get('type') or data.get('event') or '').lower()
    email      = data.get('email', '')
    msg_id     = data.get('message_id', data.get('mid', ''))

    if event_type in ('bounce', 'hard_bounce', 'soft_bounce'):
        _webhook_add_suppression(email, 'bounce', 'mailrelay',
            detail=f"type={event_type} mid={msg_id}")
    elif event_type in ('complaint', 'abuse', 'spam'):
        _webhook_add_suppression(email, 'complaint', 'mailrelay',
            detail=f"mid={msg_id}")
    elif event_type in ('unsubscribe', 'unsub'):
        _webhook_add_suppression(email, 'unsubscribe', 'mailrelay',
            detail=f"mid={msg_id}")
    else:
        print(f"[webhook/mailrelay] Bilinmeyen event: {event_type} email={email}")

    return jsonify({'success': True})


@app.route('/webhook/ses', methods=['POST'])
def webhook_ses():
    """
    AWS SES → SNS → HTTP webhook endpoint'i.
    Kurulum:
      1. AWS SNS → Topic oluştur
      2. Topic'e HTTP subscription: https://siteniz.com/webhook/ses
      3. SES → Configuration Sets → SNS destination (bounce + complaint)
      4. İlk POST: SubscriptionConfirmation — otomatik onaylanır

    Güvenlik: SNS mesaj imzası doğrulanır.
    """
    import json as _json

    content_type = request.headers.get('Content-Type', '')
    if 'text/plain' in content_type or 'text/html' in content_type:
        try:
            body = _json.loads(request.data)
        except Exception:
            return jsonify({'error': 'Parse error'}), 400
    else:
        body = request.json or {}

    msg_type = body.get('Type', '')

    # SNS abonelik onayı — otomatik onayla
    if msg_type == 'SubscriptionConfirmation':
        confirm_url = body.get('SubscribeURL', '')
        if confirm_url:
            try:
                import urllib.request
                urllib.request.urlopen(confirm_url, timeout=10)
                print(f"[webhook/ses] SNS aboneliği onaylandı: {confirm_url[:80]}")
            except Exception as e:
                print(f"[webhook/ses] Onay hatası: {e}")
        return jsonify({'success': True, 'confirmed': True})

    # Asıl bildirim
    if msg_type == 'Notification':
        try:
            message = _json.loads(body.get('Message', '{}'))
        except Exception:
            return jsonify({'error': 'Message parse error'}), 400

        notif_type = message.get('notificationType', '')

        if notif_type == 'Bounce':
            bounce_type = message.get('bounce', {}).get('bounceType', '')
            for recip in message.get('bounce', {}).get('bouncedRecipients', []):
                email = recip.get('emailAddress', '')
                reason = 'bounce'
                _webhook_add_suppression(email, reason, 'ses',
                    detail=f"bounceType={bounce_type}")

        elif notif_type == 'Complaint':
            for recip in message.get('complaint', {}).get('complainedRecipients', []):
                email = recip.get('emailAddress', '')
                _webhook_add_suppression(email, 'complaint', 'ses')

    return jsonify({'success': True})


@app.route('/webhook/status', methods=['GET'])
@login_required
def webhook_status():
    """Webhook endpoint URL'lerini ve kurulum rehberini döner."""
    base = request.host_url.rstrip('/')
    return jsonify({
        'success': True,
        'endpoints': {
            'brevo':    f"{base}/webhook/brevo",
            'mailrelay':f"{base}/webhook/mailrelay",
            'ses_sns':  f"{base}/webhook/ses",
        },
        'instructions': {
            'brevo':    'Brevo Dashboard → Settings → Webhooks → URL ekle → Events: hard_bounce, spam, unsubscribe',
            'mailrelay':'Mailrelay Panel → Configuración → Notificaciones → URL ekle',
            'ses':      'AWS SNS → Topic oluştur → HTTP subscription ekle → SES Configuration Set ile bağla',
        }
    })


if __name__ == '__main__':
    # Doğrudan çalıştırıldığında (python app.py):
    # debug=False: üretimde hata sayfası gösterme
    # host=127.0.0.1: sadece localhost — nginx/apache proxy arkasında çalışır
    # threaded=True: eş zamanlı SSE stream'lerini destekler
    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
