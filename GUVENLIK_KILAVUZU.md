# 🔐 MailSender Pro — Güvenlik Kılavuzu

## Kısa Özet: Ne Şifreli, Ne Değil?

| Veri | Durum | Neden |
|------|-------|-------|
| DB'deki SMTP şifresi | ✅ Fernet ile şifreli | Veritabanı ele geçirilse bile okunamaz |
| DB'deki AWS Access/Secret Key | ✅ Fernet ile şifreli | Aynı şekilde korunuyor |
| Unsubscribe link (kullanıcıya giden) | ✅ Token tabanlı | URL'de e-posta adresi yok, 32-byte rastgele token var, 7 gün geçerli, tek kullanımlık |
| Tarayıcı ↔ Uygulama trafiği | ⚠️ **HTTPS kurulumuna bağlı** | Aşağıya bakın |
| Uygulama ↔ DB trafiği | ⚠️ `DB_SSL=true` yapılırsa şifreli | Aynı sunucudaysanız risksiz |
| Mail içeriği | ➡️ Şifrelenemez | E-posta protokolünün sınırı |

---

## En Önemli Adım: HTTPS Kurun

HTTPS olmadan trafik açık metin gider. AWS EC2 kullanıyorsanız aşağıdaki yöntemlerden birini seçin.

---

## Yöntem 1 — Nginx + Let's Encrypt (Önerilen, Ücretsiz)

### Gereksinimler
- Domain adı (örn: `mail.sirketim.com`) → EC2 IP'nize yönlendirilmiş
- Ubuntu EC2 örneği

### Kurulum

```bash
# 1. Nginx ve Certbot kur
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx -y

# 2. Nginx config oluştur
sudo nano /etc/nginx/sites-available/mailsender
```

Şu içeriği yapıştırın (`yourdomain.com` yerine kendi domain'inizi yazın):

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Let's Encrypt doğrulaması için
    location /.well-known/acme-challenge/ { root /var/www/html; }

    # Her şeyi HTTPS'e yönlendir
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL sertifikaları (Certbot dolduracak)
    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Güvenli SSL ayarları
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Güvenlik header'ları
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    # Flask uygulamasına yönlendir
    location / {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE (Server-Sent Events) için gerekli
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600;
    }
}
```

```bash
# 3. Config'i etkinleştir
sudo ln -s /etc/nginx/sites-available/mailsender /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 4. SSL sertifikası al (ücretsiz, otomatik yenilenir)
sudo certbot --nginx -d yourdomain.com

# 5. .env dosyanızı güncelleyin
# APP_BASE_URL=https://yourdomain.com
# FORCE_HTTPS=true
```

---

## Yöntem 2 — AWS CloudFront + ACM (Domain yoksa)

Domain yoksa veya EC2 IP'si değişiyorsa:

1. AWS Certificate Manager'dan ücretsiz SSL sertifikası alın
2. CloudFront distribution oluşturun, Origin olarak EC2 IP'yi ekleyin
3. CloudFront HTTPS'i halleder, siz sadece Flask'ı çalıştırırsınız

---

## Yöntem 3 — Self-Signed (Sadece iç ağ/test için)

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

Tarayıcı uyarı verir, güvenilir değildir. Sadece iç ağda kullanın.

---

## AWS Güvenlik Grubu (Security Group) Ayarları

EC2 konsolundan şu portların açık olduğundan emin olun:

| Port | Protokol | Kaynak | Açıklama |
|------|----------|--------|----------|
| 22 | TCP | Sadece kendi IP'niz | SSH erişimi |
| 80 | TCP | 0.0.0.0/0 | HTTP → HTTPS yönlendirme |
| 443 | TCP | 0.0.0.0/0 | HTTPS |
| 5002 | TCP | **Kapalı tutun** | Flask direkt erişim olmamalı |

**Flask'ı 5002 portunda dışarıya açmayın.** Nginx üzerinden 443'ten erişin.

---

## SECRET_KEY Üretme

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Çıktıyı `.env` dosyasına yapıştırın. Bu key'i kaybederseniz DB'deki tüm şifreler okunamaz hale gelir — **mutlaka yedekleyin**.

---

## Güvenli MySQL Kullanıcısı Oluşturma

```sql
-- Sadece uygulama için sınırlı yetkili bir kullanıcı
CREATE USER 'mailsender_user'@'127.0.0.1' IDENTIFIED BY 'GUCLU_SIFRE';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON mailsender.* TO 'mailsender_user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Root kullanıcıyla bağlanmayın.

