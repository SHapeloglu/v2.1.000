"""
help_content.py — MailSender Pro Yardım İçerikleri
===================================================
Tüm sayfa ipuçları ve kılavuz içerikleri tek kaynakta tutulur.
Sayfa bazlı kısa ipuçları (HELP) ve tam kılavuz bölümleri (GUIDE) burada tanımlıdır.

Yapı:
  HELP  — Her sayfanın sağ üst köşesindeki ? butonunda görünen kısa ipuçları
  GUIDE — Ayarlar > Yardım sayfasındaki tam, aranabilir kullanım kılavuzu
"""

# ══════════════════════════════════════════════════════════════════
# SAYFA BAZLI KISA İPUÇLARI
# ══════════════════════════════════════════════════════════════════

HELP: dict = {

    "bulk_send_page": {
        "title": "📋 Toplu Gönderim",
        "intro": "Excel, veritabanı tablosu veya yapıştırılmış metin listesinden yüzlerce kişiye aynı anda kişiselleştirilmiş mail gönderir.",
        "steps": [
            ("1. Kaynak seçin", "🗄 Veritabanı Tablosu: DB'ye aktarılmış listenizi seçin · 📊 Excel Dosyası: .xlsx yükleyin · 📋 Metin Yapıştır: e-postaları satır satır yapıştırın."),
            ("2. Gönderici", "Ayarlarda tanımladığınız SMTP, SES veya API gönderici seçin."),
            ("3. Konu & İçerik", "{{Ad}}, {{Soyad}} gibi değişkenler otomatik doldurulur. Sütun adlarını süslü parantez içinde yazın. Şablon seç butonuyla kayıtlı şablonları kullanın."),
            ("4. MX Kontrolü", "🔍 MX Kaydı Kontrolü açıksa, her adresin domain'i DNS'ten sorgulanır. Geçersiz domainler gönderilmeden atlanır — bounce oranını %60-70 düşürür."),
            ("5. Sadece Doğrulanmış", "Liste Temizleme yapılmış tablolarda ✅ toggle görünür. Açıksa yalnızca is_valid=1 olan adresler gönderilir."),
            ("6. Kurallar", "Aynı kişiye çok sık gönderimi önlemek için kural seçebilirsiniz (isteğe bağlı)."),
            ("7. Batch (Parti)", "Büyük listeleri parçalara bölün ve her parti arasında bekleme süresi koyun — Brevo/SES hesaplarınızı korur."),
            ("8. Başlat", "cPanel modu: iş kuyruğa girer, worker.py gönderir. Yerel mod: anlık başlar, canlı takip edilir."),
        ],
        "tip": "💡 İlk gönderimde küçük bir test listesiyle deneyin ve bounce oranını kontrol edin.",
    },

    "single_send_page": {
        "title": "✉ Tek Mail Gönder",
        "intro": "Belirli bir kişiye anında tek mail gönderir. Test, acil mesaj ve SMTP/SES bağlantısı doğrulamak için idealdir.",
        "steps": [
            ("Alıcı", "Geçerli bir e-posta adresi girin."),
            ("Gönderici", "Ayarlarda tanımlı herhangi bir göndericiyi seçin."),
            ("Konu & İçerik", "HTML veya düz metin kullanabilirsiniz. 📌 Şablon Seç butonuyla kayıtlı şablonları kullanın."),
            ("Şablon Kaydet", "Yazdığınız konu veya mesajı 💾 butonuyla şablon olarak kaydedebilirsiniz."),
            ("Gönder", "Mail anında iletilir, Gönderim Geçmişi'ne kaydedilir."),
        ],
        "tip": "💡 SMTP/SES bağlantısını test etmek için önce buradan kendinize bir mail gönderin.",
    },

    "send_log_page": {
        "title": "📊 Gönderim Geçmişi",
        "intro": "Sisteme geçen tüm gönderimler burada kayıtlıdır. Filtreleme, arama ve CSV dışa aktarma yapabilirsiniz.",
        "steps": [
            ("Durum renkleri", "✓ Yeşil = gönderildi · ✗ Kırmızı = başarısız · ⏭ Gri = atlandı (suppression/kural)"),
            ("Hata detayı", "Hatalı satırda hata mesajı görünür — SMTP reddi, SES hatası, geçersiz adres gibi bilgiler."),
            ("Atlanma sebebi", "Suppression listesinde olan, kural nedeniyle erken çağrılan veya MX kaydı bulunmayan adresler atlanır."),
            ("Filtreleme", "Tarih aralığı, gönderici, durum ve e-posta adresi ile filtreleyebilirsiniz."),
            ("Dışa aktar", "Tablodaki verileri CSV olarak indirebilirsiniz."),
            ("📈 Genel Özet", "Sayfanın en üstündeki özet kart Bugün / Bu Ay / Tüm Zamanlar gönderim sayılarını ve başarı oranını gösterir. Oran rengi: yeşil ≥%95, sarı ≥%80, kırmızı <%80."),
        ],
        "tip": "💡 Yüksek hata oranı görüyorsanız Liste Temizleme ile listeyi doğrulayın.",
    },

    "settings_smtp": {
        "title": "📡 SMTP Gönderici",
        "intro": "Klasik e-posta sunucusu üzerinden gönderim yapar. Gmail, Outlook, cPanel Mail ve özel sunucular desteklenir.",
        "steps": [
            ("Host & Port", "Gmail: smtp.gmail.com:587 · Outlook: smtp-mail.outlook.com:587 · TLS için 587, SSL için 465."),
            ("Kullanıcı adı", "Genellikle tam e-posta adresiniz (ornek@gmail.com)."),
            ("Şifre", "Gmail kullanıyorsanız 'Uygulama Şifresi' oluşturun (2FA açık hesaplarda zorunlu)."),
            ("Gönderen adı & adresi", "Alıcıların 'Kimden' alanında göreceği isim ve adres."),
            ("Test Et", "Kaydetmeden önce mutlaka bağlantıyı test edin — gerçek bir test maili gönderir."),
        ],
        "tip": "💡 Gmail: Hesap > Güvenlik > 2 adımlı doğrulama açık > Uygulama şifresi oluştur.",
    },

    "settings_ses": {
        "title": "☁ AWS SES Gönderici",
        "intro": "Amazon Simple Email Service ile yüksek hacimli gönderim yapar. Sandbox modunda yalnızca doğrulanmış adresler alabilir.",
        "steps": [
            ("Access Key & Secret", "AWS IAM > Kullanıcı > Erişim Anahtarı oluştur. ses:SendEmail, ses:GetSendQuota izinleri gerekir."),
            ("Region", "SES'i aktifleştirdiğiniz AWS bölgesi (örn: eu-west-1, us-east-1)."),
            ("Sandbox modu", "Yeni hesaplar sandbox modunda açılır — sadece doğrulanmış adreslere gönderebilirsiniz. AWS'den production erişimi talep edin."),
            ("From adresi", "SES konsolunda doğrulanmış (verified) bir adres veya domain olmalıdır."),
            ("Kota Sorgula", "📊 butonuyla günlük limit ve kalan hakkı anlık olarak sorgulayabilirsiniz."),
        ],
        "tip": "💡 SES limitleri: sandbox 200/gün, production için AWS'den talep edin. SPF+DKIM+DMARC kurulumu zorunludur.",
    },

    "settings_api_senders": {
        "title": "🔌 API Gönderici",
        "intro": "Brevo, Mailgun, SendGrid gibi HTTP API ile gönderim yapan servisleri entegre eder. Brevo için hazır şablon mevcuttur.",
        "steps": [
            ("Host & Endpoint", "Örn: Brevo için Host: api.brevo.com · Endpoint: /v3/smtp/email"),
            ("Auth tipi", "api-key (Brevo), Bearer (Mailgun), X-AUTH-TOKEN (Mailrelay). Token şifreli saklanır."),
            ("Payload şablonu", "JSON yapısında RECIPIENT_EMAIL, SUBJECT_TEXT, HTML_CONTENT gibi yer tutucuları kullanın."),
            ("Hazır şablonlar", "💙 Brevo ve 📬 Mailrelay butonlarıyla alanlar otomatik dolar."),
            ("Brevo Kota", "📊 butonuyla hesabın kalan e-posta kredisini ve plan bilgisini sorgulayin."),
        ],
        "tip": "💡 Brevo'da günlük 300 mail sınırı var (ücretsiz). Isınma için 50/gün ile başlayın.",
    },

    "settings_rules": {
        "title": "🛡 Gönderim Kuralları",
        "intro": "Aynı kişiye çok sık mail gönderilmesini önler. Spam şikayeti ve unsubscribe oranını düşürür.",
        "steps": [
            ("Min. aralık (saat)", "Aynı alıcıya en az kaç saat arayla mail gönderileceğini belirler. Örn: 168 = haftada en fazla 1 kez."),
            ("Kural seçimi", "Toplu gönderimde kural seçerseniz, kuralı ihlal eden adresler otomatik atlanır."),
            ("Atlanma", "Kuralı ihlal eden adresler 'skipped' olarak loglanır — suppression'a eklenmez."),
        ],
        "tip": "💡 Cold email kampanyaları için 720 saat (30 gün) kuralı önerilir.",
    },

    "settings_db": {
        "title": "🗄 Veritabanı",
        "intro": "MySQL bağlantı bilgilerini, tablo yönetimini ve Excel içe aktarmayı buradan yaparsınız.",
        "steps": [
            ("Bağlantı bilgileri", "Host, port, kullanıcı adı, şifre ve DB adı .env dosyasına kaydedilir."),
            ("Bağlantıyı test et", "Kaydetmeden önce test ederek bağlantının çalıştığını doğrulayın."),
            ("Tabloları oluştur", "İlk kurulumda tüm sistem tablolarını (send_log, suppression_list vb.) oluşturur."),
            ("Excel içe aktarma", "Excel dosyasını seçerek yeni tablo olarak DB'ye ekleyin. Sütun adları otomatik algılanır."),
            ("Tablo silme", "Sistem tabloları (send_log, suppression_list vb.) silinemez — sadece kendi oluşturduklarınız silinebilir."),
        ],
        "tip": "💡 cPanel'de DB host genellikle 'localhost'. DB kullanıcısına tüm yetkiler verilmiş olmalıdır.",
    },

    "settings_subscription": {
        "title": "📧 Abonelik & Suppression",
        "intro": "E-posta suppression listesini ve domain bloklama listesini yönetirsiniz. Suppression'daki adreslere hiç gönderim yapılmaz.",
        "steps": [
            ("E-posta Manuel Ekle", "Tek adres veya virgülle/satır satır birden fazla adres girin. Sebep seçerek (bounce, şikayet vb.) listeye ekleyin."),
            ("Domain Bloklama", "Bir domain eklendiğinde o domain'e ait TÜM adreslere gönderim engellenir. Örn: rakip.com → *@rakip.com gönderilmez."),
            ("Webhook Otomasyonu", "Brevo/SES webhook'larını kurarak bounce/şikayet/unsubscribe olayları otomatik suppression'a eklenir."),
            ("Unsubscribe Uygulaması", "Mail altındaki çıkma linkini harici hosting'de çalıştırmak için URL ve API anahtarı girin."),
            ("Toplu Temizlik", "Belirli tablodan veya tüm listelerden suppression'daki adresleri silmek için 'Listelerden Temizle' bölümünü kullanın."),
            ("Sebeplere göre aksiyon", "bounce → silme, korur · complaint → asla silme, yasal risk · unsubscribe → silme, GDPR · invalid → silme, email_verify ekledi · manual → kontrol et"),
        ],
        "tip": "💡 Detaylı sebep rehberi için Yardım > Suppression ve Domain Bloklama > 'Sebeplere göre nasıl aksiyon almalıyım?' sorusuna bakın.",
    },

    "settings_templates": {
        "title": "📝 Şablonlar",
        "intro": "Sık kullandığınız konu başlıkları ve mail içeriklerini şablon olarak kaydedin. Toplu ve tek gönderimde kullanabilirsiniz.",
        "steps": [
            ("Yeni şablon", "Konu (subject) veya gövde (body) şablonu oluşturun. {{değişken}} kullanabilirsiniz."),
            ("Kullanım", "Gönderim sayfalarındaki '📌 Konu Şablonu Seç' veya '📄 Mesaj Şablonu Seç' butonlarıyla seçin."),
            ("Arama", "Modal'da arama kutusuna yazarak şablon adı veya içeriğinde arayabilirsiniz."),
            ("Kaydet", "Gönderim sayfasındaki '💾 Konuyu/Mesajı Şablon Olarak Kaydet' ile mevcut içeriği şablon yapabilirsiniz."),
        ],
        "tip": "💡 Şablonlarda {{Ad}}, {{Firma}} gibi değişkenler listenizin sütun adlarıyla eşleşmelidir.",
    },

    "settings_theme": {
        "title": "🎨 Tema",
        "intro": "Arayüz renk temasını kişisel tercihlerinize göre ayarlayın. Seçim hesabınıza kaydedilir.",
        "steps": [
            ("Tema seçimi", "Charcoal (koyu), Arctic (açık) ve diğer temalar arasından seçin — önizleme anlık güncellenir."),
            ("Kaydetme", "Kaydet'e basmadan seçtiğiniz tema sadece önizlemedir. Kayıt sonrası diğer cihazlarda da geçerli olur."),
        ],
        "tip": "💡 Uzun oturumlar için Charcoal (koyu) teması göz yorgunluğunu azaltır.",
    },

    "settings_verify": {
        "title": "✅ Liste Temizleme",
        "intro": "Mail listenizindeki geçersiz, sahte ve riskli adresleri toplu olarak tespit eder. İş arka planda çalışır, sekmeyi kapatabilirsiniz.",
        "steps": [
            ("Kaynak tablo", "Önce Veritabanı sayfasından Excel'i içe aktarın, ardından burada tabloyu seçin."),
            ("E-posta kolonu", "Tabloda hangi sütunun e-posta adresi içerdiğini belirtin — genellikle otomatik algılanır."),
            ("Mod seçimi", "⚡ Format: anlık regex kontrolü · 🔍 MX: DNS MX sorgusu, önerilen · 🔬 SMTP: gerçek bağlantı testi, yavaş"),
            ("SMTP Muaf Domainler", "Gmail, Yahoo, Outlook gibi büyük servisler SMTP'yi bloklar — otomatik muaf listesine dahildir."),
            ("Sonuçlar", "Tabloya is_valid kolonu eklenir: 1=geçerli, 0=geçersiz (→ suppression), -1=riskli/rol adresi"),
            ("Toplu Gönderimdeki kullanımı", "Toplu Gönderim > DB kaynağı > tabloda is_valid varsa '✅ Sadece Doğrulanmış' toggle'ı belirir."),
            ("Sonuç aksiyonları", "✓ Geçerli → gönder · ✗ Geçersiz → sistem suppression'a ekledi, bir şey yapma · ⚠ Riskli → gönderebilirsin ama izle · 🚫 Supp → sistem halletti"),
            ("📤 Temiz Tablo Oluştur", "Tamamlanan bir işin yanındaki '📤 Temiz Tablo' butonuyla is_valid=1 adreslerden yeni bir tablo oluşturun. Riskli adresleri dahil etme seçeneği de var."),
            ("🔄 Takılı İşleri Temizle", "İş 'Çalışıyor' durumunda takılıp kaldıysa bu butonla temizleyin. 10 dakikadan uzun süren 'running' işleri otomatik iptal eder."),
        ],
        "tip": "💡 Detaylı aksiyon rehberi için Yardım > Liste Temizleme bölümündeki 'Doğrulama bitti — ne yapmalıyım?' sorusuna bakın.",
    },

    "settings_users": {
        "title": "👥 Kullanıcılar",
        "intro": "Sisteme erişebilecek kullanıcıları yönetin. Yalnızca admin rolündeki kullanıcılar bu sayfayı görebilir.",
        "steps": [
            ("Roller", "Admin: her şeye erişir, kullanıcı yönetir, ayarları değiştirir. Editör: gönderim yapabilir, ayarlara giremez."),
            ("Yeni kullanıcı", "Kullanıcı adı, e-posta ve şifre ile hesap oluşturun. Rol atamayı unutmayın."),
            ("Şifre değiştirme", "Her kullanıcı kendi şifresini değiştirebilir. Admin herkesin şifresini sıfırlayabilir."),
            ("Kullanıcı silme", "Silinen kullanıcının gönderim geçmişi ve logları korunur, sadece giriş yapamaz."),
        ],
        "tip": "💡 İlk kurulumda varsayılan admin/admin123 şifresini hemen değiştirin.",
    },
}


