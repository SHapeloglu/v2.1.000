"""
toxic_domain.py — Toxic Domain Tespit Modülü
=============================================
verifier.py'ye entegre çalışır; verify_one() içinde disposable ve spam_trap
kontrollerinden hemen sonra çağrılır.

TOXIC DOMAIN NEDİR?
--------------------
Spam tuzaklarından farklı olarak, toxic domainler gerçek kullanıcılara ait
olabilir ancak bu domainlerden gelen veya bu domainlere gönderilen e-postalar
gönderici itibarını ciddi biçimde zedeler. Üç ana kategori:

1. Abuse/Complaint domainleri
   Yüksek oranda abuse bildirimi ve spam şikayeti alan domainler.
   Bu domainlerdeki kullanıcılar e-postaları sık sık spam olarak işaretler.

2. Bot/Fake kayıt domainleri
   Otomatik bot kayıtlarında yaygın kullanılan; gerçek insan kullanıcısı
   neredeyse hiç olmayan geçici veya sahte servis domainleri.
   Disposable'dan farkı: domain aktif görünür ve MX kaydı vardır.

3. High-risk / Kötü itibar domainleri
   Spam blacklist'lerinde sık görülen, bulk sender olarak bilinen veya
   e-posta güvenlik şirketleri tarafından riskli işaretlenmiş domainler.

DURUM KODLARI (verify_one entegrasyonu):
  toxic_domain  → is_valid=0, suppression'a eklenir
  
  check_toxic_domain() şunu döner:
    (is_toxic: bool, toxic_type: str | None, confidence: str | None)

  confidence:
    'high'   → Kesin toxic, akışı kes (is_valid=0, suppression)
    'medium' → Riskli, risk_score -25 uygular, akış devam eder
    'low'    → Şüpheli sinyal, risk_score -10 uygular

ENTEGRASYON (verifier.py):
    from toxic_domain import check_toxic_domain
    is_toxic, toxic_type, toxic_conf = check_toxic_domain(domain, meta)
    meta['toxic_domain_type']       = toxic_type
    meta['toxic_domain_confidence'] = toxic_conf
    if is_toxic and toxic_conf == 'high':
        meta['checks'].append('toxic_domain')
        return email, 'toxic_domain', meta
    elif is_toxic:
        meta['checks'].append('toxic_domain_signal')
"""

from __future__ import annotations
import re
import threading
import time