---

## Bounce Scanner Güvenlik Notları

Bounce Scanner, SMTP gönderici hesabının **IMAP kimlik bilgileriyle** bağlantı kurar.

### IMAP Şifresi
- Bounce Scanner ayrı bir şifre saklamaz — SMTP göndericisinin şifresini kullanır
- Bu şifre veritabanında **Fernet ile şifreli** saklanır (diğer SMTP şifreleriyle aynı koruma)
- IMAP bağlantısı varsayılan olarak **SSL/TLS** (port 993) ile yapılır

### Gmail Kullanıyorsanız
- Normal hesap şifresi çalışmaz — **Uygulama Şifresi** oluşturmanız gerekir
- Google hesabı → Güvenlik → 2 adımlı doğrulama açık → Uygulama Şifreleri
- Oluşturulan 16 haneli şifreyi SMTP gönderici kaydında kullanın

### İzin Verilen IP / CSRF
- `/api/bounce-scanner/scan` endpoint'i `@login_required` ile korunuyor
- `/api/bounce-scanner/manuel-ekle` endpoint'i rate limit (60/dk) ile korunuyor
- `/api/suppression/batch-check` endpoint'i rate limit (20/dk) ile korunuyor

### Tarama Sonuçları
- Tarama sonuçları sunucuda saklanmaz — her taramada sıfırdan okunur
- CSV export tarayıcıda oluşturulur, sunucuya gönderilmez

---

## Kontrol Listesi

- [ ] HTTPS kuruldu (Nginx + Let's Encrypt)
- [ ] `FORCE_HTTPS=true` `.env`'de ayarlı
- [ ] `APP_BASE_URL` HTTPS ile başlıyor
- [ ] `SECRET_KEY` güçlü ve yedeklenmiş
- [ ] EC2 Security Group'ta 5002 portu kapalı
- [ ] MySQL için ayrı, sınırlı yetkili kullanıcı var
- [ ] `.env` dosyası Git'e commit edilmemiş (`.gitignore`'a ekleyin)
- [ ] (Opsiyonel) `DB_SSL=true` — DB ayrı sunucudaysa

---

## Suppression Listesi ve Domain Bloklama — Sebep Seçiminin Etkisi

Suppression sayfasında e-posta veya domain eklerken seçilen **sebep (reason), engelleme davranışını hiçbir şekilde etkilemez.**

Gönderim öncesinde çalışan `is_suppressed()` kontrolü iki sorgu yapar:

1. Adres `suppression_list` tablosunda var mı?
2. Adresin domain'i `suppression_domains` tablosunda var mı?

Her iki kontrolde de `reason` alanına bakılmaz. Listede bulunan her adres veya domain, sebebi ne olursa olsun **aynı şekilde engellenir.**

| Özellik | Gönderimi engeller mi? | Sebep fark yaratır mı? |
|---|---|---|
| Manuel e-posta ekleme | ✅ Evet | ❌ Hayır |
| Domain bloklama | ✅ Evet | ❌ Hayır |

