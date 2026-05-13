"""
auto_reverify.py — Otomatik Zamanlanmış E-posta Yeniden Doğrulama
==================================================================
worker.py her 5 dakikada çalışırken process_auto_reverify() çağrılır.
next_run_at <= şimdi olan aktif zamanlamalar için yeni verify_job başlatır.

NASIL ÇALIŞIR
--------------
1. Kullanıcı ayarlar ekranından bir tablo için zamanlama oluşturur:
   - Hangi tablo (table_name / email_col)
   - Kaç günde bir (interval_days)
   - Hangi adresleri hedefle (target: all / valid_only / unknown_only)
   - Hangi mod (format / mx / smtp)

2. Bu modül worker döngüsünde zamanı gelen zamanlamaları bulur.

3. Her zamanlama için:
   a. Hedef tabloyu hazırlar: target'a göre is_valid kolonunu NULL'a sıfırlar
      (sadece hedeflenen adreslerde) → verify_one() bunları yeniden işler
   b. Yeni bir email_verify_jobs kaydı açar (verify_job_create())
   c. Zamanlamayı günceller: last_run_at = şimdi, next_run_at = şimdi + interval_days

4. Açılan verify_job worker'ın mevcut verify_job_list_pending() döngüsüne düşer
   ve normal akışla işlenir — ayrı bir işleme mekanizması gerekmez.

ENTEGRASYON (worker.py)
------------------------
_run_tasks() içine greylisting bloğundan sonra ekle:

    from auto_reverify import process_auto_reverify
    process_auto_reverify(log_fn=log)

DB FONKSİYONLARI (database.py'ye eklenmeli)
--------------------------------------------
auto_reverify_list_due()        — next_run_at <= şimdi olanları döner
auto_reverify_update()          — last_run_at / next_run_at / last_job_id günceller
auto_reverify_create()          — yeni zamanlama oluşturur
auto_reverify_list()            — tüm zamanlamaları listeler (UI için)
auto_reverify_delete()          — zamanlama siler
auto_reverify_reset_target()    — hedef satırları is_valid=NULL yapar
"""

from __future__ import annotations
import datetime

# Güvenli aralık: en az 1 gün, en fazla 365 gün
MIN_INTERVAL_DAYS = 1
MAX_INTERVAL_DAYS = 365


# =============================================================================
# DB YARDIMCI FONKSİYONLARI
# =============================================================================

def _get_conn():
    import database as db
    return db.get_connection()


def _list_due_schedules() -> list:
    """next_run_at <= UTC şimdi olan aktif zamanlamaları döner."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM auto_reverify_schedules
                WHERE is_active = 1
                  AND (next_run_at IS NULL OR next_run_at <= UTC_TIMESTAMP())
                ORDER BY next_run_at ASC
            """)
            return cur.fetchall() or []
    except Exception as e:
        print(f"auto_reverify — _list_due_schedules hatası: {e}")
        return []
    finally:
        conn.close()


def _update_schedule(
    schedule_id: int,
    last_run_at: str,
    next_run_at: str,
    last_job_id: int | None,
) -> None:
    """Zamanlama kaydını günceller."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE auto_reverify_schedules
                SET last_run_at=%s, next_run_at=%s, last_job_id=%s
                WHERE id=%s
            """, (last_run_at, next_run_at, last_job_id, schedule_id))
        conn.commit()
    except Exception as e:
        print(f"auto_reverify — _update_schedule hatası: {e}")
    finally:
        conn.close()


