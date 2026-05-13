"""
test_did_you_mean.py — suggest_domain() ve did_you_mean entegrasyonu testleri
==============================================================================
Calistirma:
    cd v2.1.00/
    python test_did_you_mean.py
"""
import sys, os, types
sys.path.insert(0, os.path.dirname(__file__))

# ── Minimal mock'lar (DB olmadan calistirmak icin) ─────────────────────────
mock_db = types.ModuleType('database')
mock_db.get_connection    = lambda: None
mock_db.get_db_config     = lambda: {'database': 'test'}
mock_db.smtp_skip_domains_get = lambda: []
sys.modules.setdefault('database', mock_db)

mock_sec = types.ModuleType('security')
mock_sec.safe_identifier = lambda x: x
sys.modules.setdefault('security', mock_sec)

mock_whois = types.ModuleType('whois')
sys.modules.setdefault('whois', mock_whois)

from verifier import suggest_domain, verify_one

def run(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition

# =============================================================================

def test_typo_map_hits():
    """TYPO_MAP'teki bilinen hatalar aninda oneri uretmeli."""
    print("\n── TYPO_MAP kesin eslesmeler ───────────────────────────────")
    ok = True
    cases = [
        ("gmial.com",   "gmail.com"),
        ("gmai.com",    "gmail.com"),
        ("yahooo.com",  "yahoo.com"),
        ("hotmial.com", "hotmail.com"),
        ("outlok.com",  "outlook.com"),
        ("iclooud.com", "icloud.com"),
        ("gmail.com.tr","gmail.com"),
        ("gmail.con",   "gmail.com"),
    ]
    for wrong, expected in cases:
        result = suggest_domain(wrong)
        ok &= run(f"{wrong} -> {expected}", result == expected)
    return ok


def test_levenshtein_suggestions():
    """TYPO_MAP'te olmayan ama yakın domain'lere oneri uretmeli."""
    print("\n── Levenshtein fuzzy oneri ─────────────────────────────────")
    ok = True
    cases = [
        ("gmaill.co",   "gmail.com"),    # mesafe 2
        ("hotmaill.co", "hotmail.com"),  # mesafe 2
        ("outlookk.com","outlook.com"),  # mesafe 1
        ("protonmeil.com","protonmail.com"),  # mesafe 1
        ("yandex.ruu",  "yandex.ru"),    # mesafe 1
    ]
    for wrong, expected in cases:
        result = suggest_domain(wrong)
        ok &= run(f"{wrong} -> {expected}", result == expected)
    return ok


def test_no_suggestion_for_valid():
    """Zaten gecerli FREE_PROVIDERS domainleri icin None donmeli."""
    print("\n── Gecerli domainler icin oneri yapilmamali ────────────────")
    ok = True
    for d in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
              "icloud.com", "protonmail.com", "yandex.ru"]:
        result = suggest_domain(d)
        ok &= run(f"{d} -> None", result is None)
    return ok


def test_no_suggestion_for_corporate():
    """Kurumsal / cok farkli domainler icin oneri yapilmamali."""
    print("\n── Kurumsal domainler icin oneri yapilmamali ───────────────")
    ok = True
    for d in ["company.com", "myworkplace.net", "acmecorp.io",
              "verylongcorporatedomain.org"]:
        result = suggest_domain(d)
        ok &= run(f"{d} -> None (kurumsal)", result is None)
    return ok


def test_did_you_mean_in_meta_format_mode():
    """verify_one() format modunda did_you_mean meta'ya yazilmali."""
    print("\n── verify_one() format modu did_you_mean testi ────────────")
    ok = True

    # Gmail yazim hatasi
    _, _, meta = verify_one("john@gmial.com", mode='format')
    ok &= run("gmial.com -> did_you_mean='john@gmail.com'",
              meta.get('did_you_mean') == "john@gmail.com")

    # Zaten dogru - did_you_mean olmamali
    _, _, meta2 = verify_one("john@gmail.com", mode='format')
    ok &= run("gmail.com -> did_you_mean=None",
              meta2.get('did_you_mean') is None)

    # Hotmail yazim hatasi
    _, _, meta3 = verify_one("ali@hotmial.com", mode='format')
    ok &= run("hotmial.com -> did_you_mean='ali@hotmail.com'",
              meta3.get('did_you_mean') == "ali@hotmail.com")

    return ok


def test_did_you_mean_with_plus_tag():
    """local+ tagli adreslerde did_you_mean dogru local'i korumal."""
    print("\n── +tag'li adreslerde did_you_mean ─────────────────────────")
    ok = True

    # Gmail +tag — normalize edildikten sonra did_you_mean olmamali (zaten duzgun)
    _, _, meta = verify_one("john+news@gmail.com", mode='format')
    ok &= run("+tag gmail -> did_you_mean=None",
              meta.get('did_you_mean') is None)

    return ok


def test_api_response_structure():
    """
    /api/verify/single endpoint'inin donecegi alanlari simule et.
    Gercek HTTP istegi yapilmaz — verify_one + calculate_risk_score cagrilir.
    """
    print("\n── API yanit yapisi testi ──────────────────────────────────")
    ok = True

    # risk_score mock
    mock_rs = types.ModuleType('risk_score')
    mock_rs.calculate_risk_score = lambda e, s, m, include_db=True: {
        'score': 90, 'label': 'safe', 'label_tr': 'Guvenli',
        'send_recommended': True, 'reasons': []
    }
    sys.modules['risk_score'] = mock_rs

    from verifier import STATUS_TO_IS_VALID

    email_input = "ali@gmial.com"
    final_email, status, meta = verify_one(email_input, mode='format')
    risk = mock_rs.calculate_risk_score(final_email, status, meta)

    response = {
        'email':         final_email,
        'original':      meta.get('original', email_input),
        'status':        status,
        'is_valid':      STATUS_TO_IS_VALID.get(status, -1),
        'did_you_mean':  meta.get('did_you_mean'),
        'is_role':       bool(meta.get('is_role')),
        'is_free':       bool(meta.get('is_free')),
        'risk_score':    risk['score'],
        'risk_label':    risk['label'],
    }

    ok &= run("original = 'ali@gmial.com'",
              response['original'] == 'ali@gmial.com')
    ok &= run("email = 'ali@gmail.com' (duzeltilmis)",
              response['email'] == 'ali@gmail.com')
    ok &= run("did_you_mean = 'ali@gmail.com'",
              response['did_you_mean'] == 'ali@gmail.com')
    ok &= run("status = 'typo_fixed'",
              response['status'] == 'typo_fixed')
    ok &= run("is_valid = 1",
              response['is_valid'] == 1)
    ok &= run("risk_score = 90",
              response['risk_score'] == 90)

    return ok


# =============================================================================

if __name__ == '__main__':
    results = [
        test_typo_map_hits(),
        test_levenshtein_suggestions(),
        test_no_suggestion_for_valid(),
        test_no_suggestion_for_corporate(),
        test_did_you_mean_in_meta_format_mode(),
        test_did_you_mean_with_plus_tag(),
        test_api_response_structure(),
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
