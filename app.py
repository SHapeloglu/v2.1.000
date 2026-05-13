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
    return redirect(url_for('dashboard_page'))   # Her şey tamam → dashboard

@app.route('/dashboard')
@login_required
def dashboard_page():
    """Dashboard — sistem durumu, günlük istatistikler, bounce oranı, uyarılar."""
    return render_template('pages/dashboard.html')

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
    """Tum gonderim kurallarini listeler."""
    rows = db().get_rules()
    for r in rows:
        if isinstance(r.get('created_at'), datetime.datetime):
            r['created_at'] = r['created_at'].strftime('%d.%m.%Y %H:%M')
    return jsonify({'success': True, 'data': rows})

@app.route('/api/rules', methods=['POST'])
@login_required
@csrf_protect
def create_rule():
    """Yeni gonderim kurali olusturur (gonderici veya kullanici bazli)."""
    data = request.json
    if not data.get('name') or data.get('min_interval_h') is None:
        return jsonify({'success': False, 'message': 'Ad ve min_interval_h zorunludur.'})
    if not data.get('sender_id') and not data.get('user_id'):
        return jsonify({'success': False, 'message': 'Gonderici veya kullanici secilmelidir.'})
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
# ─── Excel Preview API ────────────────────────────────────────────────

@app.route('/api/clean-emails', methods=['POST'])
@login_required
def clean_emails():
    import re, io, json
    import pandas as pd
    file = request.files.get('file')
    rules_raw = request.form.get('rules', '{}')
    email_col = request.form.get('email_col', '')
    try:
        rules = json.loads(rules_raw)
    except Exception:
        rules = {}
    fix_encoding = rules.get('fix_encoding', True)
    min_length   = int(rules.get('min_length', 2))
    banned_words = [w.strip().lower() for w in rules.get('banned_words', []) if w.strip()]
    banned_exts  = [e.strip().lower().lstrip('.') for e in rules.get('banned_exts', []) if e.strip()]
    custom_pats  = [p.strip() for p in rules.get('custom_patterns', []) if p.strip()]
    try:
        if file:
            filename = (file.filename or '').lower()
            raw = file.read()
            if filename.endswith('.csv'):
                for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1254'):
                    try:
                        df = pd.read_csv(io.BytesIO(raw), encoding=enc, sep=None, engine='python')
                        break
                    except Exception:
                        continue
                else:
                    return jsonify({'success': False, 'message': 'CSV okunamadı'})
            else:
                df = pd.read_excel(io.BytesIO(raw))
            if not email_col or email_col not in df.columns:
                for col in df.columns:
                    if 'mail' in col.lower():
                        email_col = col; break
                else:
                    email_col = df.columns[0]
            emails_raw = df[email_col].dropna().astype(str).tolist()
        else:
            body = request.get_json(silent=True) or {}
            emails_raw = body.get('emails', [])
        clean, removed = [], []
        for raw_email in emails_raw:
            email = raw_email.strip()
            reason = None
            if fix_encoding:
                try:
                    dec = email.encode('utf-8').decode('unicode_escape')
                    if '@' in dec: email = dec.strip()
                except Exception: pass
                email = re.sub(r'u00[0-9a-fA-F]{2}', '', email).strip()
            local = email.split('@')[0].lower() if '@' in email else email.lower()
            domain_part = email.split('@')[1].lower() if '@' in email else ''
            if len(local) < min_length:
                reason = f'Çok kısa ({len(local)} karakter)'
            if not reason:
                for word in banned_words:
                    if word in local or word in domain_part:
                        reason = f'Yasaklı kelime: {word}'; break
            if not reason:
                for ext in banned_exts:
                    if domain_part.endswith('.' + ext):
                        reason = f'Yasaklı uzantı: .{ext}'; break
            if not reason:
                for pat in custom_pats:
                    try:
                        if re.search(pat, email, re.IGNORECASE):
                            reason = f'Özel kural: {pat}'; break
                    except re.error:
                        if pat.lower() in email.lower():
                            reason = f'Özel kural: {pat}'; break
            if reason: removed.append({'email': raw_email.strip(), 'reason': reason})
            else: clean.append(email)
        return jsonify({'success': True, 'clean': clean, 'removed': removed,
                        'clean_count': len(clean), 'removed_count': len(removed),
                        'total': len(clean)+len(removed)})
    except Exception as e:
        import traceback; print(f"[clean_emails] {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/preview-excel', methods=['POST'])
@login_required
def preview_excel():
    """Excel veya CSV dosyasını okuyup önizleme bilgilerini döndürür"""
    try:
        if 'excel' not in request.files:
            return jsonify({'success': False, 'message': 'Dosya yok'})
        file = request.files['excel']
        filename = (file.filename or '').lower()
        if filename.endswith('.csv'):
            import io
            raw = file.read()
            for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1254'):
                try:
                    df = pd.read_csv(io.BytesIO(raw), encoding=enc, sep=None, engine='python')
                    break
                except Exception:
                    continue
            else:
                return jsonify({'success': False, 'message': 'CSV okunamadı'})
        else:
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


@app.route('/api/send/single', methods=['POST'])
@login_required
@rate_limit(30, 60)
def api_send_single():
    """Tek alıcıya anlık mail gönderir. body_html send_log'a kaydedilir (retry için)."""
    from mailer import send_one, send_via_ses, send_via_api, is_valid_email, is_suppressed, plain_to_html
    import database as _db_mod

    sender_id           = request.form.get('sender_id', '').strip()
    to                  = request.form.get('to', '').strip().lower()
    subject             = request.form.get('subject', '').strip()
    body                = request.form.get('body', '').strip()
    html_mode           = request.form.get('html_mode') == 'true'
    include_unsubscribe = request.form.get('include_unsubscribe') == 'true'
    attachment_file     = request.files.get('attachment')

    if not all([sender_id, to, subject, body]):
        return jsonify({'success': False, 'message': 'Tüm alanlar zorunludur.'})
    if not is_valid_email(to):
        return jsonify({'success': False, 'message': 'Geçersiz e-posta adresi.'})
    if is_suppressed(to):
        return jsonify({'success': False, 'message': 'Bu adres suppression listesinde.'})

    sender_row = db().get_sender(int(sender_id))
    if not sender_row:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'})

    body_html  = body if html_mode else plain_to_html(body)
    attachment = None
    if attachment_file and attachment_file.filename:
        attachment = (attachment_file.filename, attachment_file.read(), attachment_file.content_type)

    user_id  = session.get('user_id')
    username = session.get('username', 'sistem')
    mode     = sender_row.get('sender_mode', 'smtp')

    try:
        message_id = None
        if mode == 'smtp':
            ok, err = send_one(sender_row, to, subject, body_html,
                               attachment=attachment, include_unsubscribe=include_unsubscribe)
            provider = 'smtp'
        elif mode == 'ses':
            result = send_via_ses(sender_row, to, subject, body_html,
                                  attachment=attachment, include_unsubscribe=include_unsubscribe)
            ok, err = result[0], result[1]
            message_id = result[2] if len(result) > 2 else None
            provider = 'ses'
        else:
            ok, err = send_via_api(sender_row, to, subject, body_html,
                                   include_unsubscribe=include_unsubscribe)
            provider = mode

        _db_mod.log_send(
            sender_id=int(sender_id), rule_id=None,
            recipient=to, subject=subject,
            status='sent' if ok else 'failed',
            error_msg=err if not ok else None,
            user_id=user_id, username=username,
            message_id=str(message_id) if message_id else None,
            provider=provider, body_html=body_html
        )

        if ok:
            return jsonify({'success': True, 'message': 'Mail gönderildi.',
                            'message_id': str(message_id) if message_id else None})
        return jsonify({'success': False, 'message': err or 'Gönderim başarısız.'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Sunucu hatası: {str(e)}'})


@app.route('/single-send')
@login_required
def single_send_page():
    """Tek alıcıya hızlı mail gönderme sayfası."""
    return render_template('pages/single-send.html')


@app.route('/api/bounce-scanner/manuel-ekle', methods=['POST'])
@login_required
@rate_limit(60, 60)
def api_bounce_manuel_ekle():
    """Seçilen bounce kaydını bounce_adresleri + isteğe bağlı suppression'a ekler."""
    data            = request.get_json(silent=True) or {}
    email           = (data.get('email') or '').strip().lower()
    kategori        = (data.get('kategori') or 'kalici').strip()
    hata_kodu       = (data.get('hata_kodu') or '').strip()
    aciklama        = (data.get('aciklama') or '').strip()
    add_suppression = bool(data.get('add_suppression', False))
    if not email:
        return jsonify({'success': False, 'message': 'E-posta gerekli.'})
    bounce_tipi = 'kalici' if kategori in ('kalici', 'gonderici_sorunu') else 'gecici'
    bounce = {'email': email, 'bounce_tipi': bounce_tipi, 'kategori': kategori,
              'hata_kodu': hata_kodu, 'aciklama': aciklama, 'diagnostic': '', 'suppression_ekle': False}
    try:
        sonuc = db().bounce_kaydet(bounce)
        if add_suppression:
            db().add_to_suppression(email=email, reason='bounce', source='bounce_scanner_manuel')
        return jsonify({'success': True, 'sonuc': sonuc})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/suppression/batch-check', methods=['POST'])
@login_required
@rate_limit(20, 60)
def suppression_batch_check():
    """CSV'den gelen e-posta listesini suppression tablosuyla karşılaştırır."""
    data   = request.get_json(silent=True) or {}
    emails = data.get('emails', [])
    if not isinstance(emails, list):
        return jsonify({'success': False, 'message': 'emails listesi gerekli.'})
    emails = [str(e).lower().strip() for e in emails[:5000] if e]
    if not emails:
        return jsonify({'success': True, 'blocked': []})
    try:
        from database import get_connection
        conn = get_connection()
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(emails))
            cur.execute(f'SELECT email FROM suppression_list WHERE email IN ({placeholders})', emails)
            rows = cur.fetchall()
        conn.close()
        return jsonify({'success': True, 'blocked': [r['email'] for r in rows]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


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
        subject_tpl  = request.form.get('subject', '').strip()
        subject_tpl_b   = request.form.get('subject_b', '').strip()  # A/B test B konusu
        ab_mode         = request.form.get('ab_mode', 'split')       # 'split' | 'history'
        subject_seq_1   = request.form.get('subject_seq_1', '').strip()  # 0 önceki gönderim
        subject_seq_2   = request.form.get('subject_seq_2', '').strip()  # 1 önceki gönderim
        subject_seq_3   = request.form.get('subject_seq_3', '').strip()  # 2+ önceki gönderim
        ab_test         = request.form.get('ab_test') == 'true' and (bool(subject_tpl_b) or ab_mode == 'history')
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
        use_mx_check       = request.form.get('mx_check', 'true') == 'true'
        filter_role        = request.form.get('filter_role', 'false') == 'true'
        filter_disposable  = request.form.get('filter_disposable', 'true') == 'true'
        filter_catchall    = request.form.get('filter_catchall', 'false') == 'true'

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
                ok, reason = is_valid_email_with_mx(
                    em, use_mx=use_mx_check,
                    filter_role=filter_role,
                    filter_disposable=filter_disposable,
                    filter_catchall=filter_catchall,
                )
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
                ok, reason = is_valid_email_with_mx(
                    email_str, use_mx=use_mx_check,
                    filter_role=filter_role,
                    filter_disposable=filter_disposable,
                    filter_catchall=filter_catchall,
                )
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

        # Kullanıcı kimliği (can_send kullanıcı bazlı kural kontrolü için kullanır)
        _uid_pre = session.get('user_id')
        
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

            # ── Bulk performans önbellekleri — oturum başında bir kez yükle ──
            import database as _db_mod
            _supp_set        = _db_mod.load_suppression_set()
            _sender_cache    = {}
            _user_rule_cache = {}
            _sent_today_cache = {sender_row['id']: _db_mod.get_sender_sent_today(sender_row['id'])}
            _bulk_conn       = _db_mod.get_connection()
            _log_buffer      = []

            # Toplu gönderim başlangıcını logla
            db().audit(_uid, _uname, 'bulk_start', 'bulk', _bulk_file,
                       detail=f"total={total} sender_id={sender_id} invalid={len(invalid_rows)}",
                       ip_address=_ip)
            yield sse({'type': 'start', 'total': total})

            ok_c = err_c = skip_c = 0

            # Geçersiz formatlı adresleri önce skipped olarak raporla
            for inv_i, (inv_email, inv_reason) in enumerate(invalid_rows, 1):
                skip_c += 1
                _log_buffer.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                    'recipient': inv_email, 'subject': subject_tpl, 'status': 'skipped',
                    'error_msg': inv_reason, 'message_id': None, 'provider': None,
                    'user_id': _uid, 'username': _uname})
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
                
                allowed, reason = _db_mod.can_send_ctx(
                    _bulk_conn, sender_row['id'], email, min_interval_h,
                    user_id=_uid,
                    _sender_cache=_sender_cache,
                    _suppression_set=_supp_set,
                    _user_rule_cache=_user_rule_cache,
                    _sent_today_cache=_sent_today_cache,
                )
                if not allowed:
                    skip_c += 1
                    _log_buffer.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                        'recipient': email, 'subject': subject_tpl, 'status': 'skipped', 'error_msg': reason,
                        'message_id': None, 'provider': None, 'user_id': _uid, 'username': _uname})
                    if len(_log_buffer) >= 50:
                        _db_mod.log_send_bulk(_log_buffer); _log_buffer.clear()
                    yield sse({'type': 'progress', 'i': i, 'total': total, 'email': email, 'status': 'skipped', 'reason': reason})
                    yield from heartbeat_sleep(delay_ms)
                    continue
                
                # A/B Test konu seçimi
                if ab_test and ab_mode == 'history':
                    # Geçmiş gönderim sayısına göre konu seç
                    try:
                        sent_count = db().get_sent_count_to_recipient(sender_row['id'], email)
                    except Exception:
                        sent_count = 0
                    if sent_count == 0:
                        active_subject_tpl = subject_seq_1 or subject_tpl
                        ab_label = 'SEQ:1'
                    elif sent_count == 1:
                        active_subject_tpl = subject_seq_2 or subject_tpl
                        ab_label = 'SEQ:2'
                    else:
                        active_subject_tpl = subject_seq_3 or subject_tpl
                        ab_label = 'SEQ:3+'
                elif ab_test and subject_tpl_b:
                    # Split modu: ilk %50 A, son %50 B
                    half = len(valid_rows) // 2
                    row_index = i - len(invalid_rows) - 1
                    active_subject_tpl = subject_tpl if row_index < half else subject_tpl_b
                    ab_label = 'A' if row_index < half else 'B'
                else:
                    active_subject_tpl = subject_tpl
                    ab_label = None

                subject = render_template_str(active_subject_tpl, variables)
                body = render_template_str(body_tpl, variables)
                body_html = body if html_mode else plain_to_html(body)
                
                try:
                    # Madde 8: msg_id ve provider yakalanıyor
                    _mode1 = sender_row.get('sender_mode', 'smtp')
                    _msg_id1 = None
                    if _mode1 == 'ses':
                        _msg_id1 = send_via_ses(sender_row, email, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
                    elif _mode1 == 'api':
                        variables_for_name = variables if variables else {}
                        recipient_name = variables_for_name.get('name') or variables_for_name.get('ad') or ''
                        _ok1, _ret1 = send_via_api(sender_row, email, subject, body_html, recipient_name=recipient_name, include_unsubscribe=include_unsubscribe)
                        if isinstance(_ret1, str) and len(_ret1) < 500:
                            _msg_id1 = _ret1
                    else:
                        ok, err = send_one(sender_row, email, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
                        if not ok:
                            raise Exception(err)

                    ok_c += 1
                    if _sent_today_cache is not None:
                        _sent_today_cache[sender_row['id']] = _sent_today_cache.get(sender_row['id'], 0) + 1
                    log_subject = f"[A/B:{ab_label}] {subject}" if ab_label else subject
                    _log_buffer.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                        'recipient': email, 'subject': log_subject, 'status': 'sent', 'error_msg': None,
                        'message_id': _msg_id1, 'provider': _mode1, 'user_id': _uid, 'username': _uname})
                    if len(_log_buffer) >= 50:
                        _db_mod.log_send_bulk(_log_buffer); _log_buffer.clear()
                    yield sse({'type': 'progress', 'i': i, 'total': total, 'email': email, 'status': 'ok',
                               'ab': ab_label})

                except Exception as e:
                    err_c += 1
                    _log_buffer.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                        'recipient': email, 'subject': subject, 'status': 'failed', 'error_msg': str(e),
                        'message_id': None, 'provider': _mode1 if '_mode1' in dir() else None,
                        'user_id': _uid, 'username': _uname})
                    if len(_log_buffer) >= 50:
                        _db_mod.log_send_bulk(_log_buffer); _log_buffer.clear()
                    yield sse({'type': 'progress', 'i': i, 'total': total, 'email': email, 'status': 'error', 'error': str(e)})
                
                yield from heartbeat_sleep(delay_ms)
            
            # Kalan log tamponunu flush et
            if _log_buffer:
                _db_mod.log_send_bulk(_log_buffer); _log_buffer.clear()
            try:
                _bulk_conn.close()
            except Exception:
                pass
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

    # Kullanıcı kimliği (can_send kullanıcı bazlı kural kontrolü için kullanır)
    _uid2_pre = session.get('user_id')

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

        # ── Bulk performans önbellekleri ──────────────────────────────
        import database as _db_mod2
        _supp_set2        = _db_mod2.load_suppression_set()
        _sender_cache2    = {}
        _user_rule_cache2 = {}
        _sent_today_cache2 = {sender_row['id']: _db_mod2.get_sender_sent_today(sender_row['id'])}
        _bulk_conn2       = _db_mod2.get_connection()
        _log_buffer2      = []

        db().audit(_uid2, _uname2, 'bulk_start', 'bulk', table_name,
                   detail=f"total={total} sender_id={sender_id} source=db",
                   ip_address=_ip2)
        yield sse({'type':'start','total':total})

        ok_c = err_c = skip_c = 0

        for i, row in enumerate(valid,1):
            email = str(row[email_col]).strip()
            variables = {k: ('' if v is None else str(v)) for k,v in row.items()}

            allowed, reason = _db_mod2.can_send_ctx(
                _bulk_conn2, sender_row['id'], email, min_interval_h, user_id=_uid2,
                _sender_cache=_sender_cache2, _suppression_set=_supp_set2,
                _user_rule_cache=_user_rule_cache2, _sent_today_cache=_sent_today_cache2,
            )
            if not allowed:
                skip_c += 1
                _log_buffer2.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                    'recipient': email, 'subject': subject_tpl, 'status': 'skipped', 'error_msg': reason,
                    'message_id': None, 'provider': None, 'user_id': _uid2, 'username': _uname2})
                if len(_log_buffer2) >= 50:
                    _db_mod2.log_send_bulk(_log_buffer2); _log_buffer2.clear()
                yield sse({'type':'progress','i':i,'total':total,'email':email,'status':'skipped','reason':reason})
                yield from heartbeat_sleep(delay_ms)
                continue

            subj      = render_template_str(subject_tpl, variables)
            body      = render_template_str(body_tpl, variables)
            body_html = body if html_mode else plain_to_html(body)

            try:
                # Madde 8: msg_id ve provider yakalanıyor
                _mode2 = sender_row.get('sender_mode', 'smtp')
                _msg_id2 = None
                if _mode2 == 'api':
                    recipient_name = str(variables.get('name', '') or variables.get('ad', ''))
                    _ok2, _ret2 = send_via_api(sender_row, email, subj, body_html, recipient_name=recipient_name, include_unsubscribe=include_unsubscribe)
                    if isinstance(_ret2, str) and len(_ret2) < 500:
                        _msg_id2 = _ret2
                else:
                    _msg_id2 = send_via_ses(sender_row, email, subj, body_html, attachment, include_unsubscribe=include_unsubscribe)
                ok_c += 1
                if _sent_today_cache2 is not None:
                    _sent_today_cache2[sender_row['id']] = _sent_today_cache2.get(sender_row['id'], 0) + 1
                _log_buffer2.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                    'recipient': email, 'subject': subj, 'status': 'sent', 'error_msg': None,
                    'message_id': _msg_id2, 'provider': _mode2, 'user_id': _uid2, 'username': _uname2})
                if len(_log_buffer2) >= 50:
                    _db_mod2.log_send_bulk(_log_buffer2); _log_buffer2.clear()
                yield sse({'type':'progress','i':i,'total':total,'email':email,'status':'ok'})
            except Exception as e:
                err_c += 1
                _log_buffer2.append({'sender_id': sender_row['id'], 'rule_id': rule_id and int(rule_id),
                    'recipient': email, 'subject': subj, 'status': 'failed', 'error_msg': str(e),
                    'message_id': None, 'provider': _mode2 if '_mode2' in dir() else None,
                    'user_id': _uid2, 'username': _uname2})
                if len(_log_buffer2) >= 50:
                    _db_mod2.log_send_bulk(_log_buffer2); _log_buffer2.clear()
                yield sse({'type':'progress','i':i,'total':total,'email':email,'status':'error','error':str(e)})

            yield from heartbeat_sleep(delay_ms)

        if _log_buffer2:
            _db_mod2.log_send_bulk(_log_buffer2); _log_buffer2.clear()
        try:
            _bulk_conn2.close()
        except Exception:
            pass
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
    added, skipped = db().bulk_add_to_suppression(emails, reason, source='manual')
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


