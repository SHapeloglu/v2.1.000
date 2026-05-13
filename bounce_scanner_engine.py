"""
bounce_scanner_engine.py — MailSender Pro Bounce Tarama Motoru
==============================================================
IMAP kutusundan alınan ham e-posta metinlerini analiz ederek
bounce tipini, kategorisini, hata açıklamasını ve etiketini döner.

Ana fonksiyon:
    parse_bounce(icerik: str) -> dict | None

Dönen dict alanları:
    email            — Hatalı alıcı adresi
    bounce_tipi      — 'kalici' | 'gecici'
    hata_kodu        — SMTP status kodu (ör: "5.1.1")
    aciklama         — Sunucu metni + Türkçe etiket birleşimi
    etiket           — MESAJ_PATTERNS'dan üretilen kısa Türkçe etiket + ikon
    rfc_etiket       — RFC 3463 enhanced status code tablosundan otomatik etiket
    diagnostic       — Ham Diagnostic-Code satırı
    kategori         — 'kalici' | 'gecici' | 'gonderici_sorunu' | 'mail_loop' | 'internal_domain'
    suppression_ekle — bool; True ise suppression listesine eklenmeli

Kategori açıklamaları:
    kalici           — Alıcı adresi kalıcı olarak ulaşılamaz; suppression'a eklenir
    gecici           — Geçici hata (rate limit, dolu kutu vb.); eklenmez
    gonderici_sorunu — DKIM/SPF/relay hatası; alıcı geçerli, bizim tarafımız sorunlu; eklenmez
    mail_loop        — Routing döngüsü; teknik sorun, alıcıyla ilgili değil; eklenmez
    internal_domain  — .local/.lan gibi dahili domain; internet üzerinden ulaşılamaz; eklenmez

Sınıflandırma katmanları (öncelik sırasıyla):
    1. _is_real_bounce()         — DSN sinyalleri yoksa bounce değil (oto-yanıt vb.)
    2. _is_internal_domain()     — Dahili domain kontrolü
    3. GONDERICI_SORUNU_PATTERNS — DKIM/SPF/relay/auth → gonderici_sorunu
    4. GECICI_OVERRIDE_PATTERNS  — Rate limit/kota → gecici (Action:failed olsa bile)
    5. Action/Status header'ı    — failed → kalici, delayed → gecici
    6. _aciklama_from_body()     — Diagnostic-Code + MESAJ_PATTERNS → açıklama + etiket
    7. _enhanced_status_etiket() — RFC 3463 tablosu → rfc_etiket (ikinci sütun, deneme)

511 gerçek EML üzerinde test edildi — %100 parse, %99 etiket kapsama.
"""

import re
from datetime import datetime

# ── Hata kodu → Türkçe açıklama ───────────────────────────────────────────
STATUS_LABELS = {
    # Kalıcı — 5.x.x
    "5.0.0":   "Genel kalıcı hata",
    "5.0.350": "Exchange genel hata",
    "5.1.1":   "Alıcı bulunamadı",
    "5.1.2":   "Alan adı bulunamadı",
    "5.1.10":  "Alıcı bulunamadı (Exchange)",
    "5.2.1":   "Hesap devre dışı veya silinmiş",       # YENİ — Gmail inactive
    "5.2.2":   "Posta kutusu dolu (kalıcı)",
    "5.3.0":   "Posta sistemi hatası",
    "5.4.1":   "Erişim reddedildi",
    "5.4.4":   "Alan adı bulunamadı",
    "5.4.14":  "Mail döngüsü (hop count aşıldı)",       # suppression'a EKLEME
    "5.4.310": "DNS kaydı yok",
    "5.4.316": "MX kaydı hatası",
    "5.5.0":   "Posta kutusu mevcut değil",
    "5.5.1":   "Geçersiz komut (mail sistemi uyumsuz)",  # YENİ
    "5.5.4":   "Geçersiz komut",
    "5.6.0":   "İleti format/encoding hatası",           # YENİ — içerik sorunu
    "5.7.1":   "Spam filtresi / İzin reddedildi",
    "5.7.13":  "Gönderen doğrulaması başarısız",
    "5.7.64":  "TLS/Sertifika doğrulama hatası",         # YENİ — EmptyCertificate
    "5.7.124": "Gönderen politikası reddetti",
    "5.7.133": "Dağıtım listesi kısıtlaması",
    "5.7.193": "Spam engeli",

    # Geçici — 4.x.x
    "4.0.0":   "Geçici genel hata",
    "4.1.1":   "Geçici — doğrulanamayan adres",          # YENİ — disabled/full olabilir
    "4.1.8":   "Geçici — domain bulunamadı",             # YENİ — DNS geçici sorun
    "4.2.1":   "Geçici — posta kutusu devre dışı",
    "4.2.2":   "Geçici — posta kutusu dolu",
    "4.3.0":   "Geçici — sistem hatası",
    "4.3.1":   "Geçici — mail sistemi hatası (retry)",   # YENİ
    "4.4.1":   "Geçici — bağlantı kurulamadı",
    "4.4.2":   "Geçici — bağlantı kesildi",
    "4.4.3":   "Geçici — alan adı bulunamadı",
    "4.4.4":   "Geçici — yönlendirme sorunu",
    "4.7.1":   "Geçici — izin reddedildi",
}


