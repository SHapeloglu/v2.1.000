"""
verifier.py — MailSender Pro Gelişmiş E-posta Doğrulama Motoru
==============================================================
11 katmanlı doğrulama sistemi.

KONTROL KATMANLARI:
  1.  Syntax normalizasyonu  — büyük harf, +tag temizleme, googlemail→gmail
  2.  Format kontrolü        — RFC uyumlu regex + Türkçe karakter tespiti
  2b. did_you_mean           — Levenshtein ile akıllı domain önerisi
  3.  Disposable tespiti     — 150+ geçici mail servisi + dinamik DB listesi
  3b. Spam tuzağı tespiti    — pristine/typo/recycled/honeypot/mx tuzakları
  4.  Role account tespiti   — info@, admin@, noreply@ vb.
  5.  Typo düzeltme          — gmial.com→gmail.com, yahooo.com→yahoo.com
  6.  MX / A kaydı fallback  — DNS sorgusu, MX yoksa A kaydı dener (TTL önbellekli)
  7.  SPF / DMARC varlığı    — Domain mail altyapısı yapılandırılmış mı? (TTL önbellekli)
  8.  Domain yaşı kontrolü  — 30 günden yeni domain → riskli
  9.  Catch-all tespiti      — Sunucu her adrese 250 veriyorsa tespit edilir (TTL önbellekli)
  10. SMTP RCPT doğrulaması  — Gerçek posta kutusu varlık kontrolü (port 25/587/465)
  11. Greylisting retry      — unknown sonuçlar kuyruğa alınır, saatler sonra yeniden denenir

DURUM KODLARI:
  valid          → Tüm aktif kontroller geçti
  invalid_format → Format geçersiz
  disposable     → Geçici servis
  spam_trap      → Spam tuzağı (pristine/typo/recycled/honeypot/mx)
  role_account   → Kişisel olmayan rol adresi
  typo_fixed     → Yazım hatası düzeltildi
  no_mx          → DNS kaydı yok
  no_infra       → SPF/DMARC yok — zayıf domain
  catch_all      → Catch-all sunucu (teslim edilebilir ama belirsiz)
  invalid        → SMTP 550 posta kutusu yok
  unknown        → SMTP belirsiz yanıt (greylisting retry kuyruğuna alınır)
  free_provider  → Gmail/Hotmail vb. (bilgi amaçlı)

META ALANLARI (verify_one() döner):
  did_you_mean        → Yazım hatası domain önerisi (ör: "ali@gmail.com") veya None
  spam_trap_type      → 'pristine'|'typo_trap'|'recycled'|'honeypot'|'mx_trap' veya None
  spam_trap_confidence→ 'high'|'medium'|'low' veya None
  mx_server           → Bulunan MX sunucu adresi veya None

is_valid DB değerleri:
   1 → valid, typo_fixed, catch_all, free_provider
  -1 → unknown, role_account, no_infra
   0 → invalid_format, disposable, no_mx, invalid, spam_trap
"""

import re, socket, random, string, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from spam_trap import check_spam_trap
from greylist_retry import enqueue_greylist_retry
from toxic_domain import check_toxic_domain
from yahoo_aol_check import check_yahoo_aol, is_yahoo_aol_domain

# ── Regex ──────────────────────────────────────────────────────────
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9][a-zA-Z0-9\.\+\-\_]*@[a-zA-Z0-9][a-zA-Z0-9\-\.]*\.[a-zA-Z]{2,}$'
)

# ── Disposable domainler ───────────────────────────────────────────
DISPOSABLE_DOMAINS = {
    "mailinator.com","10minutemail.com","tempmail.com","guerrillamail.com",
    "throwam.com","yopmail.com","trashmail.com","fakeinbox.com",
    "sharklasers.com","spam4.me","dispostable.com","maildrop.cc",
    "getairmail.com","mailnull.com","spamgourmet.com","trashmail.me",
    "mailnesia.com","mytemp.email","tempr.email","discard.email",
    "getnada.com","mailsac.com","mailcatch.com","filzmail.com",
    "trashmail.at","trashmail.io","trashmail.net","trashmail.org",
    "trashmail.xyz","wegwerfmail.de","wegwerfmail.net","wegwerfmail.org",
    "mailtemp.info","temp-mail.org","tempinbox.com","0-mail.com",
    "10minutemail.net","10minutemail.org","20minutemail.com","33mail.com",
    "abusemail.de","armyspy.com","binkmail.com","bobmail.info",
    "boun.cr","bouncr.com","brefmail.com","buffemail.com","byom.de",
    "centermail.com","centermail.net","cmail.club","cmail.com",
    "cock.li","cool.fr.nf","courriel.fr.nf","courrieltemporaire.com",
    "crapmail.org","crazymailing.com","dayrep.com","deadaddress.com",
    "despammed.com","devnullmail.com","disposablemail.es","dispostable.me",
    "dodgit.com","einrot.com","emailsensei.com","emz.net","fakeinbox.com",
    "fastacura.com","filzmail.com","fleckens.hu","frapmail.com",
    "freemail.ms","garliclife.com","getonemail.com","giantmail.de",
    "girlsundertheinfluence.com","gishpuppy.com",
    "grandmamail.com","grandmasmail.com","great-host.in","greensloth.com",
    "grr.la","gsrv.co.uk","guerillamail.biz","guerillamail.com",
    "guerillamail.de","guerillamail.net","guerillamail.org",
    "h.mintemail.com","hartbot.de","hat-geld.de","hatespam.org",
    "hidemail.de","hidzz.com","hmamail.com","hopemail.biz",
    "hulapla.de","ieatspam.eu","ieatspam.info","ihateyoualot.info",
    "iheartspam.org","imails.info","inbax.tk","inbox.si",
    "inboxalias.com","inboxclean.com","inboxclean.org","inoutmail.de",
    "inoutmail.eu","inoutmail.info","inoutmail.net","instant-mail.de",
    "ipoo.org","irish2me.com","iwi.net","jetable.com","jetable.fr.nf",
    "jetable.net","jetable.org","jnxjn.com","jourrapide.com",
    "jsrsolutions.com","kasmail.com","kaspop.com","killmail.com",
    "killmail.net","klassmaster.com","klassmaster.net","klassmaster.org",
    "klzlk.com","koszmail.pl","kulturbetrieb.info","kurzepost.de",
    "letthemeatspam.com","lhsdv.com","ligsb.com","link2mail.net",
    "litedrop.com","loadby.us","lol.ovpn.to","lolfreak.net",
    "lookugly.com","lortemail.dk","lukemail.com","lyricspad.net",
    "maboard.com","mail-filter.com","mail-temporaire.fr","mail.mezimages.net",
    "mail.zp.ua","mail114.net","mail1a.de","mail2rss.org","mail333.com",
    "mailbidon.com","mailbiz.biz","mailblocks.com","mailbucket.org",
    "mailcat.biz","mailchop.com","mailchop.de","mailde.de","mailde.info",
    "mailexpire.com","mailf5.com","mailfall.com","mailfreeonline.com",
    "mailguard.me","mailimate.com","mailin8r.com","mailinater.com",
}