@app.route('/api/templates/defaults', methods=['GET'])
@login_required
def api_template_defaults():
    """Her tip için varsayılan şablonu döner: {'subject': {...}, 'body': {...}}"""
    return jsonify({'success': True, 'data': db().template_get_defaults()})


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

    is_default = bool(data.get('is_default', False))
    ok, result = db().template_create(tpl_type, name, content, is_default=is_default)
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
    is_default = data.get('is_default')
    ok, msg = db().template_update(
        tpl_id,
        name       = data.get('name'),
        content    = data.get('content'),
        is_default = bool(is_default) if is_default is not None else None
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
    if data.get('email')              is not None: kwargs['email']              = data['email']
    if data.get('role')               is not None: kwargs['role']               = data['role']
    if data.get('is_active')          is not None: kwargs['is_active']          = int(data['is_active'])
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

    # Madde 5: A/B test parametreleri
    subject_b     = request.form.get('subject_b', '').strip() or None
    ab_test       = request.form.get('ab_test') == 'true' and bool(subject_b)
    ab_ratio      = int(request.form.get('ab_ratio', 50))
    # Madde 2: filtre parametreleri
    filter_role       = request.form.get('filter_role', 'false') == 'true'
    filter_disposable = request.form.get('filter_disposable', 'true') == 'true'

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
            subject_b=subject_b, ab_test=ab_test, ab_ratio=ab_ratio,
            filter_role=filter_role, filter_disposable=filter_disposable,
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
    """Gönderim geçmişini filtreli ve sayfalı döner. export=csv ile tüm kayıtları CSV olarak indirir."""
    page      = int(request.args.get('page', 1))
    per_page  = int(request.args.get('per_page', 50))
    sender_id = request.args.get('sender_id')
    status    = request.args.get('status')
    search    = request.args.get('search')
    export    = request.args.get('export')
    date_from = request.args.get('date_from')  # 'YYYY-MM-DD'
    date_to   = request.args.get('date_to')    # 'YYYY-MM-DD'

    if export == 'csv':
        # Filtrelerle eşleşen TÜM kayıtları çek (sayfalama yok)
        rows, _ = db().get_send_log(page=1, per_page=999999, sender_id=sender_id, status=status, search=search, date_from=date_from, date_to=date_to)
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Tarih', 'Gönderici', 'Servis', 'Alıcı', 'Konu', 'Durum', 'Kullanıcı', 'Hata'])
        for r in rows:
            sent_at = r['sent_at'].strftime('%d.%m.%Y %H:%M:%S') if isinstance(r.get('sent_at'), datetime.datetime) else str(r.get('sent_at',''))
            # Servis adını belirle: provider varsa kullan, yoksa sender_mode + api_host'tan türet
            provider  = r.get('provider', '') or ''
            mode      = r.get('sender_mode', '') or ''
            api_host  = r.get('api_host', '') or ''
            if provider:
                service = provider
            elif mode == 'api' and api_host:
                # api_host'tan servis adını çıkar: send.api.mailtrap.io -> Mailtrap
                host_parts = api_host.replace('https://','').replace('http://','').split('.')
                service = host_parts[-2].capitalize() if len(host_parts) >= 2 else api_host
            elif mode:
                service = mode.upper()
            else:
                service = ''
            writer.writerow([
                sent_at,
                r.get('sender_name', ''),
                service,
                r.get('recipient', ''),
                r.get('subject', ''),
                r.get('status', ''),
                r.get('sent_by_username', ''),
                r.get('error_msg', '') or '',
            ])
        csv_bytes = output.getvalue().encode('utf-8-sig')  # utf-8-sig: Excel BOM desteği
        from flask import Response
        filename = f"gonderim-gecmisi-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}.csv"
        return Response(
            csv_bytes,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    rows, total = db().get_send_log(page, per_page, sender_id, status, search, date_from=date_from, date_to=date_to)
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


@app.route('/api/send-log/retry-failed', methods=['POST'])
@login_required
@csrf_protect
@rate_limit(5, 60)
def retry_failed_sends():
    """
    Send-log'daki 'failed' kayıtları tekrar gönderir.

    Parametreler (form veya JSON):
      sender_id   — (zorunlu) hangi sender kullanılacak
      log_ids     — (opsiyonel) virgülle ayrılmış log ID listesi; boşsa tüm failed kayıtlar
      max_count   — (opsiyonel) maksimum kaç kayıt denensin (varsayılan: 500)

    Akış: SSE (Server-Sent Events) — canlı ilerleme gönderir.
    Her kayıt için: can_send kontrolü → gönderim → log güncelleme
    """
    data = request.get_json(silent=True) or {}
    sender_id  = data.get('sender_id') or request.form.get('sender_id')
    log_ids_raw = data.get('log_ids') or request.form.get('log_ids', '')
    max_count  = int(data.get('max_count') or request.form.get('max_count') or 500)

    if not sender_id:
        return jsonify({'success': False, 'message': 'sender_id zorunlu'}), 400

    sender_row = db().get_sender(int(sender_id))
    if not sender_row:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı'}), 404

    # Hangi log kayıtları retry edilecek
    log_ids = [int(x.strip()) for x in log_ids_raw.split(',') if x.strip().isdigit()] if log_ids_raw else []

    # DB'den failed kayıtları al
    failed_rows = db().get_failed_logs(log_ids=log_ids, limit=max_count)
    if not failed_rows:
        return jsonify({'success': False, 'message': 'Retry edilecek başarısız kayıt bulunamadı'}), 404

    _uid   = session.get('user_id')
    _uname = session.get('username', '')

    def stream():
        total  = len(failed_rows)
        ok_c   = err_c = skip_c = 0

        yield sse({'type': 'start', 'total': total})

        for i, row in enumerate(failed_rows, 1):
            email      = row['recipient']
            subject    = row['subject'] or ''
            log_id     = row['id']
            rule_id    = row.get('rule_id')

            # can_send kontrolü (suppression + günlük limit)
            allowed, reason = db().can_send(sender_row['id'], email, 0, user_id=_uid)
            if not allowed:
                skip_c += 1
                db().update_log_status(log_id, 'skipped', f'Retry atlandı: {reason}')
                yield sse({'type': 'progress', 'i': i, 'total': total,
                           'email': email, 'status': 'skipped', 'reason': reason})
                continue

            try:
                # body_html DB'den al (send_log.body_html kolonu), yoksa subject fallback
                body_html = row.get('body_html') or f'<p>{subject}</p>'

                if sender_row.get('sender_mode') == 'ses':
                    send_via_ses(sender_row, email, subject, body_html, include_unsubscribe=False)
                elif sender_row.get('sender_mode') == 'api':
                    send_via_api(sender_row, email, subject, body_html, include_unsubscribe=False)
                else:
                    ok_r, err_r = send_one(sender_row, email, subject, body_html, include_unsubscribe=False)
                    if not ok_r:
                        raise Exception(err_r)

                ok_c += 1
                db().update_log_status(log_id, 'sent', None)
                db().log_send(sender_row['id'], rule_id, email, subject, 'sent',
                              user_id=_uid, username=_uname)
                yield sse({'type': 'progress', 'i': i, 'total': total,
                           'email': email, 'status': 'ok'})

            except Exception as e:
                err_c += 1
                db().update_log_status(log_id, 'failed', f'Retry hatası: {str(e)[:200]}')
                yield sse({'type': 'progress', 'i': i, 'total': total,
                           'email': email, 'status': 'error', 'error': str(e)})

        yield sse({'type': 'done', 'ok': ok_c, 'err': err_c,
                   'skipped': skip_c, 'total': total})

    return Response(stream(),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'X-Accel-Buffering': 'no',
                    })

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


def is_valid_email_with_mx(email: str, use_mx: bool = False,
                           filter_role: bool = False,
                           filter_disposable: bool = True,
                           filter_catchall: bool = False) -> tuple[bool, str]:
    """
    E-posta format + isteğe bağlı filtreler.

    Parametreler:
      use_mx            → Domain MX kaydı var mı? (DNS sorgusu)
      filter_role       → info@, admin@, noreply@ gibi rol adreslerini ele
      filter_disposable → mailinator, tempmail gibi geçici domainleri ele (varsayılan: aktif)
      filter_catchall   → Catch-all domain tespiti — SMTP probe, yavaş (varsayılan: kapalı)

    Dönen değer: (geçerli_mi, hata_sebebi)
      (True,  '')                                       → geçerli
      (False, 'Geçersiz e-posta formatı')               → format hatası
      (False, 'Geçici e-posta domain\'i: domain.com') → disposable
      (False, 'Rol adresi (kişisel değil): info@')      → rol adresi
      (False, 'MX kaydı yok: domain.com')               → MX yok
      (False, 'Catch-all domain: domain.com')            → catch-all
    """
    if not is_valid_email(email):
        return False, 'Geçersiz e-posta formatı'

    domain = email.rsplit('@', 1)[1].lower()

    # Disposable domain — hızlı, liste bazlı, MX'ten önce
    if filter_disposable and is_disposable(email):
        return False, f"Geçici e-posta domain\'i: {domain}"

    # Rol adresi
    if filter_role and is_role_based(email):
        local = email.split('@')[0]
        return False, f'Rol adresi (kişisel değil): {local}@'

    # MX kaydı
    if use_mx:
        if not check_mx(domain):
            return False, f'MX kaydı yok: {domain}'

    # Catch-all — en yavaş, SMTP probe, en sona
    if filter_catchall and use_mx:
        if is_catchall_domain(domain):
            return False, f'Catch-all domain (doğrulama yapılamıyor): {domain}'

    return True, ''


# Rol bazlı adres önekleri — bu adresler genelde kişisel değil, açılma oranı düşük
_ROLE_PREFIXES = {
    'info', 'admin', 'administrator', 'support', 'help', 'helpdesk',
    'noreply', 'no-reply', 'donotreply', 'do-not-reply',
    'contact', 'sales', 'marketing', 'billing', 'accounts',
    'postmaster', 'webmaster', 'hostmaster', 'abuse',
    'newsletter', 'mail', 'email', 'office', 'reception',
    'hello', 'team', 'hr', 'jobs', 'careers', 'press', 'media',
    'privacy', 'legal', 'security', 'it', 'tech', 'ops', 'devops',
    'feedback', 'inquiry', 'enquiry', 'orders', 'returns', 'service',
    'services', 'general', 'connect', 'partnerships', 'partner',
}

# Geçici/disposable e-posta domain'leri — bu domainler gerçek kullanıcı değil
_DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org',
    'tempmail.com', 'temp-mail.org', 'throwaway.email', 'sharklasers.com',
    'guerrillamailblock.com', 'grr.la', 'guerrillamail.info', 'spam4.me',
    'trashmail.com', 'trashmail.me', 'trashmail.net', 'trashmail.at',
    'trashmail.io', 'trashmail.xyz', 'dispostable.com', 'yopmail.com',
    'yopmail.fr', 'cool.fr.nf', 'jetable.fr.nf', 'nospam.ze.tc',
    'nomail.xl.cx', 'mega.zik.dj', 'speed.1s.fr', 'courriel.fr.nf',
    'moncourrier.fr.nf', 'monemail.fr.nf', 'monmail.fr.nf',
    'spamgourmet.com', 'spamgourmet.net', 'spamgourmet.org',
    'spamex.com', 'spamfree24.org', 'spamhole.com', 'spamify.com',
    'spaml.de', 'spammotel.com', 'spamobox.com', 'spamspot.com',
    'spamthis.co.uk', 'spamtroll.net', 'tempr.email', 'discard.email',
    'fakeinbox.com', 'mailnull.com', 'maildrop.cc', 'mailnesia.com',
    'mailnull.com', 'spamgob.com', 'binkmail.com', 'bob.email',
    'drdrb.com', 'emkei.cz', 'gowikimail.com', 'haltospam.com',
    'inoutmail.de', 'inoutmail.eu', 'inoutmail.info', 'inoutmail.net',
    'jetable.com', 'jetable.net', 'jetable.org', 'kasmail.com',
    'klassmaster.com', 'klassmaster.net', 'lhsdv.com', 'loadaveragezero.com',
    'mailblocks.com', 'mailcatch.com', 'maileater.com', 'mailexpire.com',
    'mailfreeonline.com', 'mailguard.me', 'mailin8r.com', 'mailinater.com',
    'mailincubator.com', 'mailme.lv', 'mailme24.com', 'mailmetrash.com',
    'mailmoat.com', 'mailnew.com', 'mailnull.com', 'mailsiphon.com',
    'mailslite.com', 'mailtemp.info', 'mailtome.de', 'mailtothis.com',
    'mailtrash.net', 'mailzilla.org', 'mbx.cc', 'meltmail.com',
    'mierdamail.com', 'mintemail.com', 'misterpinball.de', 'mt2009.com',
    'mx0.wwwnew.eu', 'mycleaninbox.net', 'myphantomemail.com', 'myscrapthat.com',
    'netmails.com', 'netmails.net', 'neverbox.com', 'nice-4u.com',
    'nincsmail.hu', 'nobulk.com', 'noclickemail.com', 'nogmailspam.info',
    'nomail.pw', 'nomail.xl.cx', 'nomail2me.com', 'nomorespamemails.com',
    'nonspam.eu', 'nonspammer.de', 'noref.in', 'nospam.ze.tc',
    'nospamfor.us', 'nospammail.net', 'nospamthanks.info', 'notmailinator.com',
    'nowmymail.com', 'objectmail.com', 'obobbo.com', 'odnorazovoe.ru',
    'oneoffemail.com', 'onewaymail.com', 'online.ms', 'oopi.org',
    'opentrash.com', 'ordinaryamerican.net', 'owlpic.com', 'pancakemail.com',
    'pookmail.com', 'privacy.net', 'proxymail.eu', 'prtnx.com',
    'punkass.com', 'putthisinyourspamdatabase.com', 'qq.com',
    'quickinbox.com', 'rcpt.at', 'recode.me', 'recursor.net',
    'regbypass.com', 'regbypass.comsafe-mail.net', 'rejectmail.com',
    'rklips.com', 'rmqkr.net', 'royal.net', 'rppkn.com',
    'rtrtr.com', 's0ny.net', 'safe-mail.net', 'safetymail.info',
    'safetypost.de', 'sandelf.de', 'saynotospams.com', 'selfdestructingmail.com',
    'sendspamhere.com', 'sharklasers.com', 'shieldedmail.com', 'shiftmail.com',
    'shit2.me', 'shitmail.me', 'shitmail.org', 'shitware.nl',
    'shmeriously.com', 'shortmail.net', 'sibmail.com', 'skeefmail.com',
    'slapsfromlastnight.com', 'slaskpost.se', 'slopsbox.com', 'smellfear.com',
    'smwg.info', 'snakemail.com', 'sneakemail.com', 'sneakmail.de',
    'snkmail.com', 'sofimail.com', 'sogetthis.com', 'soodonims.com',
    'spam.la', 'spam.su', 'spamavert.com', 'spambob.com',
    'spambob.net', 'spambob.org', 'spambog.com', 'spambog.de',
    'spambog.ru', 'spambox.info', 'spambox.irishspringrealty.com',
    'spambox.us', 'spamcannon.com', 'spamcannon.net', 'spamcero.com',
    'spamcon.org', 'spamcorptastic.com', 'spamcowboy.com', 'spamcowboy.net',
    'spamcowboy.org', 'spamday.com', 'spamex.com', 'spamfree.eu',
    'spamfree24.de', 'spamfree24.eu', 'spamfree24.info', 'spamfree24.net',
    'tempinbox.com', 'tempinbox.co.uk', 'tempomail.fr', 'temporaryemail.net',
    'temporaryforwarding.com', 'temporaryinbox.com', 'temporarymail.org',
    'tempthe.net', 'thankyou2010.com', 'thecloudindex.com',
    'throam.com', 'throwam.com', 'throwmail.me', 'tilien.com',
    'tmail.com', 'tmailinator.com', 'toiea.com', 'trashdevil.com',
    'trashdevil.de', 'trashemail.de', 'trashmail.org', 'trashmailer.com',
    'trashtimail.com', 'trillianpro.com', 'twinmail.de', 'tyldd.com',
    'uggsrock.com', 'uroid.com', 'us.af', 'venompen.com',
    'veryrealemail.com', 'viditag.com', 'viewcastmedia.com', 'viewcastmedia.net',
    'viewcastmedia.org', 'walkmail.net', 'walkmail.ru', 'webemail.me',
    'webm4il.info', 'wegwerfmail.de', 'wegwerfmail.net', 'wegwerfmail.org',
    'whatiaas.com', 'whatifnot.com', 'whopy.com', 'wilemail.com',
    'wmail.cf', 'writeme.us', 'wronghead.com', 'wuzupmail.net',
    'xagloo.com', 'xemaps.com', 'xents.com', 'xmaily.com',
    'xoxy.net', 'xyzfree.net', 'yapped.net', 'yeah.net',
    'yepmail.net', 'yogamaven.com', 'yopmail.com', 'yopmail.fr',
    'youmail.ga', 'yourdomain.com', 'ypmail.webarnak.fr.eu.org',
    'yuurok.com', 'z1p.biz', 'za.com', 'zebins.com',
    'zebins.eu', 'zehnminuten.de', 'zippymail.info', 'zoemail.net',
    'zoemail.org', 'zomg.info', 'zxcv.com', 'zxcvbnm.com',
}