# ── Bilinen yüksek-abuse domainleri ───────────────────────────────────────────
# Spam şikayeti oranı yüksek, e-posta pazarlama sektöründe "toxic" olarak
# bilinen domainler. Kaynak: industry blacklist raporları ve abuse veritabanları.
TOXIC_DOMAINS: frozenset[str] = frozenset({

    # ── Yüksek abuse / şikayet oranı bilinen domainler ──────────────────────
    "guerrillamail.info",
    "guerrillamail.biz",
    "guerrillamail.de",
    "guerrillamail.net",
    "guerrillamail.org",
    "spam4.me",
    "spamgourmet.com",
    "spamgourmet.net",
    "spamgourmet.org",
    "spamhole.com",
    "spamthis.co.uk",
    "spamtrap.ro",
    "jetable.com",
    "jetable.fr.nf",
    "jetable.net",
    "jetable.org",
    "trashmail.at",
    "trashmail.io",
    "trashmail.me",
    "trashmail.net",
    "trashmail.org",
    "trashmail.xyz",
    "trashmail.com",
    "sharklasers.com",
    "guerrillamailblock.com",
    "grr.la",
    "spam.la",
    "binkmail.com",
    "safetymail.info",
    "spamfree24.org",
    "spamfree24.de",
    "spamfree24.net",
    "spamfree24.eu",
    "spamfree24.info",
    "spamfree.eu",
    "spamoff.de",
    "spamoverwhelm.me",

    # ── Bot kayıt domainleri (MX var ama gerçek kullanıcı yok) ───────────────
    "mailnull.com",
    "maileater.com",
    "mail-filter.com",
    "nobulk.com",
    "nospam4.us",
    "nospamfor.us",
    "nospamthanks.info",
    "no-spam.ws",
    "nospam.ze.tc",
    "objectmail.com",
    "obobbo.com",
    "odaymail.com",
    "odnorazovoe.ru",
    "oneoffemail.com",
    "onewaymail.com",
    "onlatedotcom.info",
    "online.ms",
    "oopi.org",
    "opayq.com",
    "ordinaryamerican.net",
    "otherinbox.com",
    "ourklips.com",
    "outlawspam.com",
    "ovpn.to",
    "owlpic.com",

    # ── Kötü itibarıyla bilinen / blacklist'te sık görülen ───────────────────
    "abcmail.email",
    "abusemail.de",
    "altn.com",
    "antispam.de",
    "antispam24.de",
    "antispammail.de",
    "armyspy.com",
    "aron.us",
    "baxomale.ht.cx",
    "beefmilk.com",
    "bigstring.com",
    "binkmail.com",
    "bio-muesli.net",
    "bobmail.info",
    "bodhi.lawlita.com",
    "bofthew.com",
    "bootybay.de",
    "boun.cr",
    "bouncr.com",
    "breakthru.com",
    "brefmail.com",
    "brennendesreich.de",
    "broadbandninja.com",
    "bsnow.net",
    "bspamfree.org",
    "buffemail.com",
    "bugmenever.com",
    "bugmenot.com",
    "bumpymail.com",
    "bund.us",
    "burnthespam.info",
    "burstmail.info",
    "buymoreplays.com",
    "buyusedlibrarybooks.org",
    "byom.de",

    # ── Çeşitli abuse kaynaklı ────────────────────────────────────────────────
    "casualdx.com",
    "cek.pm",
    "centermail.com",
    "centermail.net",
    "chammy.info",
    "cheatmail.de",
    "chewiemail.com",
    "chogmail.com",
    "choicemail1.com",
    "clixser.com",
    "cmail.club",
    "cmail.com",
    "cmail.net",
    "cmail.org",
    "coldemail.info",
    "cool.fr.nf",
    "correo.blogos.net",
    "courriel.fr.nf",
    "courrieltemporaire.com",
    "crapmail.org",
    "crazymailing.com",
    "cron.sytes.net",
    "curryworld.de",
    "cust.in",
    "cuvox.de",
})

# ── Pattern tabanlı toxic tespit ─────────────────────────────────────────────
# Domain adında belirli anahtar kelimeler varsa toxic olarak işaretle
_TOXIC_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bspam\b',    re.I), 'spam_keyword'),
    (re.compile(r'\babuse\b',   re.I), 'abuse_keyword'),
    (re.compile(r'\bfakemail\b',re.I), 'fake_keyword'),
    (re.compile(r'\bnospam\b',  re.I), 'nospam_keyword'),
    (re.compile(r'\btrash\b',   re.I), 'trash_keyword'),
    (re.compile(r'\bjunk\b',    re.I), 'junk_keyword'),
    (re.compile(r'\bthrowaway\b',re.I),'throwaway_keyword'),
    (re.compile(r'\bfakemail\b',re.I), 'fake_keyword'),
    (re.compile(r'\bblackhole\b',re.I),'blackhole_keyword'),
]

# ── DB'den yüklenen dinamik toxic listesi önbelleği ──────────────────────────
_TOXIC_DB_CACHE: set[str] = set()
_TOXIC_DB_LOCK  = threading.Lock()
_TOXIC_DB_TS    = 0.0
_TOXIC_DB_TTL   = 3600.0   # 60 dakika

