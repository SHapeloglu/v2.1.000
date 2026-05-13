"""
spam_trap.py — Spam Tuzağı Tespit Motoru
=========================================
verifier.py'ye entegre çalışır; verify_one() içinde disposable kontrolünden
hemen sonra çağrılır.

SPAM TUZAĞI TÜRLERİ
--------------------
1. Pristine trap (saf tuzak)
   Hiçbir zaman gerçek bir kullanıcıya ait olmamış, yalnızca spam tuzağı
   amacıyla oluşturulmuş adresler. Genellikle web scraping ile toplanan
   listelerde görülür. Bunlara e-posta göndermek, gönderici itibarını
   ciddi biçimde zedeler.

2. Recycled trap (geri dönüştürülmüş tuzak)
   Eskiden gerçek bir kullanıcıya ait olan, uzun süre aktif olmadıktan
   sonra ISP/ESP tarafından tuzağa dönüştürülmüş adresler. Liste
   hijyeninin ne kadar önemli olduğunu ölçer.

3. Typo trap
   Yaygın sağlayıcı adlarının bilerek yanlış yazılmış versiyonları
   (gmali.com, yhaoo.com gibi). Satın alınmış veya kötü form doğrulaması
   olan listelerden gelir.

4. Honeypot trap
   Botların topladığı gizli/görünmez form alanlarına yerleştirilen
   adresler. Local kısım kalıplarıyla tespit edilir.

NASIL ÇALIŞIR
-------------
check_spam_trap(email, domain, local, meta) çağrısı şunu döner:
    (is_trap: bool, trap_type: str | None, confidence: str | None)

confidence: 'high' | 'medium' | 'low'
    high   → Kesin tuzak, doğrulama sonucuna bakılmaksızın is_valid=0
    medium → Muhtemel tuzak, risk skoruna yansıtılır (-30 puan)
    low    → Şüpheli, risk skoruna hafifçe yansıtılır (-15 puan)

ENTEGRASYON
-----------
verifier.py içinde disposable kontrolünden sonra:

    from spam_trap import check_spam_trap
    is_trap, trap_type, confidence = check_spam_trap(email, domain, local, meta)
    if is_trap and confidence == 'high':
        meta['spam_trap_type'] = trap_type
        meta['spam_trap_confidence'] = confidence
        meta['checks'].append('spam_trap')
        return email, 'spam_trap', meta
    elif is_trap:
        meta['spam_trap_type'] = trap_type
        meta['spam_trap_confidence'] = confidence
        meta['checks'].append('spam_trap')
        # Akışı kesmez — risk_score'a bilgi geçer, statü 'valid'/'catch_all' kalır

risk_score.py içinde calculate_risk_score() fonksiyonuna:

    if meta.get('spam_trap_type'):
        confidence = meta.get('spam_trap_confidence', 'medium')
        if confidence == 'high':
            return _build_result(0, [f'Spam tuzağı tespit edildi ({meta["spam_trap_type"]})'], db_checked=False)
        elif confidence == 'medium':
            score -= 30
            reasons.append(f'Muhtemel spam tuzağı: {meta["spam_trap_type"]} (-30)')
        else:
            score -= 15
            reasons.append(f'Şüpheli spam tuzağı sinyali: {meta["spam_trap_type"]} (-15)')
"""

from __future__ import annotations
import re

# ── Bilinen pristine spam tuzağı domainleri ───────────────────────────────────
# Bu domainler hiçbir zaman gerçek kullanıcıya e-posta servisi sunmamıştır.
# Blacklist sağlayıcıları (Spamhaus, SURBL, vb.) tarafından yönetilir.
PRISTINE_TRAP_DOMAINS: frozenset[str] = frozenset({
    # Spamhaus tarafından işletilen / kamuya açık tuzak domainleri
    "spamtrap.ro",
    "spamtrap.net",
    "spamtrap.com",
    "trapped.me",
    "spamgoes.in",
    "spamhere.net",
    "trapthem.net",
    # Araştırma / honeypot kurumları
    "abuse.ro",
    "spamhole.com",
    "honeypot.net",
    "project-honeypot.org",
    # ISP geri dönüştürülmüş tuzak domainleri (devre dışı bırakılmış servisler)
    "spamtrap.cx",
    "spamtrap.info",
    "mailspam.me",
    "spambog.com",
    "spambog.de",
    "spambog.ru",
})