# ── RFC 3463 Enhanced Status Code tablosu ────────────────────────────────
ENHANCED_STATUS = {
    "5.1.0": ("Alıcı adresi belirsiz",           "📬"),
    "5.1.1": ("Alıcı adresi bulunamadı",          "👤"),
    "5.1.2": ("Alan adı geçersiz",                "🌐"),
    "5.1.3": ("Adres sözdizimi hatası",           "⚠️"),
    "5.1.4": ("Posta kutusu belirsiz",            "📬"),
    "5.1.6": ("Adres değişmiş",                   "🔀"),
    "5.1.7": ("Gönderici adresi geçersiz",        "⚠️"),
    "5.1.8": ("Gönderici adresi reddedildi",      "🚫"),
    "5.2.0": ("Posta kutusu hatası",              "📦"),
    "5.2.1": ("Posta kutusu devre dışı",          "🔒"),
    "5.2.2": ("Posta kutusu dolu",                "📦"),
    "5.2.3": ("Mesaj boyutu aşıldı",             "📏"),
    "5.3.1": ("Disk dolu",                        "💾"),
    "5.3.4": ("Mesaj boyutu limiti",              "📏"),
    "5.4.1": ("Alıcı adresi reddedildi",          "🚫"),
    "5.4.2": ("Bağlantı kurulamadı",              "🔌"),
    "5.4.3": ("Routing döngüsü",                  "🔄"),
    "5.4.4": ("Sunucu bulunamadı",                "🌐"),
    "5.4.6": ("Routing döngüsü",                  "🔄"),
    "5.4.14": ("Mail döngüsü (Hop count)",         "🔄"),
    "5.4.310": ("Alan adı mevcut değil",           "🌐"),
    "5.4.316": ("Mesaj süresi doldu",              "⏰"),
    "5.7.13": ("Posta kutusu devre dışı",          "🔒"),
    "5.7.124": ("Dağıtım listesi kısıtlı",        "🏢"),
    "5.7.133": ("Grup gönderici yetkisi yok",      "🏢"),
    "5.7.193": ("Grup üyesi değil",                "👥"),
    "5.1.10": ("Alıcı Exchange'de bulunamadı",    "👤"),
    "5.5.1": ("Geçersiz komut",                   "⚙️"),
    "5.5.2": ("Sözdizimi hatası",                 "⚙️"),
    "5.5.4": ("Geçersiz parametre",               "⚙️"),
    "5.6.0": ("İçerik hatası",                    "📄"),
    "5.6.1": ("Medya tipi desteklenmiyor",        "📄"),
    "5.7.0": ("Güvenlik politikası reddi",        "🔐"),
    "5.7.1": ("Erişim reddedildi",                "🚫"),
    "5.7.7": ("İçerik reddedildi",                "🚫"),
    "5.7.8": ("Kimlik doğrulama hatası",          "🔑"),
    "5.7.9": ("Kimlik doğrulama gerekli",         "🔑"),
    "4.1.1": ("Alıcı geçici erişilemez",          "⏳"),
    "4.1.2": ("Alan adı geçici erişilemez",       "⏳"),
    "4.2.0": ("Posta kutusu geçici erişilemez",   "⏳"),
    "4.2.1": ("Posta kutusu geçici devre dışı",   "⏳"),
    "4.2.2": ("Posta kutusu dolu (geçici)",       "📦"),
    "4.3.1": ("Disk geçici dolu",                 "💾"),
    "4.4.1": ("Bağlantı kurulamadı (geçici)",     "🔌"),
    "4.4.2": ("Bağlantı zaman aşımı",            "🔌"),
    "4.7.1": ("Erişim reddedildi (geçici)",       "⏳"),
}

def _enhanced_status_etiket(icerik: str, status: str) -> str:
    """RFC 3463 enhanced status code'u bulup ENHANCED_STATUS tablosundan etiket döner.

    Önce Status header'ına, sonra Diagnostic-Code ve gövde içindeki 'x.y.z' formatındaki
    kodlara bakarak eşleşen ilk kodu tabloda arar. Tam eşleşme yoksa prefix (5.7.x) ile
    en yakın kaydı döner.

    Döner: 'ikon label [x.y.z]' formatında string, bulunamazsa boş string.
    Bu alan tabloda ikinci sınıflandırma sütunu olarak gösterilir (deneme aşaması).
    """
    codes = []
    if status and re.match(r"\d\.\d", status):
        codes.append(status)
    for pat in [
        r"Diagnostic-Code:\s*\S+;\s*\d{3}[\s\-]+(\d\.\d+\.\d+)",
        r"said:\s+\d{3}[\s\-]+(\d\.\d+\.\d+)",
        r"\b(\d\.[1-9]\d?\.\d{1,3})\b",
    ]:
        for m in re.finditer(pat, icerik, re.IGNORECASE):
            c = m.group(1)
            if c not in codes:
                codes.append(c)

    for code in codes:
        if code in ENHANCED_STATUS:
            label, ikon = ENHANCED_STATUS[code]
            return f"{ikon} {label} [{code}]"
        parts = code.split(".")
        if len(parts) >= 2:
            prefix = parts[0] + "." + parts[1] + "."
            for k, (lbl, ico) in ENHANCED_STATUS.items():
                if k.startswith(prefix):
                    return f"{ico} {lbl} [{code}]"
    return ""

