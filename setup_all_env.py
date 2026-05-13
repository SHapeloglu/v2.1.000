#!/usr/bin/env python3
"""
setup_all_env.py — MailSender Pro v2.1.0 Hızlı Kurulum
========================================================
Bu script asgari kurulum için gerekenleri otomatik yapar:
  1. Python paketlerini yükler (requirements.txt)
  2. .env dosyasını oluşturur (eğer yoksa)
  3. SECRET_KEY üretir
  4. Veritabanına bağlantıyı test eder
  5. Tabloları oluşturur / migrate eder (init_db + migrate_db)
  6. Admin kullanıcısını oluşturur (eğer yoksa)

Windows, macOS ve Linux ortamlarında çalışır.

Kullanım:
    python3 setup_all_env.py

Linux sunucuda Nginx, systemd, SSL ve güvenlik adımları için:
    python3 setup_linux.py
"""

import os
import sys
import subprocess
import secrets
import pathlib
import getpass

# ── Renkli çıktı ─────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"{GREEN}✔{RESET}  {msg}")
def warn(msg):  print(f"{YELLOW}⚠{RESET}  {msg}")
def err(msg):   print(f"{RED}✘{RESET}  {msg}")
def info(msg):  print(f"{CYAN}→{RESET}  {msg}")
def title(msg): print(f"\n{BOLD}{CYAN}{msg}{RESET}")

BASE_DIR = pathlib.Path(__file__).parent.resolve()
ENV_PATH = BASE_DIR / ".env"
REQ_PATH = BASE_DIR / "requirements.txt"

# ── Adım 1: Python sürümü kontrolü ──────────────────────────────────
title("Adım 1/6 — Python Sürümü Kontrolü")
major, minor = sys.version_info[:2]
if major < 3 or (major == 3 and minor < 10):
    err(f"Python 3.10+ gereklidir. Mevcut sürüm: {major}.{minor}")
    sys.exit(1)
ok(f"Python {major}.{minor} — uyumlu")

# ── Adım 2: Paket kurulumu ───────────────────────────────────────────
title("Adım 2/6 — Python Paketleri")
if not REQ_PATH.exists():
    err(f"requirements.txt bulunamadı: {REQ_PATH}")
    sys.exit(1)

info("pip install -r requirements.txt çalıştırılıyor...")
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", str(REQ_PATH), "--quiet"],
    capture_output=True, text=True
)
if result.returncode != 0:
    err("Paket kurulumu başarısız:")
    print(result.stderr)
    sys.exit(1)
ok("Tüm paketler yüklendi")

# ── Adım 3: .env dosyası ─────────────────────────────────────────────
title("Adım 3/6 — .env Yapılandırması")

if ENV_PATH.exists():
    warn(".env dosyası zaten mevcut — atlanıyor")
    warn("Mevcut .env dosyasını korumak için hiçbir değişiklik yapılmadı")
else:
    info("Yeni .env dosyası oluşturuluyor...")

    # SECRET_KEY üret
    try:
        from cryptography.fernet import Fernet
        secret_key = Fernet.generate_key().decode()
    except ImportError:
        secret_key = secrets.token_urlsafe(32)
        warn("cryptography paketi bulunamadı — token_urlsafe ile yedek key üretildi")

    print()
    print(f"  {BOLD}Veritabanı Bağlantısı{RESET}")
    db_host     = input("  DB Host     [127.0.0.1]: ").strip() or "127.0.0.1"
    db_port     = input("  DB Port     [3306]: ").strip() or "3306"
    db_user     = input("  DB User     [mailsender_user]: ").strip() or "mailsender_user"
    db_password = getpass.getpass("  DB Password : ")
    db_name     = input("  DB Name     [mailsender]: ").strip() or "mailsender"
    db_ssl      = input("  DB SSL      [false]: ").strip().lower() or "false"
    print()
    print(f"  {BOLD}Uygulama Ayarları{RESET}")
    app_url     = input("  APP_BASE_URL [http://localhost:5000]: ").strip() or "http://localhost:5000"
    force_https = input("  FORCE_HTTPS  [false]: ").strip().lower() or "false"

    env_content = f"""# ─────────────────────────────────────────────────────────────
#  MailSender Pro v2.1.0 — Ortam Değişkenleri
#  setup.py tarafından otomatik oluşturuldu.
# ─────────────────────────────────────────────────────────────

# ── Veritabanı ────────────────────────────────────────────────
DB_HOST={db_host}
DB_PORT={db_port}
DB_USER={db_user}
DB_PASSWORD={db_password}
DB_NAME={db_name}
DB_SSL={db_ssl}

# ── Şifreleme ─────────────────────────────────────────────────
# Fernet key — DB'deki SMTP/AWS şifrelerini şifrelemek için
# ÖNEMLİ: Kaybedeseniz DB'deki tüm şifreler okunamaz olur!
SECRET_KEY={secret_key}

# ── Uygulama ──────────────────────────────────────────────────
APP_BASE_URL={app_url}
FORCE_HTTPS={force_https}

# ── (Opsiyonel) Uygulama Erişim Şifresi ──────────────────────
# Tüm uygulamayı tek şifreyle korumak için:
# APP_ACCESS_PASSWORD=
"""
    ENV_PATH.write_text(env_content, encoding="utf-8")
    ok(f".env dosyası oluşturuldu: {ENV_PATH}")
    warn(f"SECRET_KEY'i yedekleyin: {secret_key}")

