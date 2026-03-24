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
        proxy_pass http://127.0.0.1:5000;
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
| 5000 | TCP | **Kapalı tutun** | Flask direkt erişim olmamalı |

**Flask'ı 5000 portunda dışarıya açmayın.** Nginx üzerinden 443'ten erişin.

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

## Kontrol Listesi

- [ ] HTTPS kuruldu (Nginx + Let's Encrypt)
- [ ] `FORCE_HTTPS=true` `.env`'de ayarlı
- [ ] `APP_BASE_URL` HTTPS ile başlıyor
- [ ] `SECRET_KEY` güçlü ve yedeklenmiş
- [ ] EC2 Security Group'ta 5000 portu kapalı
- [ ] MySQL için ayrı, sınırlı yetkili kullanıcı var
- [ ] `.env` dosyası Git'e commit edilmemiş (`.gitignore`'a ekleyin)
- [ ] (Opsiyonel) `DB_SSL=true` — DB ayrı sunucudaysa

---

## Mevcut Kod Güvenliği Özeti

- **SQL Injection**: Tüm kullanıcı girdileri parametrize sorgularla işleniyor. Tablo/sütun adları `safe_identifier()` ile whitelist doğrulamasından geçiyor.
- **Rate Limiting**: Unsubscribe (10/dk), DB config kaydetme (5/dk), toplu gönderim (5/dk) endpoint'leri IP bazlı korumalı.
- **Security Headers**: XSS, clickjacking, MIME sniffing koruması tüm yanıtlara ekleniyor.
- **Token Güvenliği**: 32-byte kriptografik rastgele token, tek kullanımlık, 7 gün geçerli, DB'de expire kontrolü.
- **Debug Modu**: Production'da `debug=False`, sadece `127.0.0.1` dinliyor.
- **Hassas Veri**: `SECRET_KEY` hiçbir API yanıtında dönmüyor.