# ── Genel kodlar için mesaj gövdesinden açıklama türet ───────────────────
# (status=5.0.0 gibi jenerik kodlarda asıl sebep plain-text'te gizlidir)
# Sırayla kontrol edilir, ilk eşleşen kullanılır.
MESAJ_PATTERNS = [
    # (pattern, kısa_etiket, ikon)
    # ── Gönderici taraflı limitler ───────────────────────────────────────
    (r'max\s+emails?\s+per\s+hour',              'Saatlik limit aşıldı',            '⏱'),
    (r'exceeded\s+the\s+max\s+emails?',          'Saatlik limit aşıldı',            '⏱'),
    (r'per\s+hour.{0,40}allowed',                'Saatlik limit aşıldı',            '⏱'),
    (r'rate\s+limit',                            'Hız sınırı aşıldı',               '⏱'),
    (r'too\s+many\s+messages?\s+per',            'Hız sınırı aşıldı',               '⏱'),
    (r'message\s+discarded',                     'Mesaj silindi',                    '🗑'),

    # ── Kimlik doğrulama / relay sorunları (gönderici taraflı) ───────────
    (r'smtp\s+auth',                             'SMTP auth gerekli',                '🔑'),
    (r'requires\s+authentication',               'SMTP auth gerekli',                '🔑'),
    (r'please\s+(turn\s+on|enable)\s+smtp',      'SMTP auth gerekli',                '🔑'),
    (r'not\s+permitted\s+to\s+relay',            'Relay izni yok',                  '🚧'),
    (r'relay\s+not\s+permitted',                 'Relay izni yok',                  '🚧'),
    (r'relay\s+(access\s+)?denied',              'Relay izni yok',                  '🚧'),

    # ── DKIM / SPF / imza hataları (gönderici taraflı) ───────────────────
    (r'dkim.{0,30}(invalid|incorrect|fail)',     'DKIM hatası',                     '🔏'),
    (r'signature_incorrect',                     'DKIM hatası',                     '🔏'),
    (r'spf.{0,30}fail',                          'SPF hatası',                      '🔏'),
    (r'dmarc.{0,30}fail',                        'DMARC hatası',                    '🔏'),

    # ── Posta kutusu sorunları (spesifik — genel pattern'lardan önce) ──────
    (r'mailbox\s+unavailable',                   'Posta kutusu yok/kullanılamıyor', '📭'),
    (r'mailbox\s+(is\s+)?full',                  'Posta kutusu dolu',               '📦'),
    (r'over\s+quota',                            'Kota doldu',                      '📦'),
    (r'quota\s+exceeded',                        'Kota doldu',                      '📦'),
    (r'QuotaExceeded',                            'Kota doldu',                      '📦'),
    (r'not\s+local',                             'Yerel hesap değil',               '📭'),

    # ── Geçici / yeniden deneniyor ────────────────────────────────────────
    (r'warning\s+only',                          'Geçici — yeniden deneniyor',      '⏳'),
    (r'will\s+be\s+retried',                    'Geçici — yeniden deneniyor',      '⏳'),
    (r'unverified\s+address',                    'Adres doğrulanamadı',             '❓'),

    # ── Alıcı yok / adres geçersiz ───────────────────────────────────────
    (r'no\s+such\s+(user|address|recipient)',    'Kullanıcı bulunamadı',            '👤'),
    (r'user\s+unknown',                          'Kullanıcı bulunamadı',            '👤'),
    (r'böyle\s+bir\s+kimse\s+yok',              'Kullanıcı bulunamadı',            '👤'),
    (r'address\s+unknown',                       'Kullanıcı bulunamadı',            '👤'),
    (r'RecipientNotFound',                        'Alıcı bulunamadı',                '👤'),
    (r'unrouteable\s+address',                   'Yönlendirilemeyen adres',         '🔀'),
    (r'does\s+not\s+exist',                      'Adres mevcut değil',              '❌'),
    (r'ADDRESS\s+DOES\s+NOT\s+EXIST',            'Adres mevcut değil',              '❌'),
    (r'NoSuchUser',                               'Kullanıcı bulunamadı',            '👤'),
    (r'No\s+Such\s+Alastyr\s+User',             'Kullanıcı bulunamadı',            '👤'),
    (r'no\s+longer\s+accepts?\s+mail',           'Adres mail almıyor',              '🚫'),
    (r'account\s+(has\s+been\s+)?(disabled|closed|deleted)', 'Hesap kapatılmış', '🔒'),
    (r'Disabled\s+recipient',                    'Adres devre dışı',                '🔒'),
    (r'retry\s+timeout\s+exceeded',             'Adres geçici olarak erişilemez',  '⏳'),
    (r'invalid\s+(recipient|address|mailbox)',   'Geçersiz adres',                  '⚠️'),
    (r'Requested\s+action\s+not\s+taken',       'İşlem gerçekleştirilemedi',       '⚠️'),
    # Spesifik reddedilme türleri — genel "Recipient address"tan önce gelmeli
    (r'Recipient\s+address.{0,30}Access\s+denied.{0,80}(EXOSmtp|aka\.ms)', 'Microsoft politikası reddi', '🏢'),
    (r'Recipient\s+address.{0,30}Access\s+denied',  'Erişim reddedildi',           '🚫'),
    (r'Access\s+denied.{0,80}(EXOSmtp|aka\.ms)',    'Microsoft politikası reddi',  '🏢'),
    (r'Recipient\s+address',                     'Alıcı adresi sorunu',             '📬'),
    (r'^Recipient$',                              'Alıcı adresi sorunu',             '📬'),
    (r'^Recipient\b',                             'Alıcı adresi sorunu',             '📬'),
    (r'Sender\s+address',                        'Gönderici adresi sorunu',         '📬'),
    (r'address\s+rejected',                      'Adres reddedildi',                '🚫'),

    # ── Spam / kara liste ─────────────────────────────────────────────────
    (r'blacklist',                               'Kara listede',                    '⛔'),
    (r'spam',                                    'Spam filtresi',                   '🚫'),
    (r'policy\s+violation',                      'Politika ihlali',                 '📋'),
    (r'blocked',                                 'Engellendi',                      '⛔'),
    (r'rejected',                                'Reddedildi',                      '✗'),

    # ── Alan adı / sunucu sorunları ───────────────────────────────────────
    (r'domain\s+not\s+found',                   'Alan adı bulunamadı',             '🌐'),
    (r'host\s+(not\s+found|unknown)',            'Sunucu bulunamadı',               '🌐'),
    (r'mx\s+record',                             'MX kaydı hatası',                 '🌐'),
    (r'connection\s+(refused|timeout)',          'Bağlantı hatası',                 '🔌'),

    # ── Sunucu / bağlantı sorunları ─────────────────────────────────────
    (r'lost\s+connection',                       'Bağlantı kesildi',                '🔌'),
    (r'Name\s+service\s+error',                 'DNS çözümlenemedi',               '🌐'),
    (r'domain.{0,30}not\s+found',               'Alan adı bulunamadı',             '🌐'),
    (r'domain.{0,30}suspended',                  'Alan adı askıya alındı',           '🌐'),
    (r'PTR\s+record|does\s+not\s+have\s+a\s+PTR|IP\s+address.{0,30}does\s+not', 'PTR kaydı eksik', '🔧'),
    (r'unauthenticated',                         'Kimlik doğrulanamadı',            '🔑'),
    (r'UnifiedGroupAgent',                       'Grup üyesi değil',                '👥'),
    (r'Insufficient\s+system\s+storage',        'Sunucu disk dolu',                '💾'),
    (r'currently\s+(suspended|unavailable)',     'Geçici olarak kullanılamıyor',    '⏳'),
    (r'is\s+currently',                          'Geçici olarak kullanılamıyor',    '⏳'),
    (r'out\s+of\s+storage',                     'Depolama alanı doldu',            '📦'),
    (r'user\s+is\s+over',                       'Kota aşıldı',                     '📦'),
    (r'no\s+mailbox\s+by\s+that\s+name',       'Posta kutusu yok',                '📭'),
    (r'could\s+not\s+deliver\s+mail\s+to',    'Teslim edilemedi',                '📬'),
    (r'no\s+valid\s+recipients',                'Geçerli alıcı yok',               '👤'),
    (r'Invalid\s+content',                       'Geçersiz içerik',                 '📄'),
    (r'Relay\s+access',                          'Relay izni yok',                  '🚧'),
    (r'DKIM.{0,30}(validat|problem|encounter)',  'DKIM doğrulama hatası',           '🔏'),
    (r'No\s+Such.{0,10}User',                   'Kullanıcı bulunamadı',            '👤'),
    (r'email\s+account.{0,40}not\s+exist',      'Adres mevcut değil',              '❌'),
    (r'email\s+account.{0,30}(tried|reach)',    'Hesap erişilemiyor',              '🔒'),
    (r'detected\s+(that|as)',                    'Şüpheli gönderim tespit edildi',  '⚠️'),

    # ── Yetki / kısıtlama ────────────────────────────────────────────────
    (r'you\s+are\s+not\s+allowed\s+to\s+send',  'Gönderme yetkisi yok',         '🚫'),
    (r'trying\s+to\s+use\s+me',                'Relay izni yok',                  '🚧'),
    (r'no\s+mail\s+servers.{0,30}could\s+be\s+reached', 'Mail sunucusuna ulaşılamıyor', '🌐'),
    (r'connect\s+to',                            'Sunucuya bağlanılamadı',          '🔌'),
    (r'RecipNotFound',                            'Alıcı bulunamadı',                '👤'),
    (r'IP\s+address\s+sending',                 'Gönderici IP engelli',            '🔧'),

    # ── Microsoft Exchange / Outlook özel kodları ───────────────────────
    (r'RESOLVER\.RST\.SenderNotAuthenticatedForGroup', 'Grup gönderici yetkisi yok', '🏢'),
    (r'RESOLVER\.RST\.RestrictedToGroupPermission',    'Dağıtım listesi kısıtlı',   '🏢'),
    (r'Hop\s+count\s+exceeded',                 'Mail döngüsü tespit edildi',      '🔄'),
    (r'UnifiedGroupAgent',                       'Grup üyesi değil',                '👥'),
    (r'SenderNotAuthenticated',                  'Gönderici kimlik doğrulaması yok','🔑'),
    (r'RestrictedToGroup',                       'Grup erişimi kısıtlı',            '🏢'),
    (r'InfoDomainNonexistent',                   'Alan adı mevcut değil',           '🌐'),
    (r'Message\s+expired',                      'Mesaj süresi doldu',              '⏰'),
    (r'connection\s+refused',                   'Bağlantı reddedildi',             '🔌'),

    # ── Posta kutusu / kota — ek varyantlar ──────────────────────────────
    (r'Mailbox\s+unknown',                       'Posta kutusu bilinmiyor',         '📭'),
    (r'Mailbox\s+size\s+limit',                 'Posta kutusu boyut limiti',       '📦'),
    (r'mailbox\s+not\s+found',                  'Posta kutusu bulunamadı',         '📭'),
    (r'Mailbox\s+has\s+exceeded',               'Posta kutusu limiti aşıldı',      '📦'),
    (r'mailbox\s+is\s+full.*Try\s+later',      'Posta kutusu dolu',               '📦'),
    (r'could\s+not\s+be\s+delivered.*mailbox\s+is\s+full', 'Posta kutusu dolu','📦'),
    (r'check-quota',                              'Kota kontrolü başarısız',         '📦'),
    (r'limit-out',                                'Gönderim limiti aşıldı',          '⏱'),
    (r'Requested\s+mail\s+action\s+aborted',   'Posta kutusu bulunamadı',         '📭'),

    # ── Spam — ek varyantlar ──────────────────────────────────────────────
    (r'classified\s+as\s+(SPAM|spam)',          'Spam olarak sınıflandırıldı',     '🚫'),
    (r'classified\s+as\s+rSPAM',               'Spam olarak sınıflandırıldı',     '🚫'),
    (r'outboundspamprotection',                  'Spam koruması engelledi',         '🚫'),
    (r'554\.30',                                 'Hesap devre dışı (Yahoo)',         '🔒'),
    (r'mailbox\s+is\s+disabled',               'Posta kutusu devre dışı',         '🔒'),

    # ── Alan adı / routing ────────────────────────────────────────────────
    (r'Unroutable\s+address',                   'Yönlendirilemeyen adres',         '🔀'),
    (r'DNS\s+lookup\s+failed',                  'DNS sorgusu başarısız',           '🌐'),
    (r'invalid_domain',                          'Geçersiz alan adı',               '🌐'),
    (r'no\s+valid\s+cert\s+for\s+gateway',   'Alan adı sertifika hatası',       '🔐'),
    (r'that\s+domain\s+isn.t\s+in\s+my\s+list', 'Alan adı yönetilmiyor',       '🌐'),
    (r'permanent\s+failure\s+for\s+one\s+or\s+more', 'Kalıcı teslimat hatası', '❌'),
    (r'X-Postfix',                               'Postfix iletim hatası',           '⚙️'),
    (r'x-unix',                                  'Sunucu sistem hatası',            '⚙️'),
    (r'can\s+not\s+be\s+delivered\s+at\s+this\s+time', 'Geçici teslim hatası','⏳'),

    # ── Türkçe açıklama zaten varsa eşleştir (diagnostic eksik CSV kayıtları için) ──
    (r'DKIM\s*hatas',                            'DKIM hatası',                     '🔏'),
    (r'Saatlik\s+limit',                        'Saatlik limit aşıldı',            '⏱'),

    # ── Geçici / retry ───────────────────────────────────────────────────
    (r'service\s+unavailable',                   'Servis kullanılamıyor',           '⏳'),
    (r'temporary',                               'Geçici hata',                     '⏳'),
]