# Catch-all domain tespiti için SMTP probe cache
# {domain: (is_catchall: bool, timestamp: float)}
_catchall_cache: dict = {}
_catchall_lock = __import__('threading').Lock()
_MAX_CATCHALL_CACHE = 10_000

def is_catchall_domain(domain: str, timeout: float = 3.0) -> bool:
    """
    Domain'in catch-all olup olmadığını tespit eder.

    Yöntem: Var olamayacak kadar rastgele bir adrese SMTP probe atar.
    Sunucu "250 OK" derse → catch-all (her adresi kabul ediyor).
    Sunucu "550 No such user" derse → catch-all değil.

    Cache: 10.000 domain'e kadar bellekte tutulur.
    Hata durumunda False döner (gönderimine izin ver, false negative tercih).

    UYARI: Bazı sunucular probe'u engeller veya greylisting yapar.
    Bu durumda False dönülür — gönderim kesilmez.
    """
    import socket, time as _time
    domain = domain.strip().lower()

    with _catchall_lock:
        cached = _catchall_cache.get(domain)
        if cached is not None:
            is_ca, ts = cached
            # 24 saat cache geçerliliği
            if _time.time() - ts < 86400:
                return is_ca
        if len(_catchall_cache) >= _MAX_CATCHALL_CACHE:
            _catchall_cache.clear()

    # Var olamayacak rastgele adres üret
    import random, string
    rand_local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    probe_addr = f"{rand_local}@{domain}"

    is_catchall = False
    try:
        # MX'i bul
        try:
            import dns.resolver
            mx_records = dns.resolver.resolve(domain, 'MX', lifetime=timeout)
            mx_host = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip('.')
        except Exception:
            # DNS yoksa veya hata varsa catch-all değil say
            with _catchall_lock:
                _catchall_cache[domain] = (False, _time.time())
            return False

        # SMTP bağlantısı
        sock = socket.create_connection((mx_host, 25), timeout=timeout)
        sock.settimeout(timeout)
        f = sock.makefile('rb')

        def recv():
            lines = []
            while True:
                line = f.readline(512).decode('utf-8', errors='replace').strip()
                lines.append(line)
                if len(line) >= 4 and line[3] == ' ':
                    break
            return lines[-1][:3], '\n'.join(lines)

        recv()  # 220 banner
        sock.sendall(b'EHLO mailcheck.local\r\n')
        recv()
        sock.sendall(b'MAIL FROM:<check@mailcheck.local>\r\n')
        recv()
        sock.sendall(f'RCPT TO:<{probe_addr}>\r\n'.encode())
        code, _ = recv()
        sock.sendall(b'QUIT\r\n')
        sock.close()

        # 250 veya 251 → sunucu adresi kabul etti → catch-all
        is_catchall = code.startswith('2')

    except Exception:
        is_catchall = False  # Bağlanamazsa catch-all değil say

    with _catchall_lock:
        _catchall_cache[domain] = (is_catchall, _time.time())

    return is_catchall