def _load_toxic_from_db() -> set[str]:
    """
    DB'deki toxic domain listesini yükler (TTL önbellekli).
    toxic_domains tablosu yoksa veya bağlantı hata verirse boş set döner.
    Tablo şeması (önerilir):
        CREATE TABLE toxic_domains (
            domain VARCHAR(255) PRIMARY KEY,
            reason VARCHAR(64),
            confidence ENUM('high','medium','low') DEFAULT 'high',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    global _TOXIC_DB_CACHE, _TOXIC_DB_TS
    now = time.monotonic()
    with _TOXIC_DB_LOCK:
        if now - _TOXIC_DB_TS < _TOXIC_DB_TTL:
            return _TOXIC_DB_CACHE
    try:
        import database as db
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT domain FROM toxic_domains")
            rows = cur.fetchall()
        conn.close()
        result = {r['domain'].lower().strip() for r in rows if r.get('domain')}
    except Exception:
        result = set()
    with _TOXIC_DB_LOCK:
        _TOXIC_DB_CACHE = result
        _TOXIC_DB_TS    = time.monotonic()
    return result


def check_toxic_domain(domain: str, meta: dict) -> tuple[bool, str | None, str | None]:
    """
    Domain'in toxic olup olmadığını kontrol eder.

    Args:
        domain: Kontrol edilecek domain (ör: 'spamhole.com')
        meta:   verify_one() meta sözlüğü (bilgi eklemek için)

    Returns:
        (is_toxic, toxic_type, confidence)
        is_toxic   : True ise toxic tespit edildi
        toxic_type : 'known_toxic' | 'pattern_match' | 'db_listed' | None
        confidence : 'high' | 'medium' | 'low' | None
    """
    d = domain.lower().strip()

    # 1. Sabit listede var mı?
    if d in TOXIC_DOMAINS:
        meta.setdefault('toxic_reason', 'known_toxic_domain')
        return True, 'known_toxic', 'high'

    # 2. DB'den yüklenen dinamik listede var mı?
    db_list = _load_toxic_from_db()
    if d in db_list:
        meta.setdefault('toxic_reason', 'db_listed_toxic')
        return True, 'db_listed', 'high'

    # 3. Pattern eşleşmesi (domain adında spam/abuse gibi kelimeler)
    for pattern, ptype in _TOXIC_PATTERNS:
        if pattern.search(d):
            meta.setdefault('toxic_reason', f'pattern:{ptype}')
            # Pattern eşleşmesi orta güvende — domain gerçekten anti-spam
            # servis de olabilir (ör: antispam.org gibi kurumsal domainler)
            return True, 'pattern_match', 'medium'

    return False, None, None


def add_toxic_domain_to_db(domain: str, reason: str = 'manual',
                            confidence: str = 'high') -> bool:
    """
    Yeni bir toxic domain'i DB'ye ekler ve önbelleği geçersiz kılar.
    
    Args:
        domain:     Eklenecek domain
        reason:     Ekleme nedeni ('manual', 'bounce_rate', 'complaint', vb.)
        confidence: 'high' | 'medium' | 'low'
    
    Returns:
        True: Başarıyla eklendi, False: Hata oluştu
    """
    global _TOXIC_DB_TS
    try:
        import database as db
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO toxic_domains (domain, reason, confidence)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE reason=%s, confidence=%s
                """,
                (domain.lower().strip(), reason, confidence, reason, confidence)
            )
        conn.commit()
        conn.close()
        # Önbelleği geçersiz kıl
        with _TOXIC_DB_LOCK:
            _TOXIC_DB_TS = 0.0
        return True
    except Exception:
        return False


def get_toxic_domain_count() -> dict:
    """
    Toxic domain istatistiklerini döner (UI için).
    Returns: {'builtin': int, 'db': int, 'total': int}
    """
    db_count = len(_load_toxic_from_db())
    return {
        'builtin': len(TOXIC_DOMAINS),
        'db':      db_count,
        'total':   len(TOXIC_DOMAINS) + db_count,
    }
