"""
greylist_retry.py — Greylisting Retry Kuyruğu
===============================================
SMTP doğrulaması sırasında sunucu ilk denemede yanıt vermediğinde
(verifier.py → 'unknown' statüsü) bu modül devreye girer.

GREYLISTING NEDİR?
------------------
Bazı mail sunucuları bilinmeyen IP'lerden gelen ilk SMTP bağlantısını
geçici olarak reddeder (451 / 421 kodu) ve aynı IP'nin birkaç saat sonra
tekrar denemesini bekler. Meşru mail sunucuları retry yapar, spam botları
yapmaz. Bu yüzden greylisting, spam filtresinin bir parçasıdır.

Sonuç: verifier.py'nin ilk denemesinde 'unknown' dönen adresler gerçekte
geçerli olabilir. Bunları direkt 'unknown' = -1 olarak bırakmak yanlış.

COZUM
------
1. verify_one() 'unknown' döndügünde adres bu modüle eklenir.
2. worker.py her calistıgında (her 5 dakika) process_greylist_retries()
   cagırılır.
3. retry_after süresi dolmus adresler yeniden SMTP dogrulamasından gecer.
4. Sonuc DB'ye yazılır: is_valid güncellenir, retry kaydı kapatılır.

RETRY ZAMANLAMA STRATEJISI
---------------------------
Deneme 1 -> 6 saat sonra
Deneme 2 -> 12 saat sonra  (1. basarısızdan itibaren)
Deneme 3 -> 24 saat sonra  (2. basarısızdan itibaren)
3 denemeden sonra hala unknown -> kalıcı 'unknown' olarak bırakılır.

ENTEGRASYON
-----------
verifier.py -> run_verify_job() icerisinde MX/SMTP modunda 'unknown' dönen
her adres icin:

    from greylist_retry import enqueue_greylist_retry
    enqueue_greylist_retry(
        email=email,
        table_name=table_name,
        email_col=email_col,
        job_id=job_id,
        mx_server=mx_server,
    )

worker.py -> _run_tasks() icerine (verify job blogundan sonra):

    from greylist_retry import process_greylist_retries
    process_greylist_retries(log_fn=log)
"""

from __future__ import annotations
import datetime

# Retry gecikme tablosu (deneme_no -> bekleme_saati)
RETRY_DELAYS_HOURS = {
    1: 6,
    2: 12,
    3: 24,
}
MAX_RETRIES = 3


# =============================================================================
# DB YARDIMCI FONKSIYONLARI
# =============================================================================

def _get_conn():
    import database as db
    return db.get_connection()


def ensure_table() -> None:
    """
    greylist_retry_queue tablosunu olusturur (yoksa).
    migrate_greylist_retry.sql ile de olusturulabilir.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS `greylist_retry_queue` (
        `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `email`       VARCHAR(254)    NOT NULL  COMMENT 'Dogrulanacak adres',
        `table_name`  VARCHAR(200)    NOT NULL  COMMENT 'Kaynak tablo',
        `email_col`   VARCHAR(200)    NOT NULL  COMMENT 'E-posta kolonu',
        `job_id`      BIGINT          DEFAULT NULL COMMENT 'Kaynak verify job ID',
        `mx_server`   VARCHAR(255)    DEFAULT NULL COMMENT 'MX sunucusu',
        `attempt`     TINYINT         NOT NULL DEFAULT 1 COMMENT 'Kacinci deneme',
        `status`      ENUM('pending','done','exhausted') NOT NULL DEFAULT 'pending',
        `retry_after` DATETIME        NOT NULL  COMMENT 'Bu zamandan once deneme yapma',
        `last_result` VARCHAR(50)     DEFAULT NULL COMMENT 'Son SMTP sonucu',
        `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        INDEX `idx_status_retry` (`status`, `retry_after`),
        INDEX `idx_email`        (`email`(100)),
        INDEX `idx_job`          (`job_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='Greylisting retry kuyrugu -- unknown SMTP sonuclari icin';
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception as e:
        print(f"greylist_retry -- tablo olusturma hatasi: {e}")
    finally:
        conn.close()


def enqueue_greylist_retry(
    email:      str,
    table_name: str,
    email_col:  str,
    job_id=None,
    mx_server=None,
    attempt:    int = 1,
) -> bool:
    """
    Greylisting kuyругuna yeni bir kayit ekler.
    Ayni e-posta + tablo kombinasyonu zaten pending ise tekrar eklemez.
    Doner: True -> eklendi, False -> zaten var veya hata
    """
    delay_h = RETRY_DELAYS_HOURS.get(attempt, 24)
    retry_after = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=delay_h)
    ).strftime('%Y-%m-%d %H:%M:%S')

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # Aynı e-posta + tablo kombinasyonu zaten pending kuyrukta ise tekrar ekleme
            cur.execute(
                "SELECT id FROM greylist_retry_queue "
                "WHERE email=%s AND table_name=%s AND email_col=%s AND status='pending' "
                "LIMIT 1",
                (email, table_name, email_col)
            )
            if cur.fetchone():
                return False  # Zaten kuyrukta — duplicate ekleme
            # Kuyruğa yeni kayıt ekle; retry_after dolunca worker işleyecek
            cur.execute(
                """INSERT INTO greylist_retry_queue
                   (email, table_name, email_col, job_id, mx_server, attempt, retry_after)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (email, table_name, email_col, job_id, mx_server, attempt, retry_after)
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"greylist_retry -- enqueue hatasi ({email}): {e}")
        return False
    finally:
        conn.close()