# check_mx — yukarıda tanımlıdır


def is_role_based(email: str) -> bool:
    """
    Rol bazlı e-posta adresi mi kontrol eder.
    info@, admin@, noreply@ gibi adresler cold email için düşük değerli.
    """
    if '@' not in email:
        return False
    local = email.split('@')[0].lower().strip()
    return local in _ROLE_PREFIXES


def is_disposable(email: str) -> bool:
    """
    Geçici/disposable e-posta domain'i mi kontrol eder.
    mailinator, tempmail, yopmail gibi domainler gerçek kullanıcı değil.
    """
    if '@' not in email:
        return False
    domain = email.rsplit('@', 1)[1].lower().strip()
    return domain in _DISPOSABLE_DOMAINS

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

@app.route('/settings/audit-log')
@login_required
def settings_audit_log():
    """Audit log görüntüleme sayfası — sadece admin erişebilir."""
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    return render_template('pages/settings/audit-log.html', active_tab='audit_log')


@app.route('/api/audit-log', methods=['GET'])
@login_required
def api_audit_log():
    """
    Audit log kayıtlarını filtreli ve sayfalı döner.
    Sadece admin erişebilir.
    Query parametreleri: page, per_page, username, action, date_from, date_to, export
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Yetkisiz erişim.'}), 403

    page      = int(request.args.get('page', 1))
    per_page  = int(request.args.get('per_page', 50))
    username  = request.args.get('username', '').strip() or None
    action    = request.args.get('action', '').strip() or None
    date_from = request.args.get('date_from', '').strip() or None
    date_to   = request.args.get('date_to', '').strip() or None
    export    = request.args.get('export', '').strip()

    rows, total = db().get_audit_log(
        page=page, per_page=per_page,
        username=username, action=action,
        date_from=date_from, date_to=date_to
    )

    if export == 'csv':
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Tarih', 'Kullanıcı', 'İşlem', 'Hedef Tip', 'Hedef ID', 'Detay', 'IP'])
        # CSV için tüm kayıtları çek
        all_rows, _ = db().get_audit_log(
            page=1, per_page=999999,
            username=username, action=action,
            date_from=date_from, date_to=date_to
        )
        for r in all_rows:
            writer.writerow([
                r.get('created_at', ''),
                r.get('username', ''),
                r.get('action', ''),
                r.get('target_type', ''),
                r.get('target_id', ''),
                r.get('detail', ''),
                r.get('ip_address', ''),
            ])
        csv_bytes = output.getvalue().encode('utf-8-sig')
        from flask import Response as _Resp
        fname = f"audit-log-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}.csv"
        return _Resp(
            csv_bytes,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{fname}"'}
        )

    return jsonify({
        'success': True,
        'data':    rows,
        'total':   total,
        'page':    page,
    })


@app.route('/api/audit-log/actions', methods=['GET'])
@login_required
def api_audit_log_actions():
    """Audit log'daki benzersiz action tiplerini döner (filtre dropdown için)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Yetkisiz erişim.'}), 403
    actions = db().get_audit_log_actions()
    return jsonify({'success': True, 'data': actions})


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


