"""
worker.py — MailSender Pro Kuyruk İşleyici
==========================================
cPanel Cron Job ile her 5 dakikada bir çalıştırılır:
  */5 * * * * cd /home/USER/public_html/mailsender && python3 worker.py >> logs/worker.log 2>&1

Local'de test:
  python worker.py

Mantık:
  1. DB'de next_run_at <= şimdi olan pending/paused görevleri bul
  2. Her görev için o partiyi gönder
  3. Eğer batch_size > 0 ise next_run_at = şimdi + batch_wait_min dk olarak güncelle, durumu 'paused' yap
  4. Liste bittiyse 'done' yap
"""
import os, sys, time, io, datetime, pathlib
from dotenv import load_dotenv

# Uygulama dizinini path'e ekle
BASE_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / '.env')

import database as db_module
from mailer import send_one, send_via_ses, send_via_api, plain_to_html, render_template_str

WORKER_LOG = BASE_DIR / 'logs' / 'worker.log'


def log(msg):
    """Zaman damgalı mesajı hem stdout'a hem worker.log dosyasına yazar."""
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        WORKER_LOG.parent.mkdir(exist_ok=True)
        with open(WORKER_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def get_rows_from_queue(task):
    """Göreve ait tüm e-posta satırlarını döner."""
    if task['source_type'] == 'db':
        ok, result = db_module.get_table_rows(task['source_table'])
        if not ok:
            raise Exception(f"Tablo okunamadı: {result}")
        email_col = task['email_col']
        return [r for r in result if r.get(email_col) and '@' in str(r[email_col])]

    elif task['source_type'] == 'excel':
        import pandas as pd
        excel_data = task['source_excel']
        if isinstance(excel_data, str):
            import base64
            excel_data = base64.b64decode(excel_data)
        df = pd.read_excel(io.BytesIO(excel_data))
        df = df.replace({float('nan'): None})
        email_col = task['email_col']
        rows = []
        for _, row in df.iterrows():
            email = row.get(email_col)
            if email and isinstance(email, str) and '@' in email:
                rows.append(dict(row))
        return rows
    else:
        raise Exception(f"Bilinmeyen source_type: {task['source_type']}")


def process_task(task):
    """Tek bir mail gönderim görevini (send_queue kaydı) işler."""
    qid        = task['id']
    email_col  = task['email_col']
    delay_ms   = int(task['delay_ms'] or 500)
    batch_size = int(task['batch_size'] or 0)
    batch_wait = int(task['batch_wait_min'] or 60)
    offset     = int(task['current_offset'] or 0)
    include_unsub = bool(task['include_unsub'])

    log(f"Görev #{qid} '{task['name']}' başlıyor (offset={offset})")

    # Gönderici
    sender_row = db_module.get_sender(int(task['sender_id']))
    if not sender_row:
        log(f"  ✗ Gönderici bulunamadı (id={task['sender_id']})")
        db_module.queue_update_status(qid, 'cancelled')
        return

    # Kural
    rule_row = db_module.get_rule(int(task['rule_id'])) if task.get('rule_id') else None
    min_interval_h = int(rule_row['min_interval_h']) if rule_row else 0

    # Ek dosya
    attachment = None
    if task.get('attachment_name') and task.get('attachment_data'):
        attachment = (task['attachment_name'], bytes(task['attachment_data']))

    # Tüm satırları yükle
    try:
        all_rows = get_rows_from_queue(task)
    except Exception as e:
        log(f"  ✗ Satırlar yüklenemedi: {e}")
        db_module.queue_update_status(qid, 'cancelled')
        return

    total = len(all_rows)
    if task['total_count'] == 0:
        db_module.queue_update_status(qid, 'running', total_count=total)

    # Bu parti için dilim
    if batch_size > 0:
        batch_rows = all_rows[offset:offset + batch_size]
    else:
        batch_rows = all_rows[offset:]

    if not batch_rows:
        log(f"  ✓ Görev #{qid} tamamlandı (gönderilecek satır kalmadı)")
        db_module.queue_update_status(qid, 'done',
            current_offset=offset,
            sent_count=task['sent_count'],
            failed_count=task['failed_count'],
            skipped_count=task['skipped_count'])
        return

    log(f"  → {len(batch_rows)} mail gönderilecek (toplam {total}, offset {offset})")
    db_module.queue_update_status(qid, 'running')

    ok_c = int(task['sent_count'] or 0)
    err_c = int(task['failed_count'] or 0)
    skip_c = int(task['skipped_count'] or 0)
    mode = sender_row.get('sender_mode', 'smtp')

    for row in batch_rows:
        email = str(row[email_col]).strip()
        variables = {k: ('' if v is None else str(v)) for k, v in row.items()}
        subject = render_template_str(task['subject_tpl'], variables)
        body = render_template_str(task['body_tpl'], variables)
        if task['html_mode']:
            body = plain_to_html(body) if not body.strip().startswith('<') else body

        # Kural kontrolü
        allowed, reason = db_module.can_send(sender_row['id'], email, min_interval_h)
        if not allowed:
            skip_c += 1
            db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                               email, subject, 'skipped', reason)
            db_module.queue_log_item(qid, email, 'skipped', reason)
            log(f"    ⏭ {email} — {reason}")
            time.sleep(delay_ms / 1000)
            continue

        try:
            if mode == 'smtp':
                success, err = send_one(sender_row, email, subject, body,
                                        attachment=attachment,
                                        include_unsubscribe=include_unsub)
                if not success:
                    raise Exception(err or 'SMTP hatası')
            elif mode == 'ses':
                send_via_ses(sender_row, email, subject, body,
                             attachment=attachment,
                             include_unsubscribe=include_unsub)
            elif mode == 'api':
                recipient_name = variables.get('Ad', variables.get('Name', ''))
                send_via_api(sender_row, email, subject, body,
                             recipient_name=recipient_name,
                             include_unsubscribe=include_unsub)

            ok_c += 1
            db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                               email, subject, 'sent')
            db_module.queue_log_item(qid, email, 'sent')
            log(f"    ✓ {email}")

        except Exception as e:
            err_c += 1
            db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                               email, subject, 'failed', str(e))
            db_module.queue_log_item(qid, email, 'failed', str(e))
            log(f"    ✗ {email} — {e}")

        time.sleep(delay_ms / 1000)

    new_offset = offset + len(batch_rows)
    log(f"  Parti bitti: ✓{ok_c} ✗{err_c} ⏭{skip_c} | offset={new_offset}/{total}")

    if batch_size > 0 and new_offset < total:
        # Sonraki partiyi zamanla
        next_run = datetime.datetime.utcnow() + datetime.timedelta(minutes=batch_wait)
        db_module.queue_update_status(qid, 'paused',
            current_offset=new_offset,
            sent_count=ok_c, failed_count=err_c, skipped_count=skip_c,
            next_run_at=next_run.strftime('%Y-%m-%d %H:%M:%S'))
        log(f"  ⏱ Sonraki parti: {next_run.strftime('%H:%M:%S')} UTC ({batch_wait} dk sonra)")
    else:
        db_module.queue_update_status(qid, 'done',
            current_offset=new_offset,
            sent_count=ok_c, failed_count=err_c, skipped_count=skip_c)
        log(f"  ✅ Görev #{qid} tamamlandı.")