# ── Typo trap domainleri ──────────────────────────────────────────────────────
# Yaygın sağlayıcı adlarının bilerek yanlış yazılmış versiyonları.
# Bunlar satın alınmış veya scrape edilmiş listelerden gelir.
# Not: verifier.py'nin TYPO_MAP'i genel yazım hatalarını düzeltir;
# bu liste ise düzeltilemeyecek kadar egzotik tuzak versiyonlarını kapsar.
TYPO_TRAP_DOMAINS: frozenset[str] = frozenset({
    # Gmail tuzakları
    "gmali.com", "gmaail.com", "gmaill.com", "gmails.com",
    "gmailc.om", "gmai1.com", "gma1l.com", "gmai.com.co",
    # Yahoo tuzakları
    "yhaoo.com", "yahooo.net", "yahho.com", "yaho.net",
    "yahooo.net", "yaho0.com",
    # Hotmail tuzakları
    "hotmai1.com", "hotmial.net", "hotnail.net", "hotmai.net",
    "hotmaill.net", "h0tmail.com",
    # Outlook tuzakları
    "outlookk.com", "outloook.net", "outlok.net",
    # iCloud tuzakları
    "iclooud.net", "iclould.net",
})

# ── Recycled trap sinyalleri ──────────────────────────────────────────────────
# Bu local (kullanıcı adı) kalıpları, ISP'lerin tuzağa dönüştürdüğü hesapları
# işaret eden örüntülerdir. Tek başına yeterli kanıt değildir; diğer
# sinyallerle birlikte değerlendirilir.
_RECYCLED_LOCAL_PATTERNS: list[re.Pattern] = [
    # Eski ISP test hesapları — "test" + rakam
    re.compile(r'^test\d{2,}$'),
    # Honeypot formu dolduranların kullandığı kalıplar
    re.compile(r'^hp[a-z]{3,8}\d{4,}$'),        # hp + rastgele + yıl
    re.compile(r'^trap[a-z0-9]{4,10}$'),
    re.compile(r'^spamtrap[a-z0-9]{0,8}$'),
    re.compile(r'^honeypot[a-z0-9]{0,8}$'),
    re.compile(r'^nospam[a-z0-9]{0,8}$'),
    re.compile(r'^antispam[a-z0-9]{0,8}$'),
    # Blacklist araştırma organizasyonlarına ait bilinen local kalıpları
    re.compile(r'^sb\d{6,}$'),                  # Spamhaus tuzak formatı
    re.compile(r'^trap\d{4,}@'),                # trap + yıl/id
]

# ── Honeypot form local kalıpları ─────────────────────────────────────────────
# Web formlarındaki gizli alanlara otomatik doldurulan adresler.
# Bot tarafından üretilmiş, hiçbir zaman gerçek inbox'a sahip olmamış.
_HONEYPOT_LOCAL_PATTERNS: list[re.Pattern] = [
    re.compile(r'^[a-z]{1,3}\d{8,}$'),          # kısa harf + uzun rakam dizisi
    re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-'),   # UUID formatı local kısımda
    re.compile(r'^\d{10,}$'),                    # sadece 10+ rakam
    re.compile(r'^[a-z]{20,}$'),                 # 20+ küçük harf (rastgele string)
    re.compile(r'^noreply\+[a-z0-9]{8,}$'),     # noreply + token
    re.compile(r'^do[-_]?not[-_]?reply\+[a-z0-9]{6,}$'),
]

# ── Yüksek riskli MX sunucu kalıpları ────────────────────────────────────────
# Bazı MX sunucuları yalnızca tuzak amaçlı kullanılır.
_TRAP_MX_PATTERNS: list[re.Pattern] = [
    re.compile(r'spamtrap', re.IGNORECASE),
    re.compile(r'honeypot', re.IGNORECASE),
    re.compile(r'blackhole', re.IGNORECASE),
    re.compile(r'devnull',   re.IGNORECASE),
    re.compile(r'\/dev\/null', re.IGNORECASE),
]


# ══════════════════════════════════════════════════════════════════════════════
# ANA KONTROL FONKSİYONU
# ══════════════════════════════════════════════════════════════════════════════