@app.route('/api/verify/export-csv', methods=['GET'])
@login_required
@rate_limit(10, 60)
def api_verify_export_csv():
    """
    Doğrulama sonuçlarını segmente göre CSV olarak indirir.

    Query parametreleri:
        table    (zorunlu)  — Kaynak tablo adı
        segment  (opsiyonel, varsayılan 'valid') — İndirilecek segment:
                  valid        → is_valid=1 (geçerli)
                  invalid      → is_valid=0 (geçersiz)
                  unknown      → is_valid=-1 (belirsiz/riskli)
                  risky        → is_valid IN (1,-1) (geçerli+riskli)
                  all          → tüm satırlar
                  catch_all    → status='catch_all'
                  spam_trap    → status='spam_trap'
                  no_infra     → status='no_infra'
                  role_account → status='role_account'
                  typo_fixed   → status='typo_fixed'
                  do_not_send  → risk_label='do_not_send'
                  high_risk    → risk_label IN ('high_risk','do_not_send')
        limit    (opsiyonel, varsayılan 500000) — Max satır sayısı
    """
    import csv, io
    from flask import Response
    from security import safe_identifier
    import database as _db_module

    table_name = request.args.get('table', '').strip()
    segment    = request.args.get('segment', 'valid').strip().lower()
    try:
        limit  = min(int(request.args.get('limit', 500000)), 1000000)
    except ValueError:
        limit  = 500000

    if not table_name:
        return jsonify({'success': False, 'message': 'Tablo adı zorunludur.'})
    try:
        safe_identifier(table_name)
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})

    # Segment → WHERE koşulu eşlemesi
    # is_valid kolonu her zaman var; status/risk_label kolonları yoksa
    # o filtreler boş sonuç döner (hata değil)
    SEGMENT_WHERE = {
        'valid':        "is_valid = 1",
        'invalid':      "is_valid = 0",
        'unknown':      "is_valid = -1",
        'risky':        "is_valid IN (1, -1)",
        'all':          None,   # WHERE yok
        'catch_all':    "status = 'catch_all'",
        'spam_trap':    "status = 'spam_trap'",
        'no_infra':     "status = 'no_infra'",
        'role_account': "status = 'role_account'",
        'typo_fixed':   "status = 'typo_fixed'",
        'do_not_send':  "risk_label = 'do_not_send'",
        'high_risk':    "risk_label IN ('high_risk', 'do_not_send')",
    }

    if segment not in SEGMENT_WHERE:
        return jsonify({
            'success': False,
            'message': f"Geçersiz segment. Kabul edilenler: {', '.join(SEGMENT_WHERE.keys())}"
        }), 400

    where_cond = SEGMENT_WHERE[segment]

    conn = _db_module.get_connection()
    try:
        with conn.cursor() as cur:
            # Tablodaki kolonları kontrol et — filtre kolonları olmayabilir
            db_name = _db_module.get_db_config()['database']
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s",
                (db_name, table_name)
            )
            existing_cols = {r['column_name'] for r in cur.fetchall()}

            # is_valid / status / risk_label kolonu yoksa where'i düşür
            if where_cond:
                needs_is_valid   = 'is_valid'   in where_cond and 'is_valid'   not in existing_cols
                needs_status     = 'status'      in where_cond and 'status'     not in existing_cols
                needs_risk_label = 'risk_label'  in where_cond and 'risk_label' not in existing_cols
                if needs_is_valid or needs_status or needs_risk_label:
                    where_cond = None   # kolon yok, filtre uygulanamaz

            where_sql = f"WHERE {where_cond}" if where_cond else ""
            cur.execute(
                f"SELECT * FROM `{table_name}` {where_sql} ORDER BY 1 LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
    except Exception as e:
        return jsonify({'success': False, 'message': f'Tablo okunamadı: {e}'})
    finally:
        conn.close()

    if not rows:
        return jsonify({'success': False, 'message': 'Bu segment için kayıt bulunamadı.'})

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    for r in rows:
        row_out = {}
        for k, v in r.items():
            if isinstance(v, datetime.datetime):
                row_out[k] = v.strftime('%d.%m.%Y %H:%M:%S')
            else:
                row_out[k] = v
        writer.writerow(row_out)

    csv_bytes = output.getvalue().encode('utf-8-sig')
    filename = (
        f"{table_name}-{segment}-"
        f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    )
    return Response(
        csv_bytes,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Total-Rows': str(len(rows)),
            'X-Segment':    segment,
        }
    )


