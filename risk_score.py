"""
risk_score.py — E-posta Teslimat Risk Skoru Hesaplayıcı
=========================================================
verify_one() sonucundaki status ve meta verilerini, DB'deki geçmiş
bounce/complaint/suppression kayıtlarını birleştirerek 0-100 arası
bir deliverability skoru üretir.

SKOR YORUMU:
  90-100 → Güvenli          — gönderin
  70-89  → Düşük risk       — gönderin
  50-69  → Orta risk        — dikkatli olun
  30-49  → Yüksek risk      — önce temizleyin
   0-29  → Gönderme         — kesinlikle göndermeyin

KULLANIM:
  from risk_score import calculate_risk_score

  email, status, meta = verify_one('test@example.com', mode='smtp')
  score_data = calculate_risk_score(email, status, meta)

  # score_data örneği:
  # {
  #   'score': 72,
  #   'label': 'low_risk',
  #   'label_tr': 'Düşük risk',
  #   'reasons': ['Catch-all sunucu (-15)', 'SPF kaydı yok (-10)'],
  #   'send_recommended': True
  # }
"""

from __future__ import annotations

# ── Skor eşikleri ────────────────────────────────────────────────────────────
SCORE_BANDS = [
    (90, 'safe',       'Güvenli',       True),
    (70, 'low_risk',   'Düşük risk',    True),
    (50, 'medium_risk','Orta risk',     True),
    (30, 'high_risk',  'Yüksek risk',   False),
    (0,  'do_not_send','Gönderme',      False),
]

# ── Status bazlı taban skorlar ────────────────────────────────────────────────
# Doğrulama sonucuna göre başlangıç skoru — üzerine cezalar/bonuslar eklenir
STATUS_BASE = {
    'valid':          95,
    'typo_fixed':     85,  # Yazım hatası düzeltildi — belirsizlik var
    'catch_all':      65,  # Sunucu her adrese 250 veriyor — teslim belirsiz
    'free_provider':  90,  # Gmail/Hotmail vb. — genellikle güvenli
    'no_infra':       45,  # SPF/DMARC yok — zayıf domain
    'role_account':   50,  # info@, admin@ — kişisel değil ama aktif olabilir; medium_risk'ten başla
    'unknown':        25,  # SMTP belirsiz — yüksek risk
    'spam_trap':       0,  # Spam tuzağı — kesinlikle gönderme
    'toxic_domain':    0,  # Abuse/bot/blacklist domain — kesinlikle gönderme
    'disabled_account':0,  # Yahoo/AOL devre dışı hesap — gönderilemez
    'no_mx':           0,  # DNS kaydı yok — gönderilemez
    'disposable':      0,  # Geçici servis — gönderilemez
    'invalid_format':  0,  # Format hatası — gönderilemez
    'invalid':         0,  # SMTP 550 — posta kutusu yok
}


# ══════════════════════════════════════════════════════════════════════════════
# DB SORGU YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════════════

def _db_email_history(email: str) -> dict:
    """
    DB'den adrese ait geçmiş bounce/complaint/suppression kayıtlarını çeker.
    DB bağlantısı yoksa güvenli bir boş sonuç döner.
    """
    result = {
        'in_suppression': False,
        'suppression_reason': None,
        'domain_blocked': False,
        'bounce_count': 0,
        'complaint_count': 0,
        'send_count': 0,
    }
    try:
        import database as db
        conn = db.get_connection()
        domain = email.split('@')[-1].lower() if '@' in email else ''

        with conn.cursor() as cur:
            # 1. Suppression listesinde var mı?
            cur.execute(
                "SELECT reason FROM suppression_list WHERE email=%s LIMIT 1",
                (email,)
            )
            row = cur.fetchone()
            if row:
                result['in_suppression'] = True
                result['suppression_reason'] = row['reason']

            # 2. Domain bloklu mu?
            if domain:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM suppression_domains WHERE domain=%s",
                    (domain,)
                )
                result['domain_blocked'] = cur.fetchone()['cnt'] > 0

            # 3. SES bounce sayısı
            cur.execute(
                "SELECT COUNT(*) as cnt FROM ses_notifications "
                "WHERE notif_type='Bounce' AND recipient=%s",
                (email,)
            )
            result['bounce_count'] = cur.fetchone()['cnt']

            # 4. SES complaint sayısı
            cur.execute(
                "SELECT COUNT(*) as cnt FROM ses_notifications "
                "WHERE notif_type='Complaint' AND recipient=%s",
                (email,)
            )
            result['complaint_count'] = cur.fetchone()['cnt']

            # 5. Daha önce kaç kez gönderildi?
            cur.execute(
                "SELECT COUNT(*) as cnt FROM send_log "
                "WHERE recipient=%s AND status='sent'",
                (email,)
            )
            result['send_count'] = cur.fetchone()['cnt']

        conn.close()
    except Exception:
        pass  # DB yoksa veya hata varsa — mevcut verilerle devam et

    return result


