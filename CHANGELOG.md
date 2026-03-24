# MailSender Pro — Değişiklik Günlüğü

Tüm önemli değişiklikler bu dosyada belgelenir.  
Format: [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/) ·  
Versiyonlama: [Semantic Versioning](https://semver.org/lang/tr/)

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