@app.route('/api/verify/verified-tables', methods=['GET'])
@login_required
def api_get_verified_tables():
    """Prefix ile eslesen kullanici tablolarini ve istatistiklerini doner."""
    prefix = request.args.get('prefix', 'mail_list_')
    ok, result = db().get_verified_tables(prefix=prefix)
    return jsonify({
        'success': ok,
        'data': result if ok else [],
        'message': '' if ok else result,
        'debug_prefix': prefix,
        'debug_count': len(result) if ok else 0,
    })


@app.route('/api/verify/merge', methods=['POST'])
@login_required
@csrf_protect
@rate_limit(5, 60)
def api_merge_verified():
    """
    Secilen dogrulanmis tablolari ayri hedef tablolara birlestir.
    target_valid : is_valid=1 adreslerin yazilacagi tablo (zorunlu)
    target_risky : is_valid=-1 adreslerin yazilacagi tablo (opsiyonel)
    """
    data          = request.json or {}
    target_valid  = data.get('target_valid', '').strip()
    target_risky  = data.get('target_risky', '').strip() or None
    source_tables = data.get('source_tables', [])

    if not target_valid:
        return jsonify({'success': False, 'message': 'Geçerli adresler için hedef tablo adı zorunludur.'})
    if not source_tables:
        return jsonify({'success': False, 'message': 'En az bir kaynak tablo seçilmelidir.'})

    ok, result = db().merge_verified_tables(target_valid, source_tables, target_risky=target_risky)
    if not ok:
        return jsonify({'success': False, 'message': str(result)})

    _audit('verify_merge', 'verify', None,
           detail=f"valid={target_valid} risky={target_risky} sources={source_tables} "
                  f"v_ins={result['valid_inserted']} r_ins={result['risky_inserted']}")

    parts = [f"✓ Geçerli → '{target_valid}': {result['valid_inserted']:,} eklendi, {result['valid_skipped']:,} tekrar atlandı"]
    if target_risky:
        parts.append(f"⚠ Riskli → '{target_risky}': {result['risky_inserted']:,} eklendi, {result['risky_skipped']:,} tekrar atlandı")
    if result.get('skipped_tables'):
        parts.append(f"⏭ Email kolonu bulunamayan tablolar: {', '.join(result['skipped_tables'])}")

    return jsonify({'success': True, 'message': ' | '.join(parts), 'result': result})


@app.route('/api/verify/drop-tables', methods=['POST'])
@login_required
@admin_required
@csrf_protect
@rate_limit(5, 60)
def api_drop_user_tables():
    """Secilen kullanici tablolarini siler. Sistem tablolari korunur."""
    data   = request.json or {}
    tables = data.get('tables', [])
    if not tables:
        return jsonify({'success': False, 'message': 'Silinecek tablo seçilmedi.'})

    ok, result = db().drop_user_tables(tables)
    if not ok:
        return jsonify({'success': False, 'message': str(result)})

    _audit('drop_tables', 'db', None,
           detail=f"dropped={result['dropped']} protected={result['protected']}")

    parts = []
    if result['dropped']:
        parts.append(f"{len(result['dropped'])} tablo silindi: {', '.join(result['dropped'])}")
    if result['protected']:
        parts.append(f"{len(result['protected'])} tablo korundu (sistem): {', '.join(result['protected'])}")
    return jsonify({'success': True, 'message': ' | '.join(parts), 'result': result})


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


@app.route('/api/verify/disposable-status', methods=['GET'])
@login_required
def api_verify_disposable_status():
    try:
        import disposable_updater as du, datetime
        ts = du._get_last_update_ts()
        cnt = len(du.load_domains_from_db())
        last = datetime.datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M') if ts > 0 else 'Hiç güncellenmedi'
        return jsonify({'success': True, 'last_update': last, 'count': cnt})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/verify/disposable-update', methods=['POST'])
@login_required
def api_verify_disposable_update():
    try:
        import disposable_updater as du
        return jsonify(du.update_disposable_domains(force=True))
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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


