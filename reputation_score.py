"""
reputation_score.py — Gönderici İtibar Skoru
==============================================
Bir SMTP/SES gönderici hesabının genel teslimat sağlığını
0–100 arası tek bir puanla özetler.

Kaynak: email_deliverability ReputationAnalyzer (MIT lisanslı) fikrinden
ilham alınarak projeye özgü DB yapısına uyarlandı.

SKOR YORUMU:
  90–100 → Mükemmel   — gönderin
  80–89  → İyi        — gönderin
  70–79  → Orta       — izleyin
  50–69  → Zayıf      — önlem alın
  0–49   → Kritik     — acil müdahale

HESAPLAMA AĞIRLIKLARI (mailguard providers.py mantığından):
  authentication  %30  — SPF/DKIM/DMARC yapılandırma durumu
  bounce_rate     %25  — Geri dönen mail oranı (son 30 gün)
  complaint_rate  %25  — Şikayet oranı (son 30 gün)
  dnsbl_status    %15  — DNSBL kara liste kontrolü
  send_volume     %5   — Tutarlı gönderim hacmi

KULLANIM:
  from reputation_score import calculate_sender_reputation

  result = calculate_sender_reputation(sender_id=3)
  # {
  #   'score': 82,
  #   'label': 'good',
  #   'label_tr': 'İyi',
  #   'components': {
  #       'authentication': 90,
  #       'bounce_rate': 85,
  #       'complaint_rate': 95,
  #       'dnsbl_status': 70,
  #       'send_volume': 60,
  #   },
  #   'issues': ['Bounce oranı yüksek (%4.2)', 'dbl.spamhaus.org listesinde'],
  #   'send_recommended': True,
  # }
"""

from __future__ import annotations

# ── Skor bantları ────────────────────────────────────────────────────────────
_SCORE_BANDS = [
    (90, 'excellent', 'Mükemmel',  True),
    (80, 'good',      'İyi',       True),
    (70, 'fair',      'Orta',      True),
    (50, 'poor',      'Zayıf',     False),
    (0,  'critical',  'Kritik',    False),
]

# ── Ağırlıklar ───────────────────────────────────────────────────────────────
_WEIGHTS = {
    'authentication':  0.30,
    'bounce_rate':     0.25,
    'complaint_rate':  0.25,
    'dnsbl_status':    0.15,
    'send_volume':     0.05,
}


# ══════════════════════════════════════════════════════════════════════════════
# DB YARDIMCI FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════════════

def _get_sender(sender_id: int) -> dict | None:
    try:
        import database as db
        return db.get_sender(sender_id)
    except Exception:
        return None


def _get_send_stats(sender_id: int, days: int = 30) -> dict:
    """Son N gündeki gönderim istatistiklerini döner."""
    result = {'total': 0, 'bounced': 0, 'complained': 0}
    try:
        import database as db
        conn = db.get_connection()
        with conn.cursor() as cur:
            # Toplam gönderim
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM send_log "
                "WHERE sender_id=%s AND status='sent' "
                "AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (sender_id, days)
            )
            result['total'] = cur.fetchone()['cnt']

            # Bounce
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM ses_notifications "
                "WHERE notif_type='Bounce' AND sender_id=%s "
                "AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (sender_id, days)
            )
            result['bounced'] = cur.fetchone()['cnt']

            # Şikayet
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM ses_notifications "
                "WHERE notif_type='Complaint' AND sender_id=%s "
                "AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (sender_id, days)
            )
            result['complained'] = cur.fetchone()['cnt']
        conn.close()
    except Exception:
        pass
    return result


def _check_dnsbl_cached(smtp_server: str) -> dict | None:
    """dnsbl_check modülünden sonuç al (önbellekli)."""
    if not smtp_server:
        return None
    try:
        from dnsbl_check import check_smtp_host
        return check_smtp_host(smtp_server)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# BILEŞEN SKORLARI
# ══════════════════════════════════════════════════════════════════════════════

def _score_authentication(sender: dict) -> tuple[int, list[str]]:
    """
    SPF/DKIM/DMARC yapılandırma varlığını domain üzerinden kontrol eder.
    Sender domain'in mail altyapısı ne kadar sağlam?
    """
    issues: list[str] = []
    domain = (sender.get('email') or '').split('@')[-1].lower() if '@' in (sender.get('email') or '') else ''
    if not domain:
        return 50, ['Gönderici e-postası bulunamadı']

    try:
        from verifier import _check_spf, _check_dmarc
        has_spf   = _check_spf(domain)
        has_dmarc = _check_dmarc(domain)
    except Exception:
        return 60, ['SPF/DMARC kontrol edilemedi']

    score = 100
    if not has_spf:
        score -= 40
        issues.append('SPF kaydı yok')
    if not has_dmarc:
        score -= 30
        issues.append('DMARC kaydı yok')

    return max(0, score), issues