**Sebep alanı yalnızca etiketleme içindir:**
- Listede filtreleme yapabilirsiniz (sadece bounce'ları göster vb.)
- İstatistik sayfasında dağılımı görebilirsiniz
- Audit logunda hangi sebeple eklendiği kayıt altına alınır

**Sebepler, kaynakları ve nasıl oluştuğu:**

| Sebep | Kaynak | Nasıl Eklenir |
|---|---|---|
| `bounce` | AWS SES/SNS webhook (`ses_sns`), Brevo webhook, Mailrelay webhook | Gönderdiğiniz mail alıcıya ulaşamazsa (posta kutusu yok, dolu, vb.) ilgili servis sunucunuza bildirim gönderir, uygulama otomatik ekler |
| `complaint` | AWS SES/SNS webhook (`ses_sns`), Brevo webhook, Mailrelay webhook | Alıcı maili spam olarak işaretlerse ilgili servis sunucunuza bildirim gönderir, uygulama otomatik ekler |
| `unsubscribe` | Uygulama içi (`unsubscribe` sayfası) | Alıcı maildeki "aboneliği iptal et" linkine tıklayınca otomatik eklenir |
| `invalid` | E-posta doğrulama sistemi (`email_verify`) | Ayarlar → E-posta Doğrulama ekranında doğrulama işlemi çalıştırılınca geçersiz bulunan adresler otomatik eklenir |
| `manual` | Suppression sayfası (elle) | Siz suppression sayfasından kendiniz eklersiniz |
| `bounce_scanner_manuel` | Bounce Scanner sonuç ekranı | Tarama sonucunda satır seçip 'Suppression'a Ekle' butonuna basıldığında eklenir |

> **Not:** `bounce` ve `complaint` için webhook'ların çalışması gerekir. AWS SNS Topic'inize `https://yourdomain.com/sns/ses-notification` adresini HTTP subscription olarak ekleyin. Uygulama `SubscriptionConfirmation` isteğini otomatik onaylar. Tanımlanmamışsa bu sebepler otomatik eklenemez.

---

## mail_list_ Tablolarındaki `is_valid` Alanı

E-posta doğrulama çalıştırıldığında her adres için tabloya `is_valid` kolonu eklenir ve sonuç buraya yazılır.

**`is_valid` değerleri:**

| Değer | Anlamı | Gönderimde |
|---|---|---|
| `1` | Geçerli | ✅ Gönderilir |
| `0` | Geçersiz | ❌ Atlanır |
| `-1` | Riskli / Belirsiz | ⚠️ Varsayılan atlanır, "riskli dahil et" seçeneğiyle gönderilebilir |

**Hangi durum hangi `is_valid` değerini alır:**

| Durum Kodu | `is_valid` | Açıklama |
|---|---|---|
| `valid` | `1` | Tüm kontroller geçti |
| `typo_fixed` | `1` | Yazım hatası düzeltildi (gmial.com → gmail.com gibi) |
| `catch_all` | `1` | Sunucu her adrese 250 veriyor — teslim belirsiz ama geçerli sayılır |
| `free_provider` | `1` | Gmail, Hotmail, Yahoo vb. ücretsiz servis |
| `no_infra` | `-1` | SPF/DMARC kaydı yok — zayıf domain, bounce riski yüksek |
| `role_account` | `-1` | Kişisel olmayan rol adresi (info@, admin@, noreply@ vb.) |
| `unknown` | `-1` | SMTP belirsiz yanıt verdi — kesin sonuç alınamadı |
| `invalid_format` | `0` | E-posta formatı geçersiz (RFC uyumsuz) |
| `disposable` | `0` | Geçici/tek kullanımlık servis (mailinator.com vb.) |
| `no_mx` | `0` | Domain için DNS/MX kaydı bulunamadı |
| `invalid` | `0` | SMTP 550 — posta kutusu yok |

**`is_valid = 0` olan adresler suppression listesine de otomatik eklenir** (`invalid` sebebiyle), bir daha gönderim denenmez.

**`is_valid = -1` olan adresler** suppression'a eklenmez. Toplu gönderim ekranında "Geçersiz/riskli adresleri dahil et" seçeneğiyle bu adreslere de gönderilebilir.

---

## Mevcut Kod Güvenliği Özeti

- **SQL Injection**: Tüm kullanıcı girdileri parametrize sorgularla işleniyor. Tablo/sütun adları `safe_identifier()` ile whitelist doğrulamasından geçiyor.
- **Rate Limiting**: Tüm kritik endpoint'ler IP bazlı korumalı:

| Endpoint | Limit |
|---|---|
| Unsubscribe | 10 istek/dakika |
| DB config kaydetme | 5 istek/dakika |
| Toplu gönderim | 5 istek/dakika |
| Bounce Scanner tarama | 10 istek/dakika |
| Bounce manuel ekle | 60 istek/dakika |
| Suppression batch-check | 20 istek/dakika |
| Suppression purge | 3 istek/dakika |
- **Security Headers**: XSS, clickjacking, MIME sniffing koruması tüm yanıtlara ekleniyor.
- **Token Güvenliği**: 32-byte kriptografik rastgele token, tek kullanımlık, 7 gün geçerli, DB'de expire kontrolü.
- **Debug Modu**: Production'da `debug=False`, sadece `127.0.0.1` dinliyor.
- **Hassas Veri**: `SECRET_KEY` hiçbir API yanıtında dönmüyor.