def _aciklama_from_body(icerik: str, fallback: str) -> tuple:
    """
    Döner: (aciklama, etiket)
      aciklama — sunucu metni + Türkçe label birleşimi (Açıklama sütunu)
      etiket   — ikon + kısa Türkçe label (Kısa Açıklama sütunu)
    """

    def _temizle(raw):
        s = raw.strip()
        s = re.sub(r'^X-Proxmox;\s*', '', s, flags=re.IGNORECASE)  # "X-Proxmox; " öneki
        s = re.sub(r'^X-Postfix;\s*', '', s, flags=re.IGNORECASE)  # "X-Postfix; " öneki
        s = re.sub(r'^x-unix;\s*',    '', s, flags=re.IGNORECASE)  # "x-unix; " öneki
        s = re.sub(r'^smtp;\s*', '', s, flags=re.IGNORECASE)        # "smtp; " öneki
        s = re.sub(r'^\d{3}[\s\-]+', '', s)                        # "550 " SMTP kodu
        s = re.sub(r'^(\d+\.\d+\.\d+\s+)+', '', s)              # "5.7.1 5.1.1 " enhanced kodlar
        s = re.sub(r'^<[^>]+>\s*', '', s)                            # "<email@addr> " öneki
        s = re.sub(r'^:\s*', '', s)                                   # ": " artığı
        # Uzun URL'leri kes (https://... kısmı okunaksız oluyor)
        s = re.sub(r'\s+https?://\S+', '', s)
        return s.strip().rstrip(';"')

    def _birlestir(sunucu, label):
        temiz = sunucu[:75].rstrip()
        if temiz and label and temiz.lower() != label.lower():
            return temiz + " — " + label
        return label if label else temiz

    # 1. Diagnostic-Code satırını al
    dm = re.search(r'Diagnostic-Code:\s*(.{1,400})', icerik, re.IGNORECASE)
    if dm:
        diag_raw  = dm.group(1).split("\n")[0].split("\r")[0].strip()
        diag_text = _temizle(diag_raw)

        for pattern, label, ikon in MESAJ_PATTERNS:
            # Önce ham Diagnostic-Code'da, sonra temizlenmiş metinde ara
            if re.search(pattern, diag_raw, re.IGNORECASE) or re.search(pattern, diag_text, re.IGNORECASE):
                return _birlestir(diag_text, label), ikon + " " + label

        if len(diag_text) > 5:
            return diag_text[:120], ""

    # 2. Tüm gövdeyi tara
    for pattern, label, ikon in MESAJ_PATTERNS:
        if re.search(pattern, icerik, re.IGNORECASE):
            return label, ikon + " " + label

    return fallback, ""



