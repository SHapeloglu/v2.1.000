<div align="center">

# ✉️ MailSender Pro

**Kurumsal toplu e-posta gönderim platformu**

Flask · MySQL · AWS SES · SMTP · REST API

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![AWS SES](https://img.shields.io/badge/AWS-SES-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com/ses)
[![License](https://img.shields.io/badge/Lisans-MIT-green?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Versiyon-v2.1.1-blue?style=flat-square)](CHANGELOG.md)

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
| **SSE Canlı İzleme** | Gönderim sırasında her satır sonucu ekranda anlık görünür |
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
│  │ Sayfa     │  │  REST API    │  │  sns_handler.py   │ │
│  │ Route'ları│  │  Endpoint'leri│  │  (SNS Blueprint)  │ │
│  └───────────┘  └──────────────┘  └───────────────────┘ │
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
├── app.py                    # Flask uygulaması — tüm route'lar
├── worker.py                 # Cron ile çalışan kuyruk işleyici
├── database.py               # MySQL bağlantı ve tüm DB fonksiyonları
├── mailer.py                 # SMTP / SES / API gönderim motoru
├── verifier.py               # E-posta doğrulama motoru
├── security.py               # Rate limit, CSRF, güvenli kimlik kontrolleri
│
├── sns_handler.py            # AWS SNS Blueprint (bounce/complaint webhook)
├── disposable_updater.py     # Disposable domain listesi otomatik güncelleyici
├── reputation_score.py       # SES itibar skoru hesaplama
├── risk_score.py             # E-posta risk skoru
├── spam_trap.py              # Spam tuzağı kontrolü
├── toxic_domain.py           # Zararlı domain kontrolü
├── dnsbl_check.py            # DNSBL / RBL kara liste kontrolü
├── yahoo_aol_check.py        # Yahoo & AOL özel SMTP doğrulama
├── greylist_retry.py         # Greylisting yeniden deneme motoru
├── auto_reverify.py          # Otomatik yeniden doğrulama zamanlayıcı
│
├── help_content.py           # Yardım içerikleri (7z arşivinden okunur)
├── version.py                # Tek kaynaklı versiyon bilgisi
│
├── reset_password.py         # CLI şifre sıfırlama aracı
├── setup_linux.py            # Tam otomatik Linux kurulum scripti
├── setup_all_env.py          # Temel kurulum (pip, .env, DB, admin)
│
├── templates/
│   ├── base.html             # Ana layout (navbar, tema, session)
│   ├── login.html
│   ├── forgot_password.html / reset_password.html
│   ├── unsubscribe.html
│   └── pages/
│       ├── bulk-send.html    # Ana gönderim sayfası
│       ├── send-log.html     # Gönderim geçmişi
│       └── settings/         # Tüm ayar sekmeleri
│           ├── smtp.html / ses.html / api.html
│           ├── users.html / theme.html / verify.html
│           ├── subscription.html / audit-log.html
│           └── help.html
│
├── static/
│   ├── css/style.css
│   └── js/main.js
│
├── _env                      # .env şablonu
├── requirements.txt
├── CHANGELOG.md
├── GUVENLIK_KILAVUZU.md
└── EC2_AUTOSTOP_KURULUM.md
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

### v2.1.1 (2026-04-18)
- `sns_handler.py` Blueprint entegrasyonu — yeni endpoint: `POST /sns/ses-notification`
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

**MailSender Pro** · v2.1.1 · Self-hosted · Türkçe

</div>