def _reset_target_rows(
    table_name: str,
    email_col:  str,
    target:     str,
) -> int:
    """
    Hedef tablosundaki ilgili satırların is_valid kolonunu NULL'a sıfırlar.
    verify_one() sadece is_valid IS NULL olanları işler (only_unchecked=True).

    target değerleri:
        'all'          → tüm satırları sıfırla
        'valid_only'   → sadece is_valid=1 olanları sıfırla
        'invalid_only' → sadece is_valid=0 olanları sıfırla
        'unknown_only' → sadece is_valid=-1 olanları sıfırla

    Döner: sıfırlanan satır sayısı
    """
    from security import safe_identifier
    try:
        safe_identifier(table_name)
        safe_identifier(email_col)
    except Exception as e:
        print(f"auto_reverify — güvensiz tablo/kolon adı: {e}")
        return 0

    # target değerine göre hangi satırların sıfırlanacağını belirle
    where_map = {
        'all':          'is_valid IS NOT NULL',   # Doğrulanmış tüm satırlar
        'valid_only':   'is_valid = 1',           # Sadece geçerli olanları yeniden denetle
        'invalid_only': 'is_valid = 0',           # Sadece geçersiz olanları yeniden denetle
        'unknown_only': 'is_valid = -1',          # Sadece belirsiz olanları yeniden denetle
    }
    where = where_map.get(target, 'is_valid IS NOT NULL')

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # is_valid kolonu var mı? Excel yüklenmiş ama verify edilmemiş tablolarda olmayabilir
            import database as db
            db_name = db.get_db_config()['database']
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s AND column_name='is_valid'",
                (db_name, table_name)
            )
            if cur.fetchone()['cnt'] == 0:
                return 0  # Kolon yok — sıfırlanacak şey yok

            # Hedef satırları NULL'a sıfırla; verify_one() sadece NULL olanları işler
            cur.execute(
                f"UPDATE `{table_name}` SET is_valid = NULL WHERE {where}"
            )
            affected = cur.rowcount
        conn.commit()
        return affected
    except Exception as e:
        print(f"auto_reverify — _reset_target_rows hatası ({table_name}): {e}")
        return 0
    finally:
        conn.close()


# =============================================================================
# ANA İŞLEME FONKSİYONU
# =============================================================================