# ── Suppression'a EKLENMEYECEK status kodları ──────────────────────────────
# Bunlar alıcı sorunu değil, teknik/routing sorunları veya geçici
SUPPRESSION_DISI = {
    "5.4.14",  # mail loop — routing sorunu
    "5.5.1",   # mail sistemi uyumsuzluğu — alıcı sorunu değil
    "5.6.0",   # format sorunu — içerik düzeltilirse geçer
    "5.7.64",  # TLS sorunu — sunucu sertifika problemi
    "4.3.1",   # geçici retry
    "4.4.2",   # bağlantı kesildi — geçici
    "4.4.3",   # domain geçici
    "4.1.8",   # DNS geçici
}

# ── Internal/özel domainler — internet üzerinden ulaşılamaz ───────────────
INTERNAL_TLDS = {
    'local', 'ilan', 'lan', 'corp', 'internal', 'intra',
    'home', 'localdomain', 'localhost',
}

# ── SPF/DKIM/DMARC fail pattern'ları ──────────────────────────────────────
SPF_DKIM_PATTERNS = re.compile(
    r'spf.*?fail|dkim.*?fail|dmarc.*?fail|'
    r'sender\s+policy\s+framework|'
    r'authentication.*?failed.*?spf|'
    r'rejected.*?dkim',
    re.IGNORECASE
)

