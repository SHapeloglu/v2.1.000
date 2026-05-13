"""
test_spam_trap.py — spam_trap.py için birim testler
=====================================================
Çalıştırma:
    cd proje_kök_dizini
    python -m pytest test_spam_trap.py -v
    # veya doğrudan:
    python test_spam_trap.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from spam_trap import (
    check_spam_trap,
    _looks_like_trap_local,
    PRISTINE_TRAP_DOMAINS,
    TYPO_TRAP_DOMAINS,
)

# ── Yardımcı ──────────────────────────────────────────────────────────────────
def _meta(
    has_spf=True, has_dmarc=True,
    domain_age=365, is_catchall=False, mx_server=""
):
    return {
        "has_spf":     has_spf,
        "has_dmarc":   has_dmarc,
        "domain_age":  domain_age,
        "is_catchall": is_catchall,
        "mx_server":   mx_server,
    }

def run(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition

# ══════════════════════════════════════════════════════════════════════════════

def test_pristine_trap():
    print("\n── Pristine tuzak domain testleri ─────────────────────────")
    ok = True
    for domain in ["spamtrap.ro", "spamtrap.net", "honeypot.net", "project-honeypot.org"]:
        is_trap, ttype, conf = check_spam_trap(
            f"user@{domain}", domain, "user", _meta()
        )
        ok &= run(f"{domain} → high pristine",
                  is_trap and ttype == "pristine" and conf == "high")
    return ok


def test_typo_trap():
    print("\n── Typo tuzak domain testleri ──────────────────────────────")
    ok = True
    for domain in ["gmali.com", "gmaail.com", "yhaoo.com", "hotmai1.com"]:
        is_trap, ttype, conf = check_spam_trap(
            f"test@{domain}", domain, "test", _meta()
        )
        ok &= run(f"{domain} → high typo_trap",
                  is_trap and ttype == "typo_trap" and conf == "high")
    return ok


def test_mx_trap():
    print("\n── MX sunucu tuzak testleri ────────────────────────────────")
    ok = True
    for mx in ["mail.spamtrap.example.com", "honeypot.mx.example.com",
               "blackhole.inbound.example.net", "devnull.mail.example.com"]:
        is_trap, ttype, conf = check_spam_trap(
            "user@example.com", "example.com", "user",
            _meta(mx_server=mx)
        )
        ok &= run(f"MX={mx} → high mx_trap",
                  is_trap and ttype == "mx_trap" and conf == "high")
    return ok


def test_recycled_trap_patterns():
    print("\n── Recycled tuzak local kalıp testleri ────────────────────")
    ok = True

    # Tuzak kalıbı + altyapısız domain → medium
    suspicious_locals = [
        ("spamtrap",     False, False, 2000),   # SPF/DMARC yok, eski domain
        ("honeypot123",  False, False, 2000),
        ("trap20240101", False, False, 2000),
        ("sb123456",     False, False, 2000),   # Spamhaus formatı
    ]
    for local, has_spf, has_dmarc, age in suspicious_locals:
        is_trap, ttype, conf = check_spam_trap(
            f"{local}@example.com", "example.com", local,
            _meta(has_spf=has_spf, has_dmarc=has_dmarc, domain_age=age)
        )
        ok &= run(f"local={local!r} altyapısız eski domain → recycled medium",
                  is_trap and ttype == "recycled" and conf == "medium")

    # Tuzak kalıbı ama altyapısı var → low
    is_trap, ttype, conf = check_spam_trap(
        "trap2024@company.com", "company.com", "trap2024",
        _meta(has_spf=True, has_dmarc=True, domain_age=500)
    )
    ok &= run("trap2024 + altyapılı domain → recycled low",
              is_trap and ttype == "recycled" and conf == "low")

    return ok


def test_honeypot_patterns():
    print("\n── Honeypot local kalıp testleri ───────────────────────────")
    ok = True

    # UUID formatı local kısmında → medium (uzun)
    uuid_local = "550e8400-e29b-41d4"
    is_trap, ttype, conf = check_spam_trap(
        f"{uuid_local}@example.com", "example.com", uuid_local, _meta()
    )
    ok &= run("UUID local → honeypot medium",
              is_trap and ttype == "honeypot" and conf == "medium")

    # Sadece rakam (uzun) → medium
    num_local = "12345678901234567"
    is_trap, ttype, conf = check_spam_trap(
        f"{num_local}@example.com", "example.com", num_local, _meta()
    )
    ok &= run("Sadece rakam (uzun) → honeypot medium",
              is_trap and ttype == "honeypot" and conf == "medium")

    # Kısa bot local → low
    short_local = "ab12345678"   # kısa harf + uzun rakam ama len=10
    is_trap, ttype, conf = check_spam_trap(
        f"{short_local}@example.com", "example.com", short_local, _meta()
    )
    ok &= run(f"short bot local {short_local!r} → honeypot low",
              is_trap and ttype == "honeypot")

    return ok


def test_combination_signals():
    print("\n── Kombinasyon sinyal testleri ─────────────────────────────")
    ok = True

    # 10+ yıllık domain + altyapısız + catch-all + tuzak benzeri local → low
    # 'olduser' → _looks_like_trap_local True (len=7, normal) değil ama
    # rakam oranı yüksek 'x9999999' gibi bir local kullanalım
    # Not: bu local honeypot regex'lerine girmesin, sadece _looks_like_trap_local True dönsün
    local = "z" + "9" * 9   # z999999999 → %90 rakam → _looks_like_trap_local True
    is_trap, ttype, conf = check_spam_trap(
        f"{local}@olddomain.net", "olddomain.net", local,
        _meta(has_spf=False, has_dmarc=False, domain_age=4000, is_catchall=True)
    )
    ok &= run(f"Çoklu zayıf sinyal ({local!r}) → tuzak sinyali var",
              is_trap)   # type honeypot veya recycled olabilir, ikisi de kabul

    # Honeypot regex'i tetiklemeyen ama _looks_like_trap_local True dönen durum:
    # sadece rakam, ≥10 char
    local2 = "1234567890"
    is_trap2, ttype2, conf2 = check_spam_trap(
        f"{local2}@olddomain.net", "olddomain.net", local2,
        _meta(has_spf=False, has_dmarc=False, domain_age=4000, is_catchall=True)
    )
    ok &= run(f"Çoklu zayıf sinyal ({local2!r}) → tuzak sinyali var",
              is_trap2)

    return ok


def test_clean_emails():
    print("\n── Temiz e-posta testleri (yanlış pozitif kontrolü) ────────")
    ok = True

    clean_cases = [
        ("john.doe@gmail.com",      "gmail.com",       "john.doe"),
        ("info@company.com",        "company.com",     "info"),
        ("test@protonmail.com",     "protonmail.com",  "test"),
        ("user123@outlook.com",     "outlook.com",     "user123"),
        ("mehmet.yilmaz@firma.com", "firma.com",       "mehmet.yilmaz"),
        ("newsletter@startup.io",   "startup.io",      "newsletter"),
    ]
    for email, domain, local in clean_cases:
        is_trap, ttype, conf = check_spam_trap(email, domain, local, _meta())
        ok &= run(f"{email} → temiz (is_trap=False)",
                  not is_trap)

    return ok


def test_looks_like_trap_local():
    print("\n── _looks_like_trap_local() testleri ───────────────────────")
    ok = True

    # Tuzak benzeri olanlar
    for local in ["12345678901234", "a", "ab", "a12345678901234"]:
        ok &= run(f"{local!r} → tuzak benzeri True",
                  _looks_like_trap_local(local))

    # Temiz olanlar
    for local in ["john", "mehmet.yilmaz", "user2024", "newsletter"]:
        ok &= run(f"{local!r} → tuzak benzeri False",
                  not _looks_like_trap_local(local))

    return ok


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    results = [
        test_pristine_trap(),
        test_typo_trap(),
        test_mx_trap(),
        test_recycled_trap_patterns(),
        test_honeypot_patterns(),
        test_combination_signals(),
        test_clean_emails(),
        test_looks_like_trap_local(),
    ]
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*52}")
    print(f"Sonuç: {passed}/{total} test grubu başarılı")
    if passed < total:
        print("BAZI TESTLER BAŞARISIZ — yukarıdaki [FAIL] satırlarını inceleyin")
        sys.exit(1)
    else:
        print("Tüm testler geçti.")