def _db_domain_bounce_rate(domain: str) -> float | None:
    """
    Domain genelinde bounce oranını döner (0.0 - 1.0).
    Yeterli veri yoksa (< 10 gönderim) None döner.
    """
    try:
        import database as db
        conn = db.get_connection()
        with conn.cursor() as cur:
            # Bu domain'e toplam gönderim
            cur.execute(
                "SELECT COUNT(*) as cnt FROM send_log "
                "WHERE recipient LIKE %s AND status='sent'",
                (f'%@{domain}',)
            )
            total = cur.fetchone()['cnt']
            if total < 10:
                return None  # Yeterli örnek yok

            # Bu domain'den gelen bounce sayısı
            cur.execute(
                "SELECT COUNT(*) as cnt FROM ses_notifications "
                "WHERE notif_type='Bounce' AND recipient LIKE %s",
                (f'%@{domain}',)
            )
            bounces = cur.fetchone()['cnt']
        conn.close()
        return bounces / total
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SKOR HESAPLAMA
# ══════════════════════════════════════════════════════════════════════════════

def calculate_risk_score(
    email: str,
    status: str,
    meta: dict,
    include_db: bool = True
) -> dict:
    """
    E-posta için 0-100 arası risk skoru hesaplar.

    Args:
        email:      Doğrulanmış (normalize edilmiş) e-posta adresi
        status:     verify_one() çıktısı — 'valid', 'catch_all' vb.
        meta:       verify_one() meta sözlüğü
        include_db: False ise DB sorguları atlanır (hız öncelikli modlar için)

    Returns:
        {
            'score':            int,   # 0-100
            'label':            str,   # 'safe' | 'low_risk' | ... | 'do_not_send'
            'label_tr':         str,   # Türkçe etiket
            'send_recommended': bool,
            'reasons':          list,  # Skoru etkileyen faktörler
            'db_checked':       bool,  # DB sorgusu yapıldı mı?
        }
    """
    reasons: list[str] = []

    # ── Taban skor ───────────────────────────────────────────────────────────
    base = STATUS_BASE.get(status, 20)
    score = base

    # Taban skor sıfırsa (kesin geçersiz) — hesap yapmaya gerek yok
    if base == 0:
        return _build_result(0, [f'Geçersiz adres ({status})'], db_checked=False)

    # ── Meta veri cezaları ────────────────────────────────────────────────────

    # Spam tuzağı sinyali — high zaten taban skor 0 yapıyor (STATUS_BASE),
    # medium/low ise buraya düşer (statü 'valid'/'catch_all' kalabilir)
    trap_type       = meta.get('spam_trap_type')
    trap_confidence = meta.get('spam_trap_confidence')
    if trap_type and trap_confidence in ('medium', 'low'):
        if trap_confidence == 'medium':
            score -= 30
            reasons.append(f'Muhtemel spam tuzağı: {trap_type} (-30)')
        else:
            score -= 15
            reasons.append(f'Şüpheli spam tuzağı sinyali: {trap_type} (-15)')

    # Toxic domain sinyali — high zaten taban skor 0 (STATUS_BASE),
    # medium → pattern eşleşmesi, -25 ceza
    toxic_type = meta.get('toxic_domain_type')
    toxic_conf = meta.get('toxic_domain_confidence')
    if toxic_type and toxic_conf == 'medium':
        score -= 25
        reasons.append(f'Riskli domain pattern tespit edildi: {toxic_type} (-25)')
    elif toxic_type and toxic_conf == 'low':
        score -= 10
        reasons.append(f'Şüpheli domain sinyali: {toxic_type} (-10)')

    # Yahoo/AOL geçici hata sinyali
    if meta.get('yahoo_aol_checked') and meta.get('yahoo_aol_signal') == 'temporary_error':
        score -= 10
        reasons.append('Yahoo/AOL geçici sunucu hatası (-10)')

    # Gibberish (saçma) local kısım — bot/otomatik üretim sinyali
    # Kaynak: EmailFilter (MIT). false-positive riski var, hafif ceza.
    if meta.get('is_gibberish'):
        score -= 20
        reasons.append('Local kısım bot/oto üretim görünümlü (gibberish) (-20)')

    # Spam keyword local kısmında (lottery@, winner@, fake@ vb.)
    # Kaynak: EmailFilter (MIT).
    if meta.get('has_spam_local'):
        score -= 15
        reasons.append('Local kısımda spam kelimesi tespit edildi (-15)')

    # ESP tespiti — kurumsal güvenlik ESP'si yüksek güven sinyali
    # Kaynak: email-verifier-free (MIT).
    esp = meta.get('esp')
    if esp:
        # Kurumsal güvenlik geçitleri: sahte adresler bu servisleri geçemez
        _enterprise_esp = {
            'Proofpoint', 'Mimecast', 'Barracuda',
            'Cisco IronPort', 'Trend Micro', 'Forcepoint',
        }
        # Büyük güvenilir sağlayıcılar
        _trusted_esp = {
            'Google Workspace', 'Microsoft 365', 'Proton Mail',
            'Fastmail', 'Zoho Mail', 'Apple iCloud',
        }
        if esp in _enterprise_esp:
            score = min(score + 10, 100)
            reasons.append(f'Kurumsal ESP: {esp} (+10)')
        elif esp in _trusted_esp:
            score = min(score + 5, 100)
            reasons.append(f'Güvenilir ESP: {esp} (+5)')
        # Bilinmeyen ESP → nötr, bonus/ceza yok

    # SMTP güven çarpanı — büyük ücretsiz sağlayıcılar privacy için accept-all yapabilir
    # Kaynak: mailguard providers.py (MIT). Gmail/Yahoo/Outlook'tan gelen 'valid' sinyali
    # kurumsal bir MX'ten gelen 'valid' kadar güvenilir değildir.
    if status == 'valid' and meta.get('is_free'):
        _weak_smtp_providers = {'gmail.com','googlemail.com','yahoo.com','ymail.com',
                                 'rocketmail.com','outlook.com','hotmail.com','live.com',
                                 'icloud.com','me.com','mac.com'}
        _domain = meta.get('original','').split('@')[-1].lower() if '@' in meta.get('original','') else ''
        if _domain in _weak_smtp_providers:
            score = max(0, score - 8)
            reasons.append(f'Büyük sağlayıcı SMTP sinyali zayıf ({_domain}) (-8)')

    # Catch-all zaten taban skorda düşük ama ek bağlam varsa daha da düşür
    if meta.get('is_catchall') and status != 'catch_all':
        score -= 10
        reasons.append('Catch-all sunucu tespit edildi (-10)')

    # SPF ve DMARC her ikisi de yoksa
    has_spf   = meta.get('has_spf', False)
    has_dmarc = meta.get('has_dmarc', False)
    if not has_spf and not has_dmarc:
        score -= 10
        reasons.append('SPF ve DMARC kaydı yok (-10)')
    elif not has_spf:
        score -= 5
        reasons.append('SPF kaydı yok (-5)')
    elif not has_dmarc:
        score -= 3
        reasons.append('DMARC kaydı yok (-3)')

    # Domain yaşı
    domain_age = meta.get('domain_age')
    if domain_age is not None:
        if domain_age < 30:
            score -= 25
            reasons.append(f'Domain çok yeni ({domain_age} gün) (-25)')
        elif domain_age < 90:
            score -= 10
            reasons.append(f'Domain yeni ({domain_age} gün) (-10)')
        elif domain_age < 180:
            score -= 5
            reasons.append(f'Domain görece yeni ({domain_age} gün) (-5)')

    # Parked / sahte / boş website tespiti
    is_parked = meta.get('is_parked')
    if is_parked == 'parked':
        score -= 30
        reasons.append('Domain park/satılık sayfası tespit edildi (-30)')
    elif is_parked == 'empty':
        score -= 15
        reasons.append('Domain web sitesi içeriksiz/boş (-15)')

    # Ücretsiz sağlayıcı — düşük kurumsal değer ama teslim genellikle iyi
    if meta.get('is_free') and status not in ('valid', 'typo_fixed'):
        score -= 5
        reasons.append('Ücretsiz e-posta sağlayıcısı (-5)')

    # Typo düzeltme — adres düzeltildi, orijinal yanlıştı
    if meta.get('typo_domain'):
        score -= 5
        reasons.append(f'Yazım hatası düzeltildi ({meta["typo_domain"]}) (-5)')

    # ── DB geçmiş verisi ceza/bonusları ──────────────────────────────────────
    db_checked = False
    if include_db:
        domain = email.split('@')[-1].lower() if '@' in email else ''
        history = _db_email_history(email)
        db_checked = True

        # Suppression listesinde — direkt sıfır
        if history['in_suppression']:
            reason_tr = {
                'bounce':      'daha önce bounce almış',
                'complaint':   'şikayet edilmiş',
                'unsubscribe': 'abonelikten çıkmış',
                'invalid':     'geçersiz olarak işaretlenmiş',
            }.get(history['suppression_reason'] or '', 'suppression listesinde')
            return _build_result(
                0,
                [f'Bu adres {reason_tr} — göndermek önerilmez'],
                db_checked=True
            )

        # Domain bloklu
        if history['domain_blocked']:
            return _build_result(
                0,
                [f'Domain ({domain}) blok listesinde'],
                db_checked=True
            )

        # Bounce geçmişi
        if history['bounce_count'] > 0:
            penalty = min(history['bounce_count'] * 20, 60)
            score -= penalty
            reasons.append(
                f'Bu adresten {history["bounce_count"]} kez bounce alındı (-{penalty})'
            )

        # Complaint geçmişi
        if history['complaint_count'] > 0:
            penalty = min(history['complaint_count'] * 30, 80)
            score -= penalty
            reasons.append(
                f'Bu adres {history["complaint_count"]} kez şikayet edildi (-{penalty})'
            )

        # Daha önce başarılı gönderim — pozitif sinyal
        if history['send_count'] > 0 and history['bounce_count'] == 0:
            bonus = min(history['send_count'] * 2, 10)
            score = min(score + bonus, 100)
            if bonus > 0:
                reasons.append(
                    f'Daha önce {history["send_count"]} başarılı gönderim (+{bonus})'
                )

        # Domain genel bounce oranı
        if domain:
            domain_rate = _db_domain_bounce_rate(domain)
            if domain_rate is not None:
                if domain_rate > 0.10:
                    score -= 20
                    reasons.append(
                        f'Domain bounce oranı yüksek (%{domain_rate*100:.0f}) (-20)'
                    )
                elif domain_rate > 0.05:
                    score -= 10
                    reasons.append(
                        f'Domain bounce oranı orta (%{domain_rate*100:.0f}) (-10)'
                    )

    # ── Skor sınırla ─────────────────────────────────────────────────────────
    score = max(0, min(100, score))

    # Eğer hiç ceza/bonus yoksa genel "temiz" mesajı
    if not reasons:
        reasons.append('Tüm kontroller temiz')

    return _build_result(score, reasons, db_checked=db_checked)