# ── Disposable DB genişletme — dinamik liste ───────────────────────
# disposable_updater.py her gece DB'yi günceller.
# Burası başlangıçta DB'deki ekstra domainleri koda gömülü sete ekler.
def _load_extra_disposable_from_db():
    """
    DB'deki güncellenmiş disposable listesini DISPOSABLE_DOMAINS setine ekler.
    Import sırasında bir kez çağrılır; hata olursa sessizce atlar.
    """
    try:
        from disposable_updater import load_domains_from_db
        extra = load_domains_from_db()
        if extra:
            DISPOSABLE_DOMAINS.update(extra)
    except Exception:
        pass  # DB bağlantısı yoksa veya updater kurulmamışsa gömülü listeyle devam et

_load_extra_disposable_from_db()


# ── Gibberish (saçma) local kısmı tespiti ────────────────────────────────────
# Kaynak: EmailFilter projesi (MIT lisanslı) — 5+ ardışık sessiz harf = bot/oto üretim
import re as _re
_GIBBERISH_RE = _re.compile(r'[bcdfghjklmnpqrstvwxyz]{5,}', _re.IGNORECASE)

def _is_gibberish(local: str) -> bool:
    """E-postanın @ önceki kısmı bot/otomatik üretimli mi? (ör: xkqrtbz, qwzxcvb)"""
    return bool(_GIBBERISH_RE.search(local))

# ── Spam keyword tespiti (local kısımda) ──────────────────────────────────────
# Kaynak: EmailFilter projesi (MIT lisanslı) — bot/spam kayıt adreslerini yakalar
# Türkçe ve yaygın İngilizce spam kelimeler. Genişletilebilir.
_SPAM_LOCAL_KEYWORDS: list[str] = [
    # İngilizce
    "lottery","prize","winner","winnings","cash","offer","freemail",
    "getrich","makemoney","clickhere","bestdeal","limitedoffer",
    # Yaygın sahte/bot kalıpları
    "test123","temp123","fake","throwaway","nobody","noone",
    "random","anonymous","noreplybot","donotreply123",
]
_SPAM_LOCAL_PATTERN = _re.compile(
    '|'.join(map(_re.escape, _SPAM_LOCAL_KEYWORDS)),
    _re.IGNORECASE
)

def _has_spam_local_keywords(local: str) -> bool:
    """E-postanın @ önceki kısmında spam/bot kayıt kelimesi var mı?"""
    return bool(_SPAM_LOCAL_PATTERN.search(local))

# ── Rol prefiksleri ────────────────────────────────────────────────
ROLE_PREFIXES = {
    "info","admin","administrator","webmaster","hostmaster","postmaster",
    "noreply","no-reply","no_reply","donotreply","do-not-reply",
    "support","help","contact","abuse","security","billing","sales",
    "marketing","newsletter","notifications","notification","alerts",
    "alert","mailer","daemon","bounce","bounces","ndr","mail","email",
    "service","services","team","office","careers","jobs","hr","press",
    "media","pr","legal","privacy","gdpr","unsubscribe","subscribe",
    "listserv","majordomo","mailman","autoresponder","auto-reply",
    "autoreply","feedback","root","sys","system","robot","bot",
    "automated","do_not_reply","reply","enquiries","enquiry","inquiry",
    "inquiries","questions","hello","hi","hey","reception","general",
}

# ── Ücretsiz sağlayıcılar ──────────────────────────────────────────
FREE_PROVIDERS = {
    "gmail.com","googlemail.com","yahoo.com","yahoo.co.uk","yahoo.fr",
    "yahoo.de","yahoo.es","yahoo.it","yahoo.co.jp","yahoo.com.br",
    "hotmail.com","hotmail.co.uk","hotmail.fr","hotmail.de","hotmail.es",
    "outlook.com","outlook.fr","outlook.de","live.com","live.co.uk",
    "live.fr","msn.com","icloud.com","me.com","mac.com","aol.com",
    "protonmail.com","proton.me","pm.me","tutanota.com","tutamail.com",
    "tuta.io","yandex.com","yandex.ru","mail.ru","inbox.ru","bk.ru",
    "list.ru","rambler.ru","gmx.com","gmx.de","gmx.net","gmx.at",
    "web.de","t-online.de","freenet.de","email.de","zoho.com",
    "fastmail.com","fastmail.fm","hushmail.com","mailfence.com",
}

# ── Typo düzeltme tablosu ──────────────────────────────────────────
TYPO_MAP = {
    "gmial.com":"gmail.com","gmai.com":"gmail.com","gmal.com":"gmail.com",
    "gmil.com":"gmail.com","gmail.co":"gmail.com","gmail.cm":"gmail.com",
    "gmail.cmo":"gmail.com","gmail.ocm":"gmail.com","gmaill.com":"gmail.com",
    "gamil.com":"gmail.com","gamail.com":"gmail.com","gmaio.com":"gmail.com",
    "gnail.com":"gmail.com","gmaiil.com":"gmail.com","gmailcom":"gmail.com",
    "yahooo.com":"yahoo.com","yaho.com":"yahoo.com","yhoo.com":"yahoo.com",
    "yahoo.co":"yahoo.com","yahoo.cm":"yahoo.com","yhaoo.com":"yahoo.com",
    "yahooo.fr":"yahoo.fr","yaho.fr":"yahoo.fr","yahoo.con":"yahoo.com",
    "hotmial.com":"hotmail.com","hotmal.com":"hotmail.com",
    "hotmai.com":"hotmail.com","hotmail.co":"hotmail.com",
    "hotmail.cm":"hotmail.com","hotmali.com":"hotmail.com",
    "hotmaill.com":"hotmail.com","hotnail.com":"hotmail.com",
    "hotmail.con":"hotmail.com",
    "outlok.com":"outlook.com","outloook.com":"outlook.com",
    "outlook.co":"outlook.com","outloo.com":"outlook.com",
    "outlookcom":"outlook.com","outook.com":"outlook.com",
    "iclooud.com":"icloud.com","icloud.co":"icloud.com",
    "iclould.com":"icloud.com",
    "yandex.ru.com":"yandex.ru","yandex.con":"yandex.com",
    "protonmail.con":"protonmail.com","protonmali.com":"protonmail.com",
    # Türkiye'ye özgü yaygın hatalar — gmail/hotmail/yahoo'ya .com.tr eklenmesi
    "gmail.com.tr":"gmail.com","hotmail.com.tr":"hotmail.com",
    "yahoo.com.tr":"yahoo.com","outlook.com.tr":"outlook.com",
    "icloud.com.tr":"icloud.com","yandex.com.tr":"yandex.com",
    # .con, .cmo, .ocm gibi TLD yazım hataları
    "gmail.con":"gmail.com","hotmail.con":"hotmail.com",
    "yahoo.con":"yahoo.com","outlook.con":"outlook.com",
    # Yaygın Türk mail servisi hataları
    "ttmail.com":"ttmail.com",  # TT (Türk Telekom) — geçerli bırak
}

# ── Akıllı domain önerisi (did_you_mean) ─────────────────────────────────────
# TYPO_MAP'te karşılığı olmayan yazım hatalarını Levenshtein mesafesiyle tespit eder.
# Harici bağımlılık yok — saf Python implementasyonu.

