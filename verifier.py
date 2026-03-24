"""
verifier.py — MailSender Pro Gelişmiş E-posta Doğrulama Motoru
==============================================================
8 katmanlı doğrulama sistemi.

KONTROL KATMANLARI:
  1. Syntax normalizasyonu  — büyük harf, +tag temizleme, googlemail→gmail
  2. Format kontrolü        — RFC uyumlu regex
  3. Disposable tespiti     — ~150 geçici mail servisi
  4. Role account tespiti   — info@, admin@, noreply@ vb.
  5. Typo düzeltme          — gmial.com→gmail.com, yahooo.com→yahoo.com
  6. MX / A kaydı fallback  — DNS sorgusu, MX yoksa A kaydı dener
  7. SPF / DMARC varlığı    — Domain mail altyapısı yapılandırılmış mı?
  8. Catch-all tespiti      — Sunucu her adrese 250 veriyorsa tespit edilir
  9. SMTP RCPT doğrulaması  — Gerçek posta kutusu varlık kontrolü

DURUM KODLARI:
  valid          → Tüm aktif kontroller geçti
  invalid_format → Format geçersiz
  disposable     → Geçici servis
  role_account   → Kişisel olmayan rol adresi
  typo_fixed     → Yazım hatası düzeltildi
  no_mx          → DNS kaydı yok
  no_infra       → SPF/DMARC yok — zayıf domain
  catch_all      → Catch-all sunucu (teslim edilebilir ama belirsiz)
  invalid        → SMTP 550 posta kutusu yok
  unknown        → SMTP belirsiz yanıt
  free_provider  → Gmail/Hotmail vb. (bilgi amaçlı)

is_valid DB değerleri:
   1 → valid, typo_fixed, catch_all, free_provider, no_infra
   0 → invalid_format, disposable, no_mx, invalid
  -1 → unknown, role_account
"""

import re, socket, random, string, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    "invalid_format":0,"disposable":0,"no_mx":0,"invalid":0,
}

# Suppression'a eklenecek kesin geçersizler
SUPPRESSION_STATUSES = {"invalid_format","disposable","no_mx","invalid"}

# ── DNS / SMTP önbellekleri ────────────────────────────────────────
_mx_cache:       dict = {}
_spf_cache:      dict = {}
_dmarc_cache:    dict = {}
_catchall_cache: dict = {}

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
    if domain in _mx_cache:
        return _mx_cache[domain]
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
    _mx_cache[domain] = mx_addr
    return mx_addr

def _check_spf(domain):

    """Domain için SPF (TXT) kaydı varlığını kontrol eder. Önbellekli."""
    domain = domain.lower()
    if domain in _spf_cache:
        return _spf_cache[domain]
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
    _spf_cache[domain] = result
    return result

def _check_dmarc(domain):

    """Domain için DMARC (_dmarc.domain TXT) kaydı varlığını kontrol eder. Önbellekli."""
    domain = domain.lower()
    if domain in _dmarc_cache:
        return _dmarc_cache[domain]
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
    _dmarc_cache[domain] = result
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

def _smtp_check(email, mx_server):

    """SMTP RCPT TO komutu ile posta kutusu varlığını test eder. 250|550|None döner."""
    try:
        import smtplib
        srv = smtplib.SMTP(mx_server, port=25, timeout=7)
        srv.ehlo_or_helo_if_needed()
        srv.mail('verify@mailsenderpro.app')
        code, _ = srv.rcpt(email)
        try: srv.quit()
        except Exception: pass
        if code == 250: return 250
        if code in (550,551,552,553,554): return 550
        return None
    except Exception:
        return None

def _catchall_check(mx_server, domain):

    """Rastgele adrese 250 dönüyorsa sunucu catch-all'dır. Önbellekli."""
    if domain in _catchall_cache:
        return _catchall_cache[domain]
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    code = _smtp_check(f"{rand}@{domain}", mx_server)
    result = (code == 250)
    _catchall_cache[domain] = result
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

    # 4. Role account
    clean_local = local.split('+')[0].lower().strip()
    meta['is_role'] = clean_local in ROLE_PREFIXES
    if meta['is_role']:
        meta['checks'].append('role')
        return email, 'role_account', meta
    meta['checks'].append('role')

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
    meta['checks'].append('mx')

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

    # 9. SMTP RCPT (sadece kurumsal / bilinmeyen domainler)
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

    job = db_module.verify_job_get(job_id)
    if not job:
        return {'error': 'İş bulunamadı'}

    table_name = job['table_name']
    email_col  = job['email_col']
    mode       = job['mode']
    threads    = min(int(job.get('threads') or 10), 20)

    db_module.verify_job_add_is_valid_column(table_name, email_col)
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
    results = []  # [(original_email, is_valid_val, status)]

    # ── FORMAT MODU: thread overhead yok, salt Python döngüsü ──────
    if mode == 'format':
        FORMAT_BATCH = 2000  # Her 2000 adiste bir DB'ye yaz ve sayaçları güncelle
        for em in emails:
            if cancel_event.is_set():
                stats['cancelled'] = True
                break
            final_email, status, meta = verify_one(em, mode)
            iv = STATUS_TO_IS_VALID.get(status, -1)
            results.append((meta.get('original', final_email), iv, status))
            stats['processed'] += 1
            if iv == 1:   stats['valid']   += 1
            elif iv == 0: stats['invalid'] += 1
            else:         stats['unknown'] += 1
            if status == 'role_account': stats['role'] += 1
            if status == 'typo_fixed':   stats['typo'] += 1

            # Ara DB yazma — UI sayaçları güncellenir, sıfır göstermez
            if len(results) >= FORMAT_BATCH:
                db_module.verify_job_mark_emails_bulk(table_name, email_col, results)
                for orig, iv2, st2 in results:
                    if st2 in SUPPRESSION_STATUSES:
                        db_module.add_to_suppression(orig, 'invalid', source='email_verify')
                        stats['suppressed'] += 1
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
            for orig, iv, status in results:
                if status in SUPPRESSION_STATUSES:
                    db_module.add_to_suppression(orig, 'invalid', source='email_verify')
                    stats['suppressed'] += 1

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
                batch.append((orig, iv, status))
                stats['processed'] += 1
                if iv == 1:   stats['valid']   += 1
                elif iv == 0: stats['invalid'] += 1
                else:         stats['unknown'] += 1
                if status == 'role_account': stats['role']      += 1
                if status == 'typo_fixed':   stats['typo']      += 1
                if status == 'catch_all':    stats['catch_all'] += 1
                if status == 'no_infra':     stats['no_infra']  += 1

                # Her BATCH_SIZE mailden sonra DB'ye yaz
                if len(batch) >= BATCH_SIZE:
                    db_module.verify_job_mark_emails_bulk(table_name, email_col, batch)
                    for orig2, iv2, st2 in batch:
                        if st2 in SUPPRESSION_STATUSES:
                            db_module.add_to_suppression(orig2, 'invalid', source='email_verify')
                            stats['suppressed'] += 1
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
            for orig2, iv2, st2 in batch:
                if st2 in SUPPRESSION_STATUSES:
                    db_module.add_to_suppression(orig2, 'invalid', source='email_verify')
                    stats['suppressed'] += 1

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
