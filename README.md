<div align="center">

# ✉️ MailSenderVerifier

**Self-hosted e-posta gönderim ve doğrulama platformu — KOBİ'ler için tasarlandı**

Flask · MySQL · AWS SES · SMTP · REST API

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![AWS SES](https://img.shields.io/badge/AWS-SES-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com/ses)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/Lisans-MIT-green?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Versiyon-v2.2.0-blue?style=flat-square)](CHANGELOG.md)

</div>

---

## 📖 İçindekiler

- [Nedir?](#-nedir)
- [Rakip Karşılaştırması](#-rakip-karşılaştırması)
- [Özellikler](#-özellikler)
- [Risk Skoru Sistemi](#-risk-skoru-sistemi)
- [Mimari](#-mimari)
- [Kurulum](#-kurulum)
- [Yapılandırma](#-yapılandırma)
- [Gönderim Modları](#-gönderim-modları)
- [E-posta Doğrulama](#-e-posta-doğrulama)
- [SNS Webhook](#-sns-webhook--bounce--complaint)
- [Güvenlik](#-güvenlik)
- [API Referansı](#-api-referansı)
- [Dosya Yapısı](#-dosya-yapısı)
- [Değişiklik Günlüğü](#-değişiklik-günlüğü)

---

## 🚀 Nedir?

MailSenderVerifier, küçük ve orta ölçekli işletmeler için geliştirilmiş, **kendi sunucunuzda çalışan** (self-hosted) kurumsal toplu e-posta gönderim ve doğrulama platformudur.

Excel listelerinden, veritabanı tablolarından ya da tek tek yazarak mail gönderebilir; gerçek zamanlı ilerleme takibi, akıllı bounce yönetimi, deliverability risk skoru ve gelişmiş liste doğrulaması yapabilirsiniz.

Dış bir SaaS servise bağımlı kalmadan kendi altyapınızda tam kontrol size aittir. **Türkçe arayüzü** ile yerel KOBİ ihtiyaçlarına odaklanmıştır.

---

## 🏆 Rakip Karşılaştırması

| Özellik | MSV | Brevo | Mailtrap | Listmonk | Sendy |
|---------|:---:|:-----:|:--------:|:--------:|:-----:|
| Self-hosted | ✅ | ❌ | ❌ | ✅ | ✅ |
| E-posta doğrulama | ✅ | ❌ | ✅ (ayrı ücret) | ❌ | ❌ |
| Deliverability risk skoru | ✅ | ❌ | ❌ | ❌ | ❌ |
| Bounce sınıflandırma | ✅ (5 kategori) | ✅ yüzeysel | ✅ yüzeysel | ✅ | ✅ |
| Greylisting retry | ✅ | ❌ | ❌ | ❌ | ❌ |
| AWS SES entegrasyonu | ✅ | ❌ | ❌ | ✅ | ✅ |
| HTTP API gönderici | ✅ | — | — | ❌ | ❌ |
| Gönderici itibar skoru | ✅ | ❌ | ❌ | ❌ | ❌ |
| Türkçe arayüz | ✅ | ❌ | ❌ | ❌ | ❌ |
| Aylık ücret | ❌ | ✅ | ✅ | ❌ | ❌ |

---

## ✨ Özellikler

### 📤 Gönderim
| Özellik | Açıklama |
|---|---|
| **Tekli Gönderim** | Anlık, tek adrese doğrudan gönderim |
| **Excel'den Toplu** | `.xlsx` yükle, sütun eşle, gönder |
| **DB Tablosundan Toplu** | Daha önce yüklediğiniz tablolardan seçim yaparak gönder |
| **Parçalı (Batch) Gönderim** | X mail gönder, Y dakika bekle — saatlik kota yönetimi |
| **Tahmini Gönderim Süresi** | Alıcı sayısı × bekleme süresi hesaplanarak tahmini süre anlık gösterilir |
| **SSE Canlı İzleme** | Gönderim sırasında her satır sonucu ekranda anlık görünür |
| **Tarih Aralığı Filtresi** | Gönderim geçmişinde başlangıç/bitiş tarihi seçimi; UTC timezone bilinçli |
| **Kuyruk Sistemi** | Hosting ortamında worker.py + cron ile arka plan gönderimi |

### 📡 Gönderici Desteği
- **SMTP** — Gmail, Yandex, şirket sunucusu, herhangi bir SMTP (TLS/SSL, 465/587)
- **AWS SES** — SDK ile doğrudan entegrasyon, kota takibi
- **HTTP API** — Brevo, Mailrelay, SendGrid, Postmark ve uyumlu her servis

### 🔍 Liste Yönetimi & Doğrulama
- **E-posta Doğrulama** — Format, MX, SMTP, catch-all, disposable, gibberish kontrolü
- **Deliverability Risk Skoru** — Her adrese 0-100 arası teslim edilebilirlik skoru
- **Otomatik Yeniden Doğrulama** — Belirli aralıklarla listeleri otomatik yeniler
- **Disposable Domain Güncelleme** — 50.000+ geçici domain listesi 6 saatte bir GitHub'dan güncellenir
- **DNSBL / RBL Kontrolü** — IP'nizin kara listede olup olmadığını kontrol eder
- **Suppression Listesi** — Bounce, complaint, unsubscribe, geçersiz — otomatik veya manuel
- **Domain Bloklama** — Tek komutla tüm domaini engelle
- **Yazım Hatası Düzeltme** — `gmial.com → gmail.com` benzeri otomatik düzeltme

### 📬 Bounce Yönetimi
| Özellik | Açıklama |
|---|---|
| **Bounce Scanner** | IMAP kutusuna bağlanarak MAILER-DAEMON maillerini otomatik tarar |
| **Akıllı Sınıflandırma** | Kalıcı / Geçici / Gönderen Sorunu / Mail Döngüsü / İç Domain |
| **Açıklama Üretimi** | Diagnostic-Code'dan Türkçe açıklama + ikon etiket üretir |
| **RFC 3463 Etiket** | Enhanced status code tablosundan otomatik ikinci sınıflandırma |
| **Checkbox Seçim** | Sonuçları gözden geçirip seçerek suppression'a ekle |
| **Toplu Uygula** | Seçilenleri suppression'a veya sadece bounce kaydına ekle |
| **CSV Export** | Tarama sonuçlarını CSV olarak indir |

### ⚙️ Sistem
- **Çoklu Kullanıcı** — Admin / Editor rolleri, bcrypt şifre hash
- **Tema Sistemi** — 7 farklı tema, hesaba kayıtlı, FOUC olmadan yükleme
- **Şablon Yönetimi** — Konu ve mesaj şablonları, Jinja2 değişken desteği
- **Kural Sistemi** — Gönderici + min. bekleme süresi kuralları
- **Greylisting Retry** — Geçici reddedilen mailleri 6/12/24 saat sonra otomatik yeniden dener
- **AWS SNS Webhook** — Bounce/complaint bildirimlerini otomatik yakalar
- **EC2 Auto-Stop** — Gönderim bitince instance'ı otomatik kapatır
- **Audit Log** — Kritik işlemler (kullanıcı, gönderici, gönderim) kayıt altına alınır
- **Şifre Sıfırlama** — Token tabanlı güvenli akış

---

## 📊 Risk Skoru Sistemi

Her e-posta adresine 0-100 arası deliverability skoru atanır. Bu skor gönderim kararlarını otomatik yönlendirir.

### Skor Bantları

| Skor | Etiket | Açıklama |
|------|--------|----------|
| 90–100 | `safe` | Güvenli gönder |
| 70–89 | `low_risk` | Düşük risk |
| 50–69 | `medium_risk` | Orta risk |
| 30–49 | `high_risk` | Yüksek risk |
| 0–29 | `do_not_send` | Gönderme |

### Başlangıç Skorları

```python
'valid':          85   # SMTP onaylı
'free_provider':  90   # Gmail, Hotmail
'catch_all':      65   # Sunucu her adrese 250 veriyor
'role_account':   60   # info@, admin@ vb.
'unknown':        40   # SMTP yanıtsız
'invalid':         0   # SMTP 550
```

### Skoru Etkileyen Faktörler

**Artıranlar:**
- Kurumsal güvenlik ESP'si (Proofpoint, Mimecast vb.): +10 ile +20
- Trusted provider (Google, Microsoft): +bonus

**Düşürenler:**
- Catch-all sunucu: -15
- SPF + DMARC her ikisi yoksa: -10 (role_account için -5)
- Sadece SPF yoksa: -5 (role_account için -3)
- Sadece DMARC yoksa: -3
- Disposable domain: büyük kesinti
- Daha önce bounce: kesinti
- Suppression listesinde: skor 0

> **Not:** Brevo/Mailtrap/Millionverifier/Trykitty karşılaştırmasında info@ adreslerinin %71-100'ünün delivered olduğu tespit edildi. `role_account` taban skoru 50→60 güncellendi, SPF/DMARC cezası role_account için yarıya indirildi. (2026-07-26)

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────────┐
│                     İstemci (Tarayıcı)                  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────┐
│              Nginx  (Reverse Proxy + SSL)                │
└──────────────────────────┬──────────────────────────────┘
                           │ 127.0.0.1:8011
┌──────────────────────────▼──────────────────────────────┐
│                  app.py  (Flask)                         │
│  ┌───────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ Sayfa     │  │  REST API    │  │  Webhook          │ │
│  │ Route'ları│  │  Endpoint'leri│  │  /sns/ses-notif  │ │
│  └───────────┘  └──────────────┘  └───────────────────┘ │
└──────────┬──────────────┬───────────────────────────────┘
           │              │
  ┌────────▼─────┐  ┌─────▼──────────────┐
  │  database.py │  │  mailer.py          │
  │  (MySQL)     │  │  verifier.py        │
  └────────┬─────┘  │  risk_score.py      │
           │        │  security.py        │
           │        │  spam_trap.py       │
           │        │  dnsbl_check.py     │
           │        │  reputation_score.py│
           │        └─────────────────────┘
           │
  ┌────────▼──────────────────────────────────┐
  │            worker.py  (Cron / 5 dk)        │
  │  Mail Kuyruğu · Verify Jobs · Greylist    │
  │  Auto-Reverify · Disposable Güncelleme    │
  └────────────────────────────────────────────┘
```

---

## 📦 Kurulum

### Gereksinimler
- Python **3.12+**
- MySQL **8.0+**
- Nginx
- Docker (önerilen)

### 🐳 Docker ile Kurulum (Önerilen)

```bash
# Repoyu klonla
git clone https://github.com/kullanici/mailsenderverifier.git
cd mailsenderverifier

# Ortam değişkenlerini ayarla
cp _env .env
nano .env

# Fernet key üret ve .env'e yapıştır
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Build ve başlat
docker compose up -d --build

# Logları izle
docker compose logs -f
```

### 🐧 Linux Manuel Kurulum

```bash
# Tam otomatik kurulum (pip, .env, DB, admin, nginx, systemd)
sudo python3 setup_linux.py

# Sistem servisleri olmadan (geliştirme)
python3 setup_linux.py --skip-system
```

#### Adım Adım Manuel

```bash
# Sanal ortam
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Migration'ları sırayla çalıştır
mysql -u root -p aws_mail_sender_pro_v3 < migrate_v2.1.002.sql
mysql -u root -p aws_mail_sender_pro_v3 < migrate_api_columns.sql
mysql -u root -p aws_mail_sender_pro_v3 < migrate_auto_reverify.sql
mysql -u root -p aws_mail_sender_pro_v3 < migrate_greylist_retry.sql
mysql -u root -p aws_mail_sender_pro_v3 < migrate_spam_trap.sql
mysql -u root -p aws_mail_sender_pro_v3 < migrate_suppression_fix.sql

# Gunicorn ile başlat
gunicorn --bind 0.0.0.0:8011 --workers 2 --timeout 120 app:app
```

---

## ⚙️ Yapılandırma

`.env` dosyası:

```ini
# ── Veritabanı ──────────────────────────────────
DB_HOST=localhost
DB_PORT=3306
DB_USER=mailsender_user
DB_PASSWORD=GUCLU_SIFRE
DB_NAME=aws_mail_sender_pro_v3
DB_SSL=false

# ── Şifreleme (asla paylaşma, git'e koyma!) ─────
# Üret: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_KEY=

# ── Gönderim Modu ───────────────────────────────
# local    → SSE ile anlık gönderim (VPS / EC2)
# hosting  → Kuyruk sistemi (cPanel / Shared Hosting)
SEND_MODE=local

# ── Uygulama ────────────────────────────────────
APP_BASE_URL=https://msv.sirketiniz.com
FORCE_HTTPS=true

# ── AWS (SES için opsiyonel) ────────────────────
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

# ── Unsubscribe (opsiyonel) ─────────────────────
UNSUB_APP_URL=https://unsub.example.com
UNSUB_API_KEY=
```

### Hosting Modu Cron (cPanel)

```cron
*/5 * * * * cd /home/USER/public_html/mailsender && python3 worker.py >> logs/worker.log 2>&1
```

---

## 📤 Gönderim Modları

```
SEND_MODE=local    →  SSE stream (anlık, VPS/EC2)
SEND_MODE=hosting  →  Kuyruk + worker.py cron (cPanel/Shared Hosting)
```

### SMTP Ayarları

| Alan | Açıklama |
|---|---|
| Host | smtp.gmail.com |
| Port | 587 (TLS) / 465 (SSL) |
| Kullanıcı | ornek@gmail.com |
| Şifre | Uygulama şifresi (app password) |

### AWS SES

Ayarlar → SES sekmesinden Access Key, Secret Key ve Region girin. Test gönderin.

### HTTP API (Brevo, Mailrelay vb.)

Ayarlar → API sekmesinden servis seçin, API anahtarı ve From adresi girin.

---

## ✅ E-posta Doğrulama

### Doğrulama Aşamaları

```
1. Format kontrolü    → RFC 5322 uyumu
2. Yazım düzeltme     → gmial.com → gmail.com
3. Disposable kontrol → 50.000+ geçici domain
4. MX kaydı           → Domain'de mail sunucusu var mı?
5. Catch-all testi    → Sunucu her adrese 250 veriyor mu?
6. SMTP doğrulama     → Posta kutusu gerçekten var mı?
7. Gibberish analizi  → asdfjkl@gmail.com gibi anlamsız adresler
8. Spam keyword       → noreply@, admin@, info@ vb. rol adresleri
```

### `is_valid` Değerleri

| Değer | Anlam | Gönderimde |
|---|---|---|
| `1` | Geçerli | ✅ Gönderilir |
| `-1` | Riskli / Belirsiz | ⚠️ Opsiyonel |
| `0` | Geçersiz | ❌ Atlanır + Suppression'a eklenir |

---

## 📡 SNS Webhook — Bounce & Complaint

### 1. AWS SNS Topic Oluşturun

```
AWS Console → SNS → Topics → Create topic → Standard
Topic adı: ses-notifications
```

### 2. Subscription Ekleyin

```
Protocol: HTTPS
Endpoint: https://yourdomain.com/sns/ses-notification
```

Uygulama `SubscriptionConfirmation` isteğini **otomatik onaylar**.

### 3. SES Configuration Set'e Bağlayın

```
AWS SES → Configuration Sets → Event Destinations
Destination type: SNS
Events: Bounce, Complaint, Delivery
```

### Webhook Davranışı

| Bildirim | İşlem |
|---|---|
| Permanent Bounce | Suppression'a eklenir (`bounce`) |
| Transient Bounce | Sadece loglanır |
| Complaint | Suppression'a eklenir (`complaint`) |
| Delivery | Loglanır |

---

## 🔐 Güvenlik

### Şifreleme

| Veri | Durum |
|---|---|
| DB'deki SMTP şifresi | ✅ Fernet ile şifreli |
| AWS Access / Secret Key | ✅ Fernet ile şifreli |
| Unsubscribe linkleri | ✅ 32-byte token, tek kullanımlık, 7 gün |
| Kullanıcı şifreleri | ✅ bcrypt hash |

### Üretim Kontrol Listesi

- [ ] HTTPS kuruldu (Nginx + Let's Encrypt)
- [ ] `FORCE_HTTPS=true` `.env`'de ayarlı
- [ ] `SECRET_KEY` güçlü ve `.env`'de tanımlı
- [ ] MySQL için ayrı, sınırlı yetkili kullanıcı oluşturuldu
- [ ] 8011 portu dışarıya kapalı (sadece Nginx üzerinden)
- [ ] `.env` dosyası `.gitignore`'a eklendi

### MySQL Güvenli Kullanıcı

```sql
CREATE USER 'mailsender_user'@'127.0.0.1' IDENTIFIED BY 'GUCLU_SIFRE';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON aws_mail_sender_pro_v3.* TO 'mailsender_user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Tam HTTPS yapılandırması için [GUVENLIK_KILAVUZU.md](GUVENLIK_KILAVUZU.md) dosyasına bakın.

---

## 🌐 API Referansı

Tüm endpoint'ler `/api/` prefix'i ile başlar, JSON döner ve giriş gerektirir.

### Gönderim

| Method | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/api/send/single` | Tekli mail gönder |
| `POST` | `/api/send/bulk-excel` | Excel'den toplu gönder (SSE) |
| `POST` | `/api/send/bulk-db` | DB tablosundan toplu gönder (SSE) |

### Göndericiler

| Method | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/senders` | Gönderici listesi |
| `POST` | `/api/senders` | Yeni gönderici ekle |
| `PUT` | `/api/senders/<id>` | Gönderici güncelle |
| `DELETE` | `/api/senders/<id>` | Gönderici sil |
| `POST` | `/api/senders/<id>/test` | Test maili gönder |

### Suppression

| Method | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/suppression` | Liste |
| `POST` | `/api/suppression` | Adres ekle |
| `DELETE` | `/api/suppression/<id>` | Adres sil |
| `POST` | `/api/suppression/purge` | Toplu temizle |
| `POST` | `/api/suppression/batch-check` | CSV'den gelen adresleri sorgula |

### E-posta Doğrulama

| Method | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/api/verify/start` | Doğrulama işi başlat |
| `GET` | `/api/verify/jobs` | İş listesi |
| `GET` | `/api/verify/jobs/<id>/status` | İş durumu |
| `POST` | `/api/verify/jobs/<id>/cancel` | İptal et |

### Bounce Scanner

| Method | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/api/bounce-scanner/scan` | IMAP taraması başlat |
| `POST` | `/api/bounce-scanner/manuel-ekle` | Seçilen kaydı ekle |
| `GET` | `/api/bounce-scanner/history` | Son tarama geçmişi |

### SES / SNS

| Method | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/sns/ses-notification` | SNS webhook |
| `GET` | `/api/ses/reputation` | Tüm göndericilerin itibarı |
| `GET` | `/api/ses/reputation/<id>` | Tek gönderici itibarı |
| `GET` | `/webhook/status` | Webhook URL'lerini göster |

---

## 📁 Dosya Yapısı

```
mailsenderverifier/
│
├── ── Ana Uygulama ──────────────────────────────────────────────────────
├── app.py                      # Flask uygulaması — tüm HTTP route ve API endpoint'leri (4.473 satır)
├── database.py                 # MySQL bağlantı katmanı — tüm DB fonksiyonları (3.765 satır)
├── mailer.py                   # Gönderim motoru — SMTP / SES / HTTP API (1.017 satır)
├── worker.py                   # Cron ile çalışan kuyruk işleyici (hosting modu)
├── security.py                 # Rate limit, CSRF koruması, güvenli tanımlayıcı doğrulama
│
├── ── Bounce & Doğrulama ────────────────────────────────────────────────
├── bounce_scanner_engine.py    # IMAP bounce tarama ve sınıflandırma motoru (778 satır)
├── verifier.py                 # E-posta doğrulama motoru (format/MX/SMTP/catch-all)
├── auto_reverify.py            # Otomatik yeniden doğrulama zamanlayıcı
├── greylist_retry.py           # Greylisting yeniden deneme motoru
├── disposable_updater.py       # 50.000+ geçici domain listesi — 6 saatlik otomatik güncelleme
├── yahoo_aol_check.py          # Yahoo & AOL özel SMTP doğrulama
│
├── ── Analiz & Skor ─────────────────────────────────────────────────────
├── risk_score.py               # E-posta deliverability risk skoru 0-100 (423 satır)
├── reputation_score.py         # Gönderici itibar skoru (SPF/DKIM/bounce/complaint/DNSBL)
├── dnsbl_check.py              # DNSBL / RBL IP kara liste kontrolü
├── spam_trap.py                # Spam tuzağı domain ve adres kontrolü
├── toxic_domain.py             # Zararlı domain kontrolü
│
├── ── İçerik & Yardım ───────────────────────────────────────────────────
├── help_content.py             # Yardım sayfası içerikleri (2.171 satır)
├── version.py                  # Tek kaynaklı versiyon bilgisi
│
├── ── Kurulum & Yönetim ─────────────────────────────────────────────────
├── setup_linux.py              # Tam otomatik Linux kurulum scripti
├── setup_all_env.py            # Temel kurulum: pip, .env, DB, admin
├── reset_password.py           # CLI şifre sıfırlama aracı
├── Dockerfile                  # Docker imajı
├── docker-compose.yml          # Docker Compose yapılandırması
│
├── ── Database Migration ────────────────────────────────────────────────
├── migrate_v2.1.002.sql
├── migrate_api_columns.sql
├── migrate_auto_reverify.sql
├── migrate_greylist_retry.sql
├── migrate_send_log_index.sql
├── migrate_spam_trap.sql
├── migrate_suppression_fix.sql
│
├── ── Şablonlar & Statik ────────────────────────────────────────────────
├── templates/
│   ├── base.html
│   ├── login.html / forgot_password.html / reset_password.html
│   ├── unsubscribe.html
│   └── pages/
│       ├── dashboard.html / bulk-send.html / single-send.html / send-log.html
│       └── settings/
│           ├── smtp.html / ses.html / api.html / rules.html / db.html
│           ├── subscription.html / bounce-scanner.html / verify.html
│           ├── templates.html / theme.html / users.html / audit-log.html / help.html
│
├── static/
│   ├── css/style.css           # 7 tema, CSS değişkenleri
│   └── js/main.js              # Paylaşılan JS fonksiyonları
│
└── ── Yapılandırma ──────────────────────────────────────────────────────
    ├── _env                    # .env şablon dosyası
    ├── requirements.txt
    ├── CHANGELOG.md
    ├── GUVENLIK_KILAVUZU.md
    └── EC2_AUTOSTOP_KURULUM.md
```

---

## 🗃️ Veritabanı Tabloları

| Tablo | Amaç |
|-------|------|
| `users` | Kullanıcı hesapları (bcrypt, rol, tema) |
| `senders` | SMTP / SES / API gönderici hesapları |
| `send_log` | Gönderim geçmişi |
| `suppression_list` | Gönderilmeyecek adresler |
| `bounce_log` | Bounce kayıtları |
| `email_templates` | Konu/mesaj şablonları |
| `send_rules` | Gönderim kuralları |
| `greylist_retry_queue` | Greylisting retry kuyruğu |
| `auto_reverify_schedules` | Otomatik yeniden doğrulama zamanlamaları |
| `spam_trap_domains` | Spam tuzağı domain listesi |
| `audit_log` | Kullanıcı/admin işlem geçmişi |
| `rate_limit_log` | IP bazlı istek sayacı |

---

## 🔄 Değişiklik Günlüğü

Detaylı sürüm geçmişi için [CHANGELOG.md](CHANGELOG.md) dosyasına bakın.

### v2.2.0 (2026-05-10)
- **Bounce Scanner** motoru eklendi — 5 kategori, RFC 3463, Türkçe açıklama (511 EML test, %99 kapsama)
- **Bounce Scanner UI** yenilendi — checkbox seçim, toplu uygula, kategori filtresi, CSV export
- **Suppression → CSV'den Ara** özelliği eklendi
- `base.html` RecursionError düzeltildi

### v2.1.2 (2026-04-22)
- **send-log:** Tarih aralığı filtresi — UTC timezone bilinçli
- **bulk-send:** Bekleme slider default 5000ms → 500ms
- **bulk-send:** Tahmini gönderim süresi hesaplama eklendi
- **worker.py:** Skip edilen adreslerde gereksiz sleep kaldırıldı

### v2.1.1 (2026-04-18)
- AWS SNS webhook entegrasyonu
- `disposable_updater.py` worker entegrasyonu
- Flask port 5000 → 8011

### v2.1.0 (2026-03-13)
- Audit Log sistemi
- Tema hesaba kayıtlı (DB kalıcı)
- SNS Handler Blueprint entegrasyonu

### v2.0.0 (2026-03-10)
- Kullanıcı auth sistemi (admin / editor rolleri)
- HTTP API gönderici modu
- Kuyruk sistemi (hosting modu)
- Unsubscribe sistemi (RFC 8058 one-click)
- EC2 Auto-Stop

### v1.0.0 (2026-01-15)
- İlk sürüm: SMTP + SES, Excel toplu gönderim, SSE canlı izleme

---

## 🤝 Katkı

1. Fork'layın
2. Feature branch oluşturun (`git checkout -b feature/yeni-ozellik`)
3. Commit'leyin (`git commit -m 'feat: yeni özellik'`)
4. Push'layın (`git push origin feature/yeni-ozellik`)
5. Pull Request açın

---

## 📄 Lisans

MIT License — detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

<div align="center">

**MailSenderVerifier** · v2.2.0 · Self-hosted · Türkçe

</div>