def _score_bounce_rate(stats: dict) -> tuple[int, list[str]]:
    """Bounce oranına göre skor. Endüstri standardı: <%2 ideal."""
    issues: list[str] = []
    total   = stats.get('total', 0)
    bounced = stats.get('bounced', 0)

    if total < 10:
        return 70, ['Yeterli gönderim verisi yok (< 10 mail)']

    rate = bounced / total * 100
    if rate <= 1.0:
        score = 100
    elif rate <= 2.0:
        score = 85
    elif rate <= 4.0:
        score = 60
        issues.append(f'Bounce oranı yüksek (%{rate:.1f})')
    elif rate <= 8.0:
        score = 35
        issues.append(f'Bounce oranı kritik (%{rate:.1f})')
    else:
        score = 0
        issues.append(f'Bounce oranı çok kritik (%{rate:.1f}) — acil temizlik gerekli')

    return score, issues


def _score_complaint_rate(stats: dict) -> tuple[int, list[str]]:
    """Şikayet oranına göre skor. Endüstri standardı: <%0.1 ideal."""
    issues: list[str] = []
    total     = stats.get('total', 0)
    complained = stats.get('complained', 0)

    if total < 10:
        return 70, []

    rate = complained / total * 100
    if rate <= 0.05:
        score = 100
    elif rate <= 0.1:
        score = 85
    elif rate <= 0.3:
        score = 50
        issues.append(f'Şikayet oranı yüksek (%{rate:.2f})')
    else:
        score = 0
        issues.append(f'Şikayet oranı kritik (%{rate:.2f}) — içerik kalitesini inceleyin')

    return score, issues


def _score_dnsbl(dnsbl_result: dict | None) -> tuple[int, list[str]]:
    """DNSBL kara liste durumuna göre skor."""
    if dnsbl_result is None:
        return 70, ['DNSBL kontrol edilemedi']

    if dnsbl_result.get('error'):
        return 70, [f'DNSBL hatası: {dnsbl_result["error"]}']

    if not dnsbl_result.get('listed'):
        return 100, []

    hits = dnsbl_result.get('hits', [])
    sev  = dnsbl_result.get('severity', 'low')

    score_map = {'critical': 0, 'high': 15, 'medium': 40, 'low': 65}
    score = score_map.get(sev, 65)
    issues = [f'{h["rbl"]} kara listesinde ({h["severity"]})' for h in hits[:3]]

    return score, issues


def _score_send_volume(stats: dict) -> tuple[int, list[str]]:
    """Son 30 günde tutarlı gönderim hacmi var mı?"""
    total = stats.get('total', 0)
    if total >= 500:
        return 100, []
    elif total >= 100:
        return 80, []
    elif total >= 20:
        return 60, []
    elif total > 0:
        return 40, ['Düşük gönderim hacmi — itibar oluşmamış']
    else:
        return 20, ['Son 30 günde gönderim yapılmamış']


# ══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ══════════════════════════════════════════════════════════════════════════════

def calculate_sender_reputation(
    sender_id: int | None = None,
    sender: dict | None = None,
) -> dict:
    """
    Bir göndericinin itibar skorunu hesaplar.

    Args:
        sender_id: DB'deki gönderici ID'si
        sender:    Direkt gönderici dict'i (sender_id yoksa)

    Returns:
        {
          'score': int,
          'label': str,
          'label_tr': str,
          'send_recommended': bool,
          'components': dict,
          'issues': list[str],
          'stats': dict,
        }
    """
    if sender is None and sender_id is not None:
        sender = _get_sender(sender_id)

    if not sender:
        return _build(0, ['Gönderici bulunamadı'], {}, {})

    _id = sender.get('id') or sender_id
    stats = _get_send_stats(_id) if _id else {'total': 0, 'bounced': 0, 'complained': 0}

    smtp_server = (sender.get('smtp_server') or '').strip()
    dnsbl_result = _check_dnsbl_cached(smtp_server) if smtp_server else None

    # Bileşen skorları
    auth_score,   auth_issues   = _score_authentication(sender)
    bounce_score, bounce_issues = _score_bounce_rate(stats)
    compl_score,  compl_issues  = _score_complaint_rate(stats)
    dnsbl_score,  dnsbl_issues  = _score_dnsbl(dnsbl_result)
    vol_score,    vol_issues    = _score_send_volume(stats)

    components = {
        'authentication':  auth_score,
        'bounce_rate':     bounce_score,
        'complaint_rate':  compl_score,
        'dnsbl_status':    dnsbl_score,
        'send_volume':     vol_score,
    }

    # Ağırlıklı ortalama
    total_score = sum(
        components[k] * _WEIGHTS[k]
        for k in _WEIGHTS
    )
    final = max(0, min(100, round(total_score)))

    all_issues = auth_issues + bounce_issues + compl_issues + dnsbl_issues + vol_issues

    return _build(final, all_issues, components, stats)


def _build(score: int, issues: list[str], components: dict, stats: dict) -> dict:
    score = max(0, min(100, score))
    for threshold, label, label_tr, send_ok in _SCORE_BANDS:
        if score >= threshold:
            return {
                'score':            score,
                'label':            label,
                'label_tr':         label_tr,
                'send_recommended': send_ok,
                'components':       components,
                'issues':           issues,
                'stats':            stats,
            }
    return {
        'score': 0, 'label': 'critical', 'label_tr': 'Kritik',
        'send_recommended': False, 'components': components,
        'issues': issues, 'stats': stats,
    }