@app.route('/api/verify/single', methods=['GET'])
@login_required
def api_verify_single():
    """
    Tek bir e-postayı gerçek zamanlı doğrular.

    Query parametreleri:
        email   (zorunlu) — Doğrulanacak e-posta adresi
        mode    (opsiyonel, varsayılan 'mx') — 'format' | 'mx' | 'smtp'

    Yanıt alanları:
        email          — Normalize edilmiş (düzeltilmiş) adres
        original       — Kullanıcının girdiği orijinal adres
        status         — Doğrulama statüsü (valid, invalid, catch_all vb.)
        is_valid       — 1 (geçerli) | 0 (geçersiz) | -1 (belirsiz/riskli)
        did_you_mean   — Yazım hatası önerisi (ör: "john@gmail.com") veya null
        is_role        — Rol adresi mi? (info@, admin@ vb.)
        is_free        — Ücretsiz sağlayıcı mı? (Gmail, Hotmail vb.)
        is_catchall    — Catch-all sunucu mu?
        has_spf        — SPF kaydı var mı?
        has_dmarc      — DMARC kaydı var mı?
        risk_score     — 0-100 arası teslimat risk skoru
        risk_label     — safe | low_risk | medium_risk | high_risk | do_not_send
        executiontime  — İşlem süresi (saniye, 2 ondalık)
    """
    import time as _time
    from verifier import verify_one, STATUS_TO_IS_VALID
    from risk_score import calculate_risk_score

    email_param = (request.args.get('email') or '').strip()
    mode        = (request.args.get('mode') or 'mx').strip().lower()

    if not email_param:
        return jsonify({
            'success': False,
            'error':   'email parametresi zorunludur.',
            'code':    'missing_email',
        }), 400

    if mode not in ('format', 'mx', 'smtp'):
        return jsonify({
            'success': False,
            'error':   'mode değeri format | mx | smtp olmalıdır.',
            'code':    'invalid_mode',
        }), 400

    t_start = _time.perf_counter()
    try:
        final_email, status, meta = verify_one(email_param, mode=mode)
        risk = calculate_risk_score(final_email, status, meta,
                                    include_db=(mode == 'smtp'))
    except Exception as e:
        return jsonify({
            'success': False,
            'error':   f'Doğrulama hatası: {e}',
            'code':    'internal_error',
        }), 500

    elapsed = round(_time.perf_counter() - t_start, 2)

    return jsonify({
        'success':       True,
        'email':         final_email,
        'original':      meta.get('original', email_param),
        'status':        status,
        'is_valid':      STATUS_TO_IS_VALID.get(status, -1),
        'did_you_mean':  meta.get('did_you_mean'),       # null veya "user@gmail.com"
        'is_role':       bool(meta.get('is_role')),
        'is_free':       bool(meta.get('is_free')),
        'is_catchall':   bool(meta.get('is_catchall')),
        'has_spf':       bool(meta.get('has_spf')),
        'has_dmarc':     bool(meta.get('has_dmarc')),
        'domain_age':    meta.get('domain_age'),
        'spam_trap':     meta.get('spam_trap_type'),      # null veya tuzak tipi
        'risk_score':    risk['score'],
        'risk_label':    risk['label'],
        'risk_label_tr': risk['label_tr'],
        'send_recommended': risk['send_recommended'],
        'executiontime': elapsed,
    })

# ══════════════════════════════════════════════════════════════════════
#  OTOMATİK YENİDEN DOĞRULAMA ZAMANLAMA API'SI
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/verify/schedules', methods=['GET'])
@login_required
def api_reverify_schedule_list():
    """Tüm otomatik yeniden doğrulama zamanlamalarını döner."""
    from auto_reverify import list_schedules
    return jsonify({'success': True, 'data': list_schedules()})


@app.route('/api/verify/schedules', methods=['POST'])
@login_required
def api_reverify_schedule_create():
    """
    Yeni zamanlama oluşturur veya mevcutu günceller.

    Body (JSON):
        table_name    (zorunlu)
        email_col     (varsayılan: 'email')
        mode          (varsayılan: 'mx')       — format | mx | smtp
        threads       (varsayılan: 10)
        interval_days (varsayılan: 90)         — 1-365 arası
        target        (varsayılan: 'all')      — all | valid_only | invalid_only | unknown_only
        start_now     (varsayılan: false)      — true ise ilk çalışma hemen
    """
    from auto_reverify import create_schedule
    data = request.json or {}

    table_name = (data.get('table_name') or '').strip()
    if not table_name:
        return jsonify({'success': False, 'message': 'table_name zorunludur.'}), 400

    ok, result = create_schedule(
        table_name    = table_name,
        email_col     = (data.get('email_col') or 'email').strip(),
        mode          = (data.get('mode') or 'mx').strip(),
        threads       = int(data.get('threads') or 10),
        interval_days = int(data.get('interval_days') or 90),
        target        = (data.get('target') or 'all').strip(),
        user_id       = g.user['id'],
        username      = g.user['username'],
        start_now     = bool(data.get('start_now', False)),
    )
    if not ok:
        return jsonify({'success': False, 'message': result}), 400
    return jsonify({'success': True, 'schedule_id': result})


@app.route('/api/verify/schedules/<int:schedule_id>', methods=['DELETE'])
@login_required
def api_reverify_schedule_delete(schedule_id):
    """Zamanlamayı siler."""
    from auto_reverify import delete_schedule
    ok = delete_schedule(schedule_id)
    return jsonify({'success': ok})


@app.route('/api/verify/schedules/<int:schedule_id>/toggle', methods=['POST'])
@login_required
def api_reverify_schedule_toggle(schedule_id):
    """Zamanlamayı aktif/pasif yapar."""
    from auto_reverify import toggle_schedule
    data      = request.json or {}
    is_active = bool(data.get('is_active', True))
    ok        = toggle_schedule(schedule_id, is_active)
    return jsonify({'success': ok})


# ══════════════════════════════════════════════════════════════════════
#  DNSBL / RBL IP KARA LİSTE KONTROLÜ
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/senders/dnsbl-check', methods=['POST'])
@login_required
@rate_limit(5, 60)   # Dakikada 5 istek — DNS sorguları ağır
def api_dnsbl_check():
    """
    Bir SMTP sunucusunu / IP adresini DNSBL kara listelerinde kontrol eder.

    Body (JSON) — birini gönderin:
        smtp_host  — SMTP hostname (ör: 'mail.example.com')
        ip         — Direkt IPv4 adresi (ör: '1.2.3.4')
        sender_id  — Mevcut gönderici ID'si (smtp_server otomatik alınır)

    Yanıt:
        ip, listed, hits, severity, checked_at
    """
    from dnsbl_check import check_ip, check_smtp_host, check_sender_row, summarize
    import database as _db_module

    data      = request.json or {}
    smtp_host = (data.get('smtp_host') or '').strip()
    ip_addr   = (data.get('ip') or '').strip()
    sender_id = data.get('sender_id')

    # sender_id verilmişse smtp_server'ı DB'den al
    if sender_id and not smtp_host and not ip_addr:
        sender = _db_module.get_sender(int(sender_id))
        if not sender:
            return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'}), 404
        result = check_sender_row(sender)
        if result is None:
            return jsonify({'success': False,
                            'message': 'Bu gönderici için SMTP sunucusu tanımlı değil.'}), 400
    elif smtp_host:
        result = check_smtp_host(smtp_host)
    elif ip_addr:
        result = check_ip(ip_addr)
    else:
        return jsonify({
            'success': False,
            'message': 'smtp_host, ip veya sender_id alanlarından biri zorunludur.',
        }), 400

    # Sonucu loglayalım
    summary = summarize(result)
    print(f"[DNSBL] {summary}")

    return jsonify({'success': True, 'data': result})


@app.route('/api/senders/<int:sender_id>/dnsbl', methods=['GET'])
@login_required
@rate_limit(5, 60)
def api_sender_dnsbl(sender_id):
    """
    Belirli bir gönderici SMTP sunucusunun DNSBL durumunu döner.
    GET /api/senders/3/dnsbl
    """
    from dnsbl_check import check_sender_row, summarize
    import database as _db_module

    sender = _db_module.get_sender(sender_id)
    if not sender:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'}), 404

    result = check_sender_row(sender)
    if result is None:
        return jsonify({'success': False,
                        'message': 'Bu gönderici için SMTP sunucusu tanımlı değil.'}), 400

    summary = summarize(result)
    print(f"[DNSBL] {summary}")
    return jsonify({'success': True, 'data': result})


@app.route('/api/senders/<int:sender_id>/reputation', methods=['GET'])
@login_required
@rate_limit(10, 60)
def api_sender_reputation(sender_id):
    """
    Bir göndericinin itibar skorunu döner.
    GET /api/senders/3/reputation
    """
    import database as _db_module
    from reputation_score import calculate_sender_reputation

    sender = _db_module.get_sender(sender_id)
    if not sender:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'}), 404

    result = calculate_sender_reputation(sender=sender)
    return jsonify({'success': True, 'data': result})


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


# ══════════════════════════════════════════════════════════════════════
#  BOUNCE SCANNER — IMAP üzerinden hata maili tarama
# ══════════════════════════════════════════════════════════════════════

@app.route('/settings/bounce-scanner')
@login_required
def settings_bounce_scanner():
    """Bounce Scanner ayarlar sayfası."""
    return render_template('pages/settings/bounce-scanner.html')