_SUGGEST_CANDIDATES: list[str] = sorted(FREE_PROVIDERS | {
    # Türkiye'ye özgü servisler
    "ttmail.com", "turk.net", "superonline.com", "ttnet.com.tr",
    "mynet.com", "mynet.com.tr", "isnet.net.tr",
})

def _levenshtein(a: str, b: str) -> int:
    """İki string arasındaki Levenshtein (düzenleme) mesafesini hesaplar."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                prev[j] + 1,        # silme
                curr[j - 1] + 1,    # ekleme
                prev[j - 1] + (ca != cb),  # değiştirme
            ))
        prev = curr
    return prev[-1]

def suggest_domain(domain: str) -> str | None:
    """
    Verilen domain'e en yakın bilinen sağlayıcı domain'ini önerir.

    Önce TYPO_MAP'e bakar (kesin eşleşme). Bulamazsa Levenshtein
    mesafesiyle en yakın aday domain'i döner.

    Kural:
      - Uzunluk farkı 4'ten büyükse öneri yapma (çok farklı)
      - Levenshtein mesafesi ≤ 2 ise öneri yap
      - Mesafe 3 ise sadece uzun domainlerde (≥10 karakter) öner
      - Zaten FREE_PROVIDERS içindeyse None döner (öneri gereksiz)

    Returns:
        Düzeltilmiş domain string'i veya None (öneri yapılamıyorsa)
    """
    d = domain.lower().strip()

    # Zaten bilinen geçerli bir domain
    if d in FREE_PROVIDERS:
        return None

    # TYPO_MAP'te kesin eşleşme var mı?
    if d in TYPO_MAP:
        return TYPO_MAP[d]

    # Levenshtein ile en yakın aday
    best_candidate = None
    best_distance  = 999

    for candidate in _SUGGEST_CANDIDATES:
        # Uzunluk farkı çok büyükse atla (hız optimizasyonu)
        if abs(len(d) - len(candidate)) > 4:
            continue
        dist = _levenshtein(d, candidate)
        if dist < best_distance:
            best_distance  = dist
            best_candidate = candidate

    if best_candidate is None or best_distance > 3:
        return None
    if best_distance == 3 and len(d) < 10:
        return None

    return best_candidate


# ── ESP (E-posta Servis Sağlayıcısı) Tespiti ─────────────────────────────────
# Kaynak: email-verifier-free projesi (MIT lisanslı).
# MX kaydındaki host adına bakarak hangi ESP kullanıldığını tespit eder.
# Risk skoru için güçlü sinyal: kurumsal ESP (Proofpoint, Mimecast) = yüksek güven.
_ESP_PATTERNS: list[tuple[str, str]] = [
    # Google
    ("aspmx.l.google",          "Google Workspace"),
    ("googlemail.com",          "Google Workspace"),
    ("google.com",              "Google Workspace"),
    # Microsoft
    ("protection.outlook.com",  "Microsoft 365"),
    ("mail.protection.outlook", "Microsoft 365"),
    ("outlook.com",             "Microsoft 365"),
    # Kurumsal güvenlik / filtre geçidi
    ("pphosted.com",            "Proofpoint"),
    ("mimecast.com",            "Mimecast"),
    ("barracudanetworks.com",   "Barracuda"),
    ("ess.cisco.com",           "Cisco IronPort"),
    ("trendmicro.com",          "Trend Micro"),
    ("forcepoint.com",          "Forcepoint"),
    # Bulut e-posta
    ("zoho.com",                "Zoho Mail"),
    ("zohomail.com",            "Zoho Mail"),
    ("yahoodns.net",            "Yahoo Mail"),
    ("icloud.com",              "Apple iCloud"),
    ("protonmail.ch",           "Proton Mail"),
    ("fastmail.com",            "Fastmail"),
    ("migadu.com",              "Migadu"),
    # Hosting / altyapı
    ("secureserver.net",        "GoDaddy"),
    ("emailsrvr.com",           "Rackspace"),
    ("amazonaws.com",           "Amazon SES"),
    ("sendgrid.net",            "SendGrid"),
    ("mailgun.org",             "Mailgun"),
    ("sparkpostmail.com",       "SparkPost"),
    ("titan.email",             "Titan"),
    # Türkiye'ye özgü
    ("ttnet.net.tr",            "TTNet"),
    ("turk.net",                "Türk.net"),
    ("superonline.net",         "Superonline"),
]

def _detect_esp(mx_host: str) -> str | None:
    """
    MX host adresine göre e-posta servis sağlayıcısını tespit eder.

    Args:
        mx_host: MX kaydının host adresi (ör: 'aspmx.l.google.com')

    Returns:
        ESP adı (ör: 'Google Workspace') veya None (bilinmeyen)
    """
    if not mx_host:
        return None
    h = mx_host.lower()
    for pattern, esp_name in _ESP_PATTERNS:
        if pattern in h:
            return esp_name
    return None

# ── SMTP atlanacak domainler ──────────────────────
# Temel liste (her zaman geçerli, DB'ye ek olarak)
_SMTP_SKIP_BASE = FREE_PROVIDERS | {
    "microsoft.com", "google.com", "apple.com", "aim.com",
}

def _get_smtp_skip_domains() -> set:
    """
    SMTP muaf domain setini döner.
    DB'deki kullanıcı listesi + yerleşik temel liste birleşimi.
    Her çağrıda DB'yi okumamak için 60sn önbellek kullanır.
    """
    import time
    now = time.time()
    cache = _get_smtp_skip_domains
    if now - getattr(cache, '_ts', 0) < 60:
        return getattr(cache, '_cached', _SMTP_SKIP_BASE)
    try:
        import database as _db
        extra = _db.smtp_skip_domains_get()
        result = _SMTP_SKIP_BASE | set(extra)
    except Exception:
        result = _SMTP_SKIP_BASE
    cache._cached = result
    cache._ts     = now
    return result

# ── Durum → is_valid eşlemesi ──────────────────────────────────────
STATUS_TO_IS_VALID = {
    "valid":1,"typo_fixed":1,"catch_all":1,"free_provider":1,
    # no_infra: SPF/DMARC yok → mail altyapısı zayıf → riskli (-1)
    # Gönderim yapılabilir ama bounce riski yüksek, kullanıcı karar versin
    "no_infra":-1,
    "role_account":-1,"unknown":-1,
    # spam_trap: Kesin tuzak → gönderilemez (is_valid=0)
    "spam_trap":0,
    # toxic_domain: Abuse/bot/blacklist domain → gönderilemez (is_valid=0)
    "toxic_domain":0,
    # disabled_account: Yahoo/AOL devre dışı hesap → gönderilemez (is_valid=0)
    "disabled_account":0,
    "invalid_format":0,"disposable":0,"no_mx":0,"invalid":0,
}

# Suppression'a eklenecek kesin geçersizler
SUPPRESSION_STATUSES = {"invalid_format","disposable","no_mx","invalid","spam_trap","toxic_domain","disabled_account"}

# ── DNS / SMTP önbellekleri — TTL destekli ────────────────────────
# Her entry: {domain: (value, expire_ts)}
# MX / SPF / DMARC: 30 dakika TTL (DNS propagasyon süresi)
# Catch-all: 60 dakika TTL (daha pahalı kontrol, daha uzun sakla)
# maxsize: her cache en fazla 2000 domain tutar — LRU mantığıyla eskiler silinir
import time as _time

_CACHE_TTL_MX       = 1800   # 30 dakika
_CACHE_TTL_SPF      = 1800   # 30 dakika
_CACHE_TTL_DMARC    = 1800   # 30 dakika
_CACHE_TTL_CATCHALL = 3600   # 60 dakika
_CACHE_MAXSIZE      = 2000   # Her cache için max domain sayısı

_mx_cache:       dict = {}
_spf_cache:      dict = {}
_dmarc_cache:    dict = {}
_catchall_cache: dict = {}
_parked_cache:   dict = {}
_CACHE_TTL_PARKED = 86400  # 24 saat — web sitesi nadiren değişir

def _cache_get(cache: dict, key: str):
    """TTL'e göre cache'den değer okur. Süresi dolmuşsa None döner."""
    entry = cache.get(key)
    if entry is None:
        return None, False          # miss
    value, expire_ts = entry
    if _time.monotonic() > expire_ts:
        del cache[key]              # expired
        return None, False
    return value, True             # hit

def _cache_set(cache: dict, key: str, value, ttl: float):
    """Cache'e TTL ile yazar. maxsize aşılırsa en eski %10'u siler (basit eviction)."""
    if len(cache) >= _CACHE_MAXSIZE:
        # En eski expire_ts'e sahip %10'u sil
        evict_count = max(1, _CACHE_MAXSIZE // 10)
        oldest = sorted(cache.items(), key=lambda x: x[1][1])[:evict_count]
        for k, _ in oldest:
            cache.pop(k, None)
    cache[key] = (value, _time.monotonic() + ttl)

# ══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════

def _normalize(email: str):

    """E-postayı normalize eder: küçük harf, +tag temizleme, googlemail→gmail."""
    original = email.strip().lower()
    local, _, domain = original.partition('@')
    if not domain:
        return original, False
    if domain == 'googlemail.com':
        domain = 'gmail.com'
    if domain == 'gmail.com':
        local = local.split('+')[0].replace('.', '')
    elif '+' in local:
        local = local.split('+')[0]
    normalized = f"{local}@{domain}"
    return normalized, normalized != original

def _mx_lookup(domain):

    """Domain için MX kaydını sorgular. Yoksa A kaydı fallback dener. Önbellekli."""
    domain = domain.lower()
    cached, hit = _cache_get(_mx_cache, domain)
    if hit:
        return cached
    mx_addr = None
    try:
        import dns.resolver
        records = dns.resolver.resolve(domain, 'MX', lifetime=5)
        mx_sorted = sorted(records, key=lambda r: r.preference)
        mx_addr = str(mx_sorted[0].exchange).rstrip('.')
    except Exception:
        pass
    if not mx_addr:
        try:
            import dns.resolver
            a_recs = dns.resolver.resolve(domain, 'A', lifetime=3)
            if a_recs:
                mx_addr = domain
        except Exception:
            pass
    _cache_set(_mx_cache, domain, mx_addr, _CACHE_TTL_MX)
    return mx_addr

def _check_spf(domain):

    """Domain için SPF (TXT) kaydı varlığını kontrol eder. Önbellekli."""
    domain = domain.lower()
    cached, hit = _cache_get(_spf_cache, domain)
    if hit:
        return cached
    result = False
    try:
        import dns.resolver
        for r in dns.resolver.resolve(domain, 'TXT', lifetime=4):
            txt = b''.join(r.strings).decode('utf-8', errors='ignore')
            if txt.startswith('v=spf1'):
                result = True
                break
    except Exception:
        pass
    _cache_set(_spf_cache, domain, result, _CACHE_TTL_SPF)
    return result

def _check_dmarc(domain):

    """Domain için DMARC (_dmarc.domain TXT) kaydı varlığını kontrol eder. Önbellekli."""
    domain = domain.lower()
    cached, hit = _cache_get(_dmarc_cache, domain)
    if hit:
        return cached
    result = False
    try:
        import dns.resolver
        for r in dns.resolver.resolve(f'_dmarc.{domain}', 'TXT', lifetime=4):
            txt = b''.join(r.strings).decode('utf-8', errors='ignore')
            if 'v=DMARC1' in txt:
                result = True
                break
    except Exception:
        pass
    _cache_set(_dmarc_cache, domain, result, _CACHE_TTL_DMARC)
    return result

def _domain_age_days(domain):

    """WHOIS ile domain yaşını gün cinsinden döner. python-whois kurulu değilse None."""
    try:
        import whois, datetime
        w = whois.whois(domain)
        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]
        if creation:
            return (datetime.datetime.now() - creation).days
    except Exception:
        pass
    return None



# ── Parked / sahte website tespiti ────────────────────────────────────────────
# Kaynak: orijinal geliştirme. Kitt AI'da bulunan "Website Verification" özelliği.
# Domain'in gerçek bir web sitesi mi yoksa park/satılık/boş mu olduğunu HTTP
# isteğiyle kontrol eder. Parked domainler genellikle sahte veya terk edilmiş
# adresleri barındırır — gönderim yapılsa bile ulaşılacak kişi yoktur.
#
# Tespit edilen durumlar:
#   'parked'   → GoDaddy/Namecheap/domain-for-sale sayfaları
#   'empty'    → HTTP 200 ama çok az içerik (< 200 karakter)
#   'timeout'  → Sunucu yanıt vermiyor
#   None       → Gerçek/aktif web sitesi

_PARKED_PATTERNS = [
    # Domain kayıt şirketleri park sayfaları
    'domain is for sale', 'buy this domain', 'domain for sale',
    'this domain is parked', 'parked domain', 'domain parking',
    'godaddy.com/domain', 'namecheap.com', 'sedo.com',
    'hugedomains.com', 'dan.com', 'afternic.com',
    # Hosting boş sayfaları
    'default web page', 'welcome to nginx', 'welcome to apache',
    'it works!', 'coming soon', 'under construction',
    'page not found', '404 not found', 'site not found',
    # Türkçe
    'bu alan adı satılıktır', 'yakında', 'yapım aşamasında',
    'bu domain satılıktır',
]

# Büyük güvenilir sağlayıcılar — web sitesi kontrolü gereksiz
_PARKED_SKIP_DOMAINS = {
    'gmail.com', 'googlemail.com', 'yahoo.com', 'ymail.com',
    'outlook.com', 'hotmail.com', 'live.com', 'icloud.com',
    'me.com', 'mac.com', 'protonmail.com', 'proton.me',
    'aol.com', 'yandex.com', 'yandex.ru', 'mail.ru',
    'zoho.com', 'fastmail.com', 'icloud.com',
    'microsoft.com', 'google.com', 'apple.com',
}

def _is_parked_domain(domain: str) -> str | None:
    """
    Domain'in park edilmiş / sahte / boş olup olmadığını HTTP ile kontrol eder.
    Önbellekli (24 saat TTL).

    Returns:
        'parked'  → Bilinen park/satılık sayfası
        'empty'   → İçerik çok az (< 200 karakter) — muhtemelen boş
        'timeout' → Sunucu yanıtsız
        None      → Aktif web sitesi (veya kontrol yapılamadı — güvenli say)
    """
    domain = domain.lower().strip()
    if domain in _PARKED_SKIP_DOMAINS:
        return None

    cached, hit = _cache_get(_parked_cache, domain)
    if hit:
        return cached

    result = None
    try:
        import urllib.request, socket
        url = f'http://{domain}'
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; EmailVerifier/1.0)'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            # Sadece ilk 4KB oku — park sayfaları genellikle başta kendini belli eder
            body = resp.read(4096).decode('utf-8', errors='ignore').lower()
            if len(body.strip()) < 200:
                result = 'empty'
            else:
                for pat in _PARKED_PATTERNS:
                    if pat in body:
                        result = 'parked'
                        break
    except OSError:
        # Connection refused, timeout, DNS çözümlenemedi vb.
        # NOT: bağlanamama ≠ parked — sunucu sadece HTTP kapatmış olabilir
        # Bu durumda None (güvenli) dön — hatalı pozitif riskini azalt
        result = None
    except Exception:
        result = None

    _cache_set(_parked_cache, domain, result, _CACHE_TTL_PARKED)
    return result

# SMTP throttle kilidi — aynı anda çok fazla eşzamanlı SMTP bağlantısı
# IP itibarını zedeler. Semaphore ile eşzamanlı SMTP sayısını sınırla.
import threading as _threading
_SMTP_SEMAPHORE = _threading.Semaphore(8)  # Aynı anda max 8 SMTP bağlantısı

def _smtp_check(email, mx_server):
    """
    SMTP RCPT TO ile posta kutusu varlığını test eder.
    Port sırası: 25 → 587 (STARTTLS) → 465 (SSL)
    250 | 550 | None döner.

    Büyük sağlayıcılar (Google Workspace, Microsoft 365, Yahoo) port 25'i
    dışarıdan engelleyebilir. 587/STARTTLS ve 465/SSL fallback'leri
    bu durumlarda 'unknown' oranını belirgin şekilde düşürür.
    """
    import smtplib, ssl

    REJECT_CODES = {550, 551, 552, 553, 554}

    def _try_port25():
        srv = smtplib.SMTP(mx_server, port=25, timeout=7)
        srv.ehlo_or_helo_if_needed()
        srv.mail('verify@mailsenderpro.app')
        code, _ = srv.rcpt(email)
        try: srv.quit()
        except Exception: pass
        return code

    def _try_port587():
        srv = smtplib.SMTP(mx_server, port=587, timeout=7)
        srv.ehlo_or_helo_if_needed()
        srv.starttls(context=ssl.create_default_context())
        srv.ehlo_or_helo_if_needed()
        srv.mail('verify@mailsenderpro.app')
        code, _ = srv.rcpt(email)
        try: srv.quit()
        except Exception: pass
        return code

    def _try_port465():
        ctx = ssl.create_default_context()
        srv = smtplib.SMTP_SSL(mx_server, port=465, timeout=7, context=ctx)
        srv.ehlo_or_helo_if_needed()
        srv.mail('verify@mailsenderpro.app')
        code, _ = srv.rcpt(email)
        try: srv.quit()
        except Exception: pass
        return code

    for attempt in (_try_port25, _try_port587, _try_port465):
        try:
            code = attempt()
            if code == 250:          return 250
            if code in REJECT_CODES: return 550
            # Belirsiz yanıt — sonraki portu dene
        except Exception:
            pass  # Bu port çalışmıyor — sonraki portu dene

    return None

def _catchall_check(mx_server, domain):

    """Rastgele adrese 250 dönüyorsa sunucu catch-all'dır. Önbellekli."""
    cached, hit = _cache_get(_catchall_cache, domain)
    if hit:
        return cached
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    code = _smtp_check(f"{rand}@{domain}", mx_server)
    result = (code == 250)
    _cache_set(_catchall_cache, domain, result, _CACHE_TTL_CATCHALL)
    return result