def process_verify_job(job):
    """
    Tek bir email_verify_jobs kaydını çalıştırır.
    Her döngüde DB'den güncel status'u okur — iptal için status='cancelled' yeterli.
    """
    import threading
    from verifier import run_verify_job

    jid   = job['id']
    jname = job.get('job_name', f"#{jid}")
    log(f"Verify job #{jid} '{jname}' başlıyor "
        f"(tablo={job['table_name']} mod={job['mode']} "
        f"thread={job['threads']} toplam={job['total_count']})")

    # İptal bayrağı: worker döngüsü içinde status='cancelled' olunca set edilir
    cancel_event = threading.Event()

    def _check_cancelled_periodically():
        """Her 10sn'de bir DB'den status kontrolü yapar, iptal edildiyse event'i set eder."""
        while not cancel_event.is_set():
            import time
            time.sleep(10)
            j = db_module.verify_job_get(jid)
            if j and j.get('status') == 'cancelled':
                cancel_event.set()
                break

    # Arka plan kontrol thread'i
    watcher = threading.Thread(target=_check_cancelled_periodically, daemon=True)
    watcher.start()

    try:
        stats = run_verify_job(
            job_id=jid,
            cancel_flags={jid: cancel_event},
        )
        cancel_event.set()  # watcher'ı durdur
        log(f"Verify job #{jid} bitti — "
            f"✓{stats.get('valid',0)} geçerli "
            f"✗{stats.get('invalid',0)} geçersiz "
            f"⚠{stats.get('unknown',0)} riskli "
            f"🚫{stats.get('suppressed',0)} suppression"
            + (" [İPTAL]" if stats.get('cancelled') else ""))
    except Exception as e:
        cancel_event.set()
        log(f"  HATA verify job #{jid}: {e}")
        import traceback
        log(traceback.format_exc())
        db_module.verify_job_update(jid, status='cancelled')


def run():
    """Worker ana döngüsü: mail kuyruğunu ve verify işlerini sırayla çalıştırır."""
    # ── File Lock: Aynı anda birden fazla worker çalışmasını önle ─────────
    # cPanel cron her 5 dakikada bir worker.py'yi başlatır.
    # Önceki worker hâlâ çalışıyorsa yeni başlatma sessizce çıkar.
    import fcntl
    lock_path = BASE_DIR / 'logs' / 'worker.lock'
    lock_path.parent.mkdir(exist_ok=True)
    try:
        lock_file = open(lock_path, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        print(f"[{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"Worker zaten çalışıyor, bu örnek çıkıyor.")
        return
    try:
        _run_tasks()
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _run_tasks():
    """Asıl iş mantığı — lock alındıktan sonra çağrılır."""
    log("─── Worker başladı ───")

    # ── Mail gönderim kuyruğu ──────────────────────────────────────
    tasks = db_module.queue_get_due()
    if tasks:
        log(f"{len(tasks)} mail görevi bulundu.")
        for task in tasks:
            try:
                process_task(task)
            except Exception as e:
                log(f"  HATA (görev #{task['id']}): {e}")
                import traceback
                log(traceback.format_exc())
    else:
        log("Bekleyen mail görevi yok.")

    # ── E-posta doğrulama kuyruğu ──────────────────────────────────
    verify_jobs = db_module.verify_job_list_pending()
    if verify_jobs:
        log(f"{len(verify_jobs)} doğrulama işi bulundu.")
        for job in verify_jobs:
            try:
                process_verify_job(job)
            except Exception as e:
                log(f"  HATA (verify job #{job['id']}): {e}")
                import traceback
                log(traceback.format_exc())
    else:
        log("Bekleyen doğrulama işi yok.")

    log("─── Worker bitti ───")


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        log("Worker kullanıcı tarafından durduruldu (KeyboardInterrupt).")
    except Exception as e:
        import traceback
        log(f"KRITIK HATA — Worker beklenmedik şekilde çöktü: {e}")
        log(traceback.format_exc())
        # Cron tekrar çalıştıracak — çıkış kodu 1 ile çık
        raise SystemExit(1)