@app.route('/api/bounce-scanner/scan', methods=['POST'])
@login_required
def api_bounce_scanner_scan():
    """
    Seçilen SMTP göndericinin kimlik bilgileriyle IMAP'a bağlanır,
    bounce maillerini tarar ve sonuçları döner.

    Body:
        sender_id       — senders tablosundaki ID
        imap_host       — (opsiyonel) IMAP sunucu; boşsa smtp_server kullanılır
        imap_port       — (varsayılan 993)
        mode            — 'unseen' | 'all'
        add_suppression — bool; kalıcı bounce'ları suppression'a ekle
    """
    data = request.json or {}
    sender_id       = data.get('sender_id')
    imap_host_ovr   = (data.get('imap_host') or '').strip() or None
    imap_port       = int(data.get('imap_port') or 993)
    mode            = data.get('mode', 'unseen')          # 'unseen' | 'all'
    add_suppression = bool(data.get('add_suppression', True))

    if not sender_id:
        return jsonify({'success': False, 'message': 'sender_id zorunludur.'}), 400

    # Göndericiyi DB'den al (şifre çözülmüş olarak)
    sender = db().get_sender(sender_id)
    if not sender:
        return jsonify({'success': False, 'message': 'Gönderici bulunamadı.'}), 404
    if sender.get('sender_mode') != 'smtp':
        return jsonify({'success': False, 'message': 'Sadece SMTP göndericiler desteklenir.'}), 400

    imap_host = imap_host_ovr or sender.get('smtp_server', '')
    imap_user = sender.get('username', '')
    imap_pass = sender.get('password', '')   # get_sender() zaten decrypt eder

    if not imap_host or not imap_user:
        return jsonify({'success': False, 'message': 'IMAP sunucu veya kullanıcı adı eksik.'}), 400

    # Bounce scanner modülünü import et
    try:
        import sys, os as _os
        # bounce-scanner kodunu inline olarak çalıştırıyoruz (imap_tools gerekli)
        from imap_tools import MailBox, AND
        import re as _re
        from datetime import datetime as _dt
    except ImportError as e:
        return jsonify({'success': False, 'message': f'Gerekli kütüphane eksik: {e}. pip install imap-tools'}), 500

    # scanner.py'deki parse_bounce fonksiyonunu kullan (proje dizininden)
    _scanner_path = _os.path.join(_os.path.dirname(__file__), 'bounce_scanner_engine.py')
    # Eğer ayrı dosya yoksa inline parse_bounce kullanırız (bounce-scanner zip'ten kopyalandı)
    try:
        import bounce_scanner_engine as _bse
        parse_bounce = _bse.parse_bounce
    except ImportError:
        # Inline fallback — temel parse mantığı
        parse_bounce = _bounce_parse_inline

    results      = []
    stats        = {'okunan': 0, 'bounce': 0, 'yeni': 0, 'guncellendi': 0, 'atlanan': 0}
    hata_mesaji  = None

    try:
        with MailBox(imap_host, imap_port).login(imap_user, imap_pass) as mb:
            tumunu = (mode == 'all')
            if tumunu:
                f1 = list(mb.fetch(AND(from_='MAILER-DAEMON'), mark_seen=True, bulk=True))
                f2 = list(mb.fetch(AND(from_='postmaster'),    mark_seen=True, bulk=True))
                f3 = list(mb.fetch(AND(from_='Mail Delivery'), mark_seen=True, bulk=True))
            else:
                f1 = list(mb.fetch(AND(from_='MAILER-DAEMON', seen=False), mark_seen=True, bulk=True))
                f2 = list(mb.fetch(AND(from_='postmaster',    seen=False), mark_seen=True, bulk=True))
                f3 = list(mb.fetch(AND(from_='Mail Delivery', seen=False), mark_seen=True, bulk=True))

            # Duplicate temizle
            seen_uid, mailler = set(), []
            for m in f1 + f2 + f3:
                if m.uid not in seen_uid:
                    seen_uid.add(m.uid)
                    mailler.append(m)

            for mail in mailler:
                stats['okunan'] += 1
                # Ham içerik
                icerik = ''
                try:
                    if hasattr(mail, 'obj') and mail.obj:
                        icerik += mail.obj.as_string()
                except Exception:
                    pass
                if mail.text:  icerik += '\n' + mail.text
                if mail.html:  icerik += '\n' + mail.html
                for ek in mail.attachments:
                    if ek.content_type in ('message/delivery-status','text/rfc822-headers','message/rfc822','text/plain'):
                        try:    icerik += '\n' + ek.payload.decode('utf-8', errors='replace')
                        except: pass
                try:
                    for k, v in mail.headers.items():
                        icerik += f'\n{k}: {v}'
                except Exception:
                    pass

                bounce = parse_bounce(icerik)
                if not bounce:
                    stats['atlanan'] += 1
                    continue

                stats['bounce'] += 1

                # DB'ye kaydet
                sonuc = db().bounce_kaydet(bounce)
                is_new = (sonuc == 'yeni')
                if is_new:
                    stats['yeni'] += 1
                else:
                    stats['guncellendi'] += 1

                # Suppression — sadece kalıcı ve suppression_ekle=True olanlar
                if add_suppression and bounce.get('suppression_ekle'):
                    try:
                        db().suppression_add(
                            email=bounce['email'],
                            reason=f"Bounce: {bounce.get('hata_kodu','')}: {bounce.get('aciklama','')}",
                            added_by='bounce_scanner'
                        )
                    except Exception:
                        pass  # Suppression hatası taramayı durdurmasın

                results.append({
                    'email':            bounce['email'],
                    'kategori':         bounce.get('kategori', 'kalici'),
                    'bounce_tipi':      bounce.get('bounce_tipi', 'kalici'),
                    'hata_kodu':        bounce.get('hata_kodu', ''),
                    'aciklama':         bounce.get('aciklama', ''),
                    'etiket':           bounce.get('etiket', ''),
                    'rfc_etiket':       bounce.get('rfc_etiket', ''),
                    'suppression_ekle': bounce.get('suppression_ekle', False),
                    'is_new':           is_new,
                })

    except Exception as e:
        hata_mesaji = str(e)

    # Tarama geçmişini kaydet
    try:
        db().bounce_tarama_gecmisi_kaydet(
            hesap=imap_user,
            okunan=stats['okunan'],
            bounce=stats['bounce'],
            yeni=stats['yeni'],
            guncellendi=stats['guncellendi'],
            atlanan=stats['atlanan'],
            hata=hata_mesaji,
        )
    except Exception:
        pass

    if hata_mesaji and stats['okunan'] == 0:
        return jsonify({'success': False, 'message': f'IMAP bağlantı hatası: {hata_mesaji}'}), 500

    # Bounce oranı uyarısı
    bounce_uyari = None
    if stats['okunan'] > 0:
        oran = round(stats['bounce'] / stats['okunan'] * 100, 1)
        if oran >= 10:
            bounce_uyari = {'seviye': 'kritik', 'oran': oran,
                'mesaj': f'⚠️ Bounce oranı %{oran} — kritik! Listenizi temizleyin.'}
        elif oran >= 5:
            bounce_uyari = {'seviye': 'uyari', 'oran': oran,
                'mesaj': f'⚠️ Bounce oranı %{oran} — yüksek. Liste kalitesini kontrol edin.'}
        elif oran >= 2:
            bounce_uyari = {'seviye': 'dikkat', 'oran': oran,
                'mesaj': f'ℹ️ Bounce oranı %{oran} — dikkat gerektiriyor.'}

    return jsonify({
        'success':      True,
        'stats':        stats,
        'results':      results,
        'message':      hata_mesaji,
        'bounce_uyari': bounce_uyari,
    })


def _bounce_parse_inline(icerik: str):
    """
    Minimal inline bounce parser — bounce_scanner_engine.py yoksa kullanılır.
    Temel RFC 3464 DSN ayrıştırması yapar.
    """
    import re

    # Return-Path kontrolü
    rp = re.search(r'^Return-Path:\s*(.+)', icerik, re.IGNORECASE | re.MULTILINE)
    if rp:
        val = rp.group(1).strip()
        if val not in ('<>', ''):
            return None

    # Final-Recipient
    m = re.search(r'Final-Recipient:\s*rfc822;\s*([^\r\n;]+)', icerik, re.IGNORECASE)
    if not m:
        orig = re.search(r'Original-Recipient:\s*rfc822;\s*([^\r\n;]+)', icerik, re.IGNORECASE)
        if not orig:
            return None
        email = orig.group(1).strip().lower()
    else:
        email = re.sub(r'^[^a-z0-9._%+\-]+', '', m.group(1).strip().lower())

    if not re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$', email):
        return None

    ma = re.search(r'^Action:\s*(\S+)', icerik, re.IGNORECASE | re.MULTILINE)
    action = ma.group(1).strip().lower() if ma else 'unknown'
    ms = re.search(r'^Status:\s*(\S+)', icerik, re.IGNORECASE | re.MULTILINE)
    status = ms.group(1).strip() if ms else ''

    if action == 'failed':
        kategori = 'kalici'
    elif action == 'delayed':
        kategori = 'gecici'
    else:
        kategori = 'kalici' if status.startswith('5') else 'gecici'

    bounce_tipi = 'kalici' if kategori == 'kalici' else 'gecici'
    suppression_ekle = (kategori == 'kalici' and status not in {'5.4.14','5.5.1','5.6.0','5.7.64'})

    return {
        'email':            email,
        'bounce_tipi':      bounce_tipi,
        'hata_kodu':        status,
        'aciklama':         '',
        'diagnostic':       '',
        'kategori':         kategori,
        'suppression_ekle': suppression_ekle,
    }


@app.route('/api/bounce-scanner/history', methods=['GET'])
@login_required
def api_bounce_scanner_history():
    """Son 20 bounce tarama geçmişini döner."""
    try:
        rows = db().bounce_tarama_gecmisi_listele()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'data': [], 'message': str(e)})


if __name__ == '__main__':
    # Doğrudan çalıştırıldığında (python app.py):
    # debug=False: üretimde hata sayfası gösterme
    # host=127.0.0.1: sadece localhost — nginx/apache proxy arkasında çalışır
    # threaded=True: eş zamanlı SSE stream'lerini destekler
    app.run(debug=False, host='127.0.0.1', port=5002, threaded=True)
