# MailSender Pro — Değişiklik Günlüğü

Tüm önemli değişiklikler bu dosyada belgelenir.  
Format: [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/) ·  
Versiyonlama: [Semantic Versioning](https://semver.org/lang/tr/)

---

## [2.2.0] — 2026-05-10

### Eklendi

- **`bounce_scanner_engine.py`** — Bounce tarama ve sınıflandırma motoru
  - IMAP kutusuna bağlanarak MAILER-DAEMON / postmaster / Mail Delivery System maillerini tarar
  - 5 kategori: `kalici` · `gecici` · `gonderici_sorunu` · `mail_loop` · `internal_domain`
  - `_aciklama_from_body()`: Diagnostic-Code'dan Türkçe açıklama + ikon etiket üretir
  - `MESAJ_PATTERNS`: 50+ pattern, öncelik sıralı, spam/DKIM/relay/kota ayrımı
  - `GONDERICI_SORUNU_PATTERNS`: DKIM/SPF/relay/auth → alıcı geçerli, suppression'a eklenmiyor
  - `GECICI_OVERRIDE_PATTERNS`: Rate limit/kota → geçici (Action:failed olsa bile)
  - `ENHANCED_STATUS` tablosu + `_enhanced_status_etiket()`: RFC 3463 tabanlı ikinci etiket (deneme)
  - 511 gerçek EML üzerinde test edildi — %100 parse, %99 etiket kapsama

- **Bounce Scanner UI** (`bounce-scanner.html`) tamamen yenilendi
  - Checkbox seçim sistemi — tarama biter, sonuçları incelersin, seçersin, uygularsın
  - Hızlı seçim: `☑ Kalıcıları Seç` · `☑ Tümünü Seç` · `☐ Temizle`
  - Alt çubuk: `🚫 Suppression'a Ekle` · `📋 Sadece Bounce Kaydı`
  - Kategori filtre pill'leri, arama, CSV export
  - `Kısa Açıklama` ve `RFC Etiket (deneme)` sütunları yan yana karşılaştırma için
  - Otomatik Suppression anahtarı varsayılan **kapalı**

- **`/api/bounce-scanner/manuel-ekle`** — Seçilen kaydı bounce + isteğe bağlı suppression'a ekler
- **`/api/suppression/batch-check`** — CSV'den gelen adresleri suppression'da toplu sorgula
- **`help_content.py`** — Bounce Scanner bölümü eklendi (8 S/C, kategori açıklamaları dahil)
- **`GUVENLIK_KILAVUZU.md`** — Bounce Scanner güvenlik notları + güncel rate limit tablosu

### Düzeltildi

- **`templates/base.html`** — `{% extends "base.html" %}` döngüsü (RecursionError) giderildi
- **`templates/pages/settings/base.html`** — Ayarlar alt navigasyonu düzeltildi
- **`app.py`** `current_user.role` → `session.get('user_role')` (audit-log sayfası NameError)
- **`bounce_scanner_engine.py`** — `_is_real_bounce()` çoklu Return-Path header sorununu çözdü
- **`bounce_scanner_engine.py`** — `_temizle()` ardışık enhanced status code'ları temizliyor
- **`bounce_scanner_engine.py`** — Spam filtresi raporundaki DKIM ifadesi yanlış `gonderici_sorunu` vermiyordu

### Teknik Notlar

- `parse_bounce()` dönüş dict'ine `etiket` ve `rfc_etiket` alanları eklendi
- Pattern araması hem ham `diag_raw` hem temizlenmiş `diag_text` üzerinde yapılıyor
- Tüm yeni endpoint'ler `@login_required` + `@rate_limit` ile korunuyor

---

## [2.1.1] — 2026-04-18

### Eklendi
- **`sns_handler.py` Blueprint entegrasyonu**: AWS SNS bounce/complaint webhook'u artık ayrı bir Flask Blueprint olarak çalışıyor
  - Yeni endpoint: `POST /sns/ses-notification` (eski: `/api/ses/sns-webhook` devre dışı)
  - `SubscriptionConfirmation` isteği otomatik onaylanıyor (`urllib` ile, harici bağımlılık yok)
  - Bounce/Complaint/Delivery tüm tiplerinde `ses_notification_save()` ile tam DB kaydı
  - `_db()` factory pattern ile proje geri kalanıyla tutarlı DB erişimi
  - `setup_sns_topic()` yardımcı fonksiyonu eklendi (CLI/admin kullanımı için)
- **`disposable_updater.py` worker entegrasyonu**: 50.000+ geçici domain listesi artık otomatik güncelleniyor
  - `worker.py`'de `_run_tasks()` sonuna entegre edildi
  - Her worker çalışmasında kontrol edilir; `MIN_UPDATE_INTERVAL = 6 saat` koruması sayesinde gereksiz HTTP isteği yapılmaz
  - Birincil kaynak başarısız olursa yedek kaynak devreye girer
  - Güncelleme sonucu worker log'una yazılır

### Değiştirildi
- `app.py` başına `from sns_handler import sns_bp` ve `app.register_blueprint(sns_bp)` eklendi
- `app.py` içindeki eski `ses_sns_webhook()` fonksiyonu devre dışı bırakıldı (yorum satırı)
- `webhook_status` endpoint'i güncellendi: `ses_sns` URL'i artık `/sns/ses-notification` döndürüyor
- `worker.py`'e `from disposable_updater import update_disposable_domains` import eklendi

### Teknik Notlar
- Flask port `5000` → `5002` olarak düzeltildi (nginx config, setup_linux.py, güvenlik kılavuzu)
- `sns_handler.py` tamamen yeniden yazıldı: eski `log_send()` bağımlılığı kaldırıldı, `ses_notification_save()` eklendi

---

## [2.1.0] — 2026-03-13

### Eklendi
- **Audit Log sistemi** (`audit_log` tablosu):
  - Kullanıcı ekleme / güncelleme / silme kayıt altına alınır
  - Gönderici (SMTP/SES/API) ekleme / güncelleme / silme kayıt altına alınır
  - Excel yükleme (tablo adı, satır sayısı, action tipi) kayıt altına alınır
  - Toplu gönderim başlangıcı ve bitişi (ok/err/skipped özeti) kayıt altına alınır
- **send_log'a kullanıcı bilgisi**:
  - `sent_by_user_id` ve `sent_by_username` kolonları eklendi
  - Tüm gönderim çağrıları (SMTP, SES, API, tek/toplu) kullanıcıyı kaydeder
- **Send-log sayfasına "Kullanıcı" kolonu** — her satırda gönderimi başlatan kullanıcı adı
- **Tema DB'ye kaydediliyor**: her kullanıcı kendi temasını hesabına kaydedebilir
  - `users.theme` kolonu, `user_set_theme()` fonksiyonu, `POST /api/me/theme` endpoint'i
  - Giriş yapıldığında tema session'a yüklenir, base.html'de FOUC olmadan uygulanır
- **version.py** — tek kaynaklı versiyon yönetimi (MAJOR.MINOR.PATCH)

### Değiştirildi
- `log_send()` imzası genişletildi: `user_id`, `username` parametreleri eklendi
- `get_send_log()` sorgusu `sent_by_username` alanını döndürüyor
- `migrate_db()` yeni kolonlar ve `audit_log` tablosu için migration içeriyor
- `base.html` FOUC scripti: tema artık sunucudan (Jinja2) alınıyor, localStorage yedek
- `theme.html`: açıklama metni güncellendi ("tarayıcıya" → "hesabınıza kaydedilir")

### Teknik Notlar
- `audit()` fonksiyonu hata olsa bile sessizce geçer — gönderim/işlem durmuyor
- Audit kayıtlarında `username` snapshot olarak saklanır: kullanıcı silinse bile log korunur
- `sent_by_username` da snapshot: gönderici hesap silinse send-log'da adı görünmeye devam eder

---

## [2.0.0] — 2026-03-10

### Eklendi
- **Kullanıcı auth sistemi**: `users` tablosu, bcrypt hash, login/logout, session yönetimi
- **Roller**: `admin` (tam yetki) · `editor` (gönderim, gönderici yönetimi)
- **Tema sistemi**: 7 tema (charcoal, black, lavender, mint, sage, coral, teal), FOUC önleme
- **Mail şablon sistemi**: konu ve mesaj şablonları, CRUD endpoint'leri
- **API gönderici modu**: Mailrelay, Brevo, SendGrid, Postmark vb. HTTP API desteği
- **Kuyruk sistemi (hosting modu)**: cPanel cron ile `worker.py`, binary Excel/ek dosya DB'de
- **Unsubscribe sistemi**: tek kullanımlık token, hosting app entegrasyonu, RFC 8058 one-click
- EC2 auto-stop: gönderim bitince instance'ı kapatma seçeneği

### Değiştirildi
- `sender_mode` ENUM: `smtp` | `ses` → `smtp` | `ses` | `api`
- `senders` tablosuna `api_*` kolonları eklendi

---

## [1.0.0] — 2026-01-15

### İlk Sürüm
- SMTP ve AWS SES ile toplu/tekli e-posta gönderimi
- Excel dosyasından e-posta listesi okuma
- MySQL DB'ye Excel aktarımı
- Gönderim logu, suppression listesi, kural sistemi
- SSE (Server-Sent Events) ile canlı ilerleme takibi
- Batch (parçalı) gönderim sistemi
