"""
test_greylist_retry.py — greylist_retry.py icin birim testler
=============================================================
Calistirma:
    python test_greylist_retry.py

DB baglantisi gerektiren fonksiyonlar mock ile test edilir.
"""

import sys, os, datetime, types
sys.path.insert(0, os.path.dirname(__file__))

# ── Mock database modulu (DB baglantisi olmadan test icin) ────────────────────
_suppression = []
_fake_db_name = 'testdb'

mock_db = types.ModuleType('database')
mock_db.get_connection   = lambda: None
mock_db.get_db_config    = lambda: {'database': _fake_db_name}
mock_db.add_to_suppression = lambda email, reason, source=None: _suppression.append(email)
sys.modules['database'] = mock_db

mock_sec = types.ModuleType('security')
mock_sec.safe_identifier = lambda x: x
sys.modules['security'] = mock_sec

# greylist_retry'yi import et (DB fonksiyonlarini mock'layacagiz)
import greylist_retry as gr

# ── Yardimci ──────────────────────────────────────────────────────────────────
def run(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition

# =============================================================================

def test_retry_delays():
    print("\n── Retry gecikme tablosu testleri ──────────────────────────")
    ok = True
    ok &= run("Deneme 1 -> 6 saat",  gr.RETRY_DELAYS_HOURS[1] == 6)
    ok &= run("Deneme 2 -> 12 saat", gr.RETRY_DELAYS_HOURS[2] == 12)
    ok &= run("Deneme 3 -> 24 saat", gr.RETRY_DELAYS_HOURS[3] == 24)
    ok &= run("MAX_RETRIES = 3",     gr.MAX_RETRIES == 3)
    return ok


def test_enqueue_sets_correct_retry_time():
    print("\n── enqueue_greylist_retry() retry_after hesaplama testi ────")
    ok = True

    inserted = []

    def fake_get_conn_enqueue():
        class FakeCursor:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def execute(self, sql, params=None):
                if 'SELECT' in sql:
                    self._last = None
                elif 'INSERT' in sql:
                    inserted.append(params)
            def fetchone(self): return None
        class FakeConn:
            def cursor(self): return FakeCursor()
            def commit(self): pass
            def close(self): pass
        return FakeConn()

    original = gr._get_conn
    gr._get_conn = fake_get_conn_enqueue

    before = datetime.datetime.utcnow()
    result = gr.enqueue_greylist_retry(
        email='test@example.com',
        table_name='contacts',
        email_col='email',
        job_id=42,
        mx_server='mail.example.com',
        attempt=1,
    )
    after = datetime.datetime.utcnow()

    gr._get_conn = original

    ok &= run("enqueue True dondurdu", result is True)
    ok &= run("INSERT cagrisi yapildi", len(inserted) == 1)

    if inserted:
        params = inserted[0]
        retry_str = params[6]   # retry_after
        retry_dt  = datetime.datetime.strptime(retry_str, '%Y-%m-%d %H:%M:%S')
        now       = datetime.datetime.utcnow()
        diff_h    = (retry_dt - now).total_seconds() / 3600
        ok &= run("retry_after ~6 saat sonra (5.9-6.1 aralik)",
                  5.9 <= diff_h <= 6.1)
        ok &= run("attempt=1 kaydedildi", params[5] == 1)
        ok &= run("mx_server kaydedildi", params[4] == 'mail.example.com')

    return ok


def test_process_no_due_records():
    print("\n── process_greylist_retries() - bekleyen kayit yok ────────")
    ok = True

    original = gr._get_due_retries
    gr._get_due_retries = lambda limit=200: []

    # verifier mock (process_greylist_retries iceride import eder)
    import types as _t2
    _mock_v2 = _t2.ModuleType('verifier')
    _mock_v2._smtp_check = lambda e, m: None
    _mock_v2._mx_lookup  = lambda d: None
    sys.modules['verifier'] = _mock_v2

    logs = []
    stats = gr.process_greylist_retries(log_fn=logs.append)

    gr._get_due_retries = original

    ok &= run("processed=0", stats['processed'] == 0)
    ok &= run("resolved=0",  stats['resolved']  == 0)
    ok &= run("requeued=0",  stats['requeued']  == 0)
    ok &= run("exhausted=0", stats['exhausted'] == 0)
    ok &= run("log mesaji yazildi", any('bekleyen' in l for l in logs))
    return ok


def test_process_valid_result():
    print("\n── process_greylist_retries() - SMTP 250 (valid) ───────────")
    ok = True

    fake_records = [
        {
            'id': 1, 'email': 'user@company.com',
            'table_name': 'contacts', 'email_col': 'email',
            'attempt': 1, 'mx_server': 'mail.company.com', 'job_id': 10,
        }
    ]

    updates = []
    writes  = []

    original_due    = gr._get_due_retries
    original_update = gr._update_retry_record
    original_write  = gr._write_result_to_source_table

    gr._get_due_retries          = lambda limit=200: fake_records
    gr._update_retry_record      = lambda *a, **kw: updates.append((a, kw))
    gr._write_result_to_source_table = lambda *a: writes.append(a)

    import verifier as _v_orig
    import types as _t
    mock_v = _t.ModuleType('verifier')
    mock_v._smtp_check = lambda email, mx: 250
    mock_v._mx_lookup  = lambda domain: 'mail.company.com'
    sys.modules['verifier'] = mock_v

    logs  = []
    stats = gr.process_greylist_retries(log_fn=logs.append)

    sys.modules['verifier'] = _v_orig
    gr._get_due_retries              = original_due
    gr._update_retry_record          = original_update
    gr._write_result_to_source_table = original_write

    ok &= run("processed=1",  stats['processed'] == 1)
    ok &= run("resolved=1",   stats['resolved']  == 1)
    ok &= run("requeued=0",   stats['requeued']  == 0)
    ok &= run("update 'done' cagrisi", any('done' in str(u) for u in updates))
    ok &= run("is_valid=1 yazildi",    any(1 in w for w in writes))
    return ok


def test_process_invalid_result():
    print("\n── process_greylist_retries() - SMTP 550 (invalid) ────────")
    ok = True

    fake_records = [
        {
            'id': 2, 'email': 'bad@company.com',
            'table_name': 'contacts', 'email_col': 'email',
            'attempt': 1, 'mx_server': 'mail.company.com', 'job_id': 10,
        }
    ]

    updates = []
    writes  = []
    _suppression.clear()

    original_due    = gr._get_due_retries
    original_update = gr._update_retry_record
    original_write  = gr._write_result_to_source_table

    gr._get_due_retries              = lambda limit=200: fake_records
    gr._update_retry_record          = lambda *a, **kw: updates.append((a, kw))
    gr._write_result_to_source_table = lambda *a: writes.append(a)

    import types as _t
    mock_v = _t.ModuleType('verifier')
    mock_v._smtp_check = lambda email, mx: 550
    mock_v._mx_lookup  = lambda domain: 'mail.company.com'
    sys.modules['verifier'] = mock_v

    stats = gr.process_greylist_retries(log_fn=lambda m: None)

    gr._get_due_retries              = original_due
    gr._update_retry_record          = original_update
    gr._write_result_to_source_table = original_write

    ok &= run("resolved=1",          stats['resolved'] == 1)
    ok &= run("is_valid=0 yazildi",  any(0 in w for w in writes))
    ok &= run("suppression'a eklendi", 'bad@company.com' in _suppression)
    return ok


def test_process_requeue():
    print("\n── process_greylist_retries() - hala unknown -> requeue ───")
    ok = True

    fake_records = [
        {
            'id': 3, 'email': 'grey@company.com',
            'table_name': 'contacts', 'email_col': 'email',
            'attempt': 1, 'mx_server': 'mail.company.com', 'job_id': 10,
        }
    ]

    updates = []

    original_due    = gr._get_due_retries
    original_update = gr._update_retry_record
    original_write  = gr._write_result_to_source_table

    gr._get_due_retries              = lambda limit=200: fake_records
    gr._update_retry_record          = lambda *a, **kw: updates.append((a, kw))
    gr._write_result_to_source_table = lambda *a: None

    import types as _t
    mock_v = _t.ModuleType('verifier')
    mock_v._smtp_check = lambda email, mx: None   # hala greylisted
    mock_v._mx_lookup  = lambda domain: 'mail.company.com'
    sys.modules['verifier'] = mock_v

    stats = gr.process_greylist_retries(log_fn=lambda m: None)

    gr._get_due_retries              = original_due
    gr._update_retry_record          = original_update
    gr._write_result_to_source_table = original_write

    ok &= run("requeued=1",   stats['requeued']  == 1)
    ok &= run("exhausted=0",  stats['exhausted'] == 0)
    # update cagrisi: status='pending', next_attempt=2
    ok &= run("next_attempt=2 set edildi",
              any(kw.get('next_attempt') == 2 for _, kw in updates))
    return ok


def test_process_exhausted():
    print("\n── process_greylist_retries() - max deneme doldu ───────────")
    ok = True

    fake_records = [
        {
            'id': 4, 'email': 'gone@company.com',
            'table_name': 'contacts', 'email_col': 'email',
            'attempt': 3,   # MAX_RETRIES = 3, bir sonraki 4 -> exhausted
            'mx_server': 'mail.company.com', 'job_id': 10,
        }
    ]

    updates = []
    writes  = []

    original_due    = gr._get_due_retries
    original_update = gr._update_retry_record
    original_write  = gr._write_result_to_source_table

    gr._get_due_retries              = lambda limit=200: fake_records
    gr._update_retry_record          = lambda *a, **kw: updates.append((a, kw))
    gr._write_result_to_source_table = lambda *a: writes.append(a)

    import types as _t
    mock_v = _t.ModuleType('verifier')
    mock_v._smtp_check = lambda email, mx: None
    mock_v._mx_lookup  = lambda domain: 'mail.company.com'
    sys.modules['verifier'] = mock_v

    stats = gr.process_greylist_retries(log_fn=lambda m: None)

    gr._get_due_retries              = original_due
    gr._update_retry_record          = original_update
    gr._write_result_to_source_table = original_write

    ok &= run("exhausted=1",     stats['exhausted'] == 1)
    ok &= run("requeued=0",      stats['requeued']  == 0)
    ok &= run("'exhausted' status yazildi",
              any('exhausted' in str(u) for u in updates))
    ok &= run("is_valid=-1 yazildi", any(-1 in w for w in writes))
    return ok


# =============================================================================

if __name__ == '__main__':
    results = [
        test_retry_delays(),
        test_enqueue_sets_correct_retry_time(),
        test_process_no_due_records(),
        test_process_valid_result(),
        test_process_invalid_result(),
        test_process_requeue(),
        test_process_exhausted(),
    ]
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*52}")
    print(f"Sonuc: {passed}/{total} test grubu basarili")
    if passed < total:
        print("BAZI TESTLER BASARISIZ")
        sys.exit(1)
    else:
        print("Tum testler gecti.")
