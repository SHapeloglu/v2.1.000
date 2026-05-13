<div align="center">

# ✉️ MailSender Pro

**Kurumsal toplu e-posta gönderim platformu**

Flask · MySQL · AWS SES · SMTP · REST API

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![AWS SES](https://img.shields.io/badge/AWS-SES-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com/ses)
[![License](https://img.shields.io/badge/Lisans-MIT-green?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Versiyon-v2.2.0-blue?style=flat-square)](CHANGELOG.md)

</div>

---

## 📖 İçindekiler

- [Nedir?](#-nedir)
- [Özellikler](#-özellikler)
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

MailSender Pro, küçük ve orta ölçekli işletmeler için geliştirilmiş, **kendi sunucunuzda çalışan** (self-hosted) kurumsal toplu e-posta gönderim platformudur. Excel listelerinden, veritabanı tablolarından ya da tek tek yazarak mail gönderebilir; gerçek zamanlı ilerleme takibi, bounce/complaint otomasyonu ve gelişmiş liste yönetimi yapabilirsiniz.

Dış bir SaaS servise bağımlı kalmadan kendi altyapınızda tam kontrol size aittir.

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
| **Tarih Aralığı Filtresi** | Gönderim geçmişinde başlangıç/bitiş tarihi seçimi; default dün–bugün, UTC timezone bilinçli |
| **Kuyruk Sistemi** | Hosting ortamında worker.py + cron ile arka plan gönderimi |

### 📡 Gönderici Desteği
- **SMTP** — Gmail, Yandex, şirket sunucusu, herhangi bir SMTP
- **AWS SES** — SDK ile doğrudan entegrasyon, kota takibi
- **HTTP API** — Brevo, Mailrelay, SendGrid, Postmark ve uyumlu her servis

### 🔍 Liste Yönetimi & Doğrulama
- **E-posta Doğrulama** — Format, MX kaydı, SMTP, catch-all, disposable, gibberish kontrolü
- **Otomatik Yeniden Doğrulama** — Belirli aralıklarla listeleri otomatik yeniler
- **Disposable Domain Güncelleme** — 50.000+ geçici domain listesi 6 saatte bir GitHub'dan güncellenir
- **DNSBL / RBL Kontrolü** — IP'nizin kara listede olup olmadığını kontrol eder
- **Suppression Listesi** — Bounce, complaint, unsubscribe, geçersiz — otomatik veya manuel engelleme
- **Domain Bloklama** — Tek komutla tüm domaini engelle
- **Yazım Hatası Düzeltme** — `gmial.com → gmail.com` benzeri otomatik düzeltme

### 📬 Bounce Yönetimi
| Özellik | Açıklama |
|---|---|
| **Bounce Scanner** | IMAP kutusuna bağlanarak MAILER-DAEMON maillerini otomatik tarar |
| **Akıllı Sınıflandırma** | Kalıcı / Geçici / Gönderen Sorunu / Mail Döngüsü kategorileri |
| **Açıklama Üretimi** | Diagnostic-Code'dan Türkçe açıklama + ikon etiket üretir |
| **RFC 3463 Etiket** | Enhanced status code tablosundan otomatik ikinci sınıflandırma |
| **Checkbox Seçim** | Sonuçları gözden geçirip seçerek suppression'a ekle |
| **Toplu Uygula** | Seçilenleri suppression'a veya sadece bounce kaydına ekle |
| **CSV Export** | Tarama sonuçlarını CSV olarak indir |
| **CSV'den Ara** | Suppression listesinde CSV'deki adresleri toplu sorgula |

### ⚙️ Sistem
- **Çoklu Kullanıcı** — Admin / Editor rolleri, bcrypt şifre hash
- **Tema Sistemi** — 7 farklı tema, hesaba kayıtlı, FOUC olmadan yükleme
- **Şablon Yönetimi** — Konu ve mesaj şablonları, Jinja2 değişken desteği
- **Kural Sistemi** — Gönderici + min. bekleme süresi kuralları
- **Greylisting Retry** — Geçici reddedilen mailleri otomatik yeniden dener
- **AWS SNS Webhook** — Bounce/complaint bildirimlerini otomatik yakalar
- **EC2 Auto-Stop** — Gönderim bitince instance'ı otomatik kapatır
- **Audit Log** — Kritik işlemler (kullanıcı, gönderici, gönderim) kayıt altına alınır
- **Şifre Sıfırlama** — Token tabanlı güvenli akış

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
                           │ 127.0.0.1:5002
┌──────────────────────────▼──────────────────────────────┐
│                  app.py  (Flask)                         │
│  ┌───────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ Sayfa     │  │  REST API    │  │  Webhook          │ │
│  │ Route'ları│  │  Endpoint'leri│  │  /webhook/brevo   │ │
│  └───────────┘  └──────────────┘  │  /webhook/ses     │ │
│                                    └───────────────────┘ │
└──────────┬──────────────┬───────────────────────────────┘
           │              │
  ┌────────▼─────┐  ┌─────▼──────────────┐
  │  database.py │  │  mailer.py          │
  │  (MySQL)     │  │  verifier.py        │
  └────────┬─────┘  │  security.py        │
           │        │  spam_trap.py       │
           │        │  toxic_domain.py    │
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

### Gönderim Modları

```
SEND_MODE=local    →  SSE stream (anlık, EC2/VPS)
SEND_MODE=hosting  →  Kuyruk + worker.py cron (cPanel/Shared Hosting)
```

---

## 📦 Kurulum

### Gereksinimler

- Python **3.10+**
- MySQL **8.0+**
- Linux (Ubuntu/Debian önerilir) ya da Windows/macOS (geliştirme)

### Hızlı Kurulum (Linux)

```bash
# 1. Repoyu klonla
git clone https://github.com/kullanici-adi/mailsender-pro.git
cd mailsender-pro

# 2. Tam otomatik kurulum (pip, .env, DB, admin, nginx, systemd)
sudo python3 setup_linux.py

# Sistem servisleri olmadan (geliştirme / cPanel)
python3 setup_linux.py --skip-system
```

### Manuel Kurulum

```bash
# 1. Bağımlılıkları yükle
pip install -r requirements.txt

# 2. .env dosyasını oluştur
cp _env .env
# .env dosyasını düzenle (aşağıya bak)

# 3. Uygulamayı başlat
python app.py
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
DB_NAME=mailsender_pro

# ── Flask Güvenlik ──────────────────────────────
# Üret: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_KEY=

# ── Gönderim Modu ───────────────────────────────
# local    → SSE ile anlık gönderim (EC2 / VPS)
# hosting  → Kuyruk sistemi (cPanel / Shared Hosting)
SEND_MODE=local

# ── AWS (SES için opsiyonel) ────────────────────
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

# ── Unsubscribe Uygulaması (opsiyonel) ──────────
UNSUB_APP_URL=https://unsub.example.com
UNSUB_API_KEY=

# ── HTTPS (nginx arkasında çalışırken) ──────────
APP_BASE_URL=https://yourdomain.com
FORCE_HTTPS=true
```

### Hosting Modu Cron Ayarı (cPanel)

```cron
*/5 * * * * cd /home/USER/public_html/mailsender && python3 worker.py >> logs/worker.log 2>&1
```

---

## 📤 Gönderim Modları

### 1. SMTP

Ayarlar → SMTP sekmesinden gönderici ekleyin:

| Alan | Açıklama |
|---|---|
| Host | smtp.gmail.com |
| Port | 587 (TLS) / 465 (SSL) |
| Kullanıcı | ornek@gmail.com |
| Şifre | Uygulama şifresi (app password) |

### 2. AWS SES

Ayarlar → SES sekmesinden:
- Access Key ve Secret Key girin
- Region seçin
- Konfigürasyon seti (opsiyonel) belirtin
- Test gönderin

### 3. HTTP API (Brevo, Mailrelay, vb.)

Ayarlar → API sekmesinden:
- Servis seçin (Brevo / Mailrelay / Generic)
- API anahtarı girin
- From adresi ve adı belirtin

---

## ✅ E-posta Doğrulama

Gönderim öncesinde listeyi temizlemek için Ayarlar → E-posta Doğrulama bölümünü kullanın.

### Doğrulama Aşamaları

```
1. Format kontrolü    → RFC 5322 uyumu
2. Yazım düzeltme     → gmial.com → gmail.com
3. Disposable kontrol → 50.000+ geçici domain
4. MX kaydı           → Domain'de mail sunucusu var mı?
5. Catch-all testi    → Sunucu her adrese 250 veriyor mu?
6. SMTP doğrulama     → Posta kutusu gerçekten var mı?
7. Gibberish analizi  → asdfjkl@gmail.com gibi anlamsız
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

AWS SES bounce ve complaint bildirimlerini otomatik yakalamak için:

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

Mevcut endpoint URL'nizi görmek için:
```
GET /webhook/status  (giriş gerektirir)
```

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
- [ ] EC2 Security Group'ta 5002 portu dışarıya kapalı
- [ ] `.env` dosyası `.gitignore`'a eklendi

### SECRET_KEY Üretme

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### MySQL Güvenli Kullanıcı

```sql
CREATE USER 'mailsender_user'@'127.0.0.1' IDENTIFIED BY 'GUCLU_SIFRE';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON mailsender_pro.* TO 'mailsender_user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### Nginx + Let's Encrypt

Tam HTTPS yapılandırması için [GUVENLIK_KILAVUZU.md](GUVENLIK_KILAVUZU.md) dosyasına bakın.

---

## 🌐 API Referansı

Tüm API endpoint'leri `/api/` prefix'i ile başlar ve JSON döner. Giriş gerektirir.

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
| `POST` | `/api/bounce-scanner/manuel-ekle` | Seçilen kaydı bounce/suppression'a ekle |
| `POST` | `/api/suppression/batch-check` | CSV'den gelen adresleri suppression'da sorgula |
| `GET` | `/api/bounce-scanner/history` | Son tarama geçmişi |

### SES / SNS

| Method | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/sns/ses-notification` | SNS webhook (auth yok) |
| `GET` | `/api/ses/reputation` | Tüm göndericilerin itibarı |
| `GET` | `/api/ses/reputation/<id>` | Tek gönderici itibarı |
| `GET` | `/webhook/status` | Webhook URL'lerini göster |

---

## 📁 Dosya Yapısı

```
mailsender-pro/
│
├── ── Ana Uygulama ──────────────────────────────────────────────────────
├── app.py                      # Flask uygulaması — tüm HTTP route ve API endpoint'leri
├── database.py                 # MySQL bağlantı katmanı — tüm DB fonksiyonları, migration
├── mailer.py                   # Gönderim motoru — SMTP / SES / HTTP API destekli
├── worker.py                   # Cron ile çalışan kuyruk işleyici (hosting modu)
├── security.py                 # Rate limit, CSRF koruması, güvenli tanımlayıcı doğrulama
│
├── ── Bounce & Doğrulama ────────────────────────────────────────────────
├── bounce_scanner_engine.py    # IMAP bounce tarama ve sınıflandırma motoru
│                               #   → 5 kategori, RFC 3463 tablosu, Türkçe açıklama üretimi
├── verifier.py                 # E-posta doğrulama motoru (format/MX/SMTP/catch-all)
├── auto_reverify.py            # Otomatik yeniden doğrulama zamanlayıcı ve iş kuyruğu
├── greylist_retry.py           # Greylisting yeniden deneme motoru
├── disposable_updater.py       # 50.000+ geçici domain listesi — 6 saatlik otomatik güncelleme
├── yahoo_aol_check.py          # Yahoo & AOL özel SMTP doğrulama (API tabanlı)
│
├── ── Analiz & Skor ─────────────────────────────────────────────────────
├── reputation_score.py         # Gönderici itibar skoru (SPF/DKIM/bounce/complaint/DNSBL)
├── risk_score.py               # E-posta teslimat risk skoru (0–100)
├── dnsbl_check.py              # DNSBL / RBL IP kara liste kontrolü (Spamhaus, Barracuda vb.)
├── spam_trap.py                # Spam tuzağı domain ve adres kontrolü
├── toxic_domain.py             # Zararlı / kötü şöhretli domain kontrolü
│
├── ── İçerik & Yardım ───────────────────────────────────────────────────
├── help_content.py             # Ayarlar > Yardım sayfasının tüm içeriği (GUIDE + HELP)
├── version.py                  # Tek kaynaklı versiyon bilgisi (VERSION, VERSION_SHORT)
│
├── ── Kurulum & Yönetim ─────────────────────────────────────────────────
├── setup_linux.py              # Tam otomatik Linux kurulum scripti (pip/nginx/systemd)
├── setup_all_env.py            # Temel kurulum: pip, .env oluşturma, DB, admin
├── reset_password.py           # CLI şifre sıfırlama aracı (UI olmadan acil erişim)
│
├── ── Test Dosyaları ────────────────────────────────────────────────────
├── test_auto_reverify.py       # auto_reverify modülü unit testleri
├── test_greylist_retry.py      # greylist_retry modülü unit testleri
├── test_spam_trap.py           # spam_trap modülü unit testleri
├── test_did_you_mean.py        # Yazım düzeltme (did_you_mean) fonksiyon testleri
│
├── ── Database Migration ────────────────────────────────────────────────
├── migrate_v2.1.002.sql        # v2.1.002 şema güncellemesi
├── migrate_api_columns.sql     # API gönderici sütunları
├── migrate_auto_reverify.sql   # Otomatik yeniden doğrulama tabloları
├── migrate_greylist_retry.sql  # Greylisting retry tabloları
├── migrate_send_log_index.sql  # Gönderim logu performans indeksleri
├── migrate_spam_trap.sql       # Spam tuzağı tabloları
├── migrate_suppression_fix.sql # Suppression listesi düzeltmeleri
│
├── ── Şablonlar ─────────────────────────────────────────────────────────
├── templates/
│   ├── base.html               # Ana layout — sidebar, navbar, tema, session
│   ├── login.html              # Giriş sayfası
│   ├── forgot_password.html    # Şifre sıfırlama isteği formu
│   ├── reset_password.html     # Yeni şifre belirleme formu
│   ├── unsubscribe.html        # Abonelik iptali onay sayfası (auth gerektirmez)
│   └── pages/
│       ├── dashboard.html      # Ana ekran — günlük istatistik, gönderici durumu, uyarılar
│       ├── bulk-send.html      # Toplu gönderim sayfası (Excel / DB / Yapıştır)
│       ├── send-log.html       # Gönderim geçmişi, filtreler, retry
│       ├── single-send.html    # Tek adrese anlık mail gönderme
│       └── settings/
│           ├── base.html       # Ayarlar alt navigasyon layout'u
│           ├── smtp.html       # SMTP gönderici yönetimi + DNSBL + itibar skoru
│           ├── ses.html        # AWS SES gönderici yönetimi
│           ├── api.html        # HTTP API gönderici yönetimi (Brevo, Mailrelay vb.)
│           ├── rules.html      # Gönderim kuralları (kullanıcı/gönderici bazlı)
│           ├── db.html         # Veritabanı bağlantı ayarları
│           ├── subscription.html # Suppression listesi ve abonelik yönetimi
│           ├── bounce-scanner.html # Bounce tarayıcı UI — checkbox seçim, toplu uygula
│           ├── verify.html     # E-posta listesi doğrulama
│           ├── templates.html  # Konu ve mesaj şablonları
│           ├── theme.html      # Arayüz teması seçimi (7 tema)
│           ├── users.html      # Kullanıcı yönetimi (admin only)
│           ├── audit-log.html  # Aktivite/denetim kayıtları (admin only)
│           └── help.html       # Tam kullanım kılavuzu
│
├── ── Statik Dosyalar ───────────────────────────────────────────────────
├── static/
│   ├── css/style.css           # Tüm arayüz stilleri — 7 tema, CSS değişkenleri
│   └── js/main.js              # Paylaşılan JS fonksiyonları (esc, showAlert, toggle vb.)
│
├── ── Yapılandırma ──────────────────────────────────────────────────────
├── _env                        # .env şablon dosyası (kopyalayıp düzenleyin)
├── requirements.txt            # Python bağımlılıkları (pip install -r)
├── CHANGELOG.md                # Sürüm geçmişi
├── GUVENLIK_KILAVUZU.md        # Güvenlik, HTTPS, rate limit kılavuzu
└── EC2_AUTOSTOP_KURULUM.md     # AWS EC2 otomatik kapatma kurulum rehberi
```

---

## 🗃️ Veritabanı Migration

Uygulama ilk çalıştığında eksik tabloları ve kolonları **otomatik oluşturur** (`auto_migrate`). Manuel migration gerekiyorsa:

```bash
# v2.0 → v2.1 örnek
mysql -u root -p mailsender_pro < migrate_v2.1.002.sql
```

---

## 🔄 Değişiklik Günlüğü

Detaylı sürüm geçmişi için [CHANGELOG.md](CHANGELOG.md) dosyasına bakın.

### v2.2.0 (2026-05-10)
- **Bounce Scanner** motoru eklendi (`bounce_scanner_engine.py`)
  - IMAP kutusundan MAILER-DAEMON maillerini otomatik tarar
  - 5 kategori: Kalıcı / Geçici / Gönderen Sorunu / Mail Döngüsü / Internal Domain
  - Diagnostic-Code'dan Türkçe açıklama + ikon etiket üretir (511 EML test, %99 kapsama)
  - RFC 3463 enhanced status code tablosu — ikinci sınıflandırma sütunu (deneme)
- **Bounce Scanner UI** tamamen yenilendi
  - Checkbox seçim sistemi — sonuçları gözden geçirip seçerek uygulama
  - Hızlı seçim: Kalıcıları Seç / Tümünü Seç / Temizle
  - Alt bar: Seçilenleri Suppression'a Ekle / Sadece Bounce Kaydı
  - Kategori filtresi, arama, CSV export
- **Suppression → CSV'den Ara** özelliği eklendi (`/api/suppression/batch-check`)
- **`base.html`** RecursionError düzeltildi (kendini extend eden döngü giderildi)
- **`settings/audit-log`** `current_user.role` → `session.get('user_role')` düzeltmesi
- **`help_content.py`** Bounce Scanner bölümü eklendi (kategori açıklamaları dahil)

### v2.1.2 (2026-04-22)
- **send-log:** Tarih aralığı filtresi eklendi — default dün/bugün, UTC timezone bilinçli (`CONVERT_TZ`)
- **send-log:** Tarih filtresi sayfalama ve CSV export'a da uygulandı
- **bulk-send:** Gönderimler arası bekleme slider default `5000ms` → `500ms`
- **bulk-send:** İlerleme polling aralığı `5000ms` → `2000ms`
- **bulk-send:** Tahmini gönderim süresi hesaplama — alıcı sayısı × delay, slider hareketi ve liste yüklenince güncellenir
- **bulk-send:** Gönderim Durumu başlığına canlı adres sayısı ve kalan süre tahmini eklendi
- **worker.py:** Skip edilen adreslerde (`is_valid`, MX, disposable, spam trap vb.) gereksiz `time.sleep` kaldırıldı — delay yalnızca gerçek gönderim sonrası uygulanır

### v2.1.1 (2026-04-18)
- AWS SNS webhook entegrasyonu — yeni endpoint: `POST /webhook/ses`
- `disposable_updater.py` worker entegrasyonu — 6 saatlik throttle ile otomatik güncelleme
- Flask port `5000` → `5002` düzeltmesi (nginx, setup_linux.py, güvenlik kılavuzu)
- `sns_handler.py` yeniden yazıldı: `_db()` factory pattern, `ses_notification_save()` desteği

### v2.1.0 (2026-03-13)
- Audit Log sistemi eklendi
- Gönderim loguna kullanıcı bilgisi eklendi
- Tema hesaba kaydediliyor (DB kalıcı)
- SNS Handler Blueprint entegrasyonu
- Disposable domain otomatik güncelleme (worker entegrasyonu)

### v2.0.0 (2026-03-10)
- Kullanıcı auth sistemi (admin / editor rolleri)
- HTTP API gönderici modu (Brevo, Mailrelay, vb.)
- Kuyruk sistemi (hosting modu / cPanel)
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

**MailSender Pro** · v2.2.0 · Self-hosted · Türkçe

</div>