# ══════════════════════════════════════════════════════════════════
# ANA DOĞRULAMA FONKSİYONU
# ══════════════════════════════════════════════════════════════════

def verify_one(email: str, mode: str = 'mx'):
    """
    Tek e-postayı doğrular. Returns: (final_email, status, meta_dict)
    """
    original = email
    meta = {
        'original': original, 'normalized': False,
        'typo_domain': None, 'is_role': False, 'is_free': False,
        'has_spf': False, 'has_dmarc': False, 'is_catchall': False,
        'domain_age': None, 'checks': [],
        'did_you_mean': None,           # Levenshtein domain önerisi
        'toxic_domain_type': None,      # 'known_toxic' | 'pattern_match' | 'db_listed'
        'toxic_domain_confidence': None,# 'high' | 'medium' | 'low'
        'yahoo_aol_checked': False,     # Yahoo/AOL disabled user kontrolü yapıldı mı
        'yahoo_aol_signal': None,       # 'disabled' | 'active' | 'temporary_error' | ...
        'is_gibberish': False,          # Bot/oto üretim local kısmı (EmailFilter MIT)
        'has_spam_local': False,        # Spam keyword local kısmında (EmailFilter MIT)
        'esp': None,                    # E-posta servis sağlayıcısı (email-verifier-free MIT)
        'is_parked': None,              # 'parked' | 'empty' | 'timeout' | None
    }

    # 1. Normalize
    email, was_norm = _normalize(email)
    meta['normalized'] = was_norm
    meta['checks'].append('normalize')

    # 2. Format — RFC 5321 uzunluk sınırları + Türkçe karakter tespiti
    # Türkçe karakter varsa önce bildir — "format hatası" yerine daha açıklayıcı
    tr_chars = set('şğüöçıŞĞÜÖÇİ')
    if any(c in tr_chars for c in email):
        meta['has_turkish_chars'] = True
        return email, 'invalid_format', meta
    if not EMAIL_REGEX.match(email):
        return email, 'invalid_format', meta
    meta['checks'].append('format')

    local, domain = email.split('@', 1)

    # did_you_mean: format geçerliyse domain önerisini hemen hesapla
    # (sonraki adımlarda domain değişse bile orijinal yazım hatası önerilir)
    _dym = suggest_domain(domain)
    if _dym and _dym != domain.lower():
        meta['did_you_mean'] = f"{local}@{_dym}"

    # RFC 5321: local kısım max 64 karakter, toplam adres max 254 karakter
    if len(local) > 64:
        return email, 'invalid_format', meta
    if len(email) > 254:
        return email, 'invalid_format', meta
    if len(domain) > 255:
        return email, 'invalid_format', meta

    # 3. Disposable
    if domain.lower() in DISPOSABLE_DOMAINS:
        return email, 'disposable', meta
    meta['checks'].append('disposable')

    # 3b. Spam tuzağı kontrolü
    # high   → kesin tuzak, akışı kes, suppression'a ekle (is_valid=0)
    # medium → muhtemel tuzak, meta'ya yaz, risk_score -30 uygular
    # low    → şüpheli sinyal, meta'ya yaz, risk_score -15 uygular
    _trap_local = local.split('+')[0].lower().strip()
    is_trap, trap_type, trap_confidence = check_spam_trap(email, domain, _trap_local, meta)
    meta['spam_trap_type']       = trap_type
    meta['spam_trap_confidence'] = trap_confidence
    if is_trap and trap_confidence == 'high':
        meta['checks'].append('spam_trap')
        return email, 'spam_trap', meta
    elif is_trap:
        meta['checks'].append('spam_trap_signal')   # sinyal var, akış devam eder

    # 3c. Toxic domain kontrolü
    # Abuse/bot kayıt/blacklist domenlerini tespit eder — spam_trap'ten farklı:
    # tuzak değil, ama bu domainlerden gelen kullanıcılar yüksek şikayet riski taşır.
    # high   → kesin toxic, akışı kes, suppression'a ekle (is_valid=0)
    # medium → riskli, meta'ya yaz, risk_score -25 uygular
    is_toxic, toxic_type, toxic_conf = check_toxic_domain(domain, meta)
    meta['toxic_domain_type']       = toxic_type
    meta['toxic_domain_confidence'] = toxic_conf
    if is_toxic and toxic_conf == 'high':
        meta['checks'].append('toxic_domain')
        return email, 'toxic_domain', meta
    elif is_toxic:
        meta['checks'].append('toxic_domain_signal')   # sinyal var, akış devam eder

    # 4. Role account
    # Rol adresleri iki gruba ayrılır:
    # HARD_STOP: sistem adresleri — gerçek insan yok, gönderilemez
    # SOFT_ROLE: kurumsal roller — aktif kişi olabilir, risk_score'a bırak (taban skor: 50)
    HARD_STOP_ROLES = {
        'noreply', 'no-reply', 'no_reply', 'donotreply', 'do-not-reply', 'do_not_reply',
        'bounce', 'bounces', 'mailer', 'daemon', 'ndr', 'autoresponder',
        'auto-reply', 'autoreply', 'robot', 'bot', 'automated',
        'root', 'postmaster', 'hostmaster', 'listserv', 'majordomo', 'mailman',
        'unsubscribe', 'abuse',
    }
    clean_local = local.split('+')[0].lower().strip()
    meta['is_role'] = clean_local in ROLE_PREFIXES
    if meta['is_role']:
        meta['checks'].append('role')
        if clean_local in HARD_STOP_ROLES:
            # Gerçek insan olmayan sistem adresleri — akışı durdur
            return email, 'role_account', meta
        # Diğer rol adresleri (info@, sales@, contact@ vb.) — devam et, risk_score karar verir
        # meta['is_role']=True olduğu için risk_score taban skoru 50'den başlatır
    else:
        meta['checks'].append('role')

    # 4b. Gibberish (saçma) local kısım tespiti
    # Kaynak: EmailFilter (MIT). 5+ ardışık sessiz harf = bot/otomatik üretim.
    # Örnekler: xkqrtbz@, qwzxcvb@, zxcvbnm@
    # medium confidence: risk_score -20; yüksek false-positive riski olduğundan
    # akışı kesmez — meta'ya yazar, risk_score bunu değerlendirir.
    meta['is_gibberish'] = _is_gibberish(clean_local)
    if meta['is_gibberish']:
        meta['checks'].append('gibberish_signal')

    # 4c. Spam keyword tespiti (local kısımda)
    # Kaynak: EmailFilter (MIT). lottery@, winner@, fake@, throwaway@ gibi adresleri yakalar.
    # medium confidence: risk_score -15; akışı kesmez.
    meta['has_spam_local'] = _has_spam_local_keywords(clean_local)
    if meta['has_spam_local']:
        meta['checks'].append('spam_local_signal')

    # 5. Typo düzeltme
    fixed = TYPO_MAP.get(domain.lower())
    if fixed:
        meta['typo_domain'] = fixed
        domain = fixed
        email = f"{local}@{domain}"
        meta['checks'].append('typo_fixed')
        if mode == 'format':
            meta['is_free'] = domain in FREE_PROVIDERS
            return email, 'typo_fixed', meta
    else:
        meta['checks'].append('typo')

    meta['is_free'] = domain in FREE_PROVIDERS

    if mode == 'format':
        return email, 'valid', meta

    # 6. Muaf domain kontrolü — MX/SMTP atla
    # Gmail, Yahoo, Outlook vb. için MX zaten kesin var, DNS sorgusu gereksiz
    if domain.lower() in _get_smtp_skip_domains():
        meta['checks'].append('trusted_domain')
        if meta['typo_domain']: return email, 'typo_fixed', meta
        return email, 'valid', meta

    # 7. MX / A fallback
    mx = _mx_lookup(domain)
    if not mx:
        return email, 'no_mx', meta
    meta['mx_server'] = mx          # MX trap tespiti için gerekli
    meta['esp']       = _detect_esp(mx)   # ESP tespiti (email-verifier-free MIT)
    meta['checks'].append('mx')

    # 7b. Parked / sahte website kontrolü
    # MX kaydı var ama web sitesi park/boş ise — adres terk edilmiş olabilir
    # Sadece smtp/full modda ve kurumsal domainlerde çalış (muaf domainler zaten döndü)
    if mode in ('smtp', 'full', 'mx'):
        _parked = _is_parked_domain(domain)
        meta['is_parked'] = _parked
        if _parked == 'parked':
            meta['checks'].append('parked_domain')
            # Akışı kesmiyoruz — risk_score'a bırakıyoruz
            # Çünkü bazı şirketler web sitesini kapatıp mail almaya devam eder
        elif _parked == 'empty':
            meta['checks'].append('empty_website')
        elif _parked:
            meta['checks'].append('website_signal')

    # 8. SPF / DMARC + domain yaşı kontrolü
    meta['has_spf']    = _check_spf(domain)
    meta['has_dmarc']  = _check_dmarc(domain)
    meta['domain_age'] = _domain_age_days(domain)
    meta['checks'].append('spf_dmarc')
    no_infra = not meta['has_spf'] and not meta['has_dmarc']

    # Domain yaşı kontrolü: 30 günden yeni domain spam tuzağı riski taşır
    # _domain_age_days None dönebilir (WHOIS başarısızsa) — None ise atla
    domain_too_new = (
        meta['domain_age'] is not None and
        meta['domain_age'] < 30
    )
    if domain_too_new:
        meta['checks'].append('new_domain')
        return email, 'no_infra', meta   # Yeni domain → riskli

    if mode == 'mx':
        if meta['typo_domain']: return email, 'typo_fixed', meta
        if no_infra:            return email, 'no_infra', meta
        return email, 'valid', meta

    # 9. Catch-all + SMTP (sadece kurumsal / bilinmeyen domainler)
    if domain.lower() in _get_smtp_skip_domains():
        meta['checks'].append('smtp_skipped')
        if meta['typo_domain']: return email, 'typo_fixed', meta
        return email, 'valid', meta

    meta['is_catchall'] = _catchall_check(mx, domain)
    if meta['is_catchall']:
        meta['checks'].append('catchall')
        return email, 'catch_all', meta
    meta['checks'].append('catchall')

    # 10. Yahoo/AOL devre dışı kullanıcı tespiti
    # Bu sağlayıcılar SMTP'de catch-all gibi davranır (her adrese 250 döner)
    # ama yanıt metninde "disabled/suspended" gibi ifadeler geçebilir.
    # Standart _smtp_check() sadece koda bakar — bu kontrol metni de analiz eder.
    if is_yahoo_aol_domain(domain):
        ya_status, ya_meta = check_yahoo_aol(email, mx)
        meta.update(ya_meta)
        if ya_status == 'disabled_account':
            meta['checks'].append('yahoo_aol_disabled')
            return email, 'disabled_account', meta
        elif ya_status == 'valid':
            meta['checks'].append('yahoo_aol_valid')
            return email, 'typo_fixed' if meta['typo_domain'] else 'valid', meta
        # ya_status == None → belirsiz, normal SMTP akışına devam et
        meta['checks'].append('yahoo_aol_unknown')

    # 11. SMTP RCPT (sadece kurumsal / bilinmeyen domainler)
    code = _smtp_check(email, mx)
    meta['checks'].append('smtp')
    if code == 250:
        return email, 'typo_fixed' if meta['typo_domain'] else 'valid', meta
    elif code == 550:
        return email, 'invalid', meta
    return email, 'unknown', meta


