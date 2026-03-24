"""
setup_full.py — MailSender Pro | Gelişmiş kurulum scripti
"""
import os
import sys
import subprocess
import pathlib

ENV_PATH  = pathlib.Path(".env")
VENV_PATH = pathlib.Path("venv")

# ─── Renk yardımcıları ────────────────────────────────────────────────
def ok(msg):   print(f"  ✅ {msg}")
def err(msg):  print(f"  ❌ {msg}")
def info(msg): print(f"  ℹ  {msg}")
def step(msg): print(f"\n{'─'*50}\n  {msg}\n{'─'*50}")

# ─── 1. Python sürüm kontrolü ─────────────────────────────────────────
step("1. Python Sürüm Kontrolü")
if sys.version_info < (3, 9):
    err(f"Python 3.9+ gerekli. Mevcut: {sys.version}")
    sys.exit(1)
ok(f"Python {sys.version.split()[0]}")

# ─── 2. Sanal ortam ──────────────────────────────────────────────────
step("2. Sanal Ortam")
if not VENV_PATH.exists():
    info("Sanal ortam oluşturuluyor...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_PATH)], check=True)
    ok("Sanal ortam oluşturuldu.")
else:
    ok("Sanal ortam zaten mevcut.")

if os.name == "nt":
    pip_exec = VENV_PATH / "Scripts" / "pip.exe"
    activate = str(VENV_PATH / "Scripts" / "activate.bat")
else:
    pip_exec = VENV_PATH / "bin" / "pip"
    activate = f"source {VENV_PATH}/bin/activate"

# Windows path ayracını düzelt
pip_cmd = str(pip_exec).replace("/", os.sep)

if not pip_exec.exists():
    err("pip bulunamadı! Sanal ortam bozuk olabilir, 'venv' klasörünü silip tekrar deneyin.")
    sys.exit(1)

# ─── 3. pip ve paketleri güncelle ────────────────────────────────────
step("3. Paketler Yükleniyor")
if not pathlib.Path("requirements.txt").exists():
    err("requirements.txt bulunamadı!")
    sys.exit(1)

info("pip güncelleniyor...")
subprocess.run([pip_cmd, "install", "--upgrade", "pip", "--quiet"])

info("Gereksinimler yükleniyor...")
result = subprocess.run(
    [pip_cmd, "install", "-r", "requirements.txt", "--quiet"],
    capture_output=True, text=True
)
if result.returncode != 0:
    err(f"Paket yükleme hatası:\n{result.stderr}")
    sys.exit(1)
ok("Tüm paketler yüklendi.")

# ─── 4. .env dosyası ─────────────────────────────────────────────────
step("4. .env Yapılandırması")

from dotenv import set_key, load_dotenv
from cryptography.fernet import Fernet

ENV_PATH.touch(exist_ok=True)
load_dotenv(ENV_PATH)

def set_if_empty(key, value):
    if not os.getenv(key, "").strip():
        set_key(str(ENV_PATH), key, value)
        info(f"{key} varsayılan değerle ayarlandı.")
    else:
        ok(f"{key} mevcut, korundu.")

# DB bilgileri — .env'den oku, eksik olanları kullanıcıdan iste
db_keys     = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
db_defaults = {"DB_HOST": "localhost", "DB_PORT": "3306", "DB_USER": "root",
               "DB_PASSWORD": "", "DB_NAME": "mailsender_pro"}

missing = [k for k in db_keys if not os.getenv(k, "").strip() and k != "DB_PASSWORD"]

if missing:
    info(f".env dosyasında şu DB alanları eksik: {', '.join(missing)}")
    info("Lütfen değerleri girin (boş bırakırsanız varsayılan kullanılır):")
    for k in db_keys:
        current = os.getenv(k, "").strip()
        if current:
            ok(f"{k} = {current if k != 'DB_PASSWORD' else '***'}")
        else:
            default = db_defaults.get(k, "")
            try:
                if k == "DB_PASSWORD":
                    import getpass
                    val = getpass.getpass(f"  {k} (boş bırakılabilir): ").strip()
                else:
                    val = input(f"  {k} [{default}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                val = ""
            final = val if val else default
            set_key(str(ENV_PATH), k, final)
            ok(f"{k} = {final if k != 'DB_PASSWORD' else '***'}")
else:
    for k in db_keys:
        v = os.getenv(k, "")
        ok(f"{k} = {v if k != 'DB_PASSWORD' else '***'}")

# SECRET_KEY — geçerli Fernet key yoksa yeni üret
existing_key = os.getenv("SECRET_KEY", "").strip()
key_valid = False
if existing_key:
    try:
        Fernet(existing_key.encode())
        key_valid = True
        ok("SECRET_KEY mevcut ve geçerli, korundu.")
    except Exception:
        err(f"SECRET_KEY geçersiz format (uzunluk: {len(existing_key)}). Yeni key üretiliyor...")

if not key_valid:
    new_key = Fernet.generate_key().decode()
    set_key(str(ENV_PATH), "SECRET_KEY", new_key)
    ok("Yeni SECRET_KEY üretildi ve .env'e kaydedildi.")
    info("⚠️  Mevcut şifreli DB kayıtları varsa yeni key ile uyumsuz olabilir!")

# AWS alanları — boş bırak, kullanıcı uygulama içinden dolduracak
set_if_empty("AWS_ACCESS_KEY_ID",     "")
set_if_empty("AWS_SECRET_ACCESS_KEY", "")
set_if_empty("AWS_REGION",            "us-east-1")

# ─── 5. Veritabanı bağlantısı ve tablo oluşturma ─────────────────────
step("5. Veritabanı Kurulumu")

load_dotenv(ENV_PATH, override=True)

try:
    import database
except ImportError as e:
    err(f"database.py import hatası: {e}")
    sys.exit(1)

ok_conn, msg_conn = database.test_connection()
if not ok_conn:
    err(f"DB bağlantısı kurulamadı: {msg_conn}")
    info("Lütfen .env dosyasındaki DB_HOST, DB_USER, DB_PASSWORD, DB_NAME değerlerini kontrol edin.")
    info("Düzelttikten sonra setup_full.py'yi tekrar çalıştırın.")
    sys.exit(1)
ok("Veritabanı bağlantısı başarılı.")

ok_db, msg_db = database.init_db()
if ok_db:
    ok(f"Tablolar hazır: {msg_db}")
else:
    err(f"Tablo oluşturma hatası: {msg_db}")

# ─── 6. Migration kontrolü ───────────────────────────────────────────
step("6. Migration Kontrolü (Mevcut DB)")

try:
    conn = database.get_connection()
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM senders LIKE 'sender_mode'")
        if not cur.fetchone():
            info("Eski senders tablosu tespit edildi. Migration uygulanıyor...")
            migrations = [
                "ALTER TABLE senders MODIFY COLUMN smtp_server VARCHAR(200) NULL",
                "ALTER TABLE senders MODIFY COLUMN username VARCHAR(200) NULL",
                "ALTER TABLE senders MODIFY COLUMN password VARCHAR(500) NULL",
                "ALTER TABLE senders ADD COLUMN IF NOT EXISTS sender_mode ENUM('smtp','ses') NOT NULL DEFAULT 'smtp' AFTER email",
                "ALTER TABLE senders ADD COLUMN IF NOT EXISTS aws_access_key VARCHAR(500) NULL AFTER use_ssl",
                "ALTER TABLE senders ADD COLUMN IF NOT EXISTS aws_secret_key VARCHAR(500) NULL AFTER aws_access_key",
                "ALTER TABLE senders ADD COLUMN IF NOT EXISTS aws_region VARCHAR(50) DEFAULT 'us-east-1' AFTER aws_secret_key",
            ]
            for sql in migrations:
                try:
                    cur.execute(sql)
                    ok(f"Migration uygulandı: {sql[:55]}...")
                except Exception as e:
                    info(f"Atlandı (zaten mevcut olabilir): {e}")
            conn.commit()
            ok("Migration tamamlandı.")
        else:
            ok("Tablo şeması güncel, migration gerekmedi.")
    conn.close()
except Exception as e:
    info(f"Migration kontrolü atlandı: {e}")

# ─── 7. Kurulum özeti ─────────────────────────────────────────────────
step("7. Kurulum Tamamlandı 🎉")
print(f"""
  Uygulamayı başlatmak için:

    {activate}
    python app.py

  Tarayıcıda açın: http://localhost:5000

  ⚠️  AWS SES kullanmak istiyorsanız:
     Uygulama içinde Göndericiler → Yeni Gönderici → AWS SES modunu seçin.
     Access Key ve Secret Key'i oradan girin (Fernet şifreli DB'ye kaydedilir).
     AWS policy'nizde şu yetkiler olmalı:
       - ses:SendEmail
       - ses:SendRawEmail
       - ses:GetIdentityVerificationAttributes
""")