# ══════════════════════════════════════════════════════════════════
# TAM KULLANIM KILAVUZU — Aranabilir bölümler
# ══════════════════════════════════════════════════════════════════

GUIDE: list = [
    {
        "id": "kurulum",
        "icon": "🚀",
        "title": "Kurulum ve İlk Başlangıç",
        "questions": [
            {
                "q": "Sistem gereksinimleri nelerdir?",
                "a": (
                    "Sunucu tarafı:\n"
                    "• Python 3.10 veya üzeri (3.11 önerilir)\n"
                    "• MySQL 5.7+ veya 8.0 (MariaDB 10.5+ da çalışır)\n"
                    "• pip paketleri: requirements.txt içindeki tümü\n\n"
                    "Barındırma seçenekleri:\n"
                    "• Yerel geliştirme: python app.py ile çalışır\n"
                    "• cPanel/Hosting: Passenger veya cron job desteği gerekir\n"
                    "• VPS/EC2: doğrudan python app.py veya gunicorn ile\n\n"
                    "Tarayıcı: Chrome, Firefox, Edge (modern sürüm). IE desteklenmez."
                ),
            },
            {
                "q": "İlk kurulumda adım adım ne yapmalıyım?",
                "a": (
                    "1) .env dosyasını oluşturun:\n"
                    "   cp .env.example .env\n"
                    "   nano .env  → DB bilgilerini ve SECRET_KEY'i doldurun\n\n"
                    "2) Paketleri kurun:\n"
                    "   pip install -r requirements.txt\n\n"
                    "3) Uygulamayı başlatın:\n"
                    "   python app.py\n"
                    "   → Tablolar otomatik oluşturulur\n\n"
                    "4) Tarayıcıdan açın: http://localhost:5000\n\n"
                    "5) Giriş yapın: admin / admin123\n"
                    "   ⚠️ Şifreyi hemen değiştirin!\n\n"
                    "6) Ayarlar > Veritabanı > Bağlantıyı Test Et ile doğrulayın\n\n"
                    "7) Ayarlar > SMTP/SES/API'den gönderici ekleyin\n\n"
                    "8) Tek Mail Gönder sayfasından test gönderin"
                ),
            },
            {
                "q": ".env dosyasına hangi değişkenleri yazmalıyım?",
                "a": (
                    "Zorunlu değişkenler:\n"
                    "  DB_HOST=localhost\n"
                    "  DB_PORT=3306\n"
                    "  DB_USER=kullanici_adi\n"
                    "  DB_PASSWORD=sifre\n"
                    "  DB_NAME=mailsender_db\n"
                    "  SECRET_KEY=cok-uzun-rastgele-string-buraya\n\n"
                    "İsteğe bağlı:\n"
                    "  SEND_MODE=local           # veya: hosting\n"
                    "  UNSUB_APP_URL=https://...  # Harici unsub uygulaması\n"
                    "  UNSUB_API_KEY=...          # Unsub API anahtarı\n"
                    "  BREVO_WEBHOOK_SECRET=...   # Brevo webhook doğrulama\n"
                    "  APP_BASE_URL=https://...   # Unsubscribe linkleri için\n\n"
                    "SECRET_KEY için rastgele string üretmek:\n"
                    "  python -c \"import secrets; print(secrets.token_hex(32))\""
                ),
            },
            {
                "q": "cPanel'de cron job nasıl kurulur?",
                "a": (
                    "cPanel > Cron Jobs bölümüne gidin.\n\n"
                    "Komut:\n"
                    "  */5 * * * * cd /home/KULLANICI/public_html/mailsender "
                    "&& python3 worker.py >> logs/worker.log 2>&1\n\n"
                    "Bu komut her 5 dakikada bir:\n"
                    "• Bekleyen toplu gönderim görevlerini işler\n"
                    "• Bekleyen Liste Temizleme işlerini çalıştırır\n\n"
                    "Python3 yolu doğru değilse:\n"
                    "  /usr/bin/python3 veya /usr/local/bin/python3 deneyin\n\n"
                    "Log dosyasını kontrol etmek için:\n"
                    "  tail -f logs/worker.log"
                ),
            },
            {
                "q": "SEND_MODE=local ve hosting arasındaki fark nedir?",
                "a": (
                    "local modu (varsayılan):\n"
                    "• Toplu Gönderim düğmesine basınca gönderim ANINDA başlar\n"
                    "• Tarayıcıda canlı ilerleme takibi yapabilirsiniz (SSE)\n"
                    "• Sayfayı kapatırsanız gönderim durur\n"
                    "• Yerel geliştirme ve VPS için idealdir\n\n"
                    "hosting modu:\n"
                    "• Gönderim kuyruğa alınır, worker.py işler\n"
                    "• Sayfayı kapatabilirsiniz, gönderim arka planda devam eder\n"
                    "• cPanel'de uzun HTTP bağlantıları kesildiğinden bu mod gereklidir\n"
                    "• Her 5 dakikada cron çalışır ve kuyruktaki görevi işler"
                ),
            },
            {
                "q": "Şifremi unuttum, ne yapabilirim?",
                "a": (
                    "Yöntem 1 — Web formu:\n"
                    "• Login sayfasında 'Şifremi unuttum →' linkine tıklayın\n"
                    "• Kullanıcı adınızı girin — kayıtlı e-postanıza link gönderilir\n"
                    "• Link 1 saat geçerlidir\n"
                    "• Not: Sistemde geçerli bir gönderici tanımlı olmalıdır\n\n"
                    "Yöntem 2 — Komut satırı (sunucu erişiminiz varsa):\n"
                    "  python reset_password.py admin yenisifre123\n"
                    "• Mail gerektirmez, doğrudan DB'yi günceller\n"
                    "• Tüm kullanıcılar için kullanılabilir"
                ),
            },
        ],
    },
    {
        "id": "gonderici",
        "icon": "📡",
        "title": "Gönderici Yapılandırması",
        "questions": [
            {
                "q": "Gmail ile SMTP kurulumu nasıl yapılır?",
                "a": (
                    "1) Gmail hesabında 2 adımlı doğrulamayı açın:\n"
                    "   myaccount.google.com > Güvenlik > 2 Adımlı Doğrulama\n\n"
                    "2) Uygulama şifresi oluşturun:\n"
                    "   myaccount.google.com > Güvenlik > Uygulama Şifreleri\n"
                    "   'Uygulama Seçin' > Diğer > isim verin > Oluştur\n"
                    "   16 karakterli şifreyi kopyalayın\n\n"
                    "3) SMTP ayarları:\n"
                    "   Host: smtp.gmail.com\n"
                    "   Port: 587\n"
                    "   Kullanıcı: ornek@gmail.com\n"
                    "   Şifre: oluşturulan 16 karakterli uygulama şifresi\n"
                    "   SSL/TLS: TLS (STARTTLS)"
                ),
            },
            {
                "q": "AWS SES sandbox'tan üretim moduna nasıl çıkılır?",
                "a": (
                    "1) AWS Console > SES > Account dashboard\n"
                    "2) 'Request production access' butonuna tıklayın\n"
                    "3) Formu doldurun:\n"
                    "   • Kullanım amacı (bülten, transactional vb.)\n"
                    "   • Günlük tahmini gönderim sayısı\n"
                    "   • Bounce/complaint yönetimi planınız\n"
                    "   • Unsubscribe mekanizmanız\n"
                    "4) 1-3 iş günü içinde onaylanır\n\n"
                    "SPF, DKIM ve DMARC kayıtlarının domain'inizde kurulu olması "
                    "onay sürecini hızlandırır ve zorunludur."
                ),
            },
            {
                "q": "Brevo (eski adıyla Sendinblue) ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Brevo panelinde: Settings > SMTP & API > API Keys\n"
                    "2) 'Generate a new API key' ile anahtar oluşturun\n\n"
                    "3) Sistem'de: Ayarlar > API Göndericiler > 💙 Brevo butonuna basın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host: api.brevo.com\n"
                    "   Endpoint: /v3/smtp/email\n"
                    "   Auth tipi: api-key\n\n"
                    "4) Token alanına Brevo API anahtarınızı yapıştırın\n\n"
                    "5) 📊 Kota Sorgula butonu ile hesap limitlerini kontrol edin\n\n"
                    "Günlük limit (ücretsiz plan): 300 mail/gün\n"
                    "Isınma için: ilk hafta 50/gün, ikinci hafta 150/gün"
                ),
            },
            {
                "q": "Birden fazla gönderici ekleyebilir miyim? Neden gerekir?",
                "a": (
                    "Evet, sınırsız gönderici eklenebilir.\n\n"
                    "Neden birden fazla gönderici kullanılır:\n"
                    "• Farklı domainlerden gönderim yaparak IP/domain dağıtımı\n"
                    "• Bir gönderici limit aşarsa diğeriyle devam etmek\n"
                    "• Farklı kampanyalar için farklı 'Kimden' adresleri\n"
                    "• A/B testi: hangi domain daha iyi açılma oranı alıyor\n\n"
                    "Her toplu gönderimde hangi göndericiyi kullanacağınızı seçersiniz.\n"
                    "Kural oluştururken de gönderici bazında sınır koyabilirsiniz."
                ),
            },
        ],
    },
    {
        "id": "gonderim",
        "icon": "📋",
        "title": "Mail Gönderimi",
        "questions": [
            {
                "q": "Toplu gönderimde hangi kaynakları kullanabilirim?",
                "a": (
                    "3 kaynak seçeneği vardır:\n\n"
                    "1) 🗄 Veritabanı Tablosu\n"
                    "   • Önce Ayarlar > Veritabanı sayfasından Excel'i içe aktarın\n"
                    "   • En güçlü seçenek: Liste Temizleme, is_valid filtresi ve kişiselleştirme destekler\n"
                    "   • Büyük listeler için önerilir\n\n"
                    "2) 📊 Excel Dosyası\n"
                    "   • .xlsx veya .xls dosyası doğrudan yükleyin\n"
                    "   • Her sütun bir değişken olur ({{AdSoyad}}, {{Şirket}} vb.)\n"
                    "   • DB'ye kayıt gerekmez, anlık gönderim için idealdir\n\n"
                    "3) 📋 Metin Yapıştır\n"
                    "   • E-posta adreslerini satır satır yapıştırın\n"
                    "   • Ayraç kullanmayın — her satır = bir adres\n"
                    "   • Kişiselleştirme değişkeni yoktur (sadece e-posta)\n"
                    "   • Hızlı ve küçük listeler için idealdir"
                ),
            },
            {
                "q": "Değişkenler ({{Ad}}, {{Şirket}} vb.) nasıl çalışır?",
                "a": (
                    "Excel veya DB tablonuzdaki her sütun adı otomatik değişken olur.\n\n"
                    "Örnek tablo sütunları: Ad, Soyad, Firma, Şehir\n\n"
                    "Konu: Sayın {{Ad}} {{Soyad}}, {{Firma}} için özel teklifimiz\n"
                    "İçerik: {{Şehir}}'deki ekibimiz sizinle görüşmek istiyor...\n\n"
                    "Her alıcı için:\n"
                    "  Ahmet Yılmaz → 'Sayın Ahmet Yılmaz, ABC Ltd için özel teklifimiz'\n\n"
                    "Önemli notlar:\n"
                    "• Büyük/küçük harf duyarlıdır: {{Ad}} ≠ {{ad}}\n"
                    "• Sütun adı boşluk içeriyorsa çalışmayabilir\n"
                    "• Var tags bölümünde sütun adlarına tıklayarak konu/içeriğe ekleyebilirsiniz"
                ),
            },
            {
                "q": "MX Kaydı Kontrolü ne işe yarar ve ne zaman açık bırakılmalı?",
                "a": (
                    "MX (Mail Exchange) kontrolü, e-posta gönderilmeden önce o adresin\n"
                    "domain'inin gerçekten bir mail sunucusuna sahip olup olmadığını DNS'ten sorgular.\n\n"
                    "Örnek:\n"
                    "  info@kapandifirma.com → DNS sorgusu → MX kaydı yok → Atla\n"
                    "  info@gercekfirma.com.tr → DNS sorgusu → MX kaydı var → Gönder\n\n"
                    "Açık bırakın eğer:\n"
                    "• Eski veya doğrulanmamış liste kullanıyorsanız\n"
                    "• Bounce oranınız yüksekse\n"
                    "• 100K gibi büyük liste gönderiyorsanız\n\n"
                    "Kapatabilirsiniz eğer:\n"
                    "• Liste zaten Liste Temizleme'den geçtiyse (is_valid=1)\n"
                    "• Küçük, güvenilir bir liste ise\n\n"
                    "Etki: Hard bounce'ların %60-70'ini göndermeden yakalar.\n"
                    "Performans: Domain başına ~0.5-2 saniye (önbelleklenir, tekrar sorgulanmaz)."
                ),
            },
            {
                "q": "Batch (Parti) gönderim ne işe yarar?",
                "a": (
                    "Büyük listeleri parçalara bölerek gönderir ve partiler arasında bekleme süresi koyar.\n\n"
                    "Neden önemlidir:\n"
                    "• Brevo/SES günlük kotalarını aşmayı önler\n"
                    "• Spam filtrelerinden korunur (ani büyük hacim şüpheli görünür)\n"
                    "• Hesap askıya alınma riskini düşürür\n\n"
                    "Örnek kullanım:\n"
                    "  1000 kişilik liste, 100'lük partiler, 2 saat bekleme:\n"
                    "  → 10 parti × 2 saat = 20 saatte tamamlanır\n"
                    "  → Günde 1200 mail (100 × 12 saat)\n\n"
                    "Önerilen ayarlar (yeni hesaplar):\n"
                    "  Parti boyutu: 50-100\n"
                    "  Bekleme süresi: 60-120 dakika\n"
                    "  Mail arası gecikme: 1000-2000 ms"
                ),
            },
            {
                "q": "502 Bad Gateway veya bağlantı kesintisi alıyorum, gönderim devam eder mi?",
                "a": (
                    "Evet, sistem otomatik retry (yeniden deneme) yapar.\n\n"
                    "Nasıl çalışır:\n"
                    "• 502, 503, 504 HTTP hataları veya 'Remote end closed connection'\n"
                    "  gibi ağ kesintilerinde sistem durumu kaydeder\n"
                    "• 10 saniye bekler (geri sayım ekranda görünür)\n"
                    "• Kaldığı yerden devam eder — o partide gönderilen adresler atlanır\n"
                    "• Maksimum 2 retry hakkı vardır\n\n"
                    "Genellikle bu hata Cloudflare'in 100 saniyelik proxy timeout'undan kaynaklanır.\n"
                    "Çözüm: Daha küçük parti boyutu kullanın veya mail arası gecikmeyi artırın.\n\n"
                    "Durdurma butonu: Geri sayım sırasında da 'Durdur' basılabilir."
                ),
            },
            {
                "q": "Gönderim sonuçlarını nasıl dışa aktarabilirim?",
                "a": (
                    "Gönderim tamamlandığında 'Gönderim Durumu' kartının sağ üst köşesinde\n"
                    "📥 CSV İndir ve 📊 Excel İndir butonları belirir.\n\n"
                    "İndirilen dosyada:\n"
                    "• Sıra numarası\n"
                    "• E-posta adresi\n"
                    "• Durum (Başarılı / Hatalı / Atlandı)\n"
                    "• Hata veya atlama nedeni\n\n"
                    "Excel dosyasında ek olarak:\n"
                    "• Özet bölümü (toplam / başarılı / hatalı / atlandı)\n"
                    "• Renk kodlaması (yeşil=başarılı, kırmızı=hatalı, sarı=atlandı)\n"
                    "• Gönderim tarihi ve saati"
                ),
            },
            {
                "q": "Gönderim Geçmişi sayfasındaki 📈 Genel Özet kartı ne gösteriyor?",
                "a": (
                    "Sayfanın en üstündeki özet kart tüm gönderimlerinizi 3 zaman\n"
                    "dilimine göre özetler:\n\n"
                    "Bugün:\n"
                    "  • Toplam istek, başarılı ve hatalı sayıları\n\n"
                    "Bu Ay:\n"
                    "  • Toplam / başarılı / hatalı / atlandı sayıları\n"
                    "  • Başarı oranı çubuğu ve yüzdesi\n\n"
                    "Tüm Zamanlar:\n"
                    "  • Sistemin kurulduğundan bu yana tüm gönderimler\n"
                    "  • Genel başarı oranı\n\n"
                    "Başarı oranı renk kodu:\n"
                    "  Yeşil  ≥ %95  → Hesap sağlıklı\n"
                    "  Sarı   %80-95 → Dikkat, izleyin\n"
                    "  Kırmızı < %80 → Liste temizleme veya ayar kontrolü gerekli"
                ),
            },
        ],
    },
    {
        "id": "liste",
        "icon": "✅",
        "title": "Liste Temizleme (E-posta Doğrulama)",
        "questions": [
            {
                "q": "Liste temizleme neden önemlidir?",
                "a": (
                    "E-posta servis sağlayıcıları (Brevo, AWS SES) bounce oranını sürekli izler.\n\n"
                    "Sınır aşıldığında ne olur:\n"
                    "  Brevo: %2 hard bounce → hesap askıya alınır\n"
                    "  AWS SES: %5 bounce, %0.1 şikayet → sandbox'a geri düşürülür\n\n"
                    "100K adreslik listeyi temizlemeden göndermek ne anlama gelir:\n"
                    "  • %10-15 geçersiz adres tahmini → 10-15K hard bounce\n"
                    "  • %10 bounce → tüm hesaplar anında askıya alınır\n\n"
                    "Liste temizleme yaptıktan sonra:\n"
                    "  • Sadece is_valid=1 adresler gönderilir\n"
                    "  • Bounce oranı %1-2'ye düşer\n"
                    "  • Hesaplar korunur, gönderim limitlerini artırabilirsiniz"
                ),
            },
            {
                "q": "Format, MX ve SMTP modları nasıl çalışır?",
                "a": (
                    "⚡ Format Modu (en hızlı):\n"
                    "  • Sadece yazım kurallarını kontrol eder\n"
                    "  • Çift nokta (info@unimet..com), hatalı format, TLD eksikliği\n"
                    "  • Ağ bağlantısı gerekmez — saniyeler içinde tamamlanır\n"
                    "  • Yakaladığı: ~%5 adres (format hataları)\n\n"
                    "🔍 MX Modu (önerilen):\n"
                    "  • Format kontrolü + DNS'ten MX kaydı sorgusu\n"
                    "  • Domain'in mail sunucusu var mı kontrol eder\n"
                    "  • Kapanmış şirketlerin domainlerini yakalar\n"
                    "  • ~100-500ms/domain (önbellek sayesinde hızlı)\n"
                    "  • Yakaladığı: ~%20-25 adres\n\n"
                    "🔬 SMTP Modu (en kapsamlı, en yavaş):\n"
                    "  • MX kontrolü + sunucuya gerçek bağlantı\n"
                    "  • Posta kutusunun gerçekten var olup olmadığını test eder\n"
                    "  • Gmail/Yahoo/Outlook otomatik muaf (bloke ederler)\n"
                    "  • ~3-10sn/adres — 100K için 5+ gün sürebilir\n"
                    "  • Kurumsal domainler için değerli"
                ),
            },
            {
                "q": "is_valid kolonu ne anlama gelir?",
                "a": (
                    "Doğrulama tamamlandıktan sonra tablonuza eklenen sütundur.\n\n"
                    "  1  = Geçerli        → Gönderim yapılabilir\n"
                    "  0  = Geçersiz       → Gönderim yapılmaz, suppression'a eklenir\n"
                    " -1  = Riskli         → info@, admin@ gibi rol adresleri\n"
                    "                        veya SMTP'den belirsiz yanıt gelenler\n"
                    " NULL = Kontrol edilmedi → Henüz doğrulama yapılmamış\n\n"
                    "Toplu Gönderim sayfasında DB kaynağı kullandığınızda:\n"
                    "  '✅ Sadece Doğrulanmış' toggle açıkken yalnızca is_valid=1\n"
                    "  olan adresler SQL sorgusuna dahil edilir — is_valid=0 ve -1\n"
                    "  adresler hiç belleğe yüklenmez."
                ),
            },
            {
                "q": "Catch-all domain nedir?",
                "a": (
                    "Bazı mail sunucuları hangi adrese yazılırsa yazılsın '250 OK' yanıtı verir.\n"
                    "Örn: xyz123@firma.com da, gercekkullanici@firma.com da kabul edilir.\n\n"
                    "Sorun: Gerçek posta kutusu var mı yok mu bilemeyiz.\n\n"
                    "Sistem bu durumda:\n"
                    "  • is_valid = 1 atar (gönderim yapılabilir olarak işaretler)\n"
                    "  • Ama 'catch_all' olarak not düşer\n\n"
                    "Pratikte catch-all domainler genellikle şunlardır:\n"
                    "  • Büyük kurumsal şirketler\n"
                    "  • Eski veya iyi yapılandırılmış mail sistemleri\n"
                    "  • Çoğunlukla gerçek kullanıcıya ulaşır"
                ),
            },
            {
                "q": "İş ne kadar sürer? Takip edebilir miyim?",
                "a": (
                    "Tahmini süreler (10 thread ile):\n"
                    "  ⚡ Format — 1000 adres: saniyeler · 100K adres: ~2 dakika\n"
                    "  🔍 MX    — 1000 adres: 2-5 dk · 100K adres: 4-8 saat\n"
                    "  🔬 SMTP  — 1000 adres: 30-60 dk · 100K adres: birkaç gün\n\n"
                    "Thread sayısını artırırsanız hızlanır ama sunucuyu zorlayabilir.\n\n"
                    "Takip:\n"
                    "  • Sayfa açıkken canlı ilerleme çubuğu görünür\n"
                    "  • Sayfayı kapatsanız bile iş arka planda devam eder\n"
                    "  • Sayfayı yeniden açtığınızda kaldığı yerden takip edilir\n"
                    "  • Geçmiş İşler tablosunda tüm sonuçlar görünür"
                ),
            },
            {
                "q": "Doğrulama bitti — ✓ Geçerli / ✗ Geçersiz / ⚠ Riskli / 🚫 Supp. için ne yapmalıyım?",
                "a": (
                    "Doğrulama tamamlandığında Geçmiş İşler tablosunda 4 sayaç görünür.\n"
                    "Her biri için yapmanız gereken şudur:\n\n"
                    "──────────────────────────────────────\n"
                    "✓ GEÇERLİ (is_valid = 1)\n"
                    "──────────────────────────────────────\n"
                    "→ Bunlara GÖNDERİN.\n\n"
                    "Toplu Gönderim sayfasında:\n"
                    "  1. Kaynak olarak 'Veritabanı Tablosu' seçin\n"
                    "  2. Doğruladığınız tabloyu seçin\n"
                    "  3. '✅ Sadece doğrulanmış adreslere gönder' toggle'ı otomatik çıkar → AÇIK bırakın\n"
                    "  4. Gönderimi başlatın\n\n"
                    "Bu toggle açıkken sistem veritabanından sadece is_valid=1 satırları çeker.\n"
                    "Geçersiz ve riskli adresler hiç belleğe yüklenmez.\n\n"
                    "──────────────────────────────────────\n"
                    "✗ GEÇERSİZ (is_valid = 0)\n"
                    "──────────────────────────────────────\n"
                    "→ SİZİN YAPMANIZ GEREKEN HİÇBİR ŞEY YOK.\n\n"
                    "Sistem bu adresleri doğrulama sırasında otomatik olarak:\n"
                    "  • Suppression listesine ekledi (kaynak: email_verify)\n"
                    "  • Artık hiçbir gönderimde bu adresler kullanılmayacak\n\n"
                    "Geçersiz statüsü verilenler:\n"
                    "  • invalid_format — yazım hatası, geçersiz format\n"
                    "  • no_mx — domain'in mail sunucusu yok (kapalı firma vb.)\n"
                    "  • disposable — geçici/sahte mail servisi (mailinator vb.)\n"
                    "  • invalid — SMTP'den '550 kullanıcı yok' yanıtı geldi\n\n"
                    "İsterseniz kontrol: Ayarlar → Abonelik → Suppression Listesi → \n"
                    "'email_verify' kaynağına göre filtreleyin\n\n"
                    "──────────────────────────────────────\n"
                    "⚠ RİSKLİ (is_valid = -1)\n"
                    "──────────────────────────────────────\n"
                    "→ GÖNDEREBİLİRSİNİZ ama beklentinizi düşürün.\n\n"
                    "Riskli statüsü verilenler ve tavsiye:\n\n"
                    "  info@, admin@, noreply@ gibi ROL ADRESLERİ:\n"
                    "    Kişisel değil departman/sistem adresi. Genellikle düşük açılma oranı.\n"
                    "    B2B kampanyalarda bazen tek iletişim yolu — gönderin ama izleyin.\n\n"
                    "  SPF/DMARC yok (no_infra):\n"
                    "    Domain var ama mail altyapısı zayıf kurulmuş.\n"
                    "    Küçük firmalar çoğunlukla bu statüde çıkar — çoğu aslında geçerli.\n"
                    "    İlk kampanyada gönderin, bounce alırsanız suppression'a ekleyin.\n\n"
                    "  SMTP belirsiz yanıt (unknown):\n"
                    "    Sunucu 250 de 550 de dönmedi — bağlantı kesildi ya da timeout.\n"
                    "    Büyük ihtimalle geçerli, gönderin.\n\n"
                    "  Catch-all domain:\n"
                    "    Her adrese 250 OK dönüyor — gerçek kutu var mı bilinemez.\n"
                    "    Gönderin, bounce oranını izleyin.\n\n"
                    "Riskli adresler toplu gönderimde '✅ Sadece doğrulanmış' toggle'ı\n"
                    "KAPALI iken gönderilir — toggle açıkken bu adresler de atlanır.\n"
                    "Karar: toggle'ı kapatıp riskli adresleri de dahil edebilirsiniz.\n\n"
                    "──────────────────────────────────────\n"
                    "🚫 SUPP. (Suppression'a Eklenenler)\n"
                    "──────────────────────────────────────\n"
                    "→ SİZİN YAPMANIZ GEREKEN HİÇBİR ŞEY YOK.\n\n"
                    "Bu sayaç, doğrulama sırasında suppression listesine eklenen\n"
                    "adreslerin sayısını gösterir. Bunlar:\n"
                    "  • Geçersiz adresler (is_valid=0) otomatik eklendi\n"
                    "  • Zaten suppression'da olanlar bu sayaca dahil değil\n\n"
                    "Neden önemli: Suppression listesine giren adresler bir daha\n"
                    "asla gönderilmez — bounce oranınızı korur.\n\n"
                    "──────────────────────────────────────\n"
                    "ÖZET — 1 SATIR\n"
                    "──────────────────────────────────────\n"
                    "Geçerli → gönder   |   Geçersiz → sistem halletti   |   Riskli → gönder ama izle   |   Supp → unutun"
                ),
            },
            {
                "q": "Doğrulama bittikten sonra aynı listeyi tekrar doğrulamak gerekir mi?",
                "a": (
                    "Hayır. Sistem artık sadece is_valid=NULL olan adresleri işler.\n"
                    "Daha önce doğrulanmış (is_valid=1, 0 veya -1) adresler tekrar\n"
                    "doğrulanmaz — zaman ve kaynak israfı önlenir.\n\n"
                    "Ne zaman tekrar doğrulamak mantıklıdır:\n"
                    "  • Listeye YENİ adresler eklendiyse\n"
                    "    (sadece yeni eklenip is_valid=NULL olanlar işlenir)\n"
                    "  • 6+ ay önce doğrulanmış ve bounce oranı tekrar yükseldiyse\n"
                    "    (bu durumda mevcut is_valid değerlerini NULL'a sıfırlayıp\n"
                    "     tekrar çalıştırabilirsiniz — DB'den manuel UPDATE gerekir)\n\n"
                    "Normal kullanımda: listeyi bir kez doğrulayın, sonra\n"
                    "her gönderimde '✅ Sadece doğrulanmış' toggle'ını açık tutun."
                ),
            },
            {
                "q": "📤 Temiz Tablo Oluştur ne işe yarar?",
                "a": (
                    "Doğrulama tamamlanan bir işin yanında '📤 Temiz Tablo' butonu çıkar.\n"
                    "Bu buton, is_valid=1 adreslerden yeni ve bağımsız bir tablo oluşturur.\n\n"
                    "Neden kullanılır:\n"
                    "  • Toplu Gönderim'de 'Sadece Doğrulanmış' toggle'ını açmayı\n"
                    "    unutma riskini sıfıra indirir — tablo zaten temiz\n"
                    "  • Orijinal tablo bozulmadan kalır, tekrar doğrulama yapılabilir\n"
                    "  • Farklı kampanyalar için farklı filtreli tablolar\n"
                    "  • Başka sisteme taşırken sadece geçerlileri almak\n\n"
                    "Kullanım:\n"
                    "  1. Geçmiş İşler tablosunda tamamlanan işin yanındaki\n"
                    "     '📤 Temiz Tablo' butonuna tıklayın\n"
                    "  2. Yeni tablo adını girin (öneri otomatik gelir, değiştirebilirsiniz)\n"
                    "  3. 'Riskli adresleri de dahil et' seçeneğini isteğe göre açın\n"
                    "  4. Oluştur'a basın — saniyeler içinde tamamlanır\n"
                    "  5. Toplu Gönderim > DB kaynağı > yeni tabloyu seçin\n\n"
                    "Not: Tablo adı sadece harf, rakam ve _ içerebilir."
                ),
            },
            {
                "q": "İş takılıp kaldı, 'Çalışıyor' durumundan çıkmıyor. Ne yapmalıyım?",
                "a": (
                    "Bu durum genellikle uygulama yeniden başlatıldığında veya\n"
                    "beklenmedik bir hata oluştuğunda meydana gelir.\n\n"
                    "Çözüm:\n"
                    "  '🔄 Takılı İşleri Temizle' butonuna basın\n"
                    "  → 10 dakikadan uzun süredir 'running' veya 'pending'\n"
                    "    durumundaki tüm işler otomatik olarak 'iptal' yapılır\n\n"
                    "Ardından işi yeniden başlatabilirsiniz.\n"
                    "Daha önce işlenen adresler (is_valid≠NULL) tekrar işlenmez —\n"
                    "kaldığı yerden devam eder."
                ),
            },
        ],
    },
    {
        "id": "suppression",
        "icon": "🚫",
        "title": "Suppression ve Domain Bloklama",
        "questions": [
            {
                "q": "Suppression listesi nasıl çalışır?",
                "a": (
                    "Suppression listesindeki bir adrese asla mail gönderilmez.\n"
                    "Her gönderim öncesi sistem bu listeyi kontrol eder.\n\n"
                    "Otomatik eklenenler:\n"
                    "  • Hard bounce alan adresler (webhook ile)\n"
                    "  • Unsubscribe linkine tıklayanlar\n"
                    "  • Spam şikayeti yapanlar\n"
                    "  • Liste Temizleme'de is_valid=0 çıkanlar\n\n"
                    "Manuel ekleme:\n"
                    "  Ayarlar > Abonelik > Manuel Ekle > adres(ler) girin > sebep seçin\n"
                    "  Tek adres veya virgülle/satır satır birden fazla adres girebilirsiniz."
                ),
            },
            {
                "q": "Domain bloklama nedir? Ne zaman kullanılır?",
                "a": (
                    "Bir domain eklendiğinde o domain'e ait TÜM adreslere gönderim engellenir.\n"
                    "Bireysel adres eklemeye gerek kalmaz.\n\n"
                    "Örnek: rakip.com eklendi\n"
                    "  → info@rakip.com    → engellenmiş\n"
                    "  → satis@rakip.com   → engellenmiş\n"
                    "  → ceo@rakip.com     → engellenmiş\n\n"
                    "Kullanım senaryoları:\n"
                    "  • Rakip şirket domainleri\n"
                    "  • Çok fazla şikayet gelen domainler\n"
                    "  • Kapanan şirketlerin domainleri\n"
                    "  • Kendi iç domainleriniz (yanlışlıkla gönderimi önlemek)\n\n"
                    "Ayarlar > Abonelik > Domain Bloklama Listesi bölümünden yönetin."
                ),
            },
            {
                "q": "Brevo/SES webhook'ları ile otomatik suppression nasıl kurulur?",
                "a": (
                    "Webhook kurulunca bounce/şikayet/unsubscribe olayları anında sisteminize gelir.\n\n"
                    "Brevo için:\n"
                    "  Brevo Panel > Settings > Webhooks > Add a Webhook\n"
                    "  URL: https://siteniz.com/webhook/brevo\n"
                    "  Events: hard_bounce ✓  spam ✓  unsubscribe ✓\n\n"
                    "AWS SES için:\n"
                    "  AWS SES > Configuration > Notification\n"
                    "  SNS Topic oluşturun ve webhook URL'sini girin\n"
                    "  URL: https://siteniz.com/webhook/ses\n\n"
                    "Webhook URL'lerini Ayarlar > API Göndericiler sayfasının\n"
                    "alt kısmındaki 'Webhook Adresleri' bölümünden kopyalayabilirsiniz."
                ),
            },
            {
                "q": "Hard bounce mu, soft bounce mu eklemeliyim?",
                "a": (
                    "Hard bounce → Hemen suppression'a ekleyin (Sebep: Bounce)\n"
                    "  • 'User does not exist' — adres hiç var olmamış\n"
                    "  • 'Domain does not exist' — domain kapalı\n"
                    "  • '550 Permanent rejection' — kalıcı red\n"
                    "  • Bu adresler 1 ay sonra da, 1 yıl sonra da aynı hatayı verir\n\n"
                    "Soft bounce → 2-3 kez tekrar ettikten sonra ekleyin\n"
                    "  • 'Mailbox full' — kutu dolu, alıcı gerçek\n"
                    "  • 'Temporarily unavailable' — geçici sorun\n"
                    "  • 1-2 hafta bekleyip tekrar deneyin\n"
                    "  • Hala bounce alıyorsanız o zaman suppression'a ekleyin\n\n"
                    "Hepsini hemen eklemeyin — soft bounce'ların %40-50'si ulaşılabilir adrestir."
                ),
            },
            {
                "q": "Suppression listesindeki sebeplere göre nasıl aksiyon almalıyım?",
                "a": (
                    "Ayarlar → Abonelik → Suppression Listesi sayfasında her kaydın\n"
                    "bir Sebep ve Kaynak sütunu vardır. Her kombinasyon farklı anlam taşır.\n\n"
                    "══════════════════════════════════════════════\n"
                    "SEBEP: bounce  (Geri Dönen Mail)\n"
                    "══════════════════════════════════════════════\n"
                    "Ne anlama gelir:\n"
                    "  Mail gönderdik, karşı sunucu kalıcı olarak reddetti.\n"
                    "  Adres ya hiç var olmamış ya da domain kapatılmış.\n\n"
                    "Kaynaklar ve aksiyon:\n"
                    "  ses_sns / brevo → Webhook çalışıyor, otomatik eklendi. Hiçbir şey yapma.\n"
                    "  manual → Siz elle eklediniz. Kontrol edin, gerekirse bırakın.\n"
                    "  email_verify → Liste temizleme buldu (no_mx veya SMTP 550). Doğru karar.\n\n"
                    "Bu adrese bir daha GÖNDERMEYİN.\n"
                    "Bounce oranı Brevo'da %2'yi aşarsa hesabınız askıya alınır.\n\n"
                    "Listeden silebilir miyim?\n"
                    "  Teknik olarak evet, ama silmeyin. Hard bounce alan adres\n"
                    "  yarın da aynı hatayı verir — suppression'da kalması sizi korur.\n\n"
                    "══════════════════════════════════════════════\n"
                    "SEBEP: complaint  (Spam Şikayeti)\n"
                    "══════════════════════════════════════════════\n"
                    "Ne anlama gelir:\n"
                    "  Alıcı maili 'spam' olarak işaretledi.\n"
                    "  Gmail/Outlook spam butonuna bastı veya Brevo'ya şikayet etti.\n\n"
                    "Kaynaklar ve aksiyon:\n"
                    "  ses_sns / brevo → Webhook tetiklendi, otomatik eklendi. Hiçbir şey yapma.\n"
                    "  manual → Siz elle eklediniz.\n\n"
                    "Bu adrese KESİNLİKLE GÖNDERMEYİN.\n"
                    "Şikayet oranı %0.1'i aşarsa Brevo hesabı askıya alınır.\n"
                    "Şikayet eden kişileri listeden silmek büyük risk — bırakın.\n\n"
                    "Çok fazla şikayet görüyorsanız:\n"
                    "  • Mail içeriğinizi gözden geçirin (agresif satış dili?)\n"
                    "  • Listenin izin alınmış olduğundan emin olun\n"
                    "  • Gönderim sıklığını azaltın\n"
                    "  • Unsubscribe linkinin görünür olduğundan emin olun\n\n"
                    "══════════════════════════════════════════════\n"
                    "SEBEP: unsubscribe  (Abonelik İptali)\n"
                    "══════════════════════════════════════════════\n"
                    "Ne anlama gelir:\n"
                    "  Alıcı maildeki 'listeden çık' linkine tıkladı.\n"
                    "  Veya Brevo/SES'in kendi unsubscribe mekanizması çalıştı.\n\n"
                    "Kaynaklar ve aksiyon:\n"
                    "  web-form → Kendi sisteminizin unsubscribe linki tıklandı.\n"
                    "  brevo → Brevo'nun kendi çıkma mekanizması tetiklendi.\n"
                    "  ses_sns → SES/SNS bildirimi geldi.\n"
                    "  manual → Siz elle eklediniz.\n\n"
                    "Bu adrese GÖNDERMEYİN — yasal zorunluluk (GDPR, CAN-SPAM).\n"
                    "Unsubscribe isteğini görmezden gelmek yasal yaptırım riski taşır.\n\n"
                    "Listeden silebilir miyim?\n"
                    "  Hayır. Çıkmak isteyen birine tekrar göndermek hem yasal\n"
                    "  risk hem de spam şikayeti riskidir. Bırakın.\n\n"
                    "══════════════════════════════════════════════\n"
                    "SEBEP: invalid  (Geçersiz Adres)\n"
                    "══════════════════════════════════════════════\n"
                    "Ne anlama gelir:\n"
                    "  Liste Temizleme işlemi bu adresin geçersiz olduğunu tespit etti.\n"
                    "  Format hatası, MX kaydı yok veya SMTP 550 yanıtı.\n\n"
                    "Kaynaklar ve aksiyon:\n"
                    "  email_verify → Doğrulama işlemi ekledi. Doğru karar, bırakın.\n"
                    "  manual → Siz elle eklediniz.\n\n"
                    "Bu adrese GÖNDERMEYİN — kesin bounce alırsınız.\n\n"
                    "══════════════════════════════════════════════\n"
                    "SEBEP: manual  (Elle Eklenen)\n"
                    "══════════════════════════════════════════════\n"
                    "Ne anlama gelir:\n"
                    "  Siz veya başka bir kullanıcı bu adresi el ile ekledi.\n\n"
                    "Aksiyon:\n"
                    "  Neden eklendiğini hatırlıyorsanız bırakın.\n"
                    "  Yanlışlıkla eklendiyse ve göndermek istiyorsanız silebilirsiniz.\n"
                    "  Silmeden önce: bu adres daha önce bounce veya şikayet üretti mi\n"
                    "  Gönderim Geçmişi sayfasından kontrol edin.\n\n"
                    "══════════════════════════════════════════════\n"
                    "GENEL KURAL — 1 SATIR\n"
                    "══════════════════════════════════════════════\n"
                    "bounce → kalıcı sil   |   complaint → asla gönderme   |   "
                    "unsubscribe → yasal zorunluluk, bırak   |   invalid → bırak   |   manual → kontrol et"
                ),
            },
            {
                "q": "Suppression listesi çok şişti, temizleyebilir miyim?",
                "a": (
                    "Dikkatli olun — temizlemeden önce sebeplere bakın.\n\n"
                    "KESİNLİKLE SİLMEYİN:\n"
                    "  • complaint (şikayet) — bu kişilere tekrar göndermek yasal risk\n"
                    "  • unsubscribe — çıkmak isteyen kişilere göndermek GDPR ihlali\n"
                    "  • bounce (hard) — aynı adreslere tekrar gönderim = kesin bounce\n\n"
                    "SİLEBİLİRSİNİZ (ama önce düşünün):\n"
                    "  • email_verify kaynağı, çok eski tarihli (1+ yıl önce)\n"
                    "    → Domain o zamandan açılmış olabilir, risk düşük\n"
                    "  • manual kayıt, yanlışlıkla eklendiğinden eminseniz\n\n"
                    "Toplu temizlik yerine şunu öneririz:\n"
                    "  Suppression listesi büyük olması sorun değil — sistem performansını\n"
                    "  etkilemez. Her gönderimde SQL sorgusu ile kontrol edilir, hızlıdır.\n"
                    "  100K suppression kaydı bile gönderim hızını etkilemez.\n\n"
                    "Belirli kaynağı temizlemek için:\n"
                    "  Ayarlar → Abonelik → Suppression Listesi → kaynak/sebep filtreleyin\n"
                    "  → tek tek silebilirsiniz (toplu silme özelliği riskli olduğundan yoktur)"
                ),
            },
        ],
    },
    {
        "id": "mimari",
        "icon": "⚙️",
        "title": "Teknik Mimari — Sistem Nasıl Çalışır?",
        "questions": [
            {
                "q": "Uygulama hangi dosyalardan oluşuyor, her biri ne iş yapıyor?",
                "a": (
                    "app.py — Ana uygulama (Flask)\n"
                    "  • Tüm HTTP route'ları tanımlar (80+ endpoint)\n"
                    "  • Giriş/çıkış, oturum yönetimi\n"
                    "  • Toplu gönderim SSE stream'leri\n"
                    "  • Webhook endpoint'leri (Brevo, SES, Mailrelay)\n"
                    "  • rate_limit decorator ile kötüye kullanım koruması\n\n"
                    "database.py — Veritabanı katmanı\n"
                    "  • MySQL bağlantı havuzu\n"
                    "  • Tüm SQL sorguları burada — app.py'de SQL yok\n"
                    "  • get_table_rows, verify_job_*, get_log_summary gibi 80+ fonksiyon\n"
                    "  • safe_identifier() ile SQL injection koruması\n\n"
                    "mailer.py — E-posta gönderim motoru\n"
                    "  • send_one() — SMTP gönderim\n"
                    "  • send_via_ses() — AWS SES send_raw_email\n"
                    "  • send_via_api() — Brevo/Mailgun HTTP API\n"
                    "  • build_message() — MIME mesaj oluşturma (ek, HTML, headers)\n"
                    "  • render_template_str() — {{Ad}}, {{Firma}} değişken doldurma\n\n"
                    "verifier.py — E-posta doğrulama motoru\n"
                    "  • 9 katmanlı kontrol: format, disposable, rol, typo, MX, SPF/DMARC, catch-all, SMTP\n"
                    "  • verify_one() — tek adres doğrular\n"
                    "  • run_verify_job() — DB'deki işi çalıştırır (thread pool)\n\n"
                    "worker.py — Arka plan iş işleyici\n"
                    "  • Her çalıştığında: bekleyen mail kuyruğu + doğrulama işleri\n"
                    "  • process_task() — kuyruktan mail gönderir\n"
                    "  • process_verify_job() — doğrulama işini çalıştırır\n"
                    "  • cPanel'de cron ile her 5dk çalıştırılır\n\n"
                    "security.py — Güvenlik yardımcıları\n"
                    "  • rate_limit() decorator — IP tabanlı istek sınırlama\n"
                    "  • safe_identifier() — SQL injection önleme\n"
                    "  • require_local_or_auth() — opsiyonel şifre koruması\n\n"
                    "help_content.py — Bu yardım içerikleri\n"
                    "  • Tüm sayfa ipuçları ve kılavuz buradan okunur\n"
                    "  • Kod değişikliği gerekmeden içerik güncellenebilir"
                ),
            },
            {
                "q": "Toplu gönderim nasıl çalışır? SSE nedir?",
                "a": (
                    "SSE (Server-Sent Events) — sunucudan tarayıcıya tek yönlü canlı veri akışı.\n\n"
                    "Normal HTTP isteğinde:\n"
                    "  Tarayıcı istek gönderir → Sunucu yanıt verir → Bağlantı kapanır\n\n"
                    "SSE ile:\n"
                    "  Tarayıcı istek gönderir → Sunucu yanıt vermeye DEVAM EDER\n"
                    "  → Her mail sonrası bir satır gönderir → Tarayıcı anlık günceller\n\n"
                    "Toplu gönderim akışı:\n"
                    "  1. Kullanıcı 'Başlat' tuşuna basar\n"
                    "  2. main.js /api/send-bulk'a POST atar (FormData ile)\n"
                    "  3. Flask SSE stream açar, Response(stream(), mimetype='text/event-stream')\n"
                    "  4. stream() generator fonksiyonu her mail için:\n"
                    "       a. Suppression kontrolü (can_send)\n"
                    "       b. Değişkenleri doldur (render_template_str)\n"
                    "       c. send_one() / send_via_ses() / send_via_api() çağır\n"
                    "       d. data: {type:progress, i:5, email:..., status:ok} yaz\n"
                    "       e. heartbeat_sleep(delay_ms) bekle\n"
                    "  5. Bitti → data: {type:done, ok:X, err:Y} yaz\n\n"
                    "Heartbeat sistemi:\n"
                    "  Cloudflare 100 saniye veri gelmezse bağlantıyı keser.\n"
                    "  heartbeat_sleep() beklemeyi 8sn'lik dilimlere böler,\n"
                    "  her dilimde ': heartbeat' SSE comment'i gönderir.\n"
                    "  Bu proxy'ye 'bağlantı canlı' sinyali verir, 502 olmaz.\n\n"
                    "Otomatik retry:\n"
                    "  Bağlantı koparsa main.js kaç mail işlendiğini sayar,\n"
                    "  batch_offset ekleyerek kaldığı yerden devam eder (max 2 deneme)."
                ),
            },
            {
                "q": "local mod ile hosting mod arasındaki teknik fark nedir?",
                "a": (
                    "local mod (SEND_MODE=local):\n"
                    "  • Toplu gönderim → SSE stream → tarayıcıda canlı takip\n"
                    "  • Liste doğrulama → threading.Thread ile anında arka planda başlar\n"
                    "  • worker.py gerekmiyor (doğrulama için)\n"
                    "  • Sayfa kapatılırsa gönderim durabilir\n\n"
                    "hosting mod (SEND_MODE=hosting):\n"
                    "  • Toplu gönderim → send_queue tablosuna INSERT → worker.py işler\n"
                    "  • Liste doğrulama → email_verify_jobs tablosuna INSERT → worker.py işler\n"
                    "  • worker.py cron ile her 5dk çalışır\n"
                    "  • Sayfa kapatılabilir, iş arka planda devam eder\n"
                    "  • cPanel gibi paylaşımlı hostinglerde zorunlu (uzun HTTP bağlantıları kesilir)\n\n"
                    "is_hosting_mode() fonksiyonu:\n"
                    "  .env'deki SEND_MODE değerini okur.\n"
                    "  local → False, hosting → True\n"
                    "  app.py'de her kritik noktada kontrol edilir."
                ),
            },
            {
                "q": "Veritabanındaki tablolar ne işe yarar?",
                "a": (
                    "Sistem tabloları (silinemez):\n\n"
                    "  senders            → Tüm göndericiler (SMTP/SES/API bilgileri şifreli)\n"
                    "  send_log           → Her gönderimin kaydı (tarih, alıcı, durum, hata)\n"
                    "  send_queue         → Hosting modunda bekleyen toplu gönderim işleri\n"
                    "  send_queue_log     → Kuyruk işlerinin satır bazlı logu\n"
                    "  suppression_list   → Gönderilmeyecek e-posta adresleri\n"
                    "  suppression_domains → Gönderilmeyecek domainler (tüm *@domain.com)\n"
                    "  send_rules         → Gönderim kuralları (min. aralık saati)\n"
                    "  mail_templates     → Kayıtlı konu/mesaj şablonları\n"
                    "  users              → Sistem kullanıcıları (şifreler bcrypt)\n"
                    "  audit_log          → Tüm sistem olaylarının izleme kaydı\n"
                    "  email_verify_jobs  → Doğrulama işleri ve ilerleme\n"
                    "  ses_notifications  → AWS SES bounce/complaint bildirimleri\n\n"
                    "Kullanıcı tabloları (Excel'den oluşturulur):\n"
                    "  • Herhangi bir isim verilebilir (sistem tablosu adları hariç)\n"
                    "  • Sütunlar Excel'den otomatik algılanır\n"
                    "  • Doğrulama sonrası is_valid kolonu eklenir\n"
                    "  • Toplu gönderimde kaynak olarak kullanılır"
                ),
            },
            {
                "q": "Güvenlik nasıl sağlanıyor?",
                "a": (
                    "Kimlik doğrulama:\n"
                    "  • Flask session ile — SECRET_KEY ile imzalı\n"
                    "  • @login_required decorator tüm korumalı endpoint'lerde\n"
                    "  • @admin_required admin-only işlemler için\n"
                    "  • Şifreler bcrypt ile hash'leniyor (salt dahil)\n\n"
                    "SQL Injection koruması:\n"
                    "  • Tüm kullanıcı girdileri %s parametreli sorgu ile\n"
                    "  • Tablo/kolon adları safe_identifier() ile doğrulanır\n"
                    "  • Sadece harf, rakam, _ içeren isimler kabul edilir\n\n"
                    "Rate Limiting:\n"
                    "  • IP tabanlı, Flask-Limiter gerekmez (hafıza içi dict)\n"
                    "  • Login: 10/dk, forgot-password: 3/5dk\n"
                    "  • Toplu gönderim: 20/dk, tek gönderim: 30/dk\n"
                    "  • SSE endpoint'lerde özel format (502 değil SSE error)\n\n"
                    "Şifre koruması:\n"
                    "  • Gönderici şifreler Fernet (AES-128-CBC) ile şifreli DB'de\n"
                    "  • SECRET_KEY .env'de tutulur, kod içinde yok\n"
                    "  • APP_ACCESS_PASSWORD ile ek koruma katmanı eklenebilir\n\n"
                    "Webhook güvenliği:\n"
                    "  • Brevo: Basic Authentication (BREVO_WEBHOOK_USER/PASS)\n"
                    "  • SES: HMAC-SHA256 imza doğrulama\n"
                    "  • Her webhook isteği kaynak doğrulamasından geçer"
                ),
            },
            {
                "q": "E-posta doğrulama (verifier.py) 9 katmanı detaylı nasıl çalışır?",
                "a": (
                    "Her adres sırayla bu 9 kontrolden geçer:\n\n"
                    "1. Normalizasyon\n"
                    "   • Küçük harfe çevir\n"
                    "   • Gmail +tag temizleme: ali+promo@gmail.com → ali@gmail.com\n"
                    "   • googlemail.com → gmail.com\n\n"
                    "2. Format (RFC 5321)\n"
                    "   • Türkçe karakter var mı? (ş, ğ, ü → geçersiz)\n"
                    "   • Local kısım max 64 karakter\n"
                    "   • Toplam adres max 254 karakter\n"
                    "   • Regex ile format kontrolü\n\n"
                    "3. Disposable tespiti\n"
                    "   • 100+ geçici mail servisi (mailinator, guerrillamail vb.) listesi\n\n"
                    "4. Rol adresi tespiti\n"
                    "   • info@, admin@, noreply@, support@ vb. 60+ önek\n"
                    "   • is_valid=-1 (riskli) döner\n\n"
                    "5. Typo düzeltme\n"
                    "   • gmial.com→gmail.com, hotmail.com.tr→hotmail.com\n"
                    "   • 40+ yaygın yazım hatası tablosu\n\n"
                    "6. MX / A kaydı DNS sorgusu\n"
                    "   • dns.resolver ile MX sorgusu (timeout: 5sn)\n"
                    "   • MX yoksa A kaydı dener (fallback)\n"
                    "   • Önbellekleme: aynı domain tekrar sorgulanmaz\n\n"
                    "7. SPF / DMARC kontrolü\n"
                    "   • _dmarc.domain ve TXT sorgusu\n"
                    "   • İkisi de yoksa no_infra (riskli)\n"
                    "   • 30 günden yeni domain → new_domain (riskli)\n\n"
                    "8. Catch-all tespiti (SMTP modunda)\n"
                    "   • Rastgele adrese RCPT TO → 250 dönüyorsa catch-all\n\n"
                    "9. SMTP RCPT doğrulama (SMTP modunda)\n"
                    "   • Port 25'ten gerçek bağlantı\n"
                    "   • 250 → geçerli, 550 → geçersiz\n"
                    "   • Gmail/Yahoo/Outlook otomatik atlanır (bloke ederler)"
                ),
            },
            {
                "q": "Webhook olayları suppression listesine nasıl ulaşıyor?",
                "a": (
                    "Tam akış (Brevo örneği):\n\n"
                    "  1. Siz Brevo'dan bir mail gönderdiniz\n"
                    "  2. Alıcı sunucu 'kullanıcı yok' dedi → hard bounce\n"
                    "  3. Brevo bounce olayını tespit etti\n"
                    "  4. Brevo panelinde tanımlı webhook URL'sine POST atar:\n"
                    "     POST https://siteniz.com/webhook/brevo\n"
                    "     Body: [{\"event\":\"hard_bounce\", \"email\":\"ali@firma.com\", ...}]\n"
                    "  5. webhook_brevo() fonksiyonu isteği alır\n"
                    "  6. Basic Auth kontrolü (BREVO_WEBHOOK_USER/PASS)\n"
                    "  7. event='hard_bounce' → _webhook_add_suppression() çağrılır\n"
                    "  8. db().add_to_suppression('ali@firma.com', 'bounce', source='brevo')\n"
                    "  9. Artık o adrese bir daha gönderim yapılmaz\n\n"
                    "AWS SES akışı:\n"
                    "  SES → SNS Topic → HTTPS Subscription → /api/ses/sns-webhook\n"
                    "  Subscription Confirmation otomatik onaylanır (urllib.request.urlopen)\n"
                    "  Bounce: sadece Permanent bounce suppression'a eklenir (Transient eklenmez)\n"
                    "  Complaint: her zaman eklenir\n"
                    "  Delivery: ses_notifications tablosuna loglanır (suppression'a eklenmez)"
                ),
            },
        ],
    },
    {
        "id": "sorun",
        "icon": "🔧",
        "title": "Sorun Giderme",
        "questions": [
            {
                "q": "SMTP bağlantı hatası alıyorum, ne yapmalıyım?",
                "a": (
                    "Adım adım kontrol listesi:\n\n"
                    "1) Host ve port doğruluğunu kontrol edin\n"
                    "   Gmail: smtp.gmail.com:587\n"
                    "   Outlook: smtp-mail.outlook.com:587\n\n"
                    "2) Gmail kullanıyorsanız:\n"
                    "   → Normal hesap şifresi değil, Uygulama Şifresi gereklidir\n"
                    "   → myaccount.google.com > Güvenlik > Uygulama Şifreleri\n\n"
                    "3) Hosting'deyseniz:\n"
                    "   → 587 veya 465 portu sağlayıcı tarafından bloke olabilir\n"
                    "   → cPanel'de 'Mail' > 'Email Accounts' > SMTP bilgilerini kontrol edin\n\n"
                    "4) Firewall/güvenlik duvarı:\n"
                    "   → VPS/EC2'de outbound 587/465 portuna izin verilmiş mi kontrol edin\n\n"
                    "5) 'Ayarlar > Test Et' butonuyla detaylı hata mesajını görün"
                ),
            },
            {
                "q": "Worker.py çalışmıyor gibi görünüyor, görevler işlenmiyor.",
                "a": (
                    "1) Log dosyasını kontrol edin:\n"
                    "   tail -f logs/worker.log\n\n"
                    "2) Manuel çalıştırın ve çıktıya bakın:\n"
                    "   python3 worker.py\n\n"
                    "3) Cron komutundaki yolu doğrulayın:\n"
                    "   cd /home/KULLANICI/public_html/mailsender  ← doğru mu?\n"
                    "   python3 worker.py  ← python3 yolu doğru mu?\n"
                    "   → Tam yol deneyin: /usr/bin/python3 worker.py\n\n"
                    "4) .env dosyasının konumunu kontrol edin:\n"
                    "   worker.py ile aynı dizinde olmalı\n\n"
                    "5) DB bağlantısını test edin:\n"
                    "   python3 -c \"from database import db; print(db().test_connection())\""
                ),
            },
            {
                "q": "Yüksek bounce oranı alıyorum, hesabım risk altında mı?",
                "a": (
                    "Risk seviyeleri:\n"
                    "  < %1 bounce  → Güvenli\n"
                    "  %1-2 bounce  → Dikkatli olun, listeyi temizleyin\n"
                    "  > %2 bounce  → Kritik — Brevo hesabı askıya alınabilir\n\n"
                    "Hemen yapmanız gerekenler:\n"
                    "1) Gönderimleri durdurun\n"
                    "2) Brevo panelinden bounce listesini indirin\n"
                    "   Contacts > Blocklist > Import ile Brevo'ya yükleyin\n"
                    "3) Aynı listeyi sisteminizin suppression listesine ekleyin\n"
                    "4) Liste Temizleme > MX modu ile tüm listeyi tarayın\n"
                    "5) Sadece is_valid=1 adreslerle devam edin\n\n"
                    "Hesap zaten askıya alındıysa:\n"
                    "   Brevo destek ile iletişime geçin, bounce yönetim planınızı anlatın."
                ),
            },
            {
                "q": "502 Bad Gateway hatası sürekli geliyor.",
                "a": (
                    "Bu hata genellikle Cloudflare'den kaynaklanır:\n"
                    "Cloudflare'in 100 saniyelik upstream timeout kuralı vardır.\n"
                    "SSE stream'inde 100 saniye boyunca veri gönderilmezse bağlantıyı keser.\n\n"
                    "Hesap: N mail × gecikme = toplam süre\n"
                    "Örn: 200 mail × 500ms = 100 saniye → tam timeout sınırında!\n\n"
                    "Çözümler:\n"
                    "1) Parti boyutunu küçültün: 200 yerine 100 mail/parti\n"
                    "2) Gecikmeyi azaltın: 500ms yerine 300ms deneyin\n"
                    "3) Sistem zaten otomatik retry yapar (10sn bekleyip devam eder)\n\n"
                    "cPanel/hosting kullanıyorsanız:\n"
                    "   SEND_MODE=hosting kullanın — gönderim cron ile arka planda çalışır,\n"
                    "   502 sorunu ortadan kalkar."
                ),
            },
            {
                "q": "Sayfa yüklenmiyor / 500 hatası alıyorum.",
                "a": (
                    "1) Terminal/konsol çıktısına bakın (app.py çalışıyorsa hata orada görünür)\n\n"
                    "2) DB bağlantısını test edin:\n"
                    "   Ayarlar > Veritabanı > Bağlantıyı Test Et\n\n"
                    "3) .env dosyasını kontrol edin:\n"
                    "   • SECRET_KEY tanımlı mı?\n"
                    "   • DB bilgileri doğru mu?\n\n"
                    "4) Paketlerin kurulu olduğunu doğrulayın:\n"
                    "   pip install -r requirements.txt --break-system-packages\n\n"
                    "5) Python versiyonu:\n"
                    "   python --version  → 3.10+ olmalı\n\n"
                    "6) logs/ klasöründe log dosyası var mı kontrol edin"
                ),
            },
            {
                "q": "Liste Temizleme başlatıyorum ama iş hiç ilerlemiyor.",
                "a": (
                    "İş 'Pending' durumunda bekliyorsa worker.py çalışmıyor demektir.\n\n"
                    "SEND_MODE=local ise:\n"
                    "   İş otomatik arka plan thread'inde başlamalıydı.\n"
                    "   Uygulama yeniden başlatıldıysa pending işler beklemede kalır.\n"
                    "   Çözüm: worker.py'yi manuel çalıştırın: python3 worker.py\n\n"
                    "SEND_MODE=hosting ise:\n"
                    "   Cron job'ın çalıştığını kontrol edin.\n"
                    "   Cron her 5 dakikada bir çalışır — işin başlaması 5 dakika sürebilir.\n"
                    "   Kontrol: tail -f logs/worker.log\n\n"
                    "İş başladıktan sonra ilerleme çok yavaşsa:\n"
                    "   • Thread sayısını artırın (10 → 15 veya 20)\n"
                    "   • SMTP modundan MX moduna geçin"
                ),
            },
        ],
    },
]