# ══════════════════════════════════════════════════════════════════
# TOPLU İŞ ÇALIŞTIRICISI
# ══════════════════════════════════════════════════════════════════

def _add_risk_columns(db_module, table_name: str):
    """
    Kullanıcı tablosuna risk_score ve risk_label kolonlarını ekler (yoksa).
    verify_job_add_is_valid_column() ile aynı pattern — MySQL 5.7 uyumlu.
    """
    try:
        from security import safe_identifier
        safe_identifier(table_name)
    except Exception:
        return
    try:
        import pymysql
        conn = db_module.get_connection()
        db_name = db_module.get_db_config()['database']
        with conn.cursor() as cur:
            for col, col_type, comment in [
                ('risk_score', 'TINYINT UNSIGNED', 'Teslimat risk skoru 0-100'),
                ('risk_label', 'VARCHAR(20)',      'safe|low_risk|medium_risk|high_risk|do_not_send'),
            ]:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
                    (db_name, table_name, col)
                )
                if cur.fetchone()['cnt'] == 0:
                    cur.execute(
                        f"ALTER TABLE `{table_name}` "
                        f"ADD COLUMN `{col}` {col_type} DEFAULT NULL "
                        f"COMMENT %s",
                        (comment,)
                    )
        conn.commit()
        conn.close()
    except Exception as e:
        pass  # Kolon ekleme başarısız olsa bile doğrulama devam etsin


