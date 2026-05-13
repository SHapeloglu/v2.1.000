"""
disposable_updater.py — Disposable Domain Listesi Otomatik Güncelleyici
=======================================================================
GitHub'daki topluluk tarafından güncellenen disposable-email-domains
reposundan (~50.000+ domain) tam listeyi çeker ve hem DB'ye hem de
verifier.py tarafından kullanılan önbelleğe yazar.

KULLANIM:
  Elle çalıştırmak için:
      python disposable_updater.py

  Cron job olarak (her gece 03:00):
      0 3 * * * /usr/bin/python3 /path/to/disposable_updater.py >> /var/log/disposable_updater.log 2>&1

  Worker içinden tetiklemek için:
      from disposable_updater import update_disposable_domains
      update_disposable_domains()

BAĞIMLILIKLAR:
  - requests (zaten requirements.txt'te mevcut)
  - database.py (proje içi)
"""

import os
import sys
import time
import logging
import requests
import database as db

# ── Kaynak URL'ler ─────────────────────────────────────────────────────────────
# Birincil kaynak: ishland/disposable-email-domains (50.000+ domain, günlük güncellenir)
PRIMARY_URL = (
    "https://raw.githubusercontent.com/disposable-email-domains/"
    "disposable-email-domains/main/disposable_email_blocklist.conf"
)

# Yedek kaynak: FGRibreau/mailchecker (farklı format — JSON array)
FALLBACK_URL = (
    "https://raw.githubusercontent.com/FGRibreau/mailchecker/master/"
    "list.txt"
)

# DB'de saklanacak setting key
DB_KEY = "disposable_domains_extra"

# Güncelleme arasındaki minimum süre (saniye) — 6 saat
MIN_UPDATE_INTERVAL = 6 * 3600

# ── Loglama ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [disposable_updater] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DB YARDIMCI FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════════════

def _get_last_update_ts() -> float:
    """Son güncelleme zamanını Unix timestamp olarak döner. Hiç güncelleme yoksa 0."""
    val = db.setting_get("disposable_last_update")
    try:
        return float(val) if val else 0.0
    except (TypeError, ValueError):
        return 0.0


def _set_last_update_ts():
    """Son güncelleme zamanını şimdiki zaman olarak kaydeder."""
    db.setting_set("disposable_last_update", str(time.time()))


def _save_domains_to_db(domains: set) -> bool:
    """
    Domain setini DB'ye kaydeder.
    Büyük listeler için 10.000'lik parçalar halinde virgülle ayrılmış
    birden fazla kayıt kullanır — MySQL TEXT kolonunun 65 KB sınırını aşmamak için.
    """
    import json
    domain_list = sorted(domains)

    # Eski parçaları temizle
    chunk_idx = 0
    while True:
        key = f"{DB_KEY}_{chunk_idx}"
        existing = db.setting_get(key)
        if existing is None:
            break
        db.setting_set(key, "")  # Boşalt (silme yerine — INSERT OR UPDATE yapısı)
        chunk_idx += 1

    # Yeni parçaları yaz (10.000 domain / parça ≈ ~150 KB, güvenli)
    CHUNK = 10_000
    chunk_idx = 0
    for i in range(0, len(domain_list), CHUNK):
        chunk = domain_list[i:i + CHUNK]
        key = f"{DB_KEY}_{chunk_idx}"
        if not db.setting_set(key, json.dumps(chunk)):
            log.error("DB yazma hatası: %s", key)
            return False
        chunk_idx += 1

    # Toplam parça sayısını kaydet
    db.setting_set(f"{DB_KEY}_chunks", str(chunk_idx))
    log.info("DB'ye %d domain, %d parça olarak yazıldı.", len(domain_list), chunk_idx)
    return True


def load_domains_from_db() -> set:
    """
    DB'deki tüm parçaları birleştirip domain seti olarak döner.
    verifier.py tarafından çağrılır.
    """
    import json
    chunks_val = db.setting_get(f"{DB_KEY}_chunks")
    if not chunks_val:
        return set()
    try:
        chunk_count = int(chunks_val)
    except (TypeError, ValueError):
        return set()

    result = set()
    for i in range(chunk_count):
        key = f"{DB_KEY}_{i}"
        val = db.setting_get(key)
        if not val:
            continue
        try:
            result.update(json.loads(val))
        except Exception:
            pass
    return result


# ══════════════════════════════════════════════════════════════════════════════
# KAYNAK ÇEKME
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_url(url: str, timeout: int = 30) -> str | None:
    """URL'den düz metin içerik çeker. Hata durumunda None döner."""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "MailSenderPro-DisposableUpdater/1.0"
        })
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        log.warning("URL çekme hatası (%s): %s", url, e)
        return None