def check_spam_trap(
    email:  str,
    domain: str,
    local:  str,
    meta:   dict,
) -> tuple[bool, str | None, str | None]:
    """
    E-postanın spam tuzağı olup olmadığını kontrol eder.

    Args:
        email:  Normalize edilmiş tam e-posta adresi
        domain: Alan adı kısmı (@ sonrası)
        local:  Kullanıcı adı kısmı (@ öncesi)
        meta:   verify_one() meta sözlüğü (MX, SPF, domain_age bilgileri var)

    Returns:
        (is_trap, trap_type, confidence)
        is_trap    : bool   — Tuzak sinyali var mı?
        trap_type  : str    — 'pristine' | 'typo_trap' | 'recycled' |
                              'honeypot' | 'mx_trap' | None
        confidence : str    — 'high' | 'medium' | 'low' | None
    """
    domain_lower = domain.lower().strip()
    local_lower  = local.lower().strip()

    # ── 1. Pristine tuzak domain kontrolü ────────────────────────────────────
    if domain_lower in PRISTINE_TRAP_DOMAINS:
        return True, 'pristine', 'high'

    # ── 2. Typo tuzak domain kontrolü ────────────────────────────────────────
    if domain_lower in TYPO_TRAP_DOMAINS:
        return True, 'typo_trap', 'high'

    # ── 3. Tuzak MX sunucusu kontrolü ────────────────────────────────────────
    mx_server = meta.get('mx_server') or ''   # verifier.py meta'ya eklenecek
    if mx_server:
        for pattern in _TRAP_MX_PATTERNS:
            if pattern.search(mx_server):
                return True, 'mx_trap', 'high'

    # ── 4. Recycled trap local kalıp kontrolü ─────────────────────────────────
    for pattern in _RECYCLED_LOCAL_PATTERNS:
        if pattern.match(local_lower):
            # Tek başına yeterli değil — domain de şüpheliyse güven artar
            domain_age = meta.get('domain_age')
            no_infra   = not meta.get('has_spf') and not meta.get('has_dmarc')
            if no_infra or (domain_age is not None and domain_age > 1825):
                # 5 yıldan eski + altyapısız domain + tuzak kalıbı = yüksek güven
                return True, 'recycled', 'medium'
            return True, 'recycled', 'low'

    # ── 5. Honeypot form local kalıp kontrolü ─────────────────────────────────
    for pattern in _HONEYPOT_LOCAL_PATTERNS:
        if pattern.match(local_lower):
            # UUID veya çok uzun rastgele string — honeypot botu işareti
            if len(local_lower) > 15:
                return True, 'honeypot', 'medium'
            return True, 'honeypot', 'low'

    # ── 6. Kombinasyonlu sinyal: çok eski domain + tuzak benzeri local ────────
    # Birden fazla "zayıf sinyal" aynı anda varsa birlikte değerlendir.
    domain_age = meta.get('domain_age')
    no_infra   = not meta.get('has_spf') and not meta.get('has_dmarc')
    is_catchall = meta.get('is_catchall', False)

    weak_signals = 0
    if domain_age is not None and domain_age > 3650:  # 10+ yıllık domain
        weak_signals += 1
    if no_infra:
        weak_signals += 1
    if is_catchall:
        weak_signals += 1
    if _looks_like_trap_local(local_lower):
        weak_signals += 1

    if weak_signals >= 3:
        return True, 'recycled', 'low'

    return False, None, None


def _looks_like_trap_local(local: str) -> bool:
    """
    Local kısmın tuzak benzeri görünüp görünmediğini heuristic ile kontrol eder.
    Tek başına yeterli değil; kombinasyonlu sinyallerde kullanılır.
    """
    # Yalnızca rakam
    if local.isdigit():
        return True
    # Çok kısa veya çok uzun (1-2 karakter ya da 30+ karakter)
    if len(local) <= 2 or len(local) >= 30:
        return True
    # Büyük çoğunluğu rakam olan local (ör: a123456789)
    digits = sum(c.isdigit() for c in local)
    if len(local) > 5 and digits / len(local) > 0.7:
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# DB'DEN TUZAK LİSTESİ YÜKLEME
# ══════════════════════════════════════════════════════════════════════════════

def load_trap_domains_from_db() -> tuple[set, set]:
    """
    DB'deki spam_trap_domains tablosundan pristine ve typo tuzak domainlerini yükler.
    Tablo yoksa veya bağlantı hatası varsa sessizce boş set döner.

    DB tablosu (migrate_spam_trap.sql ile oluşturulur):
        CREATE TABLE IF NOT EXISTS spam_trap_domains (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            domain      VARCHAR(255) NOT NULL UNIQUE,
            trap_type   ENUM('pristine','typo_trap','recycled') NOT NULL DEFAULT 'pristine',
            source      VARCHAR(100) DEFAULT NULL COMMENT 'spamhaus / manuel / api',
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_domain (domain)
        );

    Returns:
        (pristine_set, typo_set)
    """
    pristine: set[str] = set()
    typo:     set[str] = set()
    try:
        import database as db
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT domain, trap_type FROM spam_trap_domains"
            )
            for row in cur.fetchall():
                d = row['domain'].lower().strip()
                t = row.get('trap_type', 'pristine')
                if t == 'typo_trap':
                    typo.add(d)
                else:
                    pristine.add(d)
        conn.close()
    except Exception:
        pass
    return pristine, typo


def _extend_trap_lists_from_db() -> None:
    """
    Modül import sırasında DB'den ek tuzak domainleri yükler ve
    mevcut frozenset'lere ekler. DB yoksa sessizce atlar.
    """
    global PRISTINE_TRAP_DOMAINS, TYPO_TRAP_DOMAINS
    try:
        extra_pristine, extra_typo = load_trap_domains_from_db()
        if extra_pristine:
            PRISTINE_TRAP_DOMAINS = PRISTINE_TRAP_DOMAINS | extra_pristine
        if extra_typo:
            TYPO_TRAP_DOMAINS = TYPO_TRAP_DOMAINS | extra_typo
    except Exception:
        pass


_extend_trap_lists_from_db()
