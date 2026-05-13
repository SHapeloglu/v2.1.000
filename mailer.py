"""
mailer.py — MailSender Pro E-posta Gönderim Modülü
====================================================
SMTP, AWS SES ve üçüncü taraf HTTP API üzerinden mail gönderimini sağlar.

FONKSİYONLAR:
  is_valid_email()       — RFC 5322 e-posta doğrulama
  plain_to_html()        — Düz metin → <pre> HTML dönüşümü
  render_template_str()  — Jinja2 ile {{değişken}} şablon işleme
  _decrypt_pw()          — DB'deki Fernet şifreli parolayı çözer
  _resolve_aws_credentials() — Gönderici satırı veya .env'den AWS kimlik bilgileri
  smtp_connect()         — SMTP bağlantısı kurar (SSL veya STARTTLS)
  is_suppressed()        — Hosting suppression cache kontrolü (5 dk TTL)
  build_message()        — RFC 5322 MIME mesajı oluşturur (attachment, unsubscribe linki)
  send_one()             — SMTP ile tek mail gönderir
  send_via_ses()         — AWS SES send_raw_email ile gönderir
  send_via_api()         — HTTP API (Mailrelay, Brevo, vb.) ile gönderir
  test_sender()          — SMTP/SES bağlantı testi (gerçek mail göndermez)
  test_api_sender()      — API host TCP bağlantı testi

ÖNEMLİ NOTLAR:
  - Tüm göndericiler önce is_suppressed() kontrolünden geçer
  - build_message(): Türkçe gönderici adlarını RFC 2047 ile doğru encode eder
  - Unsubscribe token: önce hosting uygulamasından (UNSUB_APP_URL), olmadıysa local DB'den alınır
  - send_via_api(): payload template içindeki PLACEHOLDER değerleri JSON-escaped string ile değiştirilir
"""
import smtplib, ssl, os
from email.mime.text import MIMEText              # HTML/düz metin e-posta parçası
from email.mime.multipart import MIMEMultipart    # Çok parçalı mesaj (mixed: içerik + ek)
from email.mime.application import MIMEApplication # Ek dosya (binary attachment)
from jinja2 import Template                       # {{değişken}} şablon motoru
from email_validator import validate_email, EmailNotValidError  # RFC 5322 doğrulama

def is_valid_email(email: str) -> bool:
    """
    email-validator kütüphanesi ile RFC 5322 formatını doğrular.
    Geçersiz adreslere gönderim denenmez — bounce azaltır, SES itibar korur.
    """
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