def _parse_plain_list(text: str) -> set:
    """
    Satır başına bir domain içeren düz metin listesini parse eder.
    Boş satırları ve # ile başlayan yorumları atlar.
    """
    domains = set()
    for line in text.splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        # Sadece geçerli domain görünümlü satırları al
        if "." in line and " " not in line and len(line) < 255:
            domains.add(line)
    return domains


def _fetch_disposable_list() -> set | None:
    """
    Birincil ve yedek kaynaktan disposable domain listesini çeker.
    Her ikisi de başarısız olursa None döner.
    """
    log.info("Birincil kaynak çekiliyor: %s", PRIMARY_URL)
    text = _fetch_url(PRIMARY_URL)
    if text:
        domains = _parse_plain_list(text)
        if len(domains) > 1000:  # Makul bir minimum — bozuk yanıt değilse
            log.info("Birincil kaynak: %d domain alındı.", len(domains))
            return domains
        log.warning("Birincil kaynaktan çok az domain geldi (%d), yedek deneniyor.", len(domains))

    log.info("Yedek kaynak çekiliyor: %s", FALLBACK_URL)
    text = _fetch_url(FALLBACK_URL)
    if text:
        domains = _parse_plain_list(text)
        if domains:
            log.info("Yedek kaynak: %d domain alındı.", len(domains))
            return domains

    log.error("Her iki kaynak da başarısız oldu.")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# VERİFİER.PY ÖNBELLEK GÜNCELLEMESI
# ══════════════════════════════════════════════════════════════════════════════

def _patch_verifier_cache(new_domains: set):
    """
    Çalışan Python sürecinde verifier modülü yüklüyse
    DISPOSABLE_DOMAINS setini yerinde günceller.
    Modül yüklü değilse sessizce atlar (cron job çalışmasında normal).
    """
    try:
        import verifier
        verifier.DISPOSABLE_DOMAINS.update(new_domains)
        # DNS önbelleğini de temizle — eski sonuçlar kalsın
        verifier._mx_cache.clear()
        log.info("verifier.DISPOSABLE_DOMAINS güncellendi (bellek içi).")
    except ImportError:
        pass  # Cron job bağlamında verifier yüklü olmayabilir


# ══════════════════════════════════════════════════════════════════════════════
# ANA GÜNCELLEME FONKSİYONU
# ══════════════════════════════════════════════════════════════════════════════

def update_disposable_domains(force: bool = False) -> dict:
    """
    Disposable domain listesini günceller.

    Args:
        force: True ise MIN_UPDATE_INTERVAL kontrolünü atlar.

    Returns:
        {
            'success': bool,
            'fetched': int,          # Kaynaktan gelen domain sayısı
            'saved': int,            # DB'ye yazılan (yeni+mevcut) domain sayısı
            'skipped': bool,         # Çok erken çağrıldığı için atlandıysa True
            'message': str
        }
    """
    result = {'success': False, 'fetched': 0, 'saved': 0, 'skipped': False, 'message': ''}

    # Minimum güncelleme aralığı kontrolü
    if not force:
        last = _get_last_update_ts()
        elapsed = time.time() - last
        if elapsed < MIN_UPDATE_INTERVAL:
            remaining_min = int((MIN_UPDATE_INTERVAL - elapsed) / 60)
            msg = f"Son güncellemeden bu yana {int(elapsed/60)} dk geçti. Bir sonraki güncelleme {remaining_min} dk sonra."
            log.info(msg)
            result['skipped'] = True
            result['message'] = msg
            result['success'] = True
            return result

    # Uzak listeyі çek
    fetched = _fetch_disposable_list()
    if fetched is None:
        result['message'] = "Kaynaklara erişilemedi."
        return result

    result['fetched'] = len(fetched)

    # Mevcut DB listesiyle birleştir (eski özel eklemeler kaybolmasın)
    existing = load_domains_from_db()
    merged = fetched | existing
    result['saved'] = len(merged)

    # DB'ye yaz
    if not _save_domains_to_db(merged):
        result['message'] = "DB yazma hatası."
        return result

    # Zaman damgasını güncelle
    _set_last_update_ts()

    # Çalışan süreçteki verifier önbelleğini güncelle
    _patch_verifier_cache(fetched)

    result['success'] = True
    result['message'] = (
        f"{len(fetched):,} domain çekildi, "
        f"{len(merged):,} domain DB'ye yazıldı "
        f"({len(merged) - len(fetched):+,} önceden eklenmiş)."
    )
    log.info(result['message'])
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CRON / KOMUTSATIRı ÇALIŞMASI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        log.info("Zorla güncelleme modu aktif.")

    res = update_disposable_domains(force=force)

    if res.get('skipped'):
        log.info("Atlandı: %s", res['message'])
        sys.exit(0)

    if res['success']:
        log.info("Başarılı: %s", res['message'])
        sys.exit(0)
    else:
        log.error("Başarısız: %s", res['message'])
        sys.exit(1)