def process_auto_reverify(log_fn=None) -> dict:
    """
    Zamanı gelen otomatik yeniden doğrulama işlerini başlatır.
    worker.py'nin _run_tasks() fonksiyonundan çağrılır.

    Args:
        log_fn: worker.py'nin log() fonksiyonu (opsiyonel)

    Returns:
        {
            'checked':  int,  — kontrol edilen zamanlama sayısı
            'started':  int,  — başlatılan yeni verify_job sayısı
            'skipped':  int,  — atlanan (hata / boş tablo / zaten çalışıyor)
        }
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
        else:
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{ts}] {msg}")

    import database as db

    due = _list_due_schedules()
    if not due:
        return {'checked': 0, 'started': 0, 'skipped': 0}

    _log(f"Otomatik yeniden doğrulama: {len(due)} zamanlama kontrol ediliyor.")
    stats = {'checked': len(due), 'started': 0, 'skipped': 0}

    for sched in due:
        sid        = sched['id']
        table_name = sched['table_name']
        email_col  = sched['email_col']
        mode       = sched['mode']
        threads    = int(sched.get('threads') or 10)
        target     = sched.get('target') or 'all'
        interval   = int(sched.get('interval_days') or 90)
        created_by = sched.get('created_by') or 'auto'
        created_by_id = sched.get('created_by_id')

        _log(f"  Zamanlama #{sid}: {table_name} / {target} / {mode} / {interval}g")

        # 1. Aynı tablo için hâlâ çalışan bir job var mı?
        try:
            existing_jobs = db.verify_job_list()
            running = [
                j for j in existing_jobs
                if j.get('table_name') == table_name
                and j.get('status') in ('pending', 'running')
            ]
            if running:
                _log(f"    ⏭ Atlandı — tablo için zaten aktif job var (#{running[0]['id']})")
                stats['skipped'] += 1
                continue
        except Exception as e:
            _log(f"    ⚠ Job listesi kontrol hatası: {e}")

        # 2. Hedef satırları NULL'a sıfırla
        try:
            reset_count = _reset_target_rows(table_name, email_col, target)
            if reset_count == 0:
                _log(f"    ⏭ Atlandı — sıfırlanacak satır yok (target={target})")
                stats['skipped'] += 1
                # Zamanlamayı yine de güncelle — boş tabloya sürekli çarpmayalım
                now       = datetime.datetime.utcnow()
                next_run  = now + datetime.timedelta(days=interval)
                _update_schedule(
                    sid,
                    last_run_at=now.strftime('%Y-%m-%d %H:%M:%S'),
                    next_run_at=next_run.strftime('%Y-%m-%d %H:%M:%S'),
                    last_job_id=None,
                )
                continue
            _log(f"    → {reset_count} satır yeniden doğrulama için sıfırlandı")
        except Exception as e:
            _log(f"    ✗ Sıfırlama hatası: {e}")
            stats['skipped'] += 1
            continue

        # 3. Yeni verify_job oluştur
        job_name = (
            f"[Otomatik] {table_name} — "
            f"{datetime.datetime.utcnow().strftime('%Y-%m-%d')}"
        )
        try:
            ok, job_id = db.verify_job_create(
                job_name=job_name,
                table_name=table_name,
                email_col=email_col,
                mode=mode,
                threads=threads,
                user_id=created_by_id,
                username=f"{created_by} (auto)",
            )
            if not ok:
                _log(f"    ✗ verify_job oluşturulamadı: {job_id}")
                stats['skipped'] += 1
                continue
            _log(f"    ✓ verify_job #{job_id} oluşturuldu")
        except Exception as e:
            _log(f"    ✗ verify_job_create hatası: {e}")
            stats['skipped'] += 1
            continue

        # 4. Zamanlamayı güncelle
        now      = datetime.datetime.utcnow()
        next_run = now + datetime.timedelta(days=interval)
        _update_schedule(
            sid,
            last_run_at=now.strftime('%Y-%m-%d %H:%M:%S'),
            next_run_at=next_run.strftime('%Y-%m-%d %H:%M:%S'),
            last_job_id=job_id,
        )
        _log(f"    ✓ Sonraki çalışma: {next_run.strftime('%Y-%m-%d')} "
             f"({interval} gün sonra)")
        stats['started'] += 1

    if stats['started'] > 0:
        _log(f"Otomatik yeniden doğrulama bitti — "
             f"{stats['started']} iş başlatıldı, "
             f"{stats['skipped']} atlandı.")
    return stats


# =============================================================================
# DB FONKSİYONLARI (database.py'ye eklenecek yardımcılar)
# =============================================================================

def create_schedule(
    table_name:    str,
    email_col:     str    = 'email',
    mode:          str    = 'mx',
    threads:       int    = 10,
    interval_days: int    = 90,
    target:        str    = 'all',
    user_id:       int | None = None,
    username:      str | None = None,
    start_now:     bool   = False,
) -> tuple[bool, int | str]:
    """
    Yeni otomatik yeniden doğrulama zamanlaması oluşturur.

    Args:
        start_now: True ise next_run_at = şimdi (ilk çalışma hemen)
                   False ise next_run_at = şimdi + interval_days

    Returns:
        (True, schedule_id) veya (False, hata_metni)
    """
    from security import safe_identifier
    try:
        safe_identifier(table_name)
        safe_identifier(email_col)
    except ValueError as e:
        return False, f"Geçersiz tablo/kolon adı: {e}"

    # interval_days sınırlarını zorla — çok kısa veya çok uzun aralıkları engelle
    interval_days = max(MIN_INTERVAL_DAYS, min(MAX_INTERVAL_DAYS, interval_days))

    if mode not in ('format', 'mx', 'smtp'):
        return False, f"Geçersiz mod: {mode}"
    if target not in ('all', 'valid_only', 'invalid_only', 'unknown_only'):
        return False, f"Geçersiz hedef: {target}"

    now      = datetime.datetime.utcnow()
    # start_now=True ise next_run_at=şimdi → worker bir sonraki turda hemen başlatır
    next_run = now if start_now else now + datetime.timedelta(days=interval_days)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO auto_reverify_schedules
                    (table_name, email_col, mode, threads, interval_days,
                     target, is_active, next_run_at, created_by_id, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    mode=%s, threads=%s, interval_days=%s,
                    target=%s, is_active=1, next_run_at=%s,
                    created_by_id=%s, created_by=%s
            """, (
                table_name, email_col, mode, threads, interval_days,
                target, next_run.strftime('%Y-%m-%d %H:%M:%S'),
                user_id, username,
                # ON DUPLICATE KEY:
                mode, threads, interval_days,
                target, next_run.strftime('%Y-%m-%d %H:%M:%S'),
                user_id, username,
            ))
            sid = cur.lastrowid
        conn.commit()
        return True, sid
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def list_schedules() -> list:
    """Tüm zamanlamaları döner (UI listesi için)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM auto_reverify_schedules
                ORDER BY table_name ASC
            """)
            return cur.fetchall() or []
    except Exception:
        return []
    finally:
        conn.close()


def toggle_schedule(schedule_id: int, is_active: bool) -> bool:
    """Zamanlamayı aktif/pasif yapar."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE auto_reverify_schedules SET is_active=%s WHERE id=%s",
                (1 if is_active else 0, schedule_id)
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_schedule(schedule_id: int) -> bool:
    """Zamanlamayı siler."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM auto_reverify_schedules WHERE id=%s",
                (schedule_id,)
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()