def plain_to_html(text: str) -> str:
    """
    Düz metni minimal HTML'e çevirir: <pre> ile monospace font ve satır sonları korunur.
    HTML injection'a karşı &, < ve > karakterleri escape edilir.
    html_mode=False ile gönderilen mesajlar bu fonksiyondan geçer.
    """
    return "<pre>{}</pre>".format(text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

# Şablon derleme önbelleği — aynı şablon string'i bulk loop'ta defalarca kullanılır
# Template() her çağrıda parse eder; önbellek bunu engeller
_template_cache: dict = {}
_TEMPLATE_CACHE_MAX = 50  # Bellek koruma: en fazla 50 farklı şablon sakla

def render_template_str(template_str: str, variables: dict) -> str:
    """
    Jinja2 ile şablon string'ini işler.
    {{AdSoyad}}, {{Şehir}} gibi değişkenleri Excel/DB sütun değerleriyle doldurur.
    Değişken yoksa Jinja2 boş string bırakır (hata vermez).
    Aynı şablon bulk loop'ta tekrar kullanılırsa önbellekten alınır — yeniden parse edilmez.
    """
    tpl = _template_cache.get(template_str)
    if tpl is None:
        if len(_template_cache) >= _TEMPLATE_CACHE_MAX:
            _template_cache.clear()
        tpl = Template(template_str)
        _template_cache[template_str] = tpl
    return tpl.render(**variables)

def _decrypt_pw(sender_row: dict, field: str = 'password') -> str:
    """
    DB'deki Fernet şifreli alanı çözer.
    get_sender() zaten şifre çözülmüş değer döndürdüğünden bu fonksiyon
    genellikle gerekmez; sadece ham DB satırı kullanıldığında gerekli.
    """
    from database import decrypt_password
    return decrypt_password(sender_row.get(field, ''))

def _resolve_aws_credentials(sender_row: dict) -> tuple[str, str, str]:
    """
    Gönderici satırından AWS credentials döndürür.
    get_sender() zaten şifre çözdüğünden burada tekrar çözme yapılmaz.
    Boşsa ortam değişkenlerine fallback yapar.
    """
    aws_key    = (sender_row.get('aws_access_key') or '').strip()
    aws_secret = (sender_row.get('aws_secret_key') or '').strip()
    aws_region = (sender_row.get('aws_region') or 'us-east-1').strip()

    # Boşsa ortam değişkenlerine bak
    if not aws_key or not aws_secret:
        aws_key    = os.getenv('AWS_ACCESS_KEY_ID', '').strip()
        aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY', '').strip()
        aws_region = os.getenv('AWS_REGION', 'us-east-1').strip()

    return aws_key, aws_secret, aws_region

def smtp_connect(sender_row):
    """
    SMTP bağlantısı kurar ve kimlik doğrulaması yapar.
    use_ssl=1  (port 465): doğrudan TLS bağlantısı (SMTP_SSL)
    use_ssl=0  (port 587): STARTTLS yükseltmesi (EHLO → STARTTLS → EHLO)
    Başarılıysa açık smtplib.SMTP nesnesi döner — çağıran taraf quit() çağırmalı.
    """
    host    = sender_row['smtp_server']
    port    = int(sender_row['smtp_port'])
    user    = sender_row['username']
    pwd     = _decrypt_pw(sender_row, 'password')  # Fernet şifresini çöz
    use_ssl = sender_row.get('use_ssl', 1)

    print(f"SMTP bağlantı denemesi: {host}:{port} SSL:{use_ssl}")

    try:
        if use_ssl:
            # Port 465: TLS doğrudan açılır
            context = ssl.create_default_context()
            server  = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            # Port 587: önce düz bağlan, STARTTLS ile şifrele
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()       # Sunucuyu tanıt
            server.starttls()   # TLS'e yükselt
            server.ehlo()       # TLS üzerinde tekrar tanıt
        
        server.login(user, pwd)
        print(f"SMTP bağlantı başarılı: {host}")
        return server
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP kimlik doğrulama hatası: {e}")
        raise Exception(f"Kullanıcı adı veya şifre hatalı: {e}")
    except smtplib.SMTPConnectError as e:
        print(f"SMTP bağlantı hatası: {e}")
        raise Exception(f"Sunucuya bağlanılamadı: {host}:{port} - {e}")
    except Exception as e:
        print(f"SMTP genel hata: {e}")
        raise Exception(f"SMTP bağlantı hatası: {e}")

# ── Hosting Suppression Cache ────────────────────────────────────────
# Modül seviyesinde tek global cache — tüm thread'ler ortak kullanır.
# set(): O(1) üyelik kontrolü sağlar, büyük listeler için önemli.
_suppression_cache      = set()   # Küçük harfli e-posta adresleri kümesi
_suppression_cache_time = 0       # Son güncelleme Unix timestamp

# ── SendPulse OAuth2 Token Önbelleği ──────────────────────────────
# key: "client_id:client_secret" → value: (access_token, expire_timestamp)
_sendpulse_token_cache: dict = {}

def _sendpulse_get_token(credentials: str) -> str:
    """
    SendPulse OAuth2 access token alır ve önbelleğe saklar.
    credentials: "client_id:client_secret" formatında DB'den gelen değer.
    Token süresi dolmadan 60 saniye önce yeniler (expire - 60sn).
    Hata durumunda Exception fırlatır — gönderim durur, log'a yazılır.
    """
    import http.client as _hc, json as _j, ssl as _ssl, time as _t

    now = _t.time()
    cached = _sendpulse_token_cache.get(credentials)
    if cached:
        token, expires_at = cached
        if now < expires_at - 60:   # 60sn erken yenile
            return token

    # credentials ayır
    if ':' not in credentials:
        raise Exception("SendPulse credentials formatı geçersiz. 'client_id:client_secret' olmalı.")
    client_id, client_secret = credentials.split(':', 1)

    # Token isteği
    body = _j.dumps({
        'grant_type':    'client_credentials',
        'client_id':     client_id,
        'client_secret': client_secret,
    }).encode('utf-8')

    ctx  = _ssl.create_default_context()
    conn = _hc.HTTPSConnection('api.sendpulse.com', timeout=15, context=ctx)
    try:
        conn.request('POST', '/oauth/access_token', body, {
            'Content-Type': 'application/json',
            'User-Agent':   'MailSenderPro/1.0',
        })
        res  = conn.getresponse()
        data = _j.loads(res.read().decode('utf-8'))
    finally:
        conn.close()

    if res.status != 200 or 'access_token' not in data:
        raise Exception(f"SendPulse token alınamadı (HTTP {res.status}): {str(data)[:200]}")

    token      = data['access_token']
    expires_in = int(data.get('expires_in', 3600))
    _sendpulse_token_cache[credentials] = (token, now + expires_in)
    print(f"SendPulse OAuth2 token alındı — {expires_in}sn geçerli.")
    return token

def is_suppressed(email: str) -> bool:
    """
    E-posta adresinin suppression listesinde olup olmadığını kontrol eder.

    Cache mantığı:
      - Cache 5 dakikadan eskiyse /api/suppression-list endpoint'inden taze liste alır
      - UNSUB_APP_URL tanımlı değilse cache boş kalır (hep False döner)
      - Endpoint erişilemezse eski cache korunur (gönderim bloke olmaz)
    """  
    import time, urllib.request, json as _j
    global _suppression_cache, _suppression_cache_time

    now = time.time()
    if now - _suppression_cache_time > 300:  # 5 dakika
        unsub_app_url = os.getenv('UNSUB_APP_URL', '').rstrip('/')
        api_key       = os.getenv('UNSUB_API_KEY', '')
        if unsub_app_url:
            try:
                req = urllib.request.Request(
                    f"{unsub_app_url}/api/suppression-list",
                    headers={'X-API-Key': api_key},
                    method='GET'
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = _j.loads(resp.read())
                    if data.get('success'):
                        _suppression_cache = {r['email'].lower() for r in data.get('data', [])}
                        _suppression_cache_time = now
                        print(f"Suppression cache güncellendi: {len(_suppression_cache)} kayıt")
            except Exception as e:
                print(f"Suppression cache güncellenemedi: {e}")

    return email.lower() in _suppression_cache


def build_message(sender_row, recipient, subject, body_html, attachment=None, include_unsubscribe=True):
    """
    RFC 5322 uyumlu MIME e-posta mesajı oluşturur.

    MIME yapısı: multipart/mixed
      └─ text/html (UTF-8) — e-posta gövdesi
      └─ application/octet-stream — ek dosya (varsa)

    Gönderici adı encode'u:
      Saf ASCII iseler formataddr() kullanılır.
      Türkçe/özel karakter varsa RFC 2047 encoded-word (=?utf-8?...?=) uygulanır.
      Bu olmadan Outlook/Gmail gönderici adını bozuk gösterir.

    Unsubscribe:
      include_unsubscribe=True ise List-Unsubscribe header'ı ve mail sonuna link eklenir.
      RFC 8058 one-click unsubscribe: bazı e-posta istemcileri otomatik buton gösterir.
      Token önce hosting uygulamasından, hata varsa local DB'den alınır.
    """
    from database import generate_unsubscribe_token
    from email.headerregistry import Address
    from email.utils import formataddr
    import email.header

    msg = MIMEMultipart('mixed')  # 'mixed': içerik + ek dosya için

    # Gönderici adında Türkçe/ASCII dışı karakter varsa RFC 2047 ile doğru encode et
    sender_name  = sender_row['name']
    sender_email = sender_row['email']
    try:
        sender_name.encode('ascii')
        # Saf ASCII — düz format kullan
        msg['From'] = formataddr((sender_name, sender_email))
    except UnicodeEncodeError:
        # Türkçe/özel karakter var — RFC 2047 encoded word
        encoded_name = email.header.Header(sender_name, 'utf-8').encode()
        msg['From'] = f"{encoded_name} <{sender_email}>"

    msg['To']      = recipient
    msg['Subject'] = subject

    if include_unsubscribe:
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000').rstrip('/')
        unsub_app_url = os.getenv('UNSUB_APP_URL', '').rstrip('/')
        token = None

        # TOKEN ALMA STRATEJİSİ:
        # 1. UNSUB_APP_URL tanımlıysa hosting uygulamasına istek at (UNSUB_API_KEY ile auth)
        # 2. Hosting yoksa veya hata aldıysa local DB'den token üret
        # Token alınamazsa unsubscribe linki eklenmez ama mail yine de gönderilir.
        if unsub_app_url:
            try:
                import urllib.request, json as _json
                api_key = os.getenv('UNSUB_API_KEY', '')
                req = urllib.request.Request(
                    f"{unsub_app_url}/api/create-token",
                    data=_json.dumps({'email': recipient}).encode(),
                    headers={
                        'Content-Type': 'application/json',
                        'X-API-Key': api_key,
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = _json.loads(resp.read())
                    if result.get('success'):
                        token = result['token']
                        base_url = unsub_app_url  # link hosting'e gitsin
            except Exception as e:
                print(f"Hosting token alınamadı, local DB deneniyor: {e}")

        # Hosting yoksa veya hata aldıysa local DB'yi dene
        if not token:
            try:
                from database import generate_unsubscribe_token
                token = generate_unsubscribe_token(recipient)
            except Exception as e:
                print(f"Token üretme hatası (mail yine de gönderiliyor): {e}")
                token = None

        if token:
            unsub_url = f"{base_url}/unsubscribe?token={token}"
            # RFC 2369 List-Unsubscribe: e-posta istemcileri başlıkta unsubscribe butonu gösterir
            msg['List-Unsubscribe'] = f'<{unsub_url}>'
            # RFC 8058 One-Click: tek tıkla (POST isteği ile) abonelik iptali
            msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
            unsubscribe_html = (
                '<br><br><br>'
                '<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e5e5e5;margin-top:24px">'
                '<tr><td style="padding:20px 0;text-align:center">'
                '<p style="font-size:12px;color:#999;font-family:Arial,sans-serif;margin:0 0 8px 0">'
                'Bu e-postayı almak istemiyorsanız aşağıdaki bağlantıya tıklayarak listemizden çıkabilirsiniz.'
                '</p>'
                f'<a href="{unsub_url}" style="display:inline-block;padding:8px 20px;background:#f3f3f3;color:#666;'
                'font-size:12px;font-family:Arial,sans-serif;text-decoration:none;border-radius:4px;border:1px solid #ddd">'
                '🚫 Aboneliği İptal Et'
                '</a>'
                '</td></tr>'
                '</table>'
            )
            body_html += unsubscribe_html

    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    if attachment:
        filename, data = attachment
        part = MIMEApplication(data, Name=filename)
        part['Content-Disposition'] = f'attachment; filename="{filename}"'
        msg.attach(part)

    return msg

def send_one(sender_row, recipient, subject, body_html, attachment=None, include_unsubscribe=False):
    """
    SMTP üzerinden tek e-posta gönderir.
    Akış: doğrulama → suppression kontrolü → SMTP bağlantı → MIME mesaj → gönderim
    Dönen değer: (True, None) başarı | (False, hata_mesajı) başarısızlık
    finally bloğu: hata olsa bile SMTP bağlantısı kapatılır.
    quit() başarısız olursa close() ile zorla kapatılır.
    """
    # 1. Adres formatı kontrolü
    if not is_valid_email(recipient):
        return False, "Geçersiz e-posta adresi"
    # 2. Suppression listesi kontrolü (unsubscribe edenler veya bounce'lar)
    if is_suppressed(recipient):
        print(f"Suppression listesinde, atlanıyor: {recipient}")
        return False, "Suppression listesinde"

    server = None
    try:
        server = smtp_connect(sender_row)       # Bağlantı kur ve login yap
        msg    = build_message(sender_row, recipient, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
        server.sendmail(sender_row['email'], recipient, msg.as_string())
        print(f"E-posta gönderildi: {recipient}")
        return True, None
    except Exception as e:
        error_msg = str(e)
        print(f"Gönderim hatası: {error_msg}")
        return False, error_msg
    finally:
        # Bağlantıyı her durumda kapat — kaynak sızıntısını önler
        if server:
            try:
                server.quit()    # Normal kapatma (QUIT komutu gönderir)
            except Exception:
                try:
                    server.close()  # Zorla kapat (sunucu cevap vermezse)
                except Exception:
                    pass

def send_via_ses(sender_row, recipient, subject, body_html, attachment=None, include_unsubscribe=False):
    """
    AWS SES send_raw_email API ile e-posta gönderir.
    Neden send_raw_email (send_email değil)?
      → Ek dosya (attachment) desteği için ham MIME mesajı gerekir
      → List-Unsubscribe gibi özel header'lar ekleyebildiğimiz için
    Hata kodları ayrıştırılarak kullanıcıya anlamlı mesajlar verilir.
    """
    # 1. Suppression kontrolü
    if is_suppressed(recipient):
        raise Exception("Suppression listesinde")

    # 2. AWS kimlik bilgilerini al (sender_row → yoksa .env)
    aws_key, aws_secret, aws_region = _resolve_aws_credentials(sender_row)
    if not aws_key or not aws_secret:
        raise Exception("AWS credentials eksik. Gönderici ayarlarından Access Key ve Secret Key girin.")

    try:
        import boto3
        from botocore.exceptions import ClientError

        print(f"SES gönderim başlıyor: {recipient}")

        # Her gönderim için yeni boto3 session: farklı gönderici kimlik bilgilerini destekler
        session = boto3.Session(
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region,
        )
        client = session.client('ses')

        # MIME mesajı oluştur (ek varsa build_message zaten ekler)
        if attachment:
            msg = build_message(sender_row, recipient, subject, body_html, attachment, include_unsubscribe=include_unsubscribe)
        else:
            msg = build_message(sender_row, recipient, subject, body_html, include_unsubscribe=include_unsubscribe)

        # ConfigurationSet varsa ekle (SNS bounce/complaint takibi için)
        send_kwargs = {
            'Source':      sender_row['email'],
            'Destinations':[recipient],
            'RawMessage':  {'Data': msg.as_string()},
        }
        config_set = (sender_row.get('configuration_set') or '').strip()
        if config_set:
            send_kwargs['ConfigurationSetName'] = config_set

        response = client.send_raw_email(**send_kwargs)
        msg_id = response.get('MessageId')
        print(f"SES gönderim başarılı: {recipient} id={msg_id}")
        return msg_id  # Çağıran taraf log_send'e iletir

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_msg  = e.response.get('Error', {}).get('Message', '')

        if error_code == 'SignatureDoesNotMatch':
            raise Exception(f"AWS imza hatası: Secret Access Key yanlış. Bölge: {aws_region}")
        elif error_code == 'InvalidClientTokenId':
            raise Exception("Geçersiz AWS Access Key ID")
        elif error_code == 'AccessDenied':
            raise Exception("Erişim reddedildi. IAM politikasında ses:SendEmail yetkisi olmalı.")
        elif error_code == 'MessageRejected':
            raise Exception(f"Mesaj reddedildi: {error_msg}")
        else:
            raise Exception(f"AWS SES hatası ({error_code}): {error_msg}")
    except Exception as e:
        raise Exception(f"AWS SES bağlantı hatası: {type(e).__name__} - {str(e)}")

def test_sender(sender_row):
    """
    Gönderici bağlantısını test eder — gerçek e-posta göndermez.

    SES modu:
      - get_send_quota() ile bağlantı ve kota bilgisi alır
      - AccessDenied hatası gelirse get_identity_verification_attributes() ile
        en azından domain/e-posta doğrulama durumunu kontrol eder
      - NoCredentialsError: credentials hiç ayarlanmamış demektir

    SMTP modu:
      - smtp_connect() ile bağlanır, başarılıysa hemen quit() yapar
    """
    mode = sender_row.get('sender_mode', 'smtp')

    if mode == 'ses':
        aws_key, aws_secret, aws_region = _resolve_aws_credentials(sender_row)

        if not aws_key or not aws_secret:
            return False, "AWS credentials eksik. Gönderici ayarlarından Access Key ve Secret Key girin."

        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError

            print(f"SES test başlıyor: {aws_region}")

            session = boto3.Session(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name=aws_region,
            )
            client = session.client('ses')

            try:
                quota = client.get_send_quota()
                return True, f"AWS SES bağlantısı başarılı ✓ | Maksimum 24h: {quota['Max24HourSend']}"
            except ClientError as e:
                if 'AccessDenied' in str(e):
                    resp  = client.get_identity_verification_attributes(Identities=[sender_row['email']])
                    attrs  = resp.get('VerificationAttributes', {})
                    status = attrs.get(sender_row['email'], {}).get('VerificationStatus', 'NotFound')

                    if status == 'Success':
                        return True, f"AWS SES bağlantısı başarılı ✓ | {sender_row['email']} doğrulanmış"
                    elif status == 'Pending':
                        return False, f"AWS SES: {sender_row['email']} henüz doğrulanmamış (Pending)"
                    else:
                        return False, f"AWS SES: {sender_row['email']} SES'te kayıtlı değil (status: {status})"
                else:
                    raise e

        except NoCredentialsError:
            return False, "AWS credentials bulunamadı. Access Key ve Secret Key'i kontrol edin."
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_msg  = e.response.get('Error', {}).get('Message', '')

            if error_code == 'SignatureDoesNotMatch':
                return False, f"İmza hatası: AWS Secret Access Key yanlış. Bölge: {aws_region}"
            elif error_code == 'InvalidClientTokenId':
                return False, "Geçersiz AWS Access Key ID"
            elif error_code == 'AccessDenied':
                return False, "Erişim reddedildi. IAM politikasında ses:GetSendQuota yetkisi olmalı."
            else:
                return False, f"AWS SES hatası ({error_code}): {error_msg}"
        except Exception as e:
            return False, f"AWS SES bağlantı hatası: {type(e).__name__} - {str(e)}"
    else:
        server = None
        try:
            print(f"SMTP test başlıyor: {sender_row.get('smtp_server')}:{sender_row.get('smtp_port')}")
            server = smtp_connect(sender_row)
            return True, "SMTP bağlantısı başarılı ✓"
        except Exception as e:
            return False, f"SMTP bağlantı hatası: {e}"
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

def send_via_api(sender_row, recipient, subject, body_html, recipient_name='', include_unsubscribe=False):
    """
    Dinamik HTTP API üzerinden e-posta gönderir (Mailrelay, Brevo, SendGrid, vb.)

    PAYLOAD TEMPLATE SİSTEMİ:
      api_payload_tpl: JSON şablon, içinde PLACEHOLDER değerler bulunur.
      Örnek: {"to":[{"email":"RECIPIENT_EMAIL"}],"subject":"SUBJECT_TEXT","html_part":"HTML_CONTENT"}
      Değiştirme sırası: uzun eşleşmeler önce (FROM_EMAIL vs FROM çakışmasını önler).
      _js() fonksiyonu: değeri JSON string literal olarak encode eder.
        Örn: subject "Merhaba Dünya" → JSON'da "Merhaba Dünya" (tırnak escape'i)
        Böylece HTML veya özel karakter içeren gövde JSON'u bozmaz.

    AUTH TİPLERİ:
      X-AUTH-TOKEN (Mailrelay varsayılanı), Bearer, Token, api-key, apikey, X-API-KEY
      Tanınmayan tipler doğrudan header adı olarak kullanılır.

    HTTPS zorunludur — http.client.HTTPSConnection kullanılır.
    """ 
    import http.client, json as _json, ssl as _ssl

    # https:// veya http:// protokolü ve sondaki / varsa temizle
    host     = (sender_row.get('api_host') or '').strip()
    host     = host.removeprefix('https://').removeprefix('http://').rstrip('/')
    endpoint = (sender_row.get('api_endpoint') or '').strip()
    if endpoint and not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    auth_type = (sender_row.get('api_auth_type') or 'X-AUTH-TOKEN').strip()
    auth_token = (sender_row.get('api_auth_token') or '').strip()
    method   = (sender_row.get('api_method') or 'POST').strip().upper()
    tpl      = sender_row.get('api_payload_tpl')

    if not host or not endpoint:
        raise Exception("API host veya endpoint eksik. Gönderici ayarlarını kontrol edin.")
    if not auth_token:
        raise Exception("API auth token eksik.")
    if is_suppressed(recipient):
        raise Exception("Suppression listesinde")

    # Payload template: dict veya JSON string olabilir
    if isinstance(tpl, str):
        try:
            tpl = _json.loads(tpl)
        except Exception:
            tpl = None
    if not tpl:
        tpl = {
            "from": {"email": "FROM_EMAIL", "name": "FROM_NAME"},
            "to": [{"email": "RECIPIENT_EMAIL", "name": "RECIPIENT_NAME"}],
            "subject": "SUBJECT_TEXT",
            "html_part": "HTML_CONTENT",
            "text_part_auto": True
        }

    # Unsubscribe linki ekle
    if include_unsubscribe:
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000').rstrip('/')
        unsub_app_url = os.getenv('UNSUB_APP_URL', '').rstrip('/')
        token = None
        if unsub_app_url:
            try:
                import urllib.request, json as _j2
                api_key = os.getenv('UNSUB_API_KEY', '')
                req = urllib.request.Request(
                    f"{unsub_app_url}/api/create-token",
                    data=_j2.dumps({'email': recipient}).encode(),
                    headers={'Content-Type': 'application/json', 'X-API-Key': api_key},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = _j2.loads(resp.read())
                    if result.get('success'):
                        token = result['token']
                        base_url = unsub_app_url
            except Exception as e:
                print(f"Hosting token alınamadı: {e}")
        if not token:
            try:
                from database import generate_unsubscribe_token
                token = generate_unsubscribe_token(recipient)
            except Exception:
                token = None
        if token:
            unsub_url = f"{base_url}/unsubscribe?token={token}"
            body_html += (
                '<br><br><br>'
                '<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e5e5e5;margin-top:24px">'
                '<tr><td style="padding:20px 0;text-align:center">'
                '<p style="font-size:12px;color:#999;font-family:Arial,sans-serif;margin:0 0 8px 0">'
                'Bu e-postayı almak istemiyorsanız aşağıdaki bağlantıya tıklayarak listemizden çıkabilirsiniz.'
                '</p>'
                f'<a href="{unsub_url}" style="display:inline-block;padding:8px 20px;background:#f3f3f3;color:#666;'
                'font-size:12px;font-family:Arial,sans-serif;text-decoration:none;border-radius:4px;border:1px solid #ddd">'
                '🚫 Aboneliği İptal Et'
                '</a>'
                '</td></tr>'
                '</table>'
            )

    # PAYLOAD DEĞIŞTIRME MANTIĞI:
    # Her değeri json.dumps ile JSON string literal'e çevir (tırnak/satır sonu escape'i).
    # _js() fonksiyonu başındaki ve sonundaki " işaretini kaldırır — sadece içeriği verir.
    # Bu sayede HTML gövdesi veya "tırnaklı metin" içeren değerler JSON'u bozmaz.
    from_email_s  = sender_row.get('email', '')
    from_name_s   = sender_row.get('name', '')
    recip_name_s  = recipient_name or recipient.split('@')[0]

    tpl_str = _json.dumps(tpl, ensure_ascii=False)

    def _js(val):
        """Değeri JSON string literal olarak encode et (çevreleyen tırnaklar olmadan)."""
        return _json.dumps(val, ensure_ascii=False)[1:-1]  # başındaki ve sonundaki " kaldır

    replacements = [
        # Önce uzun eşleşmeleri yap, kısa olanlar sonra gelsin (HTML/BODY/TO gibi)
        ("FROM_EMAIL",      _js(from_email_s)),
        ("FROM_NAME",       _js(from_name_s)),
        ("SENDER_EMAIL",    _js(from_email_s)),
        ("SENDER_NAME",     _js(from_name_s)),
        ("RECIPIENT_EMAIL", _js(recipient)),
        ("RECIPIENT_NAME",  _js(recip_name_s)),
        ("TO_EMAIL",        _js(recipient)),
        ("TO_NAME",         _js(recip_name_s)),
        ("SUBJECT_TEXT",    _js(subject)),
        ("SUBJECT",         _js(subject)),
        ("HTML_CONTENT",    _js(body_html)),
        ("HTML",            _js(body_html)),
        ("BODY",            _js(body_html)),
        ("TO",              _js(recipient)),
    ]
    for placeholder, escaped_val in replacements:
        tpl_str = tpl_str.replace(f'"{placeholder}"', f'"{escaped_val}"')  # string değer
        tpl_str = tpl_str.replace(placeholder, escaped_val)                 # nested / diğer

    try:
        payload = _json.loads(tpl_str)
        payload_str = _json.dumps(payload, ensure_ascii=False)
    except Exception as parse_err:
        # JSON bozulduysa template'i olduğu gibi gönder, değerleri en-basit replace ile dene
        print(f"Payload parse hatası: {parse_err} — fallback kullanılıyor")
        payload = dict(tpl)
        payload_str = _json.dumps(payload, ensure_ascii=False)

    # AUTH HEADER AYARLA:
    # auth_type küçük harfe çevrilerek standart servis isimleriyle karşılaştırılır.
    # Mailrelay → X-AUTH-TOKEN | Brevo/SendGrid → Bearer | Postmark → X-API-KEY
    # Tanınmayan type: auth_type değeri doğrudan header adı olarak kullanılır (özel API'ler için)
    headers = {
        'Content-Type': 'application/json',
        'User-Agent':   'MailSenderPro/1.0',
    }
    at_lower = auth_type.lower()
    if at_lower == 'x-auth-token':
        headers['X-AUTH-TOKEN'] = auth_token                      # Mailrelay
    elif at_lower in ('bearer', 'authorization: bearer'):
        headers['Authorization'] = f'Bearer {auth_token}'         # Brevo, SendGrid, Mailtrap
    elif at_lower in ('token', 'authorization: token'):
        headers['Authorization'] = f'Token {auth_token}'          # DRF tabanlı API'ler
    elif at_lower == 'basic':
        import base64 as _b64
        # Mailjet: api_key:api_secret formatında base64 encode
        encoded = _b64.b64encode(auth_token.encode('utf-8')).decode('utf-8')
        headers['Authorization'] = f'Basic {encoded}'
    elif at_lower == 'sendpulse':
        # SendPulse OAuth2: client_id:client_secret → önce access_token al, sonra Bearer kullan
        bearer = _sendpulse_get_token(auth_token)
        headers['Authorization'] = f'Bearer {bearer}'
    elif at_lower == 'api-key':
        headers['api-key'] = auth_token                           # Azure benzeri
    elif at_lower == 'apikey':
        headers['apikey'] = auth_token                            # Supabase benzeri
    elif at_lower == 'x-api-key':
        headers['X-API-KEY'] = auth_token                         # AWS Gateway, Postmark
    else:
        headers[auth_type] = auth_token                           # Özel/bilinmeyen tip

    # HTTPS İSTEĞİ GÖNDER:
    # http.client kullanılır — requests kütüphanesine bağımlılıktan kaçınmak için.
    # timeout=30: yavaş API'ler için yeterli süre.
    # 2xx → başarı | diğer → HTTP {status}: {yanıt} ile hata fırlat (ilk 300 karakter)
    # RETRY MANTIĞI:
    # Geçici hatalar (timeout, 5xx, bağlantı kopması) → 3 deneme, exponential backoff
    # Kalıcı hatalar (4xx — 429 hariç) → direkt raise, retry yok
    # 429 → Retry-After kadar bekle, tekrar dene
    import time as _time

    RETRYABLE_STATUS = {500, 502, 503, 504}
    MAX_RETRIES      = 3

    for attempt in range(MAX_RETRIES):
        conn = None
        try:
            ctx  = _ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, timeout=30, context=ctx)
            conn.request(method, endpoint, payload_str.encode('utf-8'), headers)
            res  = conn.getresponse()
            data = res.read().decode('utf-8')

            # 429 Rate limit → Retry-After kadar bekle, tekrar dene
            if res.status == 429:
                retry_after = int(res.getheader('Retry-After', '60'))
                retry_after = min(retry_after, 120)
                if attempt < MAX_RETRIES - 1:
                    print(f"Rate limit (429) → {retry_after}sn bekleniyor (deneme {attempt+1}/{MAX_RETRIES})")
                    _time.sleep(retry_after)
                    continue
                raise Exception(f"Rate limit aşıldı (429). {retry_after}sn sonra tekrar deneyin.")

            # 2xx → başarı
            if 200 <= res.status < 300:
                msg_id = None
                try:
                    import json as _j
                    resp_json = _j.loads(data)
                    msg_id = (resp_json.get('messageId') or resp_json.get('message_id') or
                              resp_json.get('id') or resp_json.get('MessageId') or
                              str(resp_json.get('data', {}).get('id', '')) or None)
                    if msg_id:
                        msg_id = str(msg_id)
                except Exception:
                    pass
                print(f"API gönderim başarılı → {recipient} (HTTP {res.status}) id={msg_id}")
                return True, msg_id or data

            # 5xx geçici sunucu hatası → retry
            if res.status in RETRYABLE_STATUS:
                wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                if attempt < MAX_RETRIES - 1:
                    print(f"Geçici sunucu hatası ({res.status}) → {wait}sn sonra tekrar (deneme {attempt+1}/{MAX_RETRIES})")
                    _time.sleep(wait)
                    continue
                raise Exception(f"Sunucu geçici hata ({res.status}), {MAX_RETRIES} denemede başarısız: {data[:200]}")

            # 4xx kalıcı hata → retry yok
            raise Exception(f"HTTP {res.status}: {data[:300]}")

        except Exception as e:
            err_str = str(e)
            # Bağlantı/timeout hataları geçici → retry
            is_network = any(kw in type(e).__name__ for kw in ('Timeout', 'Connection', 'Remote', 'BrokenPipe'))
            is_network = is_network or any(kw in err_str for kw in (
                'timed out', 'Connection refused', 'RemoteDisconnected', 'BrokenPipe', 'reset by peer'))
            if is_network and attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"Ağ hatası → {wait}sn sonra tekrar (deneme {attempt+1}/{MAX_RETRIES}): {err_str[:100]}")
                _time.sleep(wait)
                continue
            raise  # Kalıcı hata veya son deneme → çağırana ilet
        finally:
            if conn:
                try: conn.close()
                except: pass


def test_api_sender(sender_row):
    """
    API gönderici bağlantısını test eder — gerçek mail göndermez.
    Sadece TCP seviyesinde HTTPS bağlantısı kurar (conn.connect()).
    Bu sayede host adı çözülebiliyorsa ve port 443 açıksa başarı döner.
    Endpoint doğruluğunu test etmez (auth gerektireceğinden deneme maili gitmez).
    """ 
    import http.client, json as _json, ssl as _ssl
    host     = (sender_row.get('api_host') or '').strip()
    endpoint = (sender_row.get('api_endpoint') or '').strip()
    auth_type = (sender_row.get('api_auth_type') or 'X-AUTH-TOKEN').strip()
    auth_token = (sender_row.get('api_auth_token') or '').strip()
    if not host:
        return False, "API host boş."
    if not auth_token:
        return False, "API auth token boş."
    # Sadece TCP bağlantısını test et
    try:
        ctx = _ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, timeout=10, context=ctx)
        conn.connect()
        conn.close()
        return True, f"✓ {host} sunucusuna bağlantı başarılı."
    except Exception as e:
        return False, f"Bağlantı hatası: {e}"



# ── E-posta Filtre Yardımcıları (worker.py'den de import edilir) ──────────
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