def _write_risk_scores(db_module, table_name: str, email_col: str, results: list):
    """
    Toplu sonuç listesindeki risk_score ve risk_label değerlerini DB'ye yazar.
    results: [(email, is_valid, status, risk_score, risk_label), ...]
    Kolon yoksa veya hata olursa sessizce atlar.
    """
    if not results:
        return
    try:
        from security import safe_identifier
        safe_identifier(table_name)
        safe_identifier(email_col)
    except Exception:
        return
    try:
        conn = db_module.get_connection()
        with conn.cursor() as cur:
            # Tek CASE WHEN sorgusuyla toplu güncelleme
            score_cases  = ' '.join(f"WHEN `{email_col}`=%s THEN %s" for _ in results)
            label_cases  = ' '.join(f"WHEN `{email_col}`=%s THEN %s" for _ in results)
            in_holders   = ','.join(['%s'] * len(results))
            sql = (
                f"UPDATE `{table_name}` SET "
                f"risk_score = CASE {score_cases} ELSE risk_score END, "
                f"risk_label = CASE {label_cases} ELSE risk_label END "
                f"WHERE `{email_col}` IN ({in_holders})"
            )
            params = []
            for em, iv, st, rs, rl in results:
                params.extend([em, rs])          # score CASE
            for em, iv, st, rs, rl in results:
                params.extend([em, rl])          # label CASE
            for em, iv, st, rs, rl in results:
                params.append(em)                # IN listesi
            cur.execute(sql, params)
        conn.commit()
        conn.close()
    except Exception:
        pass  # Risk skoru yazılamazsa doğrulama sonucu etkilenmesin


