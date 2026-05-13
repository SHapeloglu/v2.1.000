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
from mailer import is_role_based, is_disposable   # Madde 2: filtreler worker'da da çalışsın
from spam_trap import check_spam_trap              # Madde 2: spam tuzağı filtresi
from toxic_domain import check_toxic_domain        # Madde 2: toxic domain filtresi
from verifier import _mx_lookup, _catchall_check   # Madde 2: MX ve catch-all kontrolleri
from verifier import _is_gibberish, _has_spam_local_keywords  # Madde 2: gibberish ve spam keyword
from greylist_retry import process_greylist_retries
from auto_reverify import process_auto_reverify

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

    # ── Bulk performans önbellekleri — görev başında bir kez yükle ──
    _supp_set         = db_module.load_suppression_set()
    _sender_cache     = {}
    _user_rule_cache  = {}
    _sent_today_cache = {sender_row['id']: db_module.get_sender_sent_today(sender_row['id'])}
    _bulk_conn        = db_module.get_connection()
    _log_buffer       = []

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

    # Madde 2: görev bazlı e-posta filtre ayarları
    filter_role        = bool(task.get('filter_role', 0))
    filter_disposable  = bool(task.get('filter_disposable', 1))
    filter_spamtrap    = bool(task.get('filter_spamtrap', 1))    # Varsayılan: açık
    filter_toxicdomain = bool(task.get('filter_toxicdomain', 1)) # Varsayılan: açık
    filter_gibberish   = bool(task.get('filter_gibberish', 0))   # Varsayılan: kapalı
    filter_spamlocal   = bool(task.get('filter_spamlocal', 0))   # Varsayılan: kapalı
    risk_threshold     = int(task.get('risk_threshold') or 0)    # 0 = kapalı
    filter_noinfra     = bool(task.get('filter_noinfra', 0))     # Varsayılan: kapalı
    mx_check           = bool(task.get('mx_check', 1))           # Varsayılan: açık
    only_valid         = bool(task.get('only_valid', 1))         # Varsayılan: açık
    filter_catchall    = bool(task.get('filter_catchall', 0))    # Varsayılan: kapalı

    # Madde 5: A/B test ayarları
    ab_test      = bool(task.get('ab_test', 0))
    subject_b    = (task.get('subject_b') or '').strip()
    ab_ratio     = int(task.get('ab_ratio') or 50)  # A yüzdesi (varsayılan %50)
    ab_counter   = 0  # kaçıncı mail olduğunu sayar, oran hesabı için

    for row in batch_rows:
        email = str(row[email_col]).strip()
        variables = {k: ('' if v is None else str(v)) for k, v in row.items()}
        subject = render_template_str(task['subject_tpl'], variables)
        body = render_template_str(task['body_tpl'], variables)
        if task['html_mode']:
            body = plain_to_html(body) if not body.strip().startswith('<') else body

        # Madde 2: rol/disposable filtre kontrolü
        # ── only_valid: tabloda is_valid kolonu varsa sadece is_valid=1 olanları gönder
        if only_valid:
            _iv = row.get('is_valid')
            if _iv is not None:  # Kolon varsa uygula; NULL ise (verify yapılmamış) atla
                try:
                    if int(_iv) != 1:
                        skip_c += 1
                        reason = f'is_valid={_iv}, doğrulanmamış adres atlanıyor: {email}'
                        db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                           email, subject, 'skipped', reason)
                        db_module.queue_log_item(qid, email, 'skipped', reason)
                        log(f'    ⏭ {email} — is_valid={_iv}')
                        continue
                except (ValueError, TypeError):
                    pass

        # ── mx_check: domain'in MX / A kaydı var mı? (TTL önbellekli, hızlı)
        if mx_check:
            _domain_mx = email.split('@')[1].lower().strip() if '@' in email else ''
            if _domain_mx:
                _mx = _mx_lookup(_domain_mx)
                if not _mx:
                    skip_c += 1
                    reason = f'MX kaydı yok ({_domain_mx}), atlanıyor: {email}'
                    db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                       email, subject, 'skipped', reason)
                    db_module.queue_log_item(qid, email, 'skipped', reason)
                    log(f'    ⏭ {email} — MX kaydı yok')
                    continue

        if filter_disposable and is_disposable(email):
            skip_c += 1
            reason = f'Geçici e-posta domain\u2019i, atlanıyor: {email}'
            db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                               email, subject, 'skipped', reason)
            db_module.queue_log_item(qid, email, 'skipped', reason)
            log(f'    ⏭ {email} — disposable domain')
            continue
        if filter_role and is_role_based(email):
            skip_c += 1
            reason = f'Rol adresi, atlanıyor: {email}'
            db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                               email, subject, 'skipped', reason)
            db_module.queue_log_item(qid, email, 'skipped', reason)
            log(f'    ⏭ {email} — rol adresi')
            continue
        # ── Gibberish (bot üretim) adresi filtresi
        if filter_gibberish:
            _local_gb = email.split('@')[0].split('+')[0].lower().strip() if '@' in email else email
            if _is_gibberish(_local_gb):
                skip_c += 1
                reason = f'Bot/oto üretim adresi (gibberish), atlanıyor: {email}'
                db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                   email, subject, 'skipped', reason)
                db_module.queue_log_item(qid, email, 'skipped', reason)
                log(f'    ⏭ {email} — gibberish local kısım')
                continue
        # ── Spam keyword filtresi (local kısımda)
        if filter_spamlocal:
            _local_sl = email.split('@')[0].split('+')[0].lower().strip() if '@' in email else email
            if _has_spam_local_keywords(_local_sl):
                skip_c += 1
                reason = f'Spam keyword tespit edildi ({_local_sl}), atlanıyor: {email}'
                db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                   email, subject, 'skipped', reason)
                db_module.queue_log_item(qid, email, 'skipped', reason)
                log(f'    ⏭ {email} — spam keyword')
                continue
        if filter_spamtrap:
            _local = email.split('@')[0].split('+')[0].lower().strip() if '@' in email else email
            _domain = email.split('@')[1].lower().strip() if '@' in email else ''
            _is_trap, _trap_type, _trap_conf = check_spam_trap(email, _domain, _local, {})
            if _is_trap and _trap_conf == 'high':
                skip_c += 1
                reason = f'Spam tuzağı tespit edildi ({_trap_type}), atlanıyor: {email}'
                db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                   email, subject, 'skipped', reason)
                db_module.queue_log_item(qid, email, 'skipped', reason)
                log(f'    ⏭ {email} — spam tuzağı ({_trap_type})')
                continue
        if filter_toxicdomain:
            _domain = email.split('@')[1].lower().strip() if '@' in email else ''
            _is_toxic, _toxic_type, _toxic_conf = check_toxic_domain(_domain, {})
            if _is_toxic and _toxic_conf == 'high':
                skip_c += 1
                reason = f'Toxic domain tespit edildi ({_toxic_type}), atlanıyor: {email}'
                db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                   email, subject, 'skipped', reason)
                db_module.queue_log_item(qid, email, 'skipped', reason)
                log(f'    ⏭ {email} — toxic domain ({_toxic_type})')
                continue
        # Risk skoru eşiği — tabloda risk_score kolonu varsa kontrol et
        # Kolon yoksa veya NULL ise bu filtreyi atla (verify yapılmamış listeler)
        if risk_threshold > 0:
            row_risk = row.get('risk_score')
            if row_risk is not None:
                try:
                    if int(row_risk) < risk_threshold:
                        skip_c += 1
                        reason = f'Risk skoru düşük ({row_risk} < {risk_threshold}), atlanıyor: {email}'
                        db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                           email, subject, 'skipped', reason)
                        db_module.queue_log_item(qid, email, 'skipped', reason)
                        log(f'    ⏭ {email} — risk skoru {row_risk} < eşik {risk_threshold}')
                        continue
                except (ValueError, TypeError):
                    pass  # risk_score parse edilemiyorsa atla
        # ── filter_catchall: her adresi kabul eden domain'leri SMTP probe ile tespit et
        # mx_check aktifken çalışır — _mx değişkeni zaten üstte atanmış olabilir
        if filter_catchall:
            _domain_ca = email.split('@')[1].lower().strip() if '@' in email else ''
            if _domain_ca:
                _mx_ca = _mx_lookup(_domain_ca)
                if _mx_ca:
                    try:
                        _is_ca = _catchall_check(_mx_ca, _domain_ca)
                        if _is_ca:
                            skip_c += 1
                            reason = f'Catch-all domain ({_domain_ca}), atlanıyor: {email}'
                            db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                               email, subject, 'skipped', reason)
                            db_module.queue_log_item(qid, email, 'skipped', reason)
                            log(f'    ⏭ {email} — catch-all domain')
                            continue
                    except Exception:
                        pass  # Catch-all probe başarısız — güvenli tarafta kal, gönder

        # SPF / DMARC zayıf domain filtresi
        # Tabloda is_valid=-1 (no_infra) veya verify_status='no_infra' olanları atla.
        # Gmail/Yahoo/Outlook gibi güvenilir sağlayıcılar bu filtreden muaftır.
        if filter_noinfra:
            _domain = email.split('@')[1].lower().strip() if '@' in email else ''
            # Güvenilir büyük sağlayıcılar — SPF/DMARC muaf
            _trusted = {
                'gmail.com','googlemail.com','yahoo.com','ymail.com','outlook.com',
                'hotmail.com','live.com','icloud.com','me.com','protonmail.com',
                'proton.me','aol.com','yandex.com','yandex.ru','mail.ru',
            }
            if _domain and _domain not in _trusted:
                # Önce tablodaki verify_status veya is_valid kolonunu kontrol et
                _vstatus = row.get('verify_status') or ''
                _is_valid = row.get('is_valid')
                _is_noinfra = (
                    _vstatus == 'no_infra' or
                    (_is_valid is not None and str(_is_valid) == '-1' and _vstatus in ('no_infra', ''))
                )
                if not _is_noinfra:
                    # Tabloda bilgi yoksa canlı SPF/DMARC sorgusu yap (önbellekli)
                    try:
                        from verifier import _check_spf, _check_dmarc
                        _has_spf   = _check_spf(_domain)
                        _has_dmarc = _check_dmarc(_domain)
                        _is_noinfra = not _has_spf and not _has_dmarc
                    except Exception:
                        _is_noinfra = False
                if _is_noinfra:
                    skip_c += 1
                    reason = f'SPF/DMARC altyapısı yok ({_domain}), atlanıyor: {email}'
                    db_module.log_send(sender_row['id'], task.get('rule_id') and int(task['rule_id']),
                                       email, subject, 'skipped', reason)
                    db_module.queue_log_item(qid, email, 'skipped', reason)
                    log(f'    ⏭ {email} — SPF/DMARC yok ({_domain})')
                    continue

        # Kural kontrolü (suppression + günlük limit + warmup) — önbellekli
        allowed, reason = db_module.can_send_ctx(
            _bulk_conn, sender_row['id'], email, min_interval_h,
            _sender_cache=_sender_cache,
            _suppression_set=_supp_set,
            _user_rule_cache=_user_rule_cache,
            _sent_today_cache=_sent_today_cache,
        )
        if not allowed:
            skip_c += 1
            _log_buffer.append({'sender_id': sender_row['id'],
                'rule_id': task.get('rule_id') and int(task['rule_id']),
                'recipient': email, 'subject': subject, 'status': 'skipped',
                'error_msg': reason, 'message_id': None, 'provider': None,
                'user_id': None, 'username': None})
            if len(_log_buffer) >= 50:
                db_module.log_send_bulk(_log_buffer); _log_buffer.clear()
            db_module.queue_log_item(qid, email, 'skipped', reason)
            log(f"    ⏭ {email} — {reason}")
            continue

        # Madde 5: A/B test — konu satırını orana göre seç
        if ab_test and subject_b:
            ab_counter += 1
            # ab_ratio = A yüzdesi; örn. 50 → ilk 50/100 mail A, kalan B
            use_b = (ab_counter % 100) > ab_ratio
            active_subject = subject_b if use_b else subject
            ab_label = 'B' if use_b else 'A'
        else:
            active_subject = subject
            ab_label = None

        try:
            msg_id = None  # Madde 8: provider'dan dönen message ID
            if mode == 'smtp':
                success, err = send_one(sender_row, email, active_subject, body,
                                        attachment=attachment,
                                        include_unsubscribe=include_unsub)
                if not success:
                    raise Exception(err or 'SMTP hatası')
            elif mode == 'ses':
                # Madde 8: send_via_ses msg_id döndürüyor
                msg_id = send_via_ses(sender_row, email, active_subject, body,
                                      attachment=attachment,
                                      include_unsubscribe=include_unsub)
            elif mode == 'api':
                recipient_name = variables.get('Ad', variables.get('Name', ''))
                # Madde 8: send_via_api (True, msg_id) veya (True, raw) döndürüyor
                _ok, _ret = send_via_api(sender_row, email, active_subject, body,
                                         recipient_name=recipient_name,
                                         include_unsubscribe=include_unsub)
                if isinstance(_ret, str) and len(_ret) < 500:
                    msg_id = _ret

            ok_c += 1
            if _sent_today_cache is not None:
                _sent_today_cache[sender_row['id']] = _sent_today_cache.get(sender_row['id'], 0) + 1
            log_subject = f'[A/B:{ab_label}] {active_subject}' if ab_label else active_subject
            _log_buffer.append({'sender_id': sender_row['id'],
                'rule_id': task.get('rule_id') and int(task['rule_id']),
                'recipient': email, 'subject': log_subject, 'status': 'sent',
                'error_msg': None, 'message_id': msg_id, 'provider': mode,
                'user_id': None, 'username': None})
            if len(_log_buffer) >= 50:
                db_module.log_send_bulk(_log_buffer); _log_buffer.clear()
            db_module.queue_log_item(qid, email, 'sent')
            log(f"    ✓ {email}" + (f" [{ab_label}]" if ab_label else ""))

        except Exception as e:
            err_c += 1
            _log_buffer.append({'sender_id': sender_row['id'],
                'rule_id': task.get('rule_id') and int(task['rule_id']),
                'recipient': email, 'subject': active_subject, 'status': 'failed',
                'error_msg': str(e), 'message_id': None, 'provider': mode,
                'user_id': None, 'username': None})
            if len(_log_buffer) >= 50:
                db_module.log_send_bulk(_log_buffer); _log_buffer.clear()
            db_module.queue_log_item(qid, email, 'failed', str(e))
            log(f"    ✗ {email} — {e}")

        time.sleep(delay_ms / 1000)

    # Kalan log tamponunu flush et
    if _log_buffer:
        db_module.log_send_bulk(_log_buffer); _log_buffer.clear()
    try:
        _bulk_conn.close()
    except Exception:
        pass

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

    # ── Greylisting retry kuyruğu ───────────────────────────────
    try:
        gl_stats = process_greylist_retries(log_fn=log)
        if gl_stats['processed'] > 0:
            log(f"Greylisting retry: "
                f"{gl_stats['resolved']} cozuldu, "
                f"{gl_stats['requeued']} yeniden kuyruga alindi, "
                f"{gl_stats['exhausted']} exhausted.")
    except Exception as e:
        log(f"  HATA (greylist retry): {e}")
        import traceback
        log(traceback.format_exc())

    # ── Otomatik yeniden doğrulama zamanlamaları ────────────────
    try:
        ar_stats = process_auto_reverify(log_fn=log)
        if ar_stats['started'] > 0:
            log(f"Otomatik yeniden doğrulama: "
                f"{ar_stats['started']} iş başlatıldı, "
                f"{ar_stats['skipped']} atlandı.")
    except Exception as e:
        log(f"  HATA (auto_reverify): {e}")
        import traceback
        log(traceback.format_exc())

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