def _build_result(score: int, reasons: list, db_checked: bool) -> dict:
    """Skor ve etiket sözlüğünü oluşturur."""
    score = max(0, min(100, score))
    for threshold, label, label_tr, send_ok in SCORE_BANDS:
        if score >= threshold:
            return {
                'score':            score,
                'label':            label,
                'label_tr':         label_tr,
                'send_recommended': send_ok,
                'reasons':          reasons,
                'db_checked':       db_checked,
            }
    # Fallback (olmaması gerekir ama güvenlik için)
    return {
        'score': 0, 'label': 'do_not_send', 'label_tr': 'Gönderme',
        'send_recommended': False, 'reasons': reasons, 'db_checked': db_checked,
    }


# ══════════════════════════════════════════════════════════════════════════════
# verify_one ile entegre toplu skor hesaplama
# ══════════════════════════════════════════════════════════════════════════════

def score_after_verify(email: str, mode: str = 'mx') -> dict:
    """
    verify_one() çalıştırıp hemen ardından risk skoru hesaplar.
    Tek adres doğrulama için kolaylık fonksiyonu.

    Returns:
        {
            'email':   str,
            'status':  str,
            'meta':    dict,
            'risk':    dict,   # calculate_risk_score() çıktısı
        }
    """
    from verifier import verify_one
    final_email, status, meta = verify_one(email, mode=mode)
    risk = calculate_risk_score(final_email, status, meta)
    return {
        'email':  final_email,
        'status': status,
        'meta':   meta,
        'risk':   risk,
    }