def run_verify_job(job_id, cancel_flags, progress_callback=None):
    """
    DB'deki email_verify_jobs kaydını çalıştırır.

    Performans optimizasyonları:
    - format modu: tek döngü, thread overhead yok, sonuçlar bellekte birikir,
      sonda tek toplu UPDATE (CASE WHEN) ile DB'ye yazılır → çok hızlı
    - mx/smtp modu: ThreadPoolExecutor, her 100 mailden sonra ara DB yazma
    """
    import datetime
    import database as db_module
    from risk_score import calculate_risk_score

    job = db_module.verify_job_get(job_id)
    if not job:
        return {'error': 'İş bulunamadı'}

    table_name = job['table_name']
    email_col  = job['email_col']
    mode       = job['mode']
    threads    = min(int(job.get('threads') or 10), 15)  # Max 15 — IP itibarını koru

    db_module.verify_job_add_is_valid_column(table_name, email_col)
    _add_risk_columns(db_module, table_name)
    db_module.verify_job_update(job_id, status='running',
                                started_at=datetime.datetime.utcnow())

    ok, rows = db_module.get_table_rows(table_name, only_unchecked=True)
    if not ok:
        db_module.verify_job_update(job_id, status='cancelled')
        return {'error': str(rows)}

    if not rows:
        # Tüm adresler zaten doğrulanmış — işi tamamlandı say
        db_module.verify_job_update(job_id, status='done',
                                    finished_at=datetime.datetime.utcnow(),
                                    processed_count=0)
        return {'message': 'Tüm adresler zaten doğrulanmış, yeniden işleme gerek yok.'}

    # Suppression'daki adresleri zaten biliyoruz — yeniden doğrulama gereksiz
    # Bunları hızlıca is_valid=0 olarak işaretle, WHOIS/SMTP süresi harcama
    try:
        suppressed_set = set()
        import database as _db2
        supp_rows, _ = _db2.get_suppression_list(page=1, per_page=999999)
        suppressed_set = {r['email'].lower() for r in supp_rows if r.get('email')}
    except Exception:
        suppressed_set = set()

    def _extract_emails_from_cell(cell_value):
        """
        Excel hücresinde birden fazla e-posta olabilir (virgül/noktalı virgülle ayrılmış).
        Örn: "a@b.com; c@d.com" → ["a@b.com", "c@d.com"]
        Sadece '@' içerenleri döner.
        """
        raw = str(cell_value).strip()
        # Virgül veya noktalı virgülle ayır
        import re as _re
        parts = _re.split(r'[,;]+', raw)
        result = []
        for p in parts:
            p = p.strip().lower()
            if p and '@' in p and len(p) > 3:
                result.append(p)
        return result

    raw_emails = []
    for r in rows:
        cell = r.get(email_col)
        if cell:
            raw_emails.extend(_extract_emails_from_cell(cell))

    # Suppression'dakileri önceden işaretle
    pre_suppressed = []
    emails = []
    for em in raw_emails:
        if em in suppressed_set:
            pre_suppressed.append(em)
        else:
            emails.append(em)

    # Pre-suppressed adresleri hemen DB'ye yaz (is_valid=0)
    if pre_suppressed:
        pre_results = [(em, 0, 'invalid') for em in pre_suppressed]
        db_module.verify_job_mark_emails_bulk(table_name, email_col, pre_results)
        total_pre = len(pre_suppressed)
    else:
        total_pre = 0

    total = len(emails) + total_pre
    cancel_event = cancel_flags.get(job_id, threading.Event())
    # stats: pre_suppressed adresler geçersiz sayılır — başlangıç değerleri buradan
    stats = {
        'processed': total_pre,   # suppression'dakiler zaten işlendi
        'valid':     0,
        'invalid':   total_pre,   # suppression'dakiler geçersiz
        'unknown':   0,
        'suppressed':0,'role':0,'typo':0,'catch_all':0,
        'no_infra':0,'cancelled':False,
    }

    # Sonuçları bellekte topla → sonda toplu DB yazma
    results = []  # [(original_email, is_valid_val, status, risk_score, risk_label)]

    # ── FORMAT MODU: thread overhead yok, salt Python döngüsü ──────
    if mode == 'format':
        FORMAT_BATCH = 2000  # Her 2000 adiste bir DB'ye yaz ve sayaçları güncelle
        for em in emails:
            if cancel_event.is_set():
                stats['cancelled'] = True
                break
            final_email, status, meta = verify_one(em, mode)
            iv = STATUS_TO_IS_VALID.get(status, -1)
            # Format modunda DB sorgusu atla (hız öncelikli) — include_db=False
            risk = calculate_risk_score(final_email, status, meta, include_db=False)
            results.append((meta.get('original', final_email), iv, status,
                            risk['score'], risk['label']))
            stats['processed'] += 1
            if iv == 1:   stats['valid']   += 1
            elif iv == 0: stats['invalid'] += 1
            else:         stats['unknown'] += 1
            if status == 'role_account': stats['role'] += 1
            if status == 'typo_fixed':   stats['typo'] += 1

            # Ara DB yazma — UI sayaçları güncellenir, sıfır göstermez
            if len(results) >= FORMAT_BATCH:
                db_module.verify_job_mark_emails_bulk(table_name, email_col, results)
                for orig, iv2, st2, rs, rl in results:
                    if st2 in SUPPRESSION_STATUSES:
                        db_module.add_to_suppression(orig, 'invalid', source='email_verify')
                        stats['suppressed'] += 1
                _write_risk_scores(db_module, table_name, email_col, results)
                results.clear()
                # İlerleme sayaçlarını DB'ye yaz
                db_module.verify_job_update(job_id,
                    processed_count=stats['processed'],
                    valid_count=stats['valid'],
                    invalid_count=stats['invalid'],
                    unknown_count=stats['unknown'],
                    suppressed_count=stats['suppressed'])

        # Kalan adresler
        if results:
            db_module.verify_job_mark_emails_bulk(table_name, email_col, results)
            for orig, iv, status, rs, rl in results:
                if status in SUPPRESSION_STATUSES:
                    db_module.add_to_suppression(orig, 'invalid', source='email_verify')
                    stats['suppressed'] += 1
            _write_risk_scores(db_module, table_name, email_col, results)

    # ── MX / SMTP MODU: paralel thread, ara DB yazma ───────────────
    else:
        def do_one(em):
            """Tek e-postayı doğrular, iptal sinyali varsa (None, None, {}) döner."""
            if cancel_event.is_set():
                return em, None, {}
            return verify_one(em, mode)

        batch = []  # Ara yazma için buffer
        BATCH_SIZE = 100

        with ThreadPoolExecutor(max_workers=threads) as ex:
            futs = {ex.submit(do_one, e): e for e in emails}
            for f in as_completed(futs):
                if cancel_event.is_set():
                    ex.shutdown(wait=False, cancel_futures=True)
                    stats['cancelled'] = True
                    break
                try:
                    final_email, status, meta = f.result()
                except Exception:
                    continue
                if status is None:
                    continue

                iv = STATUS_TO_IS_VALID.get(status, -1)
                orig = meta.get('original', final_email)
                # MX/SMTP modunda DB geçmişi de kontrol edilir — include_db=True
                risk = calculate_risk_score(final_email, status, meta, include_db=True)
                batch.append((orig, iv, status, risk['score'], risk['label']))
                stats['processed'] += 1
                if iv == 1:   stats['valid']   += 1
                elif iv == 0: stats['invalid'] += 1
                else:         stats['unknown'] += 1
                if status == 'role_account': stats['role']      += 1
                if status == 'typo_fixed':   stats['typo']      += 1
                if status == 'catch_all':    stats['catch_all'] += 1
                if status == 'no_infra':     stats['no_infra']  += 1

                # Greylisting retry: SMTP'den None dönen (unknown) adresleri kuyruğa ekle
                if status == 'unknown' and mode == 'smtp':
                    try:
                        enqueue_greylist_retry(
                            email=orig,
                            table_name=table_name,
                            email_col=email_col,
                            job_id=job_id,
                            mx_server=meta.get('mx_server', ''),
                        )
                    except Exception:
                        pass

                # Her BATCH_SIZE mailden sonra DB'ye yaz
                if len(batch) >= BATCH_SIZE:
                    db_module.verify_job_mark_emails_bulk(table_name, email_col, batch)
                    for orig2, iv2, st2, rs2, rl2 in batch:
                        if st2 in SUPPRESSION_STATUSES:
                            db_module.add_to_suppression(orig2, 'invalid', source='email_verify')
                            stats['suppressed'] += 1
                    _write_risk_scores(db_module, table_name, email_col, batch)
                    batch.clear()
                    db_module.verify_job_update(job_id,
                        processed_count=stats['processed'],
                        valid_count=stats['valid'],
                        invalid_count=stats['invalid'],
                        unknown_count=stats['unknown'],
                        suppressed_count=stats['suppressed'])

                if progress_callback:
                    try:
                        progress_callback(stats['processed'], total,
                                          stats['valid'], stats['invalid'], stats['unknown'])
                    except Exception:
                        pass

        # Kalan batch'i yaz
        if batch:
            db_module.verify_job_mark_emails_bulk(table_name, email_col, batch)
            for orig2, iv2, st2, rs2, rl2 in batch:
                if st2 in SUPPRESSION_STATUSES:
                    db_module.add_to_suppression(orig2, 'invalid', source='email_verify')
                    stats['suppressed'] += 1
            _write_risk_scores(db_module, table_name, email_col, batch)

    final = 'cancelled' if stats['cancelled'] else 'done'
    db_module.verify_job_update(job_id,
        status=final,
        processed_count=stats['processed'],
        valid_count=stats['valid'],
        invalid_count=stats['invalid'],
        unknown_count=stats['unknown'],
        suppressed_count=stats['suppressed'],
        finished_at=datetime.datetime.utcnow())
    return stats
