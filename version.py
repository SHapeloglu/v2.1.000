"""
version.py — MailSender Pro Versiyon Bilgisi
=============================================
Tek kaynak: tüm versiyon referansları buradan okunur.

Kullanım:
    from version import VERSION, VERSION_FULL
    print(VERSION_FULL)  # "MailSender Pro v2.1.0"

Semantic Versioning (semver.org):
    MAJOR.MINOR.PATCH
    MAJOR: Geriye dönük uyumsuz değişiklik (DB şema kırılması, API değişikliği)
    MINOR: Geriye dönük uyumlu yeni özellik (yeni endpoint, yeni tablo kolonu)
    PATCH: Hata düzeltmesi, açıklama, küçük iyileştirme
"""

VERSION_MAJOR = 2
VERSION_MINOR = 1
VERSION_PATCH = 0

VERSION       = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
VERSION_FULL  = f"MailSender Pro v{VERSION}"
VERSION_SHORT = f"v{VERSION}"