# ── Gönderici taraflı sorunlar (alıcı geçerli, bizim tarafımız sorunlu) ──
# Bu pattern'lar eşleşirse kategori → gonderici_sorunu, suppression'a EKLENMEz
GONDERICI_SORUNU_PATTERNS = re.compile(
    r'requires\s+authentication'             # SMTP auth gerekli
    r'|smtp\s+auth'                          # SMTP Auth
    r'|please\s+(turn\s+on|enable)\s+smtp'  # "Please turn on SMTP"
    r'|not\s+permitted\s+to\s+relay'        # relay izni yok
    r'|relay\s+not\s+permitted'
    r'|relay\s+(access\s+)?denied'
    r'|relaying\s+blocked'
    r'|relaying\s+denied'
    r'|sender\s+verify\s+fail'
    r'|sender\s+address\s+rejected'
    r'|PTR\s+record'                         # ters DNS (PTR) sorunu
    r'|does\s+not\s+have\s+a\s+PTR'
    r'|dkim.{0,30}(signature_incorrect|invalid|fail|error)'  # DKIM imza hatası
    r'|signature_incorrect'                                    # DKIM imza yanlış
    r'|spf.{0,30}(fail|error|invalid|reject)',                # SPF fail (Diagnostic-Code'da)
    re.IGNORECASE
)

# ── Geçici / gönderici-taraflı hata pattern'ları ─────────────────────────
# Action:failed veya Status:5.x.x olsa bile bunlar geçici ya da gönderici sorunudur.
GECICI_OVERRIDE_PATTERNS = re.compile(
    r'max\s+emails?\s+per\s+hour'
    r'|exceeded\s+the\s+max\s+emails?'
    r'|rate\s+limit(ed)?'
    r'|too\s+many\s+(messages?|emails?|connections?|requests?)'
    r'|exceeded.{0,40}(quota|limit|allowed)'
    r'|(quota|limit|allowed).{0,40}exceeded'
    r'|per\s+hour.{0,30}allowed'
    r'|message\s+discarded'
    r'|temporarily\s+(blocked|deferred|rejected|unavailable)'
    r'|try\s+again\s+later'
    r'|please\s+retry'
    r'|greylisted?'
    r'|over\s+(quota|limit)'
    r'|has\s+exceeded\s+the',
    re.IGNORECASE
)

# ── Gerçek bounce mu? Return-Path kontrolü ────────────────────────────────
def _is_real_bounce(icerik: str) -> bool:
    """
    Gerçek bounce mailleri en az bir Return-Path: <> (boş) satırı içerir.
    imap_tools ile alınan maillerde birden fazla Return-Path satırı olabilir
    (outer envelope dolu, inner DSN <> boş). Bu yüzden TÜM satırları tarayıp
    herhangi biri <> ise bounce kabul ediyoruz.

    Ek kontrol: MAILER-DAEMON / Delivery Status / Auto-Submitted başlıkları
    varsa Return-Path olmasa bile bounce sayılır.
    """
    # Tüm Return-Path satırlarını bul
    tum_rp = re.findall(r'^Return-Path:\s*(.+)', icerik, re.IGNORECASE | re.MULTILINE)
    if tum_rp:
        # En az birinde <> varsa bounce
        for val in tum_rp:
            if val.strip() in ('<>', ''):
                return True
        # Hiçbirinde <> yok — ama yine de DSN işareti var mı?
        # (bazı sunucular Return-Path dolduruyor ama gerçek bounce)
    
    # Return-Path yoksa veya hepsi doluysa DSN/delivery ipuçlarına bak
    dsn_ipuclari = [
        r'Content-Type:\s*message/delivery-status',
        r'Content-Type:\s*multipart/report',
        r'Auto-Submitted:\s*auto-replied',
        r'X-Failed-Recipients:',
        r'Final-Recipient:\s*rfc822;',
        r'Action:\s*(failed|delayed)',
        r'Diagnostic-Code:\s*smtp;',
        r'This message was created automatically by mail delivery',
        r'Mail delivery (failed|deferred)',
        r'Undelivered Mail Returned',
        r'Delivery Status Notification',
        r'MAILER-DAEMON',
    ]
    for ipucu in dsn_ipuclari:
        if re.search(ipucu, icerik, re.IGNORECASE):
            return True

    # Hiçbir ipucu yoksa bounce değil
    if tum_rp:
        return False  # Return-Path dolu ve DSN ipucu yok → gerçek yanıt
    return True  # Return-Path hiç yok → bounce kabul et


def _is_internal_domain(email: str) -> bool:
    """
    .local, .ilan, .lan gibi internal/özel domainleri tespit eder.
    Bunlar internet üzerinden ulaşılamaz, suppression'a eklenmemeli.
    """
    if '@' not in email:
        return False
    domain = email.split('@')[1].lower()
    tld = domain.split('.')[-1]
    return tld in INTERNAL_TLDS


