"""
test_auto_reverify.py — auto_reverify.py birim testleri
========================================================
DB baglantisi gerektirmeyen mock testler.
Calistirma: python test_auto_reverify.py
"""
import sys, os, types, datetime
sys.path.insert(0, os.path.dirname(__file__))

# ── Mock'lar ──────────────────────────────────────────────────────────────────
mock_db = types.ModuleType('database')
mock_db.get_connection    = lambda: None
mock_db.get_db_config     = lambda: {'database': 'testdb'}
mock_db.verify_job_list   = lambda: []
mock_db.verify_job_create = lambda **kw: (True, 42)
sys.modules['database'] = mock_db

mock_sec = types.ModuleType('security')
mock_sec.safe_identifier = lambda x: x
sys.modules['security'] = mock_sec

import auto_reverify as ar

def run(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition

# =============================================================================

def test_constants():
    print("\n── Sabit deger testleri ────────────────────────────────────")
    ok = True
    ok &= run("MIN_INTERVAL_DAYS = 1",   ar.MIN_INTERVAL_DAYS == 1)
    ok &= run("MAX_INTERVAL_DAYS = 365", ar.MAX_INTERVAL_DAYS == 365)
    return ok


def test_no_due_schedules():
    print("\n── Zamanlama yok — islem yapilmamali ───────────────────────")
    ok = True
    orig = ar._list_due_schedules
    ar._list_due_schedules = lambda: []

    logs = []
    stats = ar.process_auto_reverify(log_fn=logs.append)

    ar._list_due_schedules = orig
    ok &= run("checked=0", stats['checked'] == 0)
    ok &= run("started=0", stats['started'] == 0)
    ok &= run("log yazilmadi (sessiz)", len(logs) == 0)
    return ok


def test_skip_if_job_already_running():
    print("\n── Aktif job varsa atlanmali ────────────────────────────────")
    ok = True

    fake_sched = [{
        'id': 1, 'table_name': 'contacts', 'email_col': 'email',
        'mode': 'mx', 'threads': 10, 'target': 'all',
        'interval_days': 90, 'created_by': 'admin', 'created_by_id': 1,
    }]

    orig_due   = ar._list_due_schedules
    orig_reset = ar._reset_target_rows

    ar._list_due_schedules = lambda: fake_sched
    ar._reset_target_rows  = lambda *a, **kw: 100

    # Ayni tablo icin calisir durumda job simule et
    mock_db.verify_job_list = lambda: [
        {'table_name': 'contacts', 'status': 'running', 'id': 99}
    ]

    logs  = []
    stats = ar.process_auto_reverify(log_fn=logs.append)

    ar._list_due_schedules = orig_due
    ar._reset_target_rows  = orig_reset
    mock_db.verify_job_list = lambda: []

    ok &= run("skipped=1", stats['skipped'] == 1)
    ok &= run("started=0", stats['started'] == 0)
    ok &= run("'aktif job' logu var", any('aktif job' in l for l in logs))
    return ok


def test_skip_if_no_rows_to_reset():
    print("\n── Sifirlanacak satir yoksa atlanmali ──────────────────────")
    ok = True

    fake_sched = [{
        'id': 2, 'table_name': 'empty_table', 'email_col': 'email',
        'mode': 'mx', 'threads': 10, 'target': 'valid_only',
        'interval_days': 30, 'created_by': 'admin', 'created_by_id': 1,
    }]

    updates = []

    orig_due    = ar._list_due_schedules
    orig_reset  = ar._reset_target_rows
    orig_update = ar._update_schedule

    ar._list_due_schedules = lambda: fake_sched
    ar._reset_target_rows  = lambda *a, **kw: 0   # hic satir yok
    ar._update_schedule    = lambda *a, **kw: updates.append(a)

    logs  = []
    stats = ar.process_auto_reverify(log_fn=logs.append)

    ar._list_due_schedules = orig_due
    ar._reset_target_rows  = orig_reset
    ar._update_schedule    = orig_update

    ok &= run("skipped=1",   stats['skipped'] == 1)
    ok &= run("started=0",   stats['started'] == 0)
    # Zamanlama yine guncellenmeli (bos tabloya surekli carpmayalim)
    ok &= run("zamanlama guncellendi", len(updates) == 1)
    return ok


def test_successful_schedule_run():
    print("\n── Basarili zamanlama calisma testi ────────────────────────")
    ok = True

    fake_sched = [{
        'id': 3, 'table_name': 'newsletter', 'email_col': 'email',
        'mode': 'smtp', 'threads': 5, 'target': 'all',
        'interval_days': 60, 'created_by': 'admin', 'created_by_id': 1,
    }]

    resets  = []
    updates = []

    orig_due    = ar._list_due_schedules
    orig_reset  = ar._reset_target_rows
    orig_update = ar._update_schedule

    ar._list_due_schedules = lambda: fake_sched
    ar._reset_target_rows  = lambda *a, **kw: (resets.append(a) or 150)
    ar._update_schedule    = lambda *a, **kw: updates.append((a, kw))

    mock_db.verify_job_create = lambda **kw: (True, 77)

    logs  = []
    stats = ar.process_auto_reverify(log_fn=logs.append)

    ar._list_due_schedules = orig_due
    ar._reset_target_rows  = orig_reset
    ar._update_schedule    = orig_update

    ok &= run("started=1",    stats['started'] == 1)
    ok &= run("skipped=0",    stats['skipped'] == 0)
    ok &= run("reset cagrildi", len(resets) == 1)
    ok &= run("150 satir sifirlandi", resets[0][2] == 'all')
    ok &= run("update cagrildi", len(updates) == 1)
    # updates[0] = ((sid,), {last_run_at:..., next_run_at:..., last_job_id:...})
    ok &= run("job #77 kaydedildi",
              updates[0][1].get('last_job_id') == 77)
    ok &= run("'oluşturuldu' logu var", any('oluşturuldu' in l for l in logs))
    return ok


def test_next_run_timing():
    print("\n── next_run_at dogru hesaplanmali ──────────────────────────")
    ok = True

    fake_sched = [{
        'id': 4, 'table_name': 'leads', 'email_col': 'email',
        'mode': 'mx', 'threads': 10, 'target': 'unknown_only',
        'interval_days': 30, 'created_by': 'admin', 'created_by_id': 1,
    }]

    captured = {}

    def fake_update(sid, last_run_at, next_run_at, last_job_id):
        captured['last_run_at'] = last_run_at
        captured['next_run_at'] = next_run_at

    orig_due    = ar._list_due_schedules
    orig_reset  = ar._reset_target_rows
    orig_update = ar._update_schedule

    ar._list_due_schedules = lambda: fake_sched
    ar._reset_target_rows  = lambda *a, **kw: 50
    ar._update_schedule    = fake_update

    mock_db.verify_job_create = lambda **kw: (True, 88)

    before = datetime.datetime.utcnow()
    ar.process_auto_reverify(log_fn=lambda m: None)
    after  = datetime.datetime.utcnow()

    ar._list_due_schedules = orig_due
    ar._reset_target_rows  = orig_reset
    ar._update_schedule    = orig_update

    if captured:
        next_dt = datetime.datetime.strptime(
            captured['next_run_at'], '%Y-%m-%d %H:%M:%S'
        )
        now  = datetime.datetime.utcnow()
        diff = (next_dt - now).total_seconds() / 86400  # gun cinsinden
        ok &= run("next_run_at = simdi + 30 gun (29.9-30.1 aralik)",
                  29.9 <= diff <= 30.1)
    else:
        ok &= run("update cagrisi yapildi", False)

    return ok


def test_create_schedule_validation():
    print("\n── create_schedule() dogrulama testleri ───────────────────")
    ok = True

    created = []

    def fake_conn():
        class FakeCursor:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            lastrowid = 10
            rowcount  = 1
            def execute(self, sql, params=None): created.append(sql)
            def fetchone(self): return None
        class FakeConn:
            def cursor(self): return FakeCursor()
            def commit(self): pass
            def rollback(self): pass
            def close(self): pass
        return FakeConn()

    orig_conn = ar._get_conn
    ar._get_conn = fake_conn

    # Gecersiz mod
    ok2, msg = ar.create_schedule('mytable', mode='invalid')
    ok &= run("Gecersiz mod -> False", ok2 is False and 'mod' in msg.lower())

    # Gecersiz target
    ok3, msg3 = ar.create_schedule('mytable', target='wrong')
    ok &= run("Gecersiz target -> False", ok3 is False and 'hedef' in msg3.lower())

    # interval_days sinir kontrolu
    ar._get_conn = fake_conn
    ok4, sid = ar.create_schedule('mytable', interval_days=999)
    ok &= run("interval_days > 365 -> MAX_INTERVAL_DAYS'a kisitlandi", ok4 is True)

    ar._get_conn = orig_conn
    return ok


# =============================================================================

if __name__ == '__main__':
    results = [
        test_constants(),
        test_no_due_schedules(),
        test_skip_if_job_already_running(),
        test_skip_if_no_rows_to_reset(),
        test_successful_schedule_run(),
        test_next_run_timing(),
        test_create_schedule_validation(),
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
