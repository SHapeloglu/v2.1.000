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
            ("4. 👁 Önizle", "Konu alanının yanındaki Önizle butonu Excel'in ilk satırındaki gerçek verilerle {{değişken}}'leri doldurur — göndermeden önce nasıl görüneceğini kontrol edin."),
            ("5. 🧪 A/B Test", "Konu alanı altındaki A/B Test toggle'ını açın, B Konusu girin. Liste otomatik %50/%50 bölünür. Send-log'da [A/B:A] ve [A/B:B] etiketiyle hangi konunun daha iyi çalıştığını karşılaştırın."),
            ("6. MX Kontrolü", "🔍 MX Kaydı Kontrolü açıksa, her adresin domain'i DNS'ten sorgulanır. Geçersiz domainler gönderilmeden atlanır — bounce oranını %60-70 düşürür."),
            ("7. 🚫 Rol Adresi Filtresi", "info@, admin@, noreply@ gibi kişisel olmayan adresleri otomatik atlar. Açılma oranını artırır."),
            ("8. 🗑️ Geçici E-posta Filtresi", "mailinator, tempmail, yopmail gibi 100+ tek kullanımlık servisi otomatik engeller. Varsayılan olarak açıktır."),
            ("9. 🎣 Catch-all Tespiti", "Her adresi kabul eden domain'leri SMTP probe ile tespit eder. Büyük listede yavaşlatır, küçük listeler için uygundur."),
            ("10. Sadece Doğrulanmış", "Liste Temizleme yapılmış tablolarda ✅ toggle görünür. Açıksa yalnızca is_valid=1 olan adresler gönderilir."),
            ("11. Kurallar", "Aynı kişiye çok sık gönderimi önlemek için kural seçebilirsiniz (isteğe bağlı)."),
            ("12. Batch (Parti)", "Büyük listeleri parçalara bölün ve her parti arasında bekleme süresi koyun — Brevo/SES hesaplarınızı korur."),
            ("13. Ek Dosya", "Her alıcıya aynı eki göndermek için dosya seçin. PDF, Word, Excel vb. desteklenir. Dosya boyutu gönderici limitine tabidir."),
            ("14. 🖥 EC2 Auto-Stop", "EC2 üzerinde çalışıyorsanız 'Gönderim bitince EC2'yu otomatik kapat' toggle'ı belirir. Gönderim bittiğinde instance otomatik durdurulur — veri kaybolmaz (Terminate değil Stop)."),
            ("14b. ⏱ Gönderim Süresi Tahmini", "Bekleme süresi slider'ını ayarladığınızda veya liste yüklendiğinde otomatik hesaplanır: '1.250 adres × 500ms = yaklaşık 10 dakika'. Gönderim sırasında Gönderim Durumu başlığı kalan süreyi canlı günceller."),
            ("15. Başlat", "cPanel modu: iş kuyruğa girer, worker.py gönderir. Yerel mod: anlık başlar, canlı takip edilir."),
        ],
        "tip": "💡 Hız için bekleme süresini 200-500ms'e düşürebilirsiniz. Skip edilen adresler (MX yok, disposable vb.) bekleme yapmadan geçilir — delay yalnızca gerçek gönderimler arasında uygulanır. A/B Test: aynı listeye iki farklı konu gönderin, send-log'da [A/B:A] ve [A/B:B] etiketleriyle karşılaştırın.",
    },

    "single_send_page": {
        "title": "✉ Tek Mail Gönder",
        "intro": "Tek bir alıcıya hızlıca kişiselleştirilmiş mail gönderin. Test amaçlı veya bireysel iletişim için idealdir.",
        "steps": [
            ("Gönderici & Alıcı", "Tanımlı göndericilerden birini seçin. Alıcı e-posta adresini girin — tek adres kabul edilir."),
            ("Konu", "Konu alanına yazın veya 📌 Konu Şablonu Seç butonuyla kayıtlı şablonlardan seçin. {{değişken}} kullanabilirsiniz."),
            ("HTML Modu", "HTML modu açıkken içerik HTML olarak yorumlanır — kalın metin, link, renk gibi biçimlendirmeler çalışır. Kapalıyken düz metin gönderilir."),
            ("İçerik", "Mesaj gövdesini yazın veya 📄 Mesaj Şablonu Seç ile kayıtlı şablondan seçin. {{Ad}}, {{Firma}} gibi değişkenler desteklenir."),
            ("💾 Şablon Kaydet", "Mevcut konu veya içeriği şablon olarak kaydetmek için '💾 Konuyu Şablon Olarak Kaydet' veya '💾 Mesajı Şablon Olarak Kaydet' butonlarını kullanın."),
            ("Ek Dosya", "Tek bir dosya ekleyebilirsiniz. Dosya, MIME attachment olarak iletilir. PDF, görsel, Word belgesi desteklenir."),
            ("Unsubscribe Linki", "📧 toggle açıksa mailin altına otomatik 'Listeden çık' linki eklenir. Suppression sistemine bağlıdır."),
        ],
        "tip": "💡 Toplu gönderim öncesi içerik ve göndericini test etmek için kendinize tek mail gönderin.",
    },

    "send_log_page": {
        "title": "📊 Gönderim Geçmişi",
        "intro": "Sisteme geçen tüm gönderimler burada kayıtlıdır. Filtreleme, arama, CSV dışa aktarma ve başarısız gönderimler için tekrar deneme yapabilirsiniz.",
        "steps": [
            ("Durum renkleri", "✓ Yeşil = gönderildi · ✗ Kırmızı = başarısız · ⏭ Gri = atlandı (suppression/kural)"),
            ("Hata detayı", "Hatalı satırda hata mesajı görünür — SMTP reddi, SES hatası, geçersiz adres gibi bilgiler. Geçici hatalar (timeout, 502) artık 3 kez otomatik denenir."),
            ("Atlanma sebebi", "Suppression listesinde olan, kural nedeniyle erken çağrılan, MX kaydı bulunmayan, günlük limite ulaşan veya warmup planı dolduran adresler atlanır."),
            ("🔄 Başarısızları Tekrar Dene", "Filtrede bir gönderici seçip bu butona basın — başarısız gönderimler seçili gönderici ile yeniden denenir. Günlük limit doluysa atlanır."),
            ("A/B Test etiketleri", "A/B Test ile gönderilen maillerde konu alanında [A/B:A] veya [A/B:B] etiketi görünür. Hangi konunun daha iyi çalıştığını bu etiketle karşılaştırın."),
            ("Filtreleme", "Başlangıç ve bitiş tarihi (default: dün–bugün), gönderici, durum ve e-posta adresi ile filtreleyebilirsiniz. Tarih filtresi UTC bilinçlidir — Türkiye saatiyle seçilen aralık doğru uygulanır."),
            ("Dışa aktar", "Tablodaki verileri CSV olarak indirebilirsiniz — filtreler uygulanmış halde tüm kayıtlar gelir."),
            ("🗑 Geçmişi Sil", "Yalnızca admin rolü kullanabilir. Tüm logları veya seçili göndericinin loglarını temizler. Geri alınamaz."),
            ("📈 Genel Özet", "Sayfanın en üstündeki özet kart Bugün / Bu Ay / Tüm Zamanlar gönderim sayılarını ve başarı oranını gösterir. Oran rengi: yeşil ≥%95, sarı ≥%80, kırmızı <%80."),
        ],
        "tip": "💡 Başarısız gönderimler için önce göndericiyi filtreden seçin, ardından 🔄 Başarısızları Tekrar Dene butonuna basın. Tarih filtresinde hem başlangıç hem bitiş aynı gün seçilirse o güne ait tüm kayıtlar listelenir.",
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
            ("Günlük Limit", "Bu SMTP hesabından günlük en fazla kaç mail gönderileceğini belirler. Limit dolduğunda sistem o günkü gönderimi durdurur. 0 = limitsiz."),
            ("🔥 Warmup Planı", "Yeni domain veya yeni IP ile başlarken aktif edin. Gün 1-3: 50 → Gün 4-7: 100 → Gün 8-14: 200 → Gün 15-21: 400 → Gün 22+: sınırsız."),
        ],
        "tip": "💡 Gmail: Hesap > Güvenlik > 2 adımlı doğrulama açık > Uygulama şifresi oluştur.",
    },

    "settings_ses": {
        "title": "☁ AWS SES Gönderici",
        "intro": "Amazon Simple Email Service ile yüksek hacimli gönderim yapar. Sandbox modunda yalnızca doğrulanmış adresler alabilir.",
        "steps": [
            ("Access Key & Secret", "AWS IAM > Kullanıcı > Erişim Anahtarı oluştur. ses:SendEmail, ses:GetSendQuota izinleri gerekir."),
            ("Region", "SES'i aktifleştirdiğiniz AWS bölgesi (örn: eu-west-1, us-east-1)."),
            ("Configuration Set", "AWS SES konsolundaki ConfigurationSet adını girin. SNS entegrasyonu ile bounce/complaint takibi yapar. '📋 Listele' butonuyla hesabınızdaki mevcut set'leri görüntüleyin."),
            ("Sandbox modu", "Yeni hesaplar sandbox modunda açılır — sadece doğrulanmış adreslere gönderebilirsiniz. AWS'den production erişimi talep edin."),
            ("From adresi", "SES konsolunda doğrulanmış (verified) bir adres veya domain olmalıdır."),
            ("Kota Sorgula", "📊 butonuyla günlük limit ve kalan hakkı anlık olarak sorgulayabilirsiniz."),
            ("📊 İtibar Raporu", "Gönderici listesindeki 📊 butonuyla son 7 günün bounce ve şikayet oranını görün. Yeşil=sağlıklı, sarı=dikkat, kırmızı=risk. AWS limitleri: bounce >%5, şikayet >%0.1 hesabı askıya alır."),
            ("⚡ Otomatik Delay", "Gönderici düzenleme ekranında 'Otomatik Hesapla' butonu SES hesabınızın saniyedeki max gönderim kapasitesine göre ideal gecikme süresini hesaplar ve otomatik doldurur."),
            ("Günlük Limit", "SES kotanızı aşmamak için günlük limiti doldurun. 0 = limitsiz (SES kendi kotasını uygular)."),
            ("🔥 Warmup Planı", "Yeni domain veya yeni IP için aktif edin. Gün 1-3: 50 → Gün 4-7: 100 → Gün 8-14: 200 → Gün 15-21: 400 → Gün 22+: sınırsız."),
        ],
        "tip": "💡 SES limitleri: sandbox 200/gün, production için AWS'den talep edin. SPF+DKIM+DMARC kurulumu zorunludur.",
    },

    "settings_api_senders": {
        "title": "🔌 API Gönderici",
        "intro": "Mailrelay, Brevo, SendGrid, Postmark, Resend, Mailtrap, Mailjet, SendPulse, Mailgun gibi HTTP API servisleri entegre eder. Preset butonlarıyla alanlar otomatik dolar.",
        "steps": [
            ("Preset Butonları", "Servis adına tıklayın — Host, Endpoint, Auth Tipi ve Payload şablonu otomatik dolar. Sadece Token/Key alanını siz girin."),
            ("Host & Endpoint", "Servis API sunucu adresi ve yolu. Preset kullanıyorsanız elle girmenize gerek yok."),
            ("Auth Tipi", "Her servisin kimlik doğrulama yöntemi farklıdır. Preset seçince otomatik ayarlanır."),
            ("Payload Şablonu", "JSON yapısında RECIPIENT_EMAIL, FROM_EMAIL, SUBJECT_TEXT, HTML_CONTENT yer tutucularını kullanın."),
            ("Brevo Kota", "📊 butonuyla hesabın kalan e-posta kredisini ve plan bilgisini sorgulayın."),
            ("Günlük Limit", "Servisin günlük gönderim kotasını buraya girin (Brevo ücretsiz: 300, Mailtrap: 1000). Limit dolduğunda sistem o günkü gönderimi otomatik durdurur. 0 = limitsiz."),
            ("🔥 Warmup Planı", "Yeni açılan hesaplar için kademeli ısınma. Aktifken: Gün 1-3: 50/gün → Gün 4-7: 100 → Gün 8-14: 200 → Gün 15-21: 400 → Gün 22+: sınırsız. Her gün UTC gecesi sıfırlanır."),
            ("🔔 Webhook Kurulumu", "Sayfanın alt bölümünde Bounce/Complaint webhook URL'lerini kopyalayın. Brevo için: Brevo Panel > Settings > Webhooks > Add a new webhook. Mailrelay için: Panel > Configuración > Notificaciones."),
        ],
        "tip": "💡 Yeni bir hesap açtığınızda Warmup Planını mutlaka aktif edin — hesap itibarı oluşmadan ani yüksek hacim hesabın kapatılmasına neden olabilir.",
    },

    "settings_rules": {
        "title": "🛡 Gönderim Kuralları",
        "intro": "Aynı kişiye çok sık mail gönderilmesini önler. Spam şikayeti ve unsubscribe oranını düşürür.",
        "steps": [
            ("Kural tipi", "İki tip kural tanımlanabilir: Kullanıcı Bazlı (belirli bir kullanıcı gönderim yaptığında, hangi göndericiyi kullandığından bağımsız uygulanır) veya Gönderici Bazlı (belirli bir gönderici üzerinden yapılan gönderimlerde uygulanır)."),
            ("Min. aralık (saat)", "Aynı alıcıya en az kaç saat arayla mail gönderileceğini belirler. Örn: 720 = ayda en fazla 1 kez."),
            ("Kural seçimi", "Toplu gönderimde kural seçerseniz, kuralı ihlal eden adresler otomatik atlanır. Kullanıcı bazlı kurallar ise kural seçilmeden de otomatik devreye girer."),
            ("Atlanma", "Kuralı ihlal eden adresler 'skipped' olarak loglanır — suppression listesine eklenmez."),
        ],
        "tip": "💡 Cold email kampanyaları için kullanıcı bazlı 720 saat (30 gün) kuralı önerilir.",
    },

    "settings_db": {
        "title": "🗄 Veritabanı",
        "intro": "MySQL bağlantı bilgilerini, tablo yönetimini ve Excel içe aktarmayı buradan yaparsınız.",
        "steps": [
            ("Bağlantı bilgileri", "Host, port, kullanıcı adı, şifre ve DB adı .env dosyasına kaydedilir."),
            ("Bağlantıyı test et", "Kaydetmeden önce test ederek bağlantının çalıştığını doğrulayın."),
            ("Tabloları oluştur", "İlk kurulumda tüm sistem tablolarını (send_log, suppression_list vb.) oluşturur."),
            ("Excel içe aktarma", "Excel dosyasını seçerek yeni tablo olarak DB'ye ekleyin. Sütun adları otomatik algılanır. Aynı isimde tablo varsa üzerine yazma veya atla seçeneği sunar."),
            ("Tablo silme", "Sistem tabloları (send_log, suppression_list vb.) silinemez — sadece kendi oluşturduklarınız silinebilir."),
            ("Tablo önizleme", "Tablonun yanındaki göz ikonuyla ilk 10 satırı ve sütun listesini görün."),
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
            ("Unsubscribe Sunucu Ayarları", "EC2 kapalıyken unsubscribe linklerinin çalışması için harici bir hosting'e unsub uygulaması kurulur. URL ve DB bilgilerini buradan girin. 'Kaydet & Test Et' bağlantıyı doğrular."),
            ("Toplu Temizlik", "Belirli tablodan suppression'daki adresleri silmek için 'Seçili Tablodan Sil' bölümünü kullanın. 'Tüm Tablolardan Sil' tüm kullanıcı tablolarını tarar, e-posta kolonu tahmin edilir."),
            ("Sebeplere göre aksiyon", "bounce → silme, korur · complaint → asla silme, yasal risk · unsubscribe → silme, GDPR · invalid → silme, email_verify ekledi · manual → kontrol et"),
        ],
        "tip": "💡 Detaylı sebep rehberi için Yardım > Suppression ve Domain Bloklama > 'Sebeplere göre nasıl aksiyon almalıyım?' sorusuna bakın.",
    },

    "settings_templates": {
        "title": "📝 Şablonlar",
        "intro": "Sık kullandığınız konu başlıkları ve mail içeriklerini şablon olarak kaydedin. Toplu ve tek gönderimde kullanabilirsiniz.",
        "steps": [
            ("Yeni şablon", "Konu (subject) veya gövde (body) şablonu oluşturun. {{değişken}} kullanabilirsiniz."),
            ("Varsayılan şablon", "Bir şablonu varsayılan yaparsanız gönderim sayfaları açıldığında otomatik yüklenir. Her tipten yalnızca bir varsayılan olabilir."),
            ("Kullanım", "Gönderim sayfalarındaki '📌 Konu Şablonu Seç' veya '📄 Mesaj Şablonu Seç' butonlarıyla seçin."),
            ("Arama", "Modal'da arama kutusuna yazarak şablon adı veya içeriğinde arayabilirsiniz."),
            ("Kaydet", "Gönderim sayfasındaki '💾 Konuyu/Mesajı Şablon Olarak Kaydet' ile mevcut içeriği şablon yapabilirsiniz."),
            ("Düzenleme & Silme", "Listede şablonun yanındaki ✏️ ile düzenleyin, 🗑 ile silin. Varsayılan şablonlar da silinebilir — bir sonraki kayıt varsayılan olur."),
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
            ("Paralel Thread", "1-20 arası thread sayısı seçin. Varsayılan 10. Artırırsanız hız artar ama sunucu CPU kullanımı da artar. 20 thread, büyük listeleri çok daha hızlı bitirir."),
            ("SMTP Muaf Domainler", "Gmail, Yahoo, Outlook, Hotmail, iCloud gibi 40+ büyük servis SMTP'yi bloklar — otomatik muaf listesine dahildir. Admin panelinden ek domain ekleyebilirsiniz."),
            ("Sonuçlar", "Tabloya is_valid kolonu eklenir: 1=geçerli, 0=geçersiz (→ suppression), -1=riskli/rol adresi"),
            ("Toplu Gönderimdeki kullanımı", "Toplu Gönderim > DB kaynağı > tabloda is_valid varsa '✅ Sadece Doğrulanmış' toggle'ı belirir."),
            ("Sonuç aksiyonları", "✓ Geçerli → gönder · ✗ Geçersiz → sistem suppression'a ekledi, bir şey yapma · ⚠ Riskli → gönderebilirsin ama izle · 🚫 Supp → sistem halletti"),
            ("📤 Temiz Tablo Oluştur", "Tamamlanan bir işin yanındaki '📤 Temiz Tablo' butonuyla is_valid=1 adreslerden yeni bir tablo oluşturun. Riskli adresleri dahil etme seçeneği de var."),
            ("⬇ CSV İndir (Segment)", "Tamamlanan bir işin yanındaki CSV butonuyla sonuçları 12 farklı segmentte indirebilirsiniz: Geçerli, Geçersiz, Belirsiz, Geçerli+Riskli, Tümü, Catch-all, Spam Tuzağı, No-infra, Rol Adresi, Typo Düzeltilmiş, Gönderme (risk_label), Yüksek Risk. ?segment= parametresiyle doğrudan URL üretilebilir."),
            ("🕷 Spam Tuzağı Tespiti", "Sistem doğrulama sırasında 4 tür spam tuzağını otomatik tespit eder: pristine (hiç gerçek kullanıcı olmamış domainler), typo_trap (kasıtlı yanlış yazılmış domainler: gmali.com, yhaoo.com), recycled (geri dönüştürülmüş eski hesaplar), honeypot (bot formu doldurmalarından gelen adresler). Tespit güveni: high → is_valid=0 (suppression'a eklenir), medium/low → risk skoru düşürülür."),
            ("↻ Greylisting Retry Kuyruğu", "SMTP modunda ilk denemede yanıt vermeyen (unknown) adreslere sistem otomatik olarak 6 saat sonra tekrar bağlanır. İkinci denemede de yanıt gelmezse 12 saat, üçüncüde 24 saat sonra tekrar denenir. 3 denemeden sonra hâlâ belirsizse 'unknown' olarak bırakılır. Bu sayede greylisted (geçici engelli) gerçek adresler doğru şekilde tespit edilir."),
            ("⏰ Otomatik Yeniden Doğrulama", "Liste Temizleme > 'Otomatik Zamanlama' bölümünden her tablo için otomatik yeniden doğrulama planı kurabilirsiniz. Kaç günde bir (1-365), hangi adresleri (tümü / sadece geçerliler / sadece bilinmezler), hangi modda (MX/SMTP) yeniden doğrulatılacağını seçin. Worker her 5 dakikada zamanı gelen zamanlamaları kontrol eder ve otomatik iş başlatır."),
            ("🔀 Tablolar Birleştir", "Birden fazla doğrulanmış tabloyu tek bir hedef tabloda birleştirmek için 'Tablolar Birleştir' bölümünü kullanın. Geçerli ve riskli adresler ayrı hedef tablolara yazılabilir."),
            ("🗑 Tabloları Sil", "Birleştirme panelinden seçili tablolar admin tarafından silinebilir. Sistem tabloları silinemez."),
            ("🔄 Takılı İşleri Temizle", "İş 'Çalışıyor' durumunda takılıp kaldıysa bu butonla temizleyin. 10 dakikadan uzun süren 'running' işleri otomatik iptal eder."),
        ],
        "tip": "💡 Detaylı aksiyon rehberi için Yardım > Liste Temizleme bölümündeki 'Doğrulama bitti — ne yapmalıyım?' sorusuna bakın.",
    },

    "settings_users": {
        "title": "👥 Kullanıcılar",
        "intro": "Sisteme erişebilecek kullanıcıları yönetin. Yalnızca admin rolündeki kullanıcılar bu sayfayı görebilir.",
        "steps": [
            ("Roller", "Admin: her şeye erişir, kullanıcı yönetir, ayarları değiştirir. Editör: gönderim yapabilir, raporları görür, ayarlara giremez."),
            ("Yeni kullanıcı", "Kullanıcı adı, e-posta ve şifre (min. 6 karakter) ile hesap oluşturun. Rol atamayı unutmayın. Varsayılan rol: editör."),
            ("Şifre değiştirme", "Her kullanıcı kendi şifresini değiştirebilir — eski şifresini bilmesi gerekir. Admin herkesin şifresini yeni şifre girerek sıfırlayabilir."),
            ("E-posta güncelleme", "Kullanıcı e-postası şifre sıfırlama linki için kullanılır. Güncel tutun."),
            ("Aktif / Pasif", "Kullanıcıyı pasife alırsanız sisteme giremez ama geçmiş gönderim kayıtları korunur. Geçici engelleme için sil yerine pasife alın."),
            ("Kullanıcı silme", "Silinen kullanıcının gönderim geçmişi ve logları korunur, sadece giriş yapamaz. Son admin silinemez — sistem kilitlenmesini önler."),
        ],
        "tip": "💡 İlk kurulumda varsayılan admin/admin123 şifresini hemen değiştirin.",
    },

    "settings_audit_log": {
        "title": "📋 Denetim Kaydı",
        "intro": "Sistemdeki tüm önemli işlemler zaman damgası, kullanıcı adı ve IP adresiyle birlikte otomatik kaydedilir. Kim, ne zaman, ne yaptı — eksiksiz iz.",
        "steps": [
            ("Kayıt kapsamı", "Gönderici ekle/sil/güncelle · Toplu gönderim başlat/bitir · Excel yükle · Kullanıcı oluştur/sil/güncelle · Suppression ekle · Domain blokla · Doğrulama başlat/iptal · Tablo sil · Giriş/Çıkış."),
            ("Filtreleme", "İşlem türüne (dropdown) ve tarih aralığına göre filtreleyin. Filtreler anında uygulanır."),
            ("⬇ CSV", "Filtrelenmiş kayıtları CSV olarak indirin — denetim amaçlı saklama veya raporlama için."),
            ("IP Adresi", "Her kaydın yanında işlemi yapan kullanıcının IP adresi görünür. Proxy arkasındaysa X-Forwarded-For başlığından okunur."),
            ("Otomatik kayıt", "Denetim kaydı silemezsiniz — yalnızca okuma yetkisi vardır. Kayıtlar sistemin güvenlik ve uyumluluk izidir."),
        ],
        "tip": "💡 Sistemde beklenmedik bir işlem fark ederseniz Denetim Kaydı'nı tarih ve işlem türüne göre filtreleyerek kimin yaptığını hemen bulabilirsiniz.",
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
                    "4) Tarayıcıdan açın: http://localhost:5002\n\n"
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
                "q": "AWS SES İtibar Raporu nedir? Nasıl kullanılır?",
                "a": (
                    "SES gönderici listesindeki 📊 butonu son 7 günün itibar raporunu gösterir.\n\n"
                    "Raporda neler var:\n"
                    "  • Toplam gönderim sayısı\n"
                    "  • Bounce sayısı ve oranı\n"
                    "  • Şikayet (complaint) sayısı ve oranı\n"
                    "  • Başarılı teslim oranı\n\n"
                    "Kritik eşikler (AWS politikası):\n"
                    "  Bounce    > %5     → hesap gözlem altına alınır\n"
                    "  Bounce    > %10    → gönderim duraklatılır\n"
                    "  Complaint > %0.1   → uyarı\n"
                    "  Complaint > %0.5   → hesap askıya alınır\n\n"
                    "Renk göstergesi:\n"
                    "  Yeşil  → Güvenli, sorun yok\n"
                    "  Sarı   → Dikkat, eşiğe yaklaşıyorsunuz\n"
                    "  Kırmızı → Acil aksiyon alın\n\n"
                    "Rapor için gerekli IAM izni: ses:GetSendStatistics\n"
                    "Bu izin yoksa rapor boş gelir — IAM politikanıza ekleyin.\n\n"
                    "İtibar kötüleşiyorsa:\n"
                    "  1. Gönderimleri geçici olarak durdurun\n"
                    "  2. Liste Temizleme ile listeyi tarayın\n"
                    "  3. Suppression listesini Brevo/SES webhook'larıyla güncel tutun\n"
                    "  4. Gönderim sıklığını azaltın ve warmup planını gözden geçirin"
                ),
            },
            {
                "q": "SES Auto-Delay (Otomatik Gecikme Hesaplama) ne işe yarar?",
                "a": (
                    "AWS SES her hesaba saniyede gönderilebilecek maksimum mail sayısı\n"
                    "(MaxSendRate) atar. Bu değerin üzerine çıkarsanız throttling hatası alırsınız.\n\n"
                    "Auto-Delay nasıl çalışır:\n"
                    "  Gönderici düzenleme ekranında '⚡ Hesapla' butonuna basın.\n"
                    "  Sistem SES API'den MaxSendRate değerini okur.\n"
                    "  %80 güvenlik marjıyla ideal gecikme süresini hesaplar:\n"
                    "    delay_ms = 1000 / (MaxSendRate × 0.8)\n"
                    "  Hesaplanan değeri otomatik olarak 'Mail Arası Gecikme' alanına doldurur.\n\n"
                    "Örnek:\n"
                    "  MaxSendRate = 14/sn → delay_ms = 1000 / (14 × 0.8) = ~89ms\n"
                    "  MaxSendRate = 5/sn  → delay_ms = 1000 / (5 × 0.8)  = 250ms\n\n"
                    "Minimum: 200ms (sistem alt sınırı — daha düşük hesaplansa bile 200ms uygulanır)\n\n"
                    "Gerekli IAM izni: ses:GetSendQuota"
                ),
            },
            {
                "q": "SES Configuration Set nedir? Neden gerekli?",
                "a": (
                    "Configuration Set, SES'in bounce ve complaint bildirimlerini\n"
                    "SNS aracılığıyla sisteminize iletmesi için zorunludur.\n\n"
                    "Kurulum adımları:\n"
                    "  1. AWS Console > SES > Configuration Sets > Create\n"
                    "  2. Bir isim verin (örn: mailsender-tracking)\n"
                    "  3. Event Destinations > Add destination:\n"
                    "     • Event types: Bounce ✓, Complaint ✓, Delivery ✓\n"
                    "     • Destination type: SNS\n"
                    "     • SNS Topic oluşturun veya var olanı seçin\n"
                    "  4. SNS Topic'e HTTPS subscription ekleyin:\n"
                    "     URL: https://siteniz.com/sns/ses-notification\n"
                    "     (Uygulama SubscriptionConfirmation isteğini otomatik onaylar)\n"
                    "  5. Sistemde: SES gönderici düzenle > Configuration Set alanına adı yazın\n"
                    "     veya '📋 Listele' butonuyla mevcut set'lerinizi görün ve seçin\n\n"
                    "Configuration Set olmadan:\n"
                    "  • Bounce'lar suppression listesine otomatik eklenmez\n"
                    "  • AWS SES hesabınızın itibar puanı izlenemez\n"
                    "  • Yüksek bounce oranında hesabınız fark edilmeden kötüleşir"
                ),
            },
            {
                "q": "📮 Mailrelay ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Mailrelay panelinde: Account > API Keys bölümüne gidin\n"
                    "2) Yeni bir API anahtarı oluşturun\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > 📮 Mailrelay butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : ipzmarketing.com\n"
                    "   Endpoint : /api/v1/campaigns/send_transactional\n"
                    "   Auth Tipi: X-AUTH-TOKEN\n\n"
                    "4) Token alanına Mailrelay API anahtarınızı yapıştırın\n\n"
                    "NOT: Mailrelay webhook URL'sini panelde tanımlamanız gerekir.\n"
                    "Webhook URL: Ayarlar > API Göndericiler sayfasının alt kısmında gösterilir."
                ),
            },
            {
                "q": "💙 Brevo ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Brevo panelinde: Settings > SMTP & API > API Keys\n"
                    "2) 'Generate a new API key' ile anahtar oluşturun\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > 💙 Brevo butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : api.brevo.com\n"
                    "   Endpoint : /v3/smtp/email\n"
                    "   Auth Tipi: api-key\n\n"
                    "4) Token alanına Brevo API anahtarınızı yapıştırın\n\n"
                    "5) 📊 Kota Sorgula butonu ile hesap limitlerini kontrol edin\n\n"
                    "Günlük limit (ücretsiz plan): 300 mail/gün\n"
                    "Isınma için: ilk hafta 50/gün, ikinci hafta 150/gün"
                ),
            },
            {
                "q": "✉ SendGrid ile API gönderici nasıl kurulur?",
                "a": (
                    "1) SendGrid panelinde: Settings > API Keys > Create API Key\n"
                    "2) 'Full Access' veya 'Restricted Access > Mail Send' yetkisi verin\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > ✉ SendGrid butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : api.sendgrid.com\n"
                    "   Endpoint : /v3/mail/send\n"
                    "   Auth Tipi: Authorization: Bearer\n\n"
                    "4) Token alanına SendGrid API anahtarınızı yapıştırın\n\n"
                    "NOT: SendGrid'de gönderici e-posta adresinin doğrulanmış (verified sender) olması gerekir.\n"
                    "Doğrulama: Settings > Sender Authentication"
                ),
            },
            {
                "q": "📬 Postmark ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Postmark panelinde: Servers > [Sunucunuz] > API Tokens\n"
                    "2) Server API Token'ı kopyalayın\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > 📬 Postmark butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : api.postmarkapp.com\n"
                    "   Endpoint : /email\n"
                    "   Auth Tipi: X-API-KEY\n\n"
                    "4) Token alanına Postmark Server API Token'ınızı yapıştırın\n\n"
                    "NOT: Postmark'ta 'From' adresinin Sender Signature olarak eklenmiş olması gerekir.\n"
                    "Postmark ücretsiz planda 100 mail/ay test kredisi verir."
                ),
            },
            {
                "q": "⚡ Resend ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Resend panelinde: API Keys > Create API Key\n"
                    "2) Gerekli izinleri verin (Full access veya Sending access)\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > ⚡ Resend butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : api.resend.com\n"
                    "   Endpoint : /emails\n"
                    "   Auth Tipi: Authorization: Bearer\n\n"
                    "4) Token alanına Resend API anahtarınızı yapıştırın\n\n"
                    "NOT: Resend'de gönderici domain'inin DNS kayıtlarının doğrulanmış olması gerekir.\n"
                    "Ücretsiz planda günlük 100, aylık 3.000 mail."
                ),
            },
            {
                "q": "🪤 Mailtrap ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Mailtrap panelinde: Sending > API Tokens\n"
                    "   ya da: https://mailtrap.io/api-tokens\n"
                    "2) Yeni token oluşturun\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > 🪤 Mailtrap butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : send.api.mailtrap.io\n"
                    "   Endpoint : /api/send\n"
                    "   Auth Tipi: Authorization: Bearer\n\n"
                    "4) Token alanına Mailtrap API token'ınızı yapıştırın\n\n"
                    "NOT: Mailtrap hem test (sandbox) hem production gönderim sunar.\n"
                    "Üretim gönderimi için 'Sending' bölümündeki token'ı kullanın, sandbox token'ı değil."
                ),
            },
            {
                "q": "✈ Mailjet ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Mailjet panelinde: Account Settings > API Keys\n"
                    "   ya da: https://app.mailjet.com/account/apikeys\n"
                    "2) API Key (Public Key) ve Secret Key'i kopyalayın\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > ✈ Mailjet butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : api.mailjet.com\n"
                    "   Endpoint : /v3.1/send\n"
                    "   Auth Tipi: Authorization: Basic (Mailjet)\n\n"
                    "4) Public Key (API Key) kutusuna API Key'i girin\n"
                    "5) Secret Key kutusuna Secret Key'i girin\n\n"
                    "NOT: Mailjet ücretsiz planda günlük 200, aylık 6.000 mail.\n"
                    "Gönderici e-postanın Mailjet panelinde doğrulanmış olması gerekir."
                ),
            },
            {
                "q": "💚 SendPulse ile API gönderici nasıl kurulur?",
                "a": (
                    "1) SendPulse panelinde: Settings > API\n"
                    "   ya da: https://login.sendpulse.com/settings/#api\n"
                    "2) REST API ID ve Secret'i kopyalayın\n\n"
                    "3) Sistemde: Ayarlar > API Göndericiler > 💚 SendPulse butonuna tıklayın\n"
                    "   Alanlar otomatik dolar:\n"
                    "   Host     : api.sendpulse.com\n"
                    "   Endpoint : /smtp/emails\n"
                    "   Auth Tipi: OAuth2 — SendPulse\n\n"
                    "4) Client ID kutusuna REST API ID'yi girin\n"
                    "5) Client Secret kutusuna Secret'i girin\n\n"
                    "SendPulse diğerlerinden farklı çalışır:\n"
                    "• Her gönderimde önce /oauth/access_token ile geçici token alınır\n"
                    "• Bu token 1 saat geçerlidir ve sistem önbellekte saklar\n"
                    "• Süre dolunca otomatik yenilenir, sizin yapmanız gereken bir şey yok\n\n"
                    "NOT: SendPulse ücretsiz planda aylık 15.000 mail.\n"
                    "SMTP servisinin aktif olması gerekir: SendPulse > Email > SMTP"
                ),
            },
            {
                "q": "🔫 Mailgun ile API gönderici nasıl kurulur?",
                "a": (
                    "1) Mailgun panelinde: Account > API Security > Mailgun API Keys\n"
                    "   'Add new key' ile yeni anahtar oluşturun\n\n"
                    "2) Sistemde: Ayarlar > API Göndericiler > Manuel kurulum:\n"
                    "   Host     : api.mailgun.net\n"
                    "   Endpoint : /v3/YOUR_DOMAIN/messages\n"
                    "             (YOUR_DOMAIN yerine Mailgun'daki domaininizi yazın)\n"
                    "   Auth Tipi: Authorization: Basic (Mailjet)\n"
                    "   Public Key kutusuna: api\n"
                    "   Secret Key kutusuna: Mailgun API anahtarınız\n\n"
                    "Payload şablonu:\n"
                    "{\n"
                    '  "from": "FROM_NAME <FROM_EMAIL>",\n'
                    '  "to": "RECIPIENT_EMAIL",\n'
                    '  "subject": "SUBJECT_TEXT",\n'
                    '  "html": "HTML_CONTENT"\n'
                    "}\n\n"
                    "NOT: Mailgun'da domain'inizi doğrulamanız ve DNS kayıtlarını\n"
                    "eklemeniz (SPF, DKIM) zorunludur. Ücretsiz planda günlük 100 mail.\n"
                    "EU bölgesi için host: api.eu.mailgun.net kullanın."
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
            {
                "q": "Günlük limit nedir? Nasıl ayarlanır?",
                "a": (
                    "Her gönderici için günlük maksimum gönderim sayısı belirlenebilir.\n\n"
                    "Ayarlama:\n"
                    "  Ayarlar > SMTP / SES / API Göndericiler > Göndericiyi düzenle\n"
                    "  > 'Günlük Limit' alanına değer girin (0 = limitsiz)\n\n"
                    "Nasıl çalışır:\n"
                    "  • Her gönderim öncesi sistem bugün bu sender'dan kaç mail\n"
                    "    gönderildiğini send_log'dan sayar\n"
                    "  • Limit dolduğunda o alıcı 'skipped' olarak loglanır:\n"
                    "    'Günlük limit aşıldı: 80/80 mail gönderildi'\n"
                    "  • UTC gece yarısı otomatik sıfırlanır\n\n"
                    "Önerilen değerler:\n"
                    "  Mailtrap ücretsiz  : 1000/gün\n"
                    "  Brevo ücretsiz     : 300/gün\n"
                    "  Mailjet ücretsiz   : 200/gün\n"
                    "  SendPulse ücretsiz : 500/gün\n"
                    "  Resend ücretsiz    : 100/gün\n\n"
                    "NOT: Limit, warmup planından bağımsız çalışır. İkisi birlikte\n"
                    "aktifse daha kısıtlayıcı olan uygulanır."
                ),
            },
            {
                "q": "🔥 Warmup (Isınma) planı nedir? Nasıl kullanılır?",
                "a": (
                    "Yeni bir e-posta hesabı veya domain açtığınızda, spam filtreleri\n"
                    "ani yüksek hacimli gönderimi şüpheli bulur ve hesabı kısıtlayabilir.\n\n"
                    "Warmup planı, hesabın itibarını kademeli olarak oluşturur:\n"
                    "  Gün 1-3   : 50 mail/gün\n"
                    "  Gün 4-7   : 100 mail/gün\n"
                    "  Gün 8-14  : 200 mail/gün\n"
                    "  Gün 15-21 : 400 mail/gün\n"
                    "  Gün 22+   : Sınırsız (warmup tamamlandı)\n\n"
                    "Aktifleştirme:\n"
                    "  Ayarlar > Gönderici > Düzenle > 🔥 Warmup Planı toggle'ını açın\n"
                    "  Sistem bugünün tarihini başlangıç olarak kaydeder\n\n"
                    "Nasıl çalışır:\n"
                    "  Her gönderim öncesi sistem warmup gününü hesaplar\n"
                    "  O güne ait maksimum mail sayısına ulaşıldığında\n"
                    "  sonraki mailleri 'Warmup limiti aşıldı: X/Y' olarak loglar\n\n"
                    "Warmup tamamlandı mı?\n"
                    "  22. günden itibaren sistem otomatik olarak sınır uygulamaz.\n"
                    "  Toggle'ı kapatmak zorunda değilsiniz — otomatik devre dışı kalır.\n\n"
                    "İPUCU: Warmup süresince listenizin en kaliteli (en aktif)\n"
                    "adreslerine gönderin. Bu, hesap itibarını en hızlı şekilde oluşturur."
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
                    "• Sütun adı boşluk içeriyorsa çalışmayabilir — alt çizgi kullanın\n"
                    "• 'Vars' bölümünde sütun adlarına tıklayarak konu/içeriğe ekleyebilirsiniz"
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
                "q": "🧪 A/B Test nasıl kullanılır?",
                "a": (
                    "Aynı listeye iki farklı konu başlığı göndererek hangisinin daha\n"
                    "iyi çalıştığını test etmenizi sağlar.\n\n"
                    "Kullanım:\n"
                    "  1. Toplu Gönderim sayfasında A Konusunu (ana konu) girin\n"
                    "  2. 'A/B Test' toggle'ını açın — B Konusu alanı belirir\n"
                    "  3. B Konusunu girin\n"
                    "  4. Gönderimi başlatın\n\n"
                    "Nasıl çalışır:\n"
                    "  • Liste otomatik %50 / %50'ye bölünür\n"
                    "  • İlk yarı A konusunu, ikinci yarı B konusunu alır\n"
                    "  • Send-log'da konu alanında [A/B:A] veya [A/B:B] etiketi görünür\n\n"
                    "Sonuçları okumak:\n"
                    "  Gönderim Geçmişi sayfasında [A/B:A] ve [A/B:B] etiketli\n"
                    "  kayıtları konu arama filtresiyle bulabilirsiniz.\n\n"
                    "İPUCU: Cold mail'de konu satırı açılma oranının %80'ini belirler.\n"
                    "A/B testini her kampanyada kullanarak en iyi konuyu bulun."
                ),
            },
            {
                "q": "🔄 Başarısız gönderimler nasıl tekrar denenir?",
                "a": (
                    "Gönderim Geçmişi sayfasında başarısız (kırmızı ✗) kayıtları\n"
                    "toplu olarak tekrar gönderebilirsiniz.\n\n"
                    "Kullanım:\n"
                    "  1. Gönderim Geçmişi sayfasına gidin\n"
                    "  2. Filtre bölümünden bir gönderici seçin\n"
                    "  3. '🔄 Başarısızları Tekrar Dene' butonuna basın\n"
                    "  4. Onay verin — gönderim başlar, sonuç ekranda gösterilir\n\n"
                    "Ne yapar:\n"
                    "  • Seçili gönderici ile tüm 'failed' kayıtları yeniden gönderir\n"
                    "  • Suppression listesi ve günlük limit kontrolü yapılır\n"
                    "  • Limit doluysa o kayıt 'skipped' olur\n"
                    "  • Başarılı olanlar log'da 'sent' durumuna güncellenir\n\n"
                    "Otomatik retry (farklı):\n"
                    "  API ile gönderimde sistem zaten 3 kez otomatik dener:\n"
                    "  • 502, 503, 504 sunucu hataları\n"
                    "  • Bağlantı kopması, timeout\n"
                    "  • Her denemede 1-2-4 saniye bekler (exponential backoff)\n"
                    "  • 3 denemeden sonra 'failed' olarak loglanır — o zaman manuel retry kullanın."
                ),
            },
            {
                "q": "Rol adresi, disposable ve catch-all filtreler ne işe yarar?",
                "a": (
                    "Toplu Gönderim sayfasında MX kontrolünün altında 3 filtre bulunur:\n\n"
                    "🚫 Rol Adresi Filtresi:\n"
                    "  info@, admin@, noreply@, support@, sales@, contact@ gibi\n"
                    "  kişisel olmayan departman adreslerini atlar.\n"
                    "  Bu adresler genellikle düşük açılma oranı verir ve\n"
                    "  şikayet riskini artırır.\n"
                    "  Varsayılan: kapalı (B2B kampanyalarda info@ kaçınılmaz olabilir)\n\n"
                    "🗑️ Geçici E-posta Filtresi:\n"
                    "  mailinator.com, tempmail.com, yopmail.com gibi 100+ tek\n"
                    "  kullanımlık e-posta servisi otomatik engellenir.\n"
                    "  Liste tabanlıdır — DNS sorgusu gerekmez, hızlıdır.\n"
                    "  Varsayılan: açık\n\n"
                    "🎣 Catch-all Domain Tespiti:\n"
                    "  'Her adresi kabul ediyorum' diyen sunucuları tespit eder.\n"
                    "  Rastgele bir adrese SMTP probe atılır; 250 OK dönüyorsa catch-all.\n"
                    "  Bu domainlerdeki adreslerin geçerli posta kutusu olup olmadığı\n"
                    "  bilinemez — gönderim risklidir.\n"
                    "  Uyarı: Port 25 SMTP probe gerektirir — ev interneti bloklar.\n"
                    "  Varsayılan: kapalı (büyük listede yavaşlatır)"
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
            {
                "q": "🗑 Gönderim geçmişini nasıl temizlerim?",
                "a": (
                    "Gönderim Geçmişi sayfasının sağ üst köşesindeki '🗑 Geçmişi Sil'\n"
                    "butonu yalnızca admin rolündeki kullanıcılarda görünür.\n\n"
                    "İki silme seçeneği vardır:\n\n"
                    "Tüm logları sil:\n"
                    "  • Sistemdeki tüm gönderim kayıtlarını kalıcı olarak siler\n"
                    "  • Geri alınamaz — onay kutusunu işaretlemeniz istenir\n\n"
                    "Belirli gönderici loglarını sil:\n"
                    "  • Önce filtreden bir gönderici seçin\n"
                    "  • 'Geçmişi Sil' butonu sadece seçili göndericinin loglarını siler\n\n"
                    "Ne korunur, ne silinir:\n"
                    "  • Suppression listesi ETKİLENMEZ — orada kalan adresler korunur\n"
                    "  • Gönderim kurallarının aralık hesabı ETKİLENİR — son gönderim\n"
                    "    tarihi sıfırlandığı için aynı adreslere tekrar gönderilebilir\n\n"
                    "Ne zaman kullanılır:\n"
                    "  • Test dönemindeki gönderimler gerçek istatistikleri bozuyorsa\n"
                    "  • DB boyutunu küçültmek için (100K+ kayıt sonrası)\n"
                    "  • Eski kampanya verilerini temizlemek için"
                ),
            },
            {
                "q": "🖥 EC2 Auto-Stop (Otomatik Durdurma) nedir? Nasıl kurulur?",
                "a": (
                    "EC2 üzerinde çalışırken gönderim bittiğinde instance'ı otomatik\n"
                    "durdurmak (Stop — Terminate değil) için kullanılır.\n\n"
                    "Kullanım:\n"
                    "  Toplu Gönderim sayfasında 'EC2' kartında instance bilgisi\n"
                    "  görünüyorsa toggle aktiftir. Gönderim bitince EC2 durur.\n"
                    "  EC2 üzerinde değilseniz kart otomatik gizlenir.\n\n"
                    "Kurulum (IAM rolü gerekli):\n"
                    "  1. AWS Console > IAM > Roles > Create role\n"
                    "  2. 'AWS service' > 'EC2' seçin\n"
                    "  3. Aşağıdaki inline policy ekleyin:\n"
                    "     {\n"
                    "       \"Version\": \"2012-10-17\",\n"
                    "       \"Statement\": [{\n"
                    "         \"Effect\": \"Allow\",\n"
                    "         \"Action\": \"ec2:StopInstances\",\n"
                    "         \"Resource\": \"*\"\n"
                    "       }]\n"
                    "     }\n"
                    "  4. Role adı: mailsender-ec2-role (istediğiniz bir isim)\n"
                    "  5. EC2 Console > Instance seç > Actions > Security >\n"
                    "     'Modify IAM role' > Oluşturduğunuz rolü seçin > Save\n\n"
                    "IAM rolü olmadan:\n"
                    "  Toggle görünür ama gönderim bittiğinde hata alınır,\n"
                    "  instance durdurulamaz. Hata send-log'a yazılır.\n\n"
                    "Önemli: Stop = veri ve script korunur. Terminate DEĞİL."
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
                    "Thread sayısını artırırsanız hızlanır ama sunucuyu zorlayabilir.\n"
                    "Maksimum: 20 thread (büyük listeler için 15-20 önerilir).\n\n"
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
                    "──────────────────────────────────────\n"
                    "✗ GEÇERSİZ (is_valid = 0)\n"
                    "──────────────────────────────────────\n"
                    "→ SİZİN YAPMANIZ GEREKEN HİÇBİR ŞEY YOK.\n\n"
                    "Sistem bu adresleri doğrulama sırasında otomatik olarak:\n"
                    "  • Suppression listesine ekledi (kaynak: email_verify)\n"
                    "  • Artık hiçbir gönderimde bu adresler kullanılmayacak\n\n"
                    "──────────────────────────────────────\n"
                    "⚠ RİSKLİ (is_valid = -1)\n"
                    "──────────────────────────────────────\n"
                    "→ GÖNDEREBİLİRSİNİZ ama beklentinizi düşürün.\n\n"
                    "Riskli statüsü verilenler: rol adresleri (info@, admin@),\n"
                    "SPF/DMARC altyapısı zayıf domainler, SMTP belirsiz yanıtlar,\n"
                    "catch-all domainler. Gönderin, bounce oranını izleyin.\n\n"
                    "──────────────────────────────────────\n"
                    "🚫 SUPP. (Suppression'a Eklenenler)\n"
                    "──────────────────────────────────────\n"
                    "→ SİZİN YAPMANIZ GEREKEN HİÇBİR ŞEY YOK.\n\n"
                    "Bu sayaç, doğrulama sırasında suppression listesine eklenen\n"
                    "adreslerin sayısını gösterir. Bunlar bir daha asla gönderilmez.\n\n"
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
                    "     tekrar çalıştırabilirsiniz — DB'den manuel UPDATE gerekir)"
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
                    "  2. Yeni tablo adını girin (öneri otomatik gelir)\n"
                    "  3. 'Riskli adresleri de dahil et' seçeneğini isteğe göre açın\n"
                    "  4. Oluştur'a basın — saniyeler içinde tamamlanır\n\n"
                    "Not: Tablo adı sadece harf, rakam ve _ içerebilir."
                ),
            },
            {
                "q": "⬇ Doğrulama sonuçlarını CSV olarak nasıl indirebilirim?",
                "a": (
                    "Geçmiş İşler tablosunda tamamlanan her işin yanında CSV indirme\n"
                    "butonu bulunur.\n\n"
                    "3 filtre seçeneği vardır:\n\n"
                    "  Sadece Geçerli (is_valid=1):\n"
                    "    Onaylanmış, gönderilebilir adresleri indirir.\n"
                    "    Başka bir sisteme taşımak için idealdir.\n\n"
                    "  Geçerli + Riskli (is_valid=1 ve -1):\n"
                    "    Geçerli adresler + rol adresleri, catch-all ve SMTP belirsizleri.\n"
                    "    Riskli gruba da göndermek istiyorsanız bu seçeneği kullanın.\n\n"
                    "  Tümü:\n"
                    "    Tablodaki tüm satırlar — is_valid değerinden bağımsız.\n"
                    "    Analiz veya yedekleme için kullanın.\n\n"
                    "İndirilen CSV:\n"
                    "  • Tablonun tüm sütunlarını içerir (is_valid, is_valid etiketi dahil)\n"
                    "  • UTF-8 BOM ile kaydedilir — Excel'de Türkçe karakterler düzgün görünür\n"
                    "  • Dosya adı: tabloadı-filtre-tarih.csv formatında"
                ),
            },
            {
                "q": "🔀 Doğrulanmış tabloları birleştirme (Merge) nasıl çalışır?",
                "a": (
                    "Birden fazla doğrulanmış tabloyu tek bir hedef tabloda birleştirmenizi sağlar.\n\n"
                    "Neden kullanılır:\n"
                    "  • Farklı kaynaklardan gelen listeleri tek kampanya için birleştirmek\n"
                    "  • Geçerli adresleri ve riskli adresleri ayrı tablolara toplamak\n"
                    "  • Dağınık küçük tabloları büyük bir listede konsolide etmek\n\n"
                    "Kullanım:\n"
                    "  1. Liste Temizleme sayfasında 'Tablolar Birleştir' bölümüne gidin\n"
                    "  2. Prefix filtresi yazın (ör: mail_list_) ya da boş bırakın (tümü)\n"
                    "  3. Birleştirmek istediğiniz tabloları onay kutusundan seçin\n"
                    "  4. '✓ Geçerli Adresler → Hedef Tablo' alanına hedef tablo adı yazın\n"
                    "  5. İsteğe bağlı: '⚠ Riskli Adresler → Hedef Tablo' için ayrı ad yazın\n"
                    "  6. '🔀 Seçilileri Birleştir' butonuna basın\n\n"
                    "Nasıl çalışır:\n"
                    "  • Seçili tablolardaki is_valid=1 adresler hedef tabloya kopyalanır\n"
                    "  • Riskli hedef tablo girilmişse is_valid=-1 adresler de ayrı tabloya eklenir\n"
                    "  • Hedef tablo yoksa otomatik oluşturulur\n"
                    "  • Mükerrer (duplicate) adresler otomatik atlanır (INSERT IGNORE)\n"
                    "  • Kaynak tablolar silinmez, olduğu gibi korunur\n\n"
                    "Tablo silme:\n"
                    "  Birleştirme panelindeki '🗑 Seçilileri Sil' butonu (sadece admin)\n"
                    "  seçili kullanıcı tablolarını kalıcı olarak siler."
                ),
            },
            {
                "q": "🚫 SMTP Muaf Domain listesi nedir? Nasıl yönetilir?",
                "a": (
                    "SMTP doğrulama modunda bazı domainler port 25 bağlantısını reddeder\n"
                    "veya tüm adreslere 250 OK verir — doğrulama anlamsız olur.\n"
                    "Bu domainler SMTP testinden muaf tutulur, MX kontrolüyle yetinilir.\n\n"
                    "Varsayılan muaf liste (her zaman aktif, değiştirilemez):\n"
                    "  Gmail, Googlemail, Yahoo (tüm ülke uzantıları), Hotmail,\n"
                    "  Outlook, Live, MSN, iCloud, Me, Mac, AOL, ProtonMail,\n"
                    "  Tutanota, Yandex, Mail.ru, GMX, Fastmail ve daha fazlası.\n"
                    "  Toplam 40+ büyük ücretsiz e-posta servisi.\n\n"
                    "Kullanıcı tanımlı muaf domainler (admin ekleyebilir):\n"
                    "  Liste Temizleme sayfası > '🚫 SMTP Muaf Domainler' bölümü\n"
                    "  • Yeni domain ekleyin (firma.com formatında, @ olmadan)\n"
                    "  • Listeden domain silin\n"
                    "  • Değişiklikler 60 saniye içinde aktif olur (önbellek süresi)\n\n"
                    "Ne zaman eklenir:\n"
                    "  • Belirli bir kurumsal domain her SMTP denemeye timeout veriyorsa\n"
                    "  • Sunucu catch-all davranıyorsa ve zaten bilinen geçerli bir domainse\n"
                    "  • SMTP testi o domainleri yanlış 'invalid' işaretliyorsa\n\n"
                    "Not: Yalnızca admin rolü muaf liste güncelleyebilir."
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
            {
                "q": "🕷 Spam tuzağı nedir? Neden tehlikelidir?",
                "a": (
                    "Spam tuzakları, gönderici itibarını test etmek için kullanılan\n"
                    "özel e-posta adresleridir. Bunlara gönderim yapmak hesabınızın\n"
                    "kara listeye alınmasına neden olabilir.\n\n"
                    "4 tür spam tuzağı vardır:\n\n"
                    "🔴 Pristine (Saf) Tuzak:\n"
                    "   Hiçbir zaman gerçek kullanıcıya ait olmamış, yalnızca\n"
                    "   tuzak amacıyla oluşturulmuş adresler.\n"
                    "   Örn: spamtrap.ro, honeypot.net domainleri.\n"
                    "   Buraya gönderim = listeyi scraping ile topladığınızın kanıtı.\n\n"
                    "🟠 Typo Tuzağı:\n"
                    "   Yaygın sağlayıcı adlarının kasıtlı yanlış yazılmış versiyonları.\n"
                    "   Örn: gmali.com, yhaoo.com, hotmai1.com\n"
                    "   Satın alınmış veya form doğrulaması zayıf listelerden gelir.\n\n"
                    "🟡 Recycled (Geri Dönüştürülmüş) Tuzak:\n"
                    "   Eskiden gerçek kullanıcıya ait, uzun süre aktif olmadıktan\n"
                    "   sonra ISP tarafından tuzağa dönüştürülmüş adresler.\n"
                    "   Liste hijyeninin ne kadar önemli olduğunu ölçer.\n\n"
                    "🟢 Honeypot Tuzağı:\n"
                    "   Web formlarındaki gizli alanlara botların doldurduğu adresler.\n"
                    "   UUID formatı veya uzun rastgele string içeren local kısımlar.\n\n"
                    "Sistem tepkisi:\n"
                    "   high güven → is_valid=0, suppression listesine eklenir\n"
                    "   medium güven → risk skoru -30 düşer\n"
                    "   low güven → risk skoru -15 düşer"
                ),
            },
            {
                "q": "↻ Greylisting Retry Kuyruğu nedir? Nasıl çalışır?",
                "a": (
                    "Greylisting, bazı mail sunucularının bilinmeyen IP'lerden gelen\n"
                    "ilk SMTP bağlantısını geçici olarak reddetme yöntemidir.\n"
                    "Meşru sunucular tekrar dener, spam botları denemez.\n\n"
                    "Sorun: Verifier ilk denemede 'unknown' dönen adresler gerçekte\n"
                    "geçerli olabilir — greylisted sunucu nedeniyle yanıt vermemiştir.\n\n"
                    "Çözüm — Retry Kuyruğu:\n"
                    "  SMTP modunda 'unknown' dönen her adres otomatik kuyruğa alınır.\n\n"
                    "Retry zamanlaması:\n"
                    "  1. deneme → 6 saat sonra\n"
                    "  2. deneme → 12 saat sonra (1. başarısızdan itibaren)\n"
                    "  3. deneme → 24 saat sonra (2. başarısızdan itibaren)\n"
                    "  3 denemeden sonra hâlâ bilinmiyorsa → kalıcı 'unknown'\n\n"
                    "Sonuçlar:\n"
                    "  250 (Geçerli) → is_valid=1 güncellenir\n"
                    "  550 (Geçersiz) → is_valid=0, suppression'a eklenir\n"
                    "  Hâlâ bilinmiyor → is_valid=-1 kalır\n\n"
                    "Worker her 5 dakikada bir süresi dolan retry kayıtlarını işler.\n"
                    "Kullanıcının herhangi bir şey yapması gerekmez — otomatik çalışır."
                ),
            },
            {
                "q": "⏰ Otomatik Yeniden Doğrulama Zamanlaması nasıl kurulur?",
                "a": (
                    "Listeler zaman içinde eskir: adresler kapanır, domainler değişir.\n"
                    "90 gün önce doğrulanmış bir listede %5-10 adres artık geçersiz olabilir.\n\n"
                    "Zamanlama kurulumu:\n"
                    "  API: POST /api/verify/schedules\n"
                    "  Body (JSON):\n"
                    "    table_name    : Yeniden doğrulanacak tablo\n"
                    "    email_col     : E-posta kolonu (varsayılan: 'email')\n"
                    "    interval_days : Kaç günde bir (1-365, varsayılan: 90)\n"
                    "    mode          : format | mx | smtp\n"
                    "    target        : all | valid_only | invalid_only | unknown_only\n"
                    "    start_now     : true ise ilk çalışma hemen\n\n"
                    "target seçenekleri:\n"
                    "  all          → Tüm adresleri yeniden doğrula\n"
                    "  valid_only   → Sadece geçerli adresleri kontrol et (eskidiler mi?)\n"
                    "  unknown_only → Sadece belirsiz adresleri tekrar dene\n"
                    "  invalid_only → Sadece geçersizleri dene (nadir değişim)\n\n"
                    "Nasıl çalışır:\n"
                    "  1. Zamanlama geldiğinde target'a göre adresler NULL'a sıfırlanır\n"
                    "  2. Yeni bir doğrulama işi otomatik oluşturulur\n"
                    "  3. Worker normal akışla işlemi çalıştırır\n"
                    "  4. Sonraki çalışma tarihi güncellenir\n\n"
                    "Zamanlama yönetimi:\n"
                    "  GET    /api/verify/schedules           → Tüm zamanlamaları listele\n"
                    "  POST   /api/verify/schedules/<id>/toggle → Aktif/pasif yap\n"
                    "  DELETE /api/verify/schedules/<id>      → Zamanlamayı sil"
                ),
            },
            {
                "q": "💡 did_you_mean (Domain Önerisi) nedir?",
                "a": (
                    "Doğrulama sırasında sistem, yanlış yazılmış domain'ler için\n"
                    "otomatik düzeltme önerisi üretir.\n\n"
                    "Nasıl çalışır:\n"
                    "  1. Önce TYPO_MAP'e bakar (kesin eşleşme)\n"
                    "  2. Bulamazsa Levenshtein mesafesiyle en yakın\n"
                    "     bilinen sağlayıcıyı önerir\n"
                    "  3. Kurumsal domainlere asla öneri yapılmaz (yanlış pozitif riski)\n\n"
                    "Örnekler:\n"
                    "  ali@gmial.com    → did_you_mean: ali@gmail.com\n"
                    "  john@yhaoo.com   → did_you_mean: john@yahoo.com\n"
                    "  user@outlookk.com → did_you_mean: user@outlook.com\n\n"
                    "API yanıtında:\n"
                    "  /api/verify/single?email=ali@gmial.com\n"
                    "  → { did_you_mean: 'ali@gmail.com', status: 'typo_fixed' }\n\n"
                    "Kullanım:\n"
                    "  Web formlarında kullanıcıya 'Bunu mu demek istediniz?' gösterin.\n"
                    "  Toplu doğrulamada typo_fixed statüsündeki adresler\n"
                    "  düzeltilmiş haliyle kaydedilir (is_valid=1)."
                ),
            },
            {
                "q": "⬇ CSV İndirmede hangi segmentler mevcut?",
                "a": (
                    "Doğrulama sonuçlarını 12 farklı segmente göre indirebilirsiniz:\n\n"
                    "is_valid bazlı segmentler:\n"
                    "  valid        → is_valid=1 (geçerli) — gönderime hazır\n"
                    "  invalid      → is_valid=0 (geçersiz) — gönderme\n"
                    "  unknown      → is_valid=-1 (belirsiz/riskli)\n"
                    "  risky        → is_valid IN (1,-1) — geçerli ve riskli birlikte\n"
                    "  all          → Tüm satırlar\n\n"
                    "Statü bazlı segmentler:\n"
                    "  catch_all    → Catch-all sunucu adresler\n"
                    "  spam_trap    → Spam tuzağı tespit edilenler\n"
                    "  no_infra     → SPF/DMARC altyapısı zayıf domainler\n"
                    "  role_account → Rol adresleri (info@, admin@ vb.)\n"
                    "  typo_fixed   → Yazım hatası düzeltilmiş adresler\n\n"
                    "Risk skoru bazlı segmentler:\n"
                    "  do_not_send  → risk_label='do_not_send' (skor 0-29)\n"
                    "  high_risk    → risk_label='high_risk' veya 'do_not_send'\n\n"
                    "Kullanım: GET /api/verify/export-csv?table=TABLO&segment=spam_trap\n"
                    "Dosya adı: tablo-segment-tarih.csv formatında oluşur.\n"
                    "UTF-8 BOM ile kaydedilir — Excel'de Türkçe karakterler düzgün görünür."
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
                    "  URL: https://siteniz.com/sns/ses-notification\n"
                    "  (SubscriptionConfirmation isteği otomatik onaylanır)\n\n"
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
                    "SEBEP: bounce → Bu adrese bir daha GÖNDERMEYİN.\n"
                    "  ses_sns / brevo → Webhook çalışıyor, otomatik eklendi. Hiçbir şey yapma.\n"
                    "  email_verify → Liste temizleme buldu. Doğru karar, bırakın.\n"
                    "  manual → Siz elle eklediniz. Kontrol edin, gerekirse bırakın.\n\n"
                    "SEBEP: complaint → Bu adrese KESİNLİKLE GÖNDERMEYİN.\n"
                    "  Şikayet oranı %0.1'i aşarsa Brevo hesabı askıya alınır.\n"
                    "  Şikayet eden kişileri listeden silmek büyük risk — bırakın.\n\n"
                    "SEBEP: unsubscribe → Bu adrese GÖNDERMEYİN — yasal zorunluluk (GDPR, CAN-SPAM).\n"
                    "  web-form → Kendi sisteminizin unsubscribe linki tıklandı.\n"
                    "  brevo / ses_sns → Servisin kendi çıkma mekanizması tetiklendi.\n\n"
                    "SEBEP: invalid → Bu adrese GÖNDERMEYİN — kesin bounce alırsınız.\n"
                    "  email_verify → Doğrulama işlemi ekledi. Doğru karar, bırakın.\n\n"
                    "SEBEP: manual → Neden eklendiğini hatırlıyorsanız bırakın.\n"
                    "  Yanlışlıkla eklendiyse ve göndermek istiyorsanız silebilirsiniz.\n\n"
                    "GENEL KURAL:\n"
                    "bounce → kalıcı sil   |   complaint → asla gönderme   |\n"
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
                    "  100K suppression kaydı bile gönderim hızını etkilemez."
                ),
            },
            {
                "q": "Unsubscribe (Listeden Çıkma) linki nasıl çalışır? EC2 kapalıyken ne olur?",
                "a": (
                    "Mail altındaki 'Listeden çık' linki, alıcıyı sisteminizin\n"
                    "unsubscribe sayfasına yönlendirir.\n\n"
                    "Normal çalışma:\n"
                    "  Link → https://siteniz.com/unsubscribe?token=XXX\n"
                    "  Token tek kullanımlık ve 30 günlük süre sınırlı.\n"
                    "  Alıcı butona bastığında adres suppression listesine eklenir.\n\n"
                    "EC2 kapalıyken sorun:\n"
                    "  EC2 instance durdurulduğunda siteniz erişilemez olur.\n"
                    "  Alıcı unsubscribe linkine tıklarsa sayfa açılmaz.\n"
                    "  Bu durum yasal uyumluluk açısından risk oluşturur.\n\n"
                    "Çözüm — Harici Unsubscribe Sunucusu:\n"
                    "  Ayarlar > Abonelik > Unsubscribe Sunucu Ayarları bölümünden\n"
                    "  harici bir hosting'e unsub uygulamasının URL ve DB bilgilerini girin.\n\n"
                    "  Kurulum:\n"
                    "  1. Ayrı bir hosting'e (cPanel, VPS) unsub uygulamasını kurun\n"
                    "  2. DB bilgilerini ve App URL'sini sisteme girin\n"
                    "  3. 'Kaydet & Test Et' ile bağlantıyı doğrulayın\n"
                    "  4. Bundan sonra unsubscribe token'ları bu harici sunucuya yönlendirilir\n\n"
                    "  Harici sunucu her zaman açık kalır → EC2 kapalıyken de unsubscribe çalışır."
                ),
            },
        ],
    },
    {
        "id": "bounce_scanner",
        "icon": "📬",
        "title": "Bounce Scanner",
        "questions": [
            {
                "q": "Bounce Scanner nedir ve ne işe yarar?",
                "a": (
                    "Bounce Scanner, SMTP gönderici hesabınızın IMAP gelen kutusuna bağlanarak "
                    "teslim edilemeyen mail (bounce) bildirimlerini otomatik okur ve sınıflandırır.\n\n"
                    "Ne yapar:\n"
                    "  • MAILER-DAEMON, postmaster ve Mail Delivery System kaynaklı hata "
                    "maillerini tarar\n"
                    "  • Her bounce'u e-posta adresi, hata kodu ve açıklamasıyla kaydeder\n"
                    "  • Kalıcı bounce'ları isteğe bağlı olarak Suppression listesine ekler\n"
                    "  • Geçici hatalar ve gönderici sorunları için listeyi kirletmez\n\n"
                    "Ne zaman kullanmalısınız:\n"
                    "  • Toplu gönderim sonrası gelen bounce maillerini toplu işlemek için\n"
                    "  • Listenizdeki geçersiz adresleri otomatik temizlemek için\n"
                    "  • Gönderim itibarınızı korumak için bounce oranını düşürmek amacıyla"
                ),
            },
            {
                "q": "Bounce kategorileri ne anlama gelir?",
                "a": (
                    "Her bounce dört kategoriden birine atanır:\n\n"
                    "❌  Kalıcı (Hard Bounce)\n"
                    "  Adres kalıcı olarak ulaşılamaz. Suppression listesine eklenir,\n"
                    "  bir daha gönderim yapılmaz.\n"
                    "  Örnekler:\n"
                    "    • Kullanıcı bulunamadı (550 No such user)\n"
                    "    • E-posta adresi mevcut değil\n"
                    "    • Hesap kapatılmış\n"
                    "    • Alıcı sunucu spam diye reddetti\n\n"
                    "⚠️  Geçici (Soft Bounce)\n"
                    "  Anlık bir sorun var, adres geçerli olabilir. Suppression'a eklenmez.\n"
                    "  Örnekler:\n"
                    "    • Posta kutusu dolu (452 Mailbox full)\n"
                    "    • Saatlik gönderim limiti aşıldı\n"
                    "    • Sunucu geçici olarak kullanılamıyor\n"
                    "    • Bağlantı zaman aşımı\n\n"
                    "🔒  Gönderen Sorunu\n"
                    "  Alıcı adresi geçerli — sorun bizim gönderimizde. "
                    "Suppression'a eklenmez,\n"
                    "  adres silinmemeli; ancak tekrar denemeden önce sorun giderilmeli.\n"
                    "  Örnekler:\n"
                    "    • DKIM imza doğrulanamadı (signature_incorrect)\n"
                    "    • SPF kaydı başarısız\n"
                    "    • Relay izni yok — gönderici IP engelli\n"
                    "    • SMTP kimlik doğrulama gerekiyor\n"
                    "    • PTR (ters DNS) kaydı eksik\n\n"
                    "  ⚡ Ne yapmalısınız: Alan adınızın DKIM/SPF kayıtlarını kontrol edin,\n"
                    "  gönderici IP'nizin PTR kaydı olduğundan emin olun.\n\n"
                    "🔄  Mail Döngüsü\n"
                    "  Mail kendine geri dönüyor (hop count aşıldı). Routing sorunudur,\n"
                    "  alıcı veya göndericiyle ilgili değil. Suppression'a eklenmez."
                ),
            },
            {
                "q": "Spam reddi neden Kalıcı kategorisinde, Gönderen Sorunu değil?",
                "a": (
                    "İnce ama önemli bir ayrım:\n\n"
                    "  Gönderen Sorunu → Teknik sorun (DKIM, SPF, relay) bizim tarafımızda.\n"
                    "                    Sorunu çözersek aynı adrese gönderebiliriz.\n\n"
                    "  Kalıcı (Spam reddi) → Alıcı sunucu içeriğimizi veya IP'mizi reddetti.\n"
                    "                         Bu adrese tekrar göndermek itibarımızı daha da\n"
                    "                         düşürür.\n\n"
                    "Spam reddi Kalıcı kategorisine girer çünkü:\n"
                    "  • O alıcı sunucusu artık bizden mail almak istemiyor\n"
                    "  • Tekrar denersek spam şikayet oranımız artar\n"
                    "  • Brevo/SES hesabınız risk altına girer\n\n"
                    "DKIM/SPF sorununda ise adres geçerlidir — sorunsuz bir gönderici ile\n"
                    "veya DKIM'i düzelttikten sonra o adrese ulaşabilirsiniz."
                ),
            },
            {
                "q": "Suppression anahtarı ne zaman açık, ne zaman kapalı olmalı?",
                "a": (
                    "Varsayılan: Kapalı\n\n"
                    "Ne zaman AÇIK bırakmalısınız:\n"
                    "  • Listeyi kalıcı olarak temizlemek istiyorsanız\n"
                    "  • Kalıcı bounce adreslerinin bir daha gönderim listesine girmemesini\n"
                    "    istiyorsanız\n"
                    "  • Brevo/SES hesabınızın bounce oranını düşürmeye çalışıyorsanız\n\n"
                    "Ne zaman KAPALI bırakmalısınız:\n"
                    "  • Sadece bounce raporunu görmek istiyorsanız (simülasyon)\n"
                    "  • Yanlış sınıflandırılan adresleri kendiniz inceleyecekseniz\n"
                    "  • İlk taramada sonuçları önce gözden geçirmek istiyorsanız\n\n"
                    "Not: Geçici bounce ve Gönderen Sorunu kategorileri, anahtar açık olsa\n"
                    "bile suppression listesine hiçbir zaman eklenmez."
                ),
            },
            {
                "q": "Tarama sonucunda bounce tespit edilmedi — neden?",
                "a": (
                    "Olası sebepler:\n\n"
                    "  1. Tarama Modu: 'Sadece Okunmamış' seçiliyse ve tüm bounce mailleri\n"
                    "     zaten okunmuşsa sıfır sonuç gelir. 'Tümünü Tara' modunu deneyin.\n\n"
                    "  2. IMAP klasörü: Bounce mailler farklı bir klasöre (Junk, Spam, Trash)\n"
                    "     düşmüş olabilir. Scanner yalnızca INBOX'ı tarar.\n\n"
                    "  3. IMAP sunucu farklı: SMTP sunucusu ile IMAP sunucusu aynı olmayabilir.\n"
                    "     'IMAP Sunucu (opsiyonel)' alanına doğru host'u girin.\n\n"
                    "  4. Bounce mailler otomatik silinmiş: Bazı mail sunucuları bounce\n"
                    "     bildirimlerini belirli süre sonra otomatik siler."
                ),
            },
            {
                "q": "Sonuçları gördükten sonra nasıl suppression'a eklerim?",
                "a": (
                    "Tarama tamamlandıktan sonra sonuçları görmeden hiçbir şey eklenmez\n"
                    "(Otomatik Suppression anahtarı kapalıysa). Akış şöyle:\n\n"
                    "  1. Tara → Sonuçları incele\n"
                    "  2. Hızlı seçim: '☑ Kalıcıları Seç' butonu ile tüm kalıcı bounce'ları\n"
                    "     tek tıkla seç. Ya da her satırda checkbox ile tek tek seç.\n"
                    "  3. Alt çubukta '🚫 Suppression'a Ekle' butonuna tıkla.\n"
                    "  4. Sadece bounce kaydı oluşturmak istersen 'Sadece Bounce Kaydı'nı seç.\n\n"
                    "Gönderen Sorunu kategorisindeki adresler hiçbir zaman suppression'a eklenmez.\n"
                    "Geçici bounce'lar da eklenmez — bunları elle seçsen bile sistem izin vermez."
                ),
            },
            {
                "q": "Kısa Açıklama ve RFC Etiket sütunları ne fark yapar?",
                "a": (
                    "Tabloda iki farklı etiket sütunu var:\n\n"
                    "Kısa Açıklama — Diagnostic-Code metninden üretilir. Hata mesajındaki\n"
                    "anahtar kelimelere (spam, relay, DKIM, mailbox full vb.) göre Türkçe\n"
                    "etiket atanır. Örn: 'Rejected by spam filter' → '🚫 Spam filtresi'\n\n"
                    "RFC Etiket (deneme) — SMTP enhanced status code'dan (5.1.1, 5.7.1 vb.)\n"
                    "RFC 3463 standardına göre üretilir. Pattern listesinden bağımsız,\n"
                    "tamamen kod tabanlı çalışır. Örn: 5.1.1 → '👤 Alıcı adresi bulunamadı [5.1.1]'\n\n"
                    "İkisi yan yana gösterilir. Zamanla hangisinin daha doğru sınıflandırdığı\n"
                    "gözlemlenecek — sonunda en güvenilir olanı kalacak."
                ),
            },
        ],
    },
    {
        "id": "denetim",
        "icon": "📋",
        "title": "Denetim Kaydı (Audit Log)",
        "questions": [
            {
                "q": "Denetim kaydı nedir? Hangi olaylar kaydedilir?",
                "a": (
                    "Sistemdeki tüm kritik işlemler otomatik olarak kaydedilir.\n"
                    "Her kayıt: Tarih/Saat · Kullanıcı adı · İşlem türü · Hedef · IP adresi\n\n"
                    "Kaydedilen olaylar:\n\n"
                    "Gönderici yönetimi:\n"
                    "  • Gönderici eklendi / güncellendi / silindi\n\n"
                    "Gönderim:\n"
                    "  • Toplu gönderim başladı (liste büyüklüğü, gönderici bilgisi)\n"
                    "  • Toplu gönderim bitti (toplam / başarılı / hatalı / atlandı)\n"
                    "  • Excel dosyası yüklendi (tablo adı, satır sayısı)\n\n"
                    "Kullanıcı yönetimi:\n"
                    "  • Kullanıcı oluşturuldu / güncellendi / silindi\n\n"
                    "Suppression:\n"
                    "  • Suppression listesine adres eklendi\n"
                    "  • Domain bloklandı / blok kaldırıldı\n\n"
                    "Liste Temizleme:\n"
                    "  • Doğrulama başladı / iptal edildi\n"
                    "  • Doğrulama sonuçları CSV olarak indirildi\n"
                    "  • Tablolar birleştirildi\n"
                    "  • Tablolar silindi\n"
                    "  • SMTP muaf domain listesi güncellendi\n\n"
                    "Oturum:\n"
                    "  • Giriş yapıldı / çıkış yapıldı"
                ),
            },
            {
                "q": "Denetim kaydını nasıl filtrelerim ve dışa aktarırım?",
                "a": (
                    "Filtreleme:\n"
                    "  • İşlem Türü dropdown'ından belirli bir olay seçin\n"
                    "    (Giriş yapıldı, Gönderici silindi, Doğrulama başladı vb.)\n"
                    "  • Tarih Aralığı: Başlangıç ve bitiş tarihini seçin\n"
                    "  • Her iki filtre birlikte uygulanır\n"
                    "  • 'Temizle' butonu tüm filtreleri sıfırlar\n\n"
                    "CSV Dışa Aktarma:\n"
                    "  '⬇ CSV' butonuna basın — aktif filtrelerle eşleşen tüm kayıtlar\n"
                    "  CSV olarak indirilir. Sütunlar:\n"
                    "  Tarih · Kullanıcı · İşlem · Hedef Tip · Hedef ID · Detay · IP\n\n"
                    "Silme:\n"
                    "  Denetim kayıtları silinemez. Bu tasarım gereği bir güvenlik önlemidir.\n"
                    "  Kayıtlar sistemin yasal ve operasyonel iz bırakma (audit trail) temelidir.\n\n"
                    "Erişim:\n"
                    "  Tüm oturum açmış kullanıcılar denetim kaydını okuyabilir.\n"
                    "  Yalnızca admin, silinmiş kullanıcıların kayıtlarını da görebilir."
                ),
            },
            {
                "q": "IP adresi bilgisi nasıl elde ediliyor? Güvenilir mi?",
                "a": (
                    "Sistem IP adresini şu sırayla okur:\n\n"
                    "  1. X-Forwarded-For başlığı (Cloudflare, nginx proxy, load balancer)\n"
                    "  2. X-Real-IP başlığı (bazı proxy yapılandırmaları)\n"
                    "  3. Flask'ın request.remote_addr değeri (doğrudan bağlantı)\n\n"
                    "Güvenilirlik:\n"
                    "  • Cloudflare arkasındaysanız gerçek kullanıcı IP'si X-Forwarded-For'dan gelir\n"
                    "  • VPN veya proxy kullanan kullanıcılar kendi IP'lerini gizleyebilir\n"
                    "  • Aynı ofis ağından giriş yapanlar aynı IP'yi paylaşabilir\n\n"
                    "Güvenlik notu:\n"
                    "  X-Forwarded-For başlığı manipüle edilebilir.\n"
                    "  Denetim kaydındaki IP bilgisi gösterge niteliğindedir,\n"
                    "  kesin teknik kanıt değildir. Ciddi güvenlik olaylarında\n"
                    "  sunucu access loglarını da inceleyin."
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
                    "  • Tüm HTTP route'ları tanımlar (90+ endpoint)\n"
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
                    "  • 11 katmanlı kontrol: format, did_you_mean, disposable, spam_trap,\n"
                    "    rol, typo, MX (TTL önbellekli), SPF/DMARC, domain yaşı, catch-all, SMTP\n"
                    "  • verify_one() — tek adres doğrular, meta'da did_you_mean + spam_trap alanları döner\n"
                    "  • run_verify_job() — DB'deki işi çalıştırır (thread pool)\n"
                    "  • suggest_domain() — Levenshtein ile akıllı domain önerisi\n\n"
                    "spam_trap.py — Spam tuzağı tespit motoru\n"
                    "  • 4 tür tuzak: pristine, typo_trap, recycled, honeypot\n"
                    "  • high/medium/low güven seviyeleri\n\n"
                    "greylist_retry.py — Greylisting retry kuyruğu\n"
                    "  • unknown SMTP sonuçlarını 6h/12h/24h aralıklarla yeniden dener\n"
                    "  • Başarılı olanlar is_valid=1 güncellenir\n\n"
                    "auto_reverify.py — Otomatik yeniden doğrulama\n"
                    "  • Tablolar için zamanlanmış yeniden doğrulama (kaç günde bir)\n"
                    "  • target: all/valid_only/invalid_only/unknown_only\n\n"
                    "dnsbl_check.py — IP kara liste kontrolü\n"
                    "  • 13 RBL listesi paralel kontrol (Spamhaus, Barracuda, SpamCop vb.)\n"
                    "  • 1 saat TTL önbellek, özel IP'ler otomatik atlanır\n\n"
                    "risk_score.py — Teslimat risk skoru hesaplayıcı\n"
                    "  • 0-100 arası skor: 90+ güvenli, 70-89 düşük risk, 50-69 orta, 30-49 yüksek, 0-29 gönderme\n"
                    "  • Doğrulama sonucunu DB bounce/complaint geçmişiyle birleştirir\n"
                    "  • risk_score ve risk_label kolonları tabloya yazılır\n\n"
                    "worker.py — Arka plan iş işleyici\n"
                    "  • Her çalıştığında: bekleyen mail kuyruğu + doğrulama işleri\n"
                    "  • process_task() — kuyruktan mail gönderir\n"
                    "  • process_verify_job() — doğrulama işini çalıştırır\n"
                    "  • cPanel'de cron ile her 5dk çalıştırılır\n\n"
                    "security.py — Güvenlik yardımcıları\n"
                    "  • rate_limit() decorator — IP tabanlı istek sınırlama\n"
                    "  • safe_identifier() — SQL injection önleme\n\n"
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
                    "  ses_notifications  → AWS SES bounce/complaint bildirimleri\n"
                    "  spam_trap_domains   → Spam tuzağı domain listesi (pristine/typo_trap)\n"
                    "  greylist_retry_queue → Greylisting retry kuyruğu (unknown SMTP sonuçları)\n"
                    "  auto_reverify_schedules → Otomatik yeniden doğrulama zamanlamaları\n\n"
                    "Kullanıcı tabloları (Excel'den oluşturulur):\n"
                    "  • Herhangi bir isim verilebilir (sistem tablosu adları hariç)\n"
                    "  • Sütunlar Excel'den otomatik algılanır\n"
                    "  • Doğrulama sonrası is_valid ve risk_score kolonları eklenir\n"
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
                    "  • Toplu gönderim: 20/dk, tek gönderim: 30/dk\n\n"
                    "Şifre koruması:\n"
                    "  • Gönderici şifreler Fernet (AES-128-CBC) ile şifreli DB'de\n"
                    "  • SECRET_KEY .env'de tutulur, kod içinde yok\n\n"
                    "Webhook güvenliği:\n"
                    "  • Brevo: Basic Authentication (BREVO_WEBHOOK_USER/PASS)\n"
                    "  • SES: HMAC-SHA256 imza doğrulama\n"
                    "  • Her webhook isteği kaynak doğrulamasından geçer"
                ),
            },
            {
                "q": "E-posta doğrulama (verifier.py) 9 katmanı detaylı nasıl çalışır?",
                "a": (
                    "Her adres sırayla bu 11 kontrolden geçer:\n\n"
                    "1. Normalizasyon\n"
                    "   • Küçük harfe çevir\n"
                    "   • Gmail +tag temizleme: ali+promo@gmail.com → ali@gmail.com\n"
                    "   • googlemail.com → gmail.com\n\n"
                    "2. Format (RFC 5321)\n"
                    "   • Türkçe karakter var mı? (ş, ğ, ü → geçersiz)\n"
                    "   • Local kısım max 64 karakter\n"
                    "   • Toplam adres max 254 karakter\n"
                    "   • Regex ile format kontrolü\n\n"
                    "2b. did_you_mean önerisi\n"
                    "   • Format geçerliyse domain Levenshtein ile bilinen sağlayıcılara karşı test edilir\n"
                    "   • gmial.com → gmail.com gibi öneriler meta['did_you_mean'] alanına yazılır\n\n"
                    "3. Disposable tespiti\n"
                    "   • 150+ geçici mail servisi + dinamik DB listesi\n\n"
                    "3b. Spam tuzağı tespiti (spam_trap.py)\n"
                    "   • pristine tuzak domainleri, typo trap, recycled local kalıpları, honeypot bot adresleri\n"
                    "   • high → is_valid=0 + suppression, medium/low → risk skoru düşer\n\n"
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
                    "   • Port 25 → 587 → 465 fallback ile gerçek bağlantı\n"
                    "   • 250 → geçerli, 550 → geçersiz, None → greylisting kuyruğuna ekle\n"
                    "   • Gmail/Yahoo/Outlook ve 40+ büyük servis otomatik atlanır\n\n"
                    "10. Greylisting retry (greylist_retry.py)\n"
                    "   • unknown sonuçlar 6h/12h/24h aralıklarla 3 kez yeniden denenir\n"
                    "   • Worker her 5 dakikada kuyruğu kontrol eder\n\n"
                    "11. TTL önbellek yönetimi\n"
                    "   • MX/SPF/DMARC: 30 dakika, catch-all: 60 dakika\n"
                    "   • Her önbellek max 2000 domain tutar (LRU eviction)"
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
                    '     Body: [{"event":"hard_bounce", "email":"ali@firma.com", ...}]\n'
                    "  5. webhook_brevo() fonksiyonu isteği alır\n"
                    "  6. Basic Auth kontrolü (BREVO_WEBHOOK_USER/PASS)\n"
                    "  7. event='hard_bounce' → _webhook_add_suppression() çağrılır\n"
                    "  8. db().add_to_suppression('ali@firma.com', 'bounce', source='brevo')\n"
                    "  9. Artık o adrese bir daha gönderim yapılmaz\n\n"
                    "AWS SES akışı:\n"
                    "  SES → SNS Topic → HTTPS Subscription → /sns/ses-notification\n"
                    "  Subscription Confirmation otomatik onaylanır\n"
                    "  Bounce: sadece Permanent bounce suppression'a eklenir (Transient eklenmez)\n"
                    "  Complaint: her zaman eklenir\n"
                    "  Delivery: ses_notifications tablosuna loglanır (suppression'a eklenmez)"
                ),
            },
        ],
    },
    {
        "id": "dnsbl",
        "icon": "🛡",
        "title": "IP Kara Liste Kontrolü (DNSBL)",
        "questions": [
            {
                "q": "DNSBL / RBL nedir? Neden önemlidir?",
                "a": (
                    "DNSBL (DNS-based Blackhole List) veya RBL (Realtime Blacklist),\n"
                    "spam gönderen IP adreslerini takip eden DNS tabanlı kara listelerdir.\n\n"
                    "Neden önemlidir:\n"
                    "  • Çoğu büyük mail sunucusu (Gmail, Outlook, Hotmail) gelen her\n"
                    "    mailing IP'sini DNSBL listelerine karşı kontrol eder\n"
                    "  • Listelenen bir IP'den gelen mailler otomatik spam klasörüne düşer\n"
                    "    veya tamamen reddedilir\n"
                    "  • Bounce oranı %20-40'a çıkabilir — hesabınız risk altına girer\n\n"
                    "Sistem 13 farklı RBL listesini paralel olarak kontrol eder:\n"
                    "  🔴 Critical: Spamhaus ZEN, SBL, XBL; Barracuda BRBL\n"
                    "  🟠 High: Spamhaus PBL, SpamCop, SORBS spam\n"
                    "  🟡 Medium: SORBS birleşik, UCEProtect L1/L2, JustSpam\n"
                    "  🟢 Low: Manitu NiX Spam\n\n"
                    "Sonuç için severity seviyeleri:\n"
                    "  critical → Hemen aksiyon alın, gönderimi durdurun\n"
                    "  high     → Önemli sorun, listeye giriş sebebini araştırın\n"
                    "  medium   → Dikkat edin, izleyin\n"
                    "  low      → Bilgi amaçlı, büyük servisler bu listeyi kullanmaz\n"
                    "  clean    → Hiçbir listede değil, temiz"
                ),
            },
            {
                "q": "Gönderici SMTP sunucusunu DNSBL'de nasıl kontrol ederim?",
                "a": (
                    "API ile kontrol:\n\n"
                    "  Yöntem 1 — Gönderici ID ile:\n"
                    "    GET /api/senders/<sender_id>/dnsbl\n"
                    "    → Gönderici SMTP sunucusunu otomatik çözer ve kontrol eder\n\n"
                    "  Yöntem 2 — SMTP hostname ile:\n"
                    "    POST /api/senders/dnsbl-check\n"
                    "    Body: { smtp_host: 'mail.example.com' }\n\n"
                    "  Yöntem 3 — Direkt IP ile:\n"
                    "    POST /api/senders/dnsbl-check\n"
                    "    Body: { ip: '1.2.3.4' }\n\n"
                    "Yanıt yapısı:\n"
                    "  ip         → Kontrol edilen IP adresi\n"
                    "  listed     → true/false — kara listede mi?\n"
                    "  severity   → critical/high/medium/low/clean\n"
                    "  hits       → Listelenen RBL'ler (ad, yanıt kodu, şiddet)\n"
                    "  clean      → Temiz bulunan RBL'ler\n"
                    "  cached     → true ise önbellekten geldi (1 saat TTL)\n"
                    "  checked_at → Kontrol zamanı (UTC)"
                ),
            },
            {
                "q": "IP kara listeye düştü, ne yapmalıyım?",
                "a": (
                    "Hangi listeye düştüğünüze göre aksiyon farklıdır:\n\n"
                    "🔴 Spamhaus SBL/ZEN (critical):\n"
                    "  → spamhaus.org/lookup adresinden IP'yi araştırın\n"
                    "  → Listeden çıkarma (delist) talebinde bulunun\n"
                    "  → Genellikle 1-3 iş günü sürer\n"
                    "  → Bounce kaynağını temizlemeden delist kalıcı olmaz\n\n"
                    "🟠 Spamhaus PBL (ISP dinamik IP):\n"
                    "  → PBL listesi dinamik/ev IP'leri kapsar\n"
                    "  → Çözüm: Dedicated server IP veya SMTP relay kullanın\n"
                    "  → Kendi IP'niz değilse ISP'den statik IP talep edin\n\n"
                    "🟠 Barracuda BRBL:\n"
                    "  → barracudacentral.org/lookups üzerinden delist talep\n"
                    "  → E-posta ile doğrulama gerektirebilir\n\n"
                    "🟠 SpamCop:\n"
                    "  → SpamCop listesi 24-48 saat içinde otomatik temizlenir\n"
                    "  → Aktif spam gönderimi durdurulursa liste otomatik düşer\n\n"
                    "Genel aksiyon planı:\n"
                    "  1. Gönderimleri hemen durdurun\n"
                    "  2. Son 48 saatin bounce raporunu inceleyin\n"
                    "  3. Şikayet yaratan adresleri suppression'a ekleyin\n"
                    "  4. Liste temizleme yapın (MX modu)\n"
                    "  5. Delist talebinde bulunun\n"
                    "  6. 24 saat bekleyip tekrar DNSBL kontrolü yapın"
                ),
            },
            {
                "q": "Ne sıklıkla DNSBL kontrolü yapmalıyım?",
                "a": (
                    "Önerilen kontrol sıklığı:\n\n"
                    "  Düzenli kullanımda: Haftada 1 kez\n"
                    "  Yüksek hacimli kampanya öncesi: Her kampanya öncesi\n"
                    "  Bounce oranı arttığında: Hemen kontrol edin\n"
                    "  Yeni IP/domain ile başlarken: Günlük kontrol (ilk 2 hafta)\n\n"
                    "Önbellek bilgisi:\n"
                    "  Sistem her IP sonucunu 1 saat önbellekte tutar.\n"
                    "  Aynı IP'yi 1 saat içinde tekrar sorgulamak önbellekten döner\n"
                    "  (cached: true) — gereksiz DNS trafiği önlenir.\n\n"
                    "Özel IP kontrolü:\n"
                    "  192.168.x.x, 10.x.x.x gibi özel/loopback IP'ler\n"
                    "  DNSBL kontrolünden otomatik muaf tutulur.\n"
                    "  Bu IP'ler zaten dış ağda görünmez."
                ),
            },
        ],
    },
    {
        "id": "api_dogrulama",
        "icon": "🔌",
        "title": "Tek E-posta Doğrulama API'si",
        "questions": [
            {
                "q": "/api/verify/single endpoint'i nedir? Nasıl kullanılır?",
                "a": (
                    "Tek bir e-postayı gerçek zamanlı olarak doğrulayan REST API endpoint'idir.\n"
                    "Web formlarına, CRM sistemlerine veya herhangi bir uygulamaya entegre edilebilir.\n\n"
                    "İstek:\n"
                    "  GET /api/verify/single?email=ali@gmail.com&mode=mx\n\n"
                    "Parametreler:\n"
                    "  email  (zorunlu) — Doğrulanacak e-posta adresi\n"
                    "  mode   (opsiyonel, varsayılan 'mx'):\n"
                    "    format → Sadece yazım kontrolü (anlık)\n"
                    "    mx     → Format + DNS MX sorgusu (önerilen)\n"
                    "    smtp   → MX + gerçek SMTP bağlantısı (yavaş, en doğru)\n\n"
                    "Yanıt alanları:\n"
                    "  email           → Normalize edilmiş (düzeltilmiş) adres\n"
                    "  original        → Kullanıcının girdiği orijinal adres\n"
                    "  status          → valid / invalid / catch_all / typo_fixed / spam_trap vb.\n"
                    "  is_valid        → 1 (geçerli) / 0 (geçersiz) / -1 (riskli)\n"
                    "  did_you_mean    → Yazım hatası önerisi (ör: ali@gmail.com) veya null\n"
                    "  is_role         → Rol adresi mi? (true/false)\n"
                    "  is_free         → Ücretsiz sağlayıcı mı? (true/false)\n"
                    "  is_catchall     → Catch-all sunucu mu? (true/false)\n"
                    "  has_spf         → SPF kaydı var mı? (true/false)\n"
                    "  has_dmarc       → DMARC kaydı var mı? (true/false)\n"
                    "  spam_trap       → Tuzak tipi veya null\n"
                    "  risk_score      → 0-100 arası teslimat risk skoru\n"
                    "  risk_label      → safe / low_risk / medium_risk / high_risk / do_not_send\n"
                    "  send_recommended → Gönderim önerilir mi? (true/false)\n"
                    "  executiontime   → İşlem süresi (saniye)"
                ),
            },
            {
                "q": "did_you_mean alanını web formumda nasıl kullanırım?",
                "a": (
                    "Kullanıcı e-posta adresini girerken (veya submit sonrası)\n"
                    "/api/verify/single?email=ADRES&mode=format çağrısı yapın.\n\n"
                    "Yanıtta did_you_mean null değilse:\n"
                    "  Kullanıcıya öneri gösterin:\n"
                    "  'Bunu mu demek istediniz: ali@gmail.com?'\n\n"
                    "JavaScript örneği:\n"
                    "  const res = await fetch('/api/verify/single?email=' + encodeURIComponent(email) + '&mode=format')\n"
                    "  const data = await res.json()\n"
                    "  if (data.data?.did_you_mean) {\n"
                    "    showSuggestion(data.data.did_you_mean)\n"
                    "  }\n\n"
                    "mode=format kullanın (format kontrolü + typo önerisi anlık gelir,\n"
                    "DNS sorgusu yapmaz, gecikme ~5ms). Kullanıcı formdayken\n"
                    "gerçek zamanlı öneri için idealdir.\n\n"
                    "Öneri mantığı:\n"
                    "  • TYPO_MAP'te bilinen hatalar anında eşleşir\n"
                    "  • Bilinmeyen hatalar Levenshtein mesafesi ≤ 2 ise önerilir\n"
                    "  • Kurumsal domainlere (company.com) asla öneri yapılmaz"
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
            {
                "q": "Excel dosyası yüklenmiyor veya sütunlar tanınmıyor.",
                "a": (
                    "Yaygın sorunlar ve çözümler:\n\n"
                    "1) Dosya formatı\n"
                    "   • Desteklenen: .xlsx ve .xls\n"
                    "   • .csv, .ods, .numbers desteklenmez\n"
                    "   • Google Sheets'ten 'Excel olarak indir' (.xlsx) seçeneğini kullanın\n\n"
                    "2) Sütun adları\n"
                    "   • İlk satır mutlaka başlık satırı olmalı\n"
                    "   • Birleşik (merged) hücreler sorun çıkarabilir\n"
                    "   • Özel karakterlerden kaçının: /, \\, (, ), ?\n\n"
                    "3) Şifreli/korumalı Excel\n"
                    "   • Dosya şifreli veya salt-okunur modundaysa açılamaz\n"
                    "   • Excel'de 'Korumayı Kaldır' yapın, tekrar deneyin\n\n"
                    "4) Büyük dosyalar\n"
                    "   • 100K+ satır için import süresi uzayabilir\n"
                    "   • cPanel'de upload timeout yaşanıyorsa dosyayı bölerek yükleyin"
                ),
            },
        ],
    },
]