# ── Adım 4: DB bağlantı testi ────────────────────────────────────────
title("Adım 4/6 — Veritabanı Bağlantı Testi")
sys.path.insert(0, str(BASE_DIR))
from dotenv import load_dotenv
load_dotenv(ENV_PATH)

try:
    from database import test_connection
    test_connection()
    ok("Veritabanına bağlantı başarılı")
except Exception as e:
    err(f"Veritabanı bağlantısı başarısız: {e}")
    err("DB_HOST, DB_USER, DB_PASSWORD, DB_NAME değerlerini kontrol edin")
    sys.exit(1)

# ── Adım 5: Tablo oluşturma ve migrasyon ─────────────────────────────
title("Adım 5/6 — Veritabanı Şeması (init + migrate)")
try:
    from database import init_db, migrate_db
    init_db()
    ok("Tablolar oluşturuldu (init_db)")
    migrate_db()
    ok("Migrasyon tamamlandı (migrate_db)")
except Exception as e:
    err(f"DB kurulum hatası: {e}")
    sys.exit(1)

# ── Adım 6: Admin kullanıcı ──────────────────────────────────────────
title("Adım 6/6 — Admin Kullanıcı")
try:
    from database import user_count, user_create
    count = user_count()
    if count > 0:
        warn(f"Sistemde zaten {count} kullanıcı mevcut — admin oluşturma atlandı")
    else:
        info("İlk admin kullanıcısı oluşturuluyor...")
        print()
        admin_user  = input("  Kullanıcı adı [admin]: ").strip() or "admin"
        admin_email = input("  E-posta       [admin@localhost]: ").strip() or "admin@localhost"
        while True:
            admin_pw  = getpass.getpass("  Şifre (en az 8 karakter): ")
            admin_pw2 = getpass.getpass("  Şifre tekrar             : ")
            if admin_pw != admin_pw2:
                warn("Şifreler eşleşmiyor, tekrar deneyin")
            elif len(admin_pw) < 8:
                warn("Şifre en az 8 karakter olmalı")
            else:
                break
        user_create(admin_user, admin_pw, admin_email, role="admin")
        ok(f"Admin kullanıcısı oluşturuldu: {admin_user}")
except Exception as e:
    err(f"Kullanıcı oluşturma hatası: {e}")
    sys.exit(1)

# ── Kurulum tamamlandı ───────────────────────────────────────────────
print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════╗
║      MailSender Pro v2.1.0 — Kurulum OK      ║
╚══════════════════════════════════════════════╝{RESET}

  Uygulamayı başlatmak için:
    {CYAN}python3 app.py{RESET}

  Varsayılan adres:
    {CYAN}http://127.0.0.1:5000{RESET}

  Worker (hosting/kuyruk modu için):
    {CYAN}python3 worker.py{RESET}

  Nginx + HTTPS kurulumu için:
    {CYAN}python3 setup_linux.py{RESET}
    ya da GUVENLIK_KILAVUZU.md dosyasını inceleyin
""")