def _get_due_retries(limit: int = 200) -> list:
    """retry_after suresi dolmus, pending kayitlari doner."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM greylist_retry_queue
                   WHERE status='pending' AND retry_after <= UTC_TIMESTAMP()
                   ORDER BY retry_after ASC
                   LIMIT %s""",
                (limit,)
            )
            return cur.fetchall() or []
    except Exception as e:
        print(f"greylist_retry -- _get_due_retries hatasi: {e}")
        return []
    finally:
        conn.close()


def _update_retry_record(
    record_id:        int,
    status:           str,
    result,
    next_attempt=None,
    next_retry_after=None,
) -> None:
    """Retry kaydini gunceller."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if next_attempt and next_retry_after:
                # Sonraki deneme için attempt ve retry_after güncelle — kuyrukta kalsın
                cur.execute(
                    """UPDATE greylist_retry_queue
                       SET status=%s, last_result=%s,
                           attempt=%s, retry_after=%s
                       WHERE id=%s""",
                    (status, result, next_attempt, next_retry_after, record_id)
                )
            else:
                # Kesin sonuç (done/exhausted) — sadece durum ve sonucu güncelle
                cur.execute(
                    """UPDATE greylist_retry_queue
                       SET status=%s, last_result=%s
                       WHERE id=%s""",
                    (status, result, record_id)
                )
        conn.commit()
    except Exception as e:
        print(f"greylist_retry -- _update_retry_record hatasi: {e}")
    finally:
        conn.close()


def _write_result_to_source_table(
    table_name: str,
    email_col:  str,
    email:      str,
    is_valid:   int,
    status:     str,
) -> None:
    """Retry sonucunu kaynak tablodaki is_valid kolonuna yazar."""
    try:
        import database as db
        from security import safe_identifier
        # SQL injection koruması — tablo ve kolon adı whitelist doğrulaması
        safe_identifier(table_name)
        safe_identifier(email_col)
        conn = db.get_connection()
        with conn.cursor() as cur:
            db_name = db.get_db_config()['database']
            # is_valid kolonu bu tabloda var mı? Yoksa güvenle çık
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s AND column_name='is_valid'",
                (db_name, table_name)
            )
            if cur.fetchone()['cnt'] == 0:
                return  # Kolon yok — kaynak tablo henüz verify edilmemiş olabilir
            # Retry sonucunu kaynak tabloya yaz; verify_job da aynı kolonu kullanır
            cur.execute(
                f"UPDATE `{table_name}` SET is_valid=%s WHERE `{email_col}`=%s",
                (is_valid, email)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"greylist_retry -- kaynak tablo yazma hatasi ({email}): {e}")


# =============================================================================
# ANA ISLEME FONKSIYONU
# =============================================================================

def process_greylist_retries(log_fn=None) -> dict:
    """
    Suresi dolmus greylisting retry kayitlarini isler.
    worker.py'nin _run_tasks() fonksiyonundan cagrilir.

    Args:
        log_fn: worker.py'nin log() fonksiyonu (opsiyonel)

    Returns:
        {
            'processed': int,   -- toplam islenen
            'resolved':  int,   -- kesin sonuca ulasan (valid/invalid)
            'requeued':  int,   -- yeniden kuyruga alinan (hala unknown)
            'exhausted': int,   -- max deneme doldu, unknown kaldi
        }
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            import datetime as _dt
            print(f"[{_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

    from verifier import _smtp_check, _mx_lookup

    due = _get_due_retries(limit=200)
    if not due:
        _log("Greylisting retry: bekleyen kayit yok.")
        return {'processed': 0, 'resolved': 0, 'requeued': 0, 'exhausted': 0}

    _log(f"Greylisting retry: {len(due)} adres yeniden denenecek.")

    stats = {'processed': 0, 'resolved': 0, 'requeued': 0, 'exhausted': 0}

    for rec in due:
        email      = rec['email']
        table_name = rec['table_name']
        email_col  = rec['email_col']
        attempt    = int(rec['attempt'])
        mx_server  = rec.get('mx_server') or ''
        rec_id     = rec['id']

        stats['processed'] += 1

        # MX sunucusu kaydedilmemişse domain'den yeniden sorgula
        if not mx_server:
            domain = email.split('@')[-1] if '@' in email else ''
            mx_server = _mx_lookup(domain) or ''

        if not mx_server:
            # MX kaydı bulunamadı — domain artık geçersiz, exhausted olarak kapat
            _update_retry_record(rec_id, 'exhausted', 'no_mx')
            _write_result_to_source_table(table_name, email_col, email, -1, 'unknown')
            stats['exhausted'] += 1
            _log(f"  greylist: {email} -- MX bulunamadi, exhausted")
            continue

        # SMTP yeniden dene — greylisting geçti mi?
        try:
            code = _smtp_check(email, mx_server)
        except Exception as e:
            code = None
            _log(f"  greylist: {email} -- SMTP hatası: {e}")

        if code == 250:
            # 250 OK — sunucu bu sefer kabul etti, greylisting geçildi
            _update_retry_record(rec_id, 'done', 'valid')
            _write_result_to_source_table(table_name, email_col, email, 1, 'valid')
            stats['resolved'] += 1
            _log(f"  greylist: {email} -- geçerli (greylisting geçti)")

        elif code == 550:
            # 550 — posta kutusu yok, kalıcı hata; suppression'a da ekle
            _update_retry_record(rec_id, 'done', 'invalid')
            _write_result_to_source_table(table_name, email_col, email, 0, 'invalid')
            try:
                import database as db
                db.add_to_suppression(email, 'invalid', source='greylist_retry')
            except Exception:
                pass
            stats['resolved'] += 1
            _log(f"  greylist: {email} -- geçersiz (550)")

        else:
            # Hâlâ unknown (greylisting devam ediyor) — max deneme aşıldı mı?
            next_attempt = attempt + 1
            if next_attempt > MAX_RETRIES:
                # Max deneme doldu — kalıcı unknown olarak bırak
                _update_retry_record(rec_id, 'exhausted', 'unknown')
                _write_result_to_source_table(table_name, email_col, email, -1, 'unknown')
                stats['exhausted'] += 1
                _log(f"  greylist: {email} -- max deneme doldu, unknown kaldı")
            else:
                # Bir sonraki deneme için yeniden zamanla
                delay_h = RETRY_DELAYS_HOURS.get(next_attempt, 24)
                next_retry = (
                    datetime.datetime.utcnow() + datetime.timedelta(hours=delay_h)
                ).strftime('%Y-%m-%d %H:%M:%S')
                _update_retry_record(
                    rec_id, 'pending', 'unknown',
                    next_attempt=next_attempt,
                    next_retry_after=next_retry,
                )
                stats['requeued'] += 1
                _log(f"  greylist: {email} -- deneme {next_attempt}/{MAX_RETRIES}, "
                     f"{delay_h} saat sonra tekrar")

    _log(
        f"Greylisting retry bitti -- "
        f"cozuldu:{stats['resolved']} "
        f"yeniden-kuyruk:{stats['requeued']} "
        f"exhausted:{stats['exhausted']}"
    )
    return stats