def _extract_email_fallback(icerik: str) -> str | None:
    """
    Final-Recipient yoksa alternatif yollarla email bulmaya çalışır:
    1. Original-Recipient header'ı
    2. "The following addresses had delivery problems" formatı
    3. Inline <email> pattern'ı (dikkatli kullan — gönderen de olabilir)
    """
    # 1. Original-Recipient
    orig = re.search(r'Original-Recipient:\s*rfc822;\s*([^\r\n;]+)', icerik, re.IGNORECASE)
    if orig:
        return orig.group(1).strip().lower()

    # 2. McAfee/gateway "delivery problems" formatı
    problems = re.search(
        r'following addresses had delivery problems.*?<([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})>',
        icerik, re.IGNORECASE | re.DOTALL
    )
    if problems:
        return problems.group(1).strip().lower()

    # 3. "deferred" / plain-text Exim formatı:
    #    "The following address(es) deferred:\n\n  email@domain.com"
    deferred = re.search(
        r'address(?:es)?\s+(?:deferred|failed)[:\s]+\s*([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})',
        icerik, re.IGNORECASE
    )
    if deferred:
        return deferred.group(1).strip().lower()

    # 4. Satır başında tek başına duran email adresi (Exim plain-text bounce)
    #    Örn: "  info@mgm.gov.tr\n    Domain ... exceeded..."
    inline = re.search(
        r'\n\s{2,}([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})\s*\n',
        icerik, re.IGNORECASE
    )
    if inline:
        return inline.group(1).strip().lower()

    return None


def _detect_kategori(icerik: str, status: str, action: str, email: str) -> str:
    """
    Bounce kategorisini belirler:
      kalici          — gerçek kalıcı bounce (5.1.1 vb.)
      gecici          — geçici sorun (4.x.x)
      gonderici_sorunu — SPF/DKIM fail — alıcı değil gönderen sorunlu
      mail_loop       — routing döngüsü (5.4.14)
      internal_domain — .local/.ilan gibi internet dışı
      atla            — bounce değil, işleme
    """
    if _is_internal_domain(email):
        return 'internal_domain'

    if status == '5.4.14':
        return 'mail_loop'

    if SPF_DKIM_PATTERNS.search(icerik):
        # SPF/DKIM ifadesi sadece spam filtresi RAPORUNDA geçiyorsa kalici say.
        # Gerçek DKIM/SPF reddi: Diagnostic-Code'da veya asıl hata satırında olur.
        # Spam skoru raporu (SpamAssassin, KAM_DMARC_STATUS vb.) içinde geçiyorsa
        # asıl sebep spam reddidir → kalici.
        diag = re.search(r'Diagnostic-Code:\s*(.{0,300})', icerik, re.IGNORECASE)
        diag_text = diag.group(1) if diag else ''
        
        # Diagnostic-Code'da spam ifadesi varsa → alıcı spam diye reddetti → kalici
        if re.search(r'spam|blocked|rejected', diag_text, re.IGNORECASE):
            return 'kalici'
        
        # Diagnostic-Code'da gerçek DKIM/SPF fail varsa → gönderici sorunu
        if SPF_DKIM_PATTERNS.search(diag_text):
            return 'gonderici_sorunu'
        
        # Diagnostic-Code yoksa ama 5.7.x kodu varsa → alıcı sistemi reddetti
        if status.startswith('5.7') and action == 'failed':
            return 'kalici'
        
        # Gövdede spam ifadesi varsa → alıcı tarafı reddetti → kalici
        # Sadece spam raporu satırlarında (SpamAssassin skoru) geçiyorsa da kalici
        # çünkü asıl red sebebi spam filtresi
        spam_in_body = re.search(
            r'(spam|blocked by spam|detected.{0,20}spam|spam.{0,20}filter)',
            icerik, re.IGNORECASE
        )
        if spam_in_body:
            return 'kalici'

        return 'gonderici_sorunu'

    # Gönderici taraflı sorunlar — önce Diagnostic-Code'da ara, sonra gövdede
    # Spam ile birlikte geliyorsa (spam filtresi raporu) kalici sayılır
    diag_m2 = re.search(r'Diagnostic-Code:\s*(.{0,300})', icerik, re.IGNORECASE)
    diag_text2 = diag_m2.group(1) if diag_m2 else ''
    if GONDERICI_SORUNU_PATTERNS.search(diag_text2):
        # Diagnostic-Code'da hem gönderici sorunu hem spam varsa → kalici
        if re.search(r'spam', diag_text2, re.IGNORECASE):
            return 'kalici'
        return 'gonderici_sorunu'
    # Gövde genelinde ara (relay, auth vb.)
    if GONDERICI_SORUNU_PATTERNS.search(icerik):
        # Gövdede spam da varsa → kalici
        if re.search(r'spam', icerik, re.IGNORECASE):
            return 'kalici'
        return 'gonderici_sorunu'

    # Rate limit / kota gibi geçici hatalar "failed" gelse de suppression'a girmemeli
    if GECICI_OVERRIDE_PATTERNS.search(icerik):
        return 'gecici'

    if action == 'failed':
        return 'kalici'
    elif action == 'delayed':
        return 'gecici'
    else:
        return 'kalici' if status.startswith('5') else 'gecici'


def parse_bounce(icerik: str) -> dict | None:
    """
    Mail içeriğinden bounce bilgilerini çıkarır.
    Bulamazsa veya bounce değilse None döner.

    Desteklenen formatlar:
      - RFC 3464 DSN (Final-Recipient + Action + Status)
      - Original-Recipient fallback
      - McAfee/gateway "delivery problems" formatı
      - Exchange NDR (postmaster@ kaynaklı)
      - postmaster@ kaynaklı bounce'lar (MAILER-DAEMON olmayan)

    Atlanacaklar:
      - Return-Path dolu (gerçek yanıt, oto-reply)
      - .local/.ilan gibi internal domainler (kategori:internal_domain)
      - No-reply / noreply gelen kutusuna düşen mailler
    """

    # 0. Gerçek bounce mu kontrol et
    if not _is_real_bounce(icerik):
        return None

    # 1. Final-Recipient — en güvenilir
    m = re.search(r'Final-Recipient:\s*rfc822;\s*([^\r\n;]+)', icerik, re.IGNORECASE)

    if m:
        email = m.group(1).strip().lower()
        # Exchange encoding artifact temizle (örn: "0Auinfo@firma.com" → "info@firma.com")
        email = re.sub(r'^[^a-z0-9._%+\-]+', '', email)
    else:
        # 2. Fallback — Original-Recipient veya satır içi format
        email = _extract_email_fallback(icerik)
        if not email:
            return None

    # Geçerli email mi?
    if not re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$', email):
        return None

    # 3. Action: failed / delayed
    ma = re.search(r'^Action:\s*(\S+)', icerik, re.IGNORECASE | re.MULTILINE)
    action = ma.group(1).strip().lower() if ma else 'unknown'

    # 4. Status kodu
    ms = re.search(r'^Status:\s*(\S+)', icerik, re.IGNORECASE | re.MULTILINE)
    status = ms.group(1).strip() if ms else ''

    # 5. Kategori belirle
    kategori = _detect_kategori(icerik, status, action, email)

    # 6. Bounce tipi (geriye uyumluluk)
    if kategori in ('kalici', 'gonderici_sorunu', 'mail_loop', 'internal_domain'):
        bounce_tipi = 'kalici'
    else:
        bounce_tipi = 'gecici'

    # 7. Açıklama üret — her zaman Diagnostic-Code'a öncelik ver
    # STATUS_LABELS sadece fallback olarak kullanılır.
    # _aciklama_from_body: Diagnostic-Code temizle → pattern eşleştir →
    #   eşleşirse "sunucu metni — Türkçe etiket", eşleşmezse sunucu metni doğrudan
    # Jenerik kodlar için fallback boş bırak → Diagnostic-Code metni doğrudan kullanılır
    GENEL_KODLAR = {'5.0.0', '4.0.0', '5.0.350', ''}
    aciklama_fallback = '' if status in GENEL_KODLAR else STATUS_LABELS.get(status, '')
    aciklama, etiket = _aciklama_from_body(icerik, aciklama_fallback)

    # 8. Diagnostic-Code tam metin
    mdiag = re.search(
        r'Diagnostic-Code:\s*([\s\S]{0,500}?)(?=\r?\n\S|\Z)',
        icerik, re.IGNORECASE
    )
    diagnostic = ''
    if mdiag:
        diagnostic = re.sub(r'\s+', ' ', mdiag.group(1)).strip()[:500]

    # 9. Suppression'a eklenip eklenmeyeceği
    suppression_ekle = (
        kategori == 'kalici' and
        status not in SUPPRESSION_DISI
    )

    rfc_etiket = _enhanced_status_etiket(icerik, status)

    return {
        'email':            email,
        'bounce_tipi':      bounce_tipi,
        'hata_kodu':        status,
        'aciklama':         aciklama,
        'etiket':           etiket,
        'rfc_etiket':       rfc_etiket,
        'diagnostic':       diagnostic,
        'kategori':         kategori,
        'suppression_ekle': suppression_ekle,
    }


def db_kaydet(cursor, bounce: dict) -> str:
    """
    Bounce'u veritabanına yazar.
    'yeni', 'guncellendi' veya 'atlandi' döner.
    """
    # Suppression dışı kategoriler DB'ye yazılır ama suppression'a eklenmez
    # Bu ayrım main.py'de yapılır

    cursor.execute(
        "SELECT id, bounce_tipi FROM bounce_adresleri WHERE email = %s",
        (bounce['email'],)
    )
    mevcut = cursor.fetchone()
    simdi = datetime.now()

    if not mevcut:
        cursor.execute("""
            INSERT INTO bounce_adresleri
                (email, bounce_tipi, hata_kodu, aciklama, diagnostic,
                 kategori, ilk_gorulme, son_gorulme, adet)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (
            bounce['email'],
            bounce['bounce_tipi'],
            bounce['hata_kodu'],
            bounce['aciklama'],
            bounce['diagnostic'],
            bounce.get('kategori', 'kalici'),
            simdi, simdi
        ))
        return 'yeni'

    else:
        # Geçici → kalıcı'ya yükselebilir, tersi olmaz
        yeni_tip = mevcut[1]
        if bounce['bounce_tipi'] == 'kalici':
            yeni_tip = 'kalici'

        cursor.execute("""
            UPDATE bounce_adresleri
            SET son_gorulme = %s,
                adet        = adet + 1,
                bounce_tipi = %s,
                hata_kodu   = IF(%s = 'kalici', %s, hata_kodu),
                aciklama    = IF(%s = 'kalici', %s, aciklama),
                kategori    = IF(%s = 'kalici', %s, kategori)
            WHERE email = %s
        """, (
            simdi,
            yeni_tip,
            bounce['bounce_tipi'], bounce['hata_kodu'],
            bounce['bounce_tipi'], bounce['aciklama'],
            bounce['bounce_tipi'], bounce.get('kategori', 'kalici'),
            bounce['email']
        ))
        return 'guncellendi'
