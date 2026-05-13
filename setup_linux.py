#!/usr/bin/env python3
"""
setup_linux.py — MailSender Pro v2.1.0 Tam Üretim Kurulumu (Linux)
====================================================================
Temel kuruluma ek olarak şunları yapar:
  1. setup_all_env.py adımlarını çalıştırır (paket, .env, DB, admin)
  2. systemd servis dosyası oluşturur (app.py + worker.py)
  3. Nginx reverse-proxy config yazar
  4. Güvenlik kontrol listesini doğrular
  5. Crontab (hosting/kuyruk modu) için talimat gösterir
  6. Firewall (ufw) kurallarını uygular

Yalnızca Linux (Ubuntu/Debian) sunucularda çalışır.
Windows/macOS için: python3 setup_all_env.py

Kullanım:
    sudo python3 setup_linux.py          # Nginx + systemd için sudo gerekli
    python3 setup_linux.py --skip-system # Sistem servislerini atla
"""

import os
import sys
import subprocess
import secrets
import pathlib
import getpass
import argparse
import textwrap
import shutil

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
def title(msg): print(f"\n{BOLD}{CYAN}{'─'*52}\n{msg}\n{'─'*52}{RESET}")
def section(msg): print(f"\n{BOLD}{msg}{RESET}")

BASE_DIR  = pathlib.Path(__file__).parent.resolve()
ENV_PATH  = BASE_DIR / ".env"
REQ_PATH  = BASE_DIR / "requirements.txt"
APP_USER  = os.environ.get("SUDO_USER") or os.environ.get("USER") or "ubuntu"
APP_PY    = sys.executable   # Bu Python yorumlayıcısının tam yolu

# ── Argümanlar ───────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="MailSender Pro tam kurulum")
parser.add_argument("--skip-system", action="store_true",
                    help="systemd ve Nginx adımlarını atla")
parser.add_argument("--skip-base", action="store_true",
                    help="Temel kurulum (setup.py) adımlarını atla")
args = parser.parse_args()

# ── Yardımcı: komutu çalıştır ────────────────────────────────────────
def run(cmd, check=True, capture=False):
    """Shell komutu çalıştırır. check=True ise hata fırlatır, capture=True ise çıktıyı döner."""
    return subprocess.run(
        cmd, shell=isinstance(cmd, str),
        capture_output=capture, text=True,
        check=check
    )

def cmd_ok(cmd):
    """Komutun sistemde var olup olmadığını kontrol et."""
    return shutil.which(cmd) is not None

# ════════════════════════════════════════════════════════════════════
# BÖLÜM A — Temel Kurulum (setup.py mantığı, yeniden kullanılır)
# ════════════════════════════════════════════════════════════════════

title("BÖLÜM A — Temel Kurulum")

# ── A1: Python sürümü ────────────────────────────────────────────────
section("A1 — Python Sürümü")
major, minor = sys.version_info[:2]
if major < 3 or (major == 3 and minor < 10):
    err(f"Python 3.10+ gereklidir. Mevcut: {major}.{minor}")
    sys.exit(1)
ok(f"Python {major}.{minor} uyumlu")

if not args.skip_base:
    # ── A2: Paket kurulumu ───────────────────────────────────────────
    section("A2 — Python Paketleri")
    if not REQ_PATH.exists():
        err(f"requirements.txt bulunamadı: {REQ_PATH}")
        sys.exit(1)
    info("pip install -r requirements.txt...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQ_PATH), "--quiet"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        err("Paket kurulumu başarısız:")
        print(result.stderr)
        sys.exit(1)
    ok("Paketler yüklendi")

    # ── A3: .env dosyası ─────────────────────────────────────────────
    section("A3 — .env Yapılandırması")
    if ENV_PATH.exists():
        warn(".env mevcut — atlanıyor")
    else:
        try:
            from cryptography.fernet import Fernet
            secret_key = Fernet.generate_key().decode()
        except ImportError:
            secret_key = secrets.token_urlsafe(32)

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
        domain      = input("  Domain adı  (örn: mail.sirketim.com): ").strip()
        app_url     = f"https://{domain}" if domain else "http://localhost:5002"
        force_https = "true" if domain else "false"

        env_content = f"""# ─────────────────────────────────────────────────────────────
#  MailSender Pro v2.1.0 — Ortam Değişkenleri
#  setup_full.py tarafından otomatik oluşturuldu.
# ─────────────────────────────────────────────────────────────

# ── Veritabanı ────────────────────────────────────────────────
DB_HOST={db_host}
DB_PORT={db_port}
DB_USER={db_user}
DB_PASSWORD={db_password}
DB_NAME={db_name}
DB_SSL={db_ssl}

# ── Şifreleme ─────────────────────────────────────────────────
SECRET_KEY={secret_key}

# ── Uygulama ──────────────────────────────────────────────────
APP_BASE_URL={app_url}
FORCE_HTTPS={force_https}
"""
        ENV_PATH.write_text(env_content, encoding="utf-8")
        ok(f".env oluşturuldu: {ENV_PATH}")
        warn(f"SECRET_KEY'i yedekleyin → {secret_key}")
        if domain:
            domain_for_nginx = domain
        else:
            domain_for_nginx = "localhost"

    # ── A4: DB bağlantı testi ────────────────────────────────────────
    section("A4 — DB Bağlantı Testi")
    sys.path.insert(0, str(BASE_DIR))
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)

    try:
        from database import test_connection
        test_connection()
        ok("DB bağlantısı başarılı")
    except Exception as e:
        err(f"DB bağlantısı başarısız: {e}")
        sys.exit(1)

    # ── A5: Şema + migrasyon ─────────────────────────────────────────
    section("A5 — Veritabanı Şeması")
    try:
        from database import init_db, migrate_db
        init_db()
        ok("Tablolar oluşturuldu (init_db)")
        migrate_db()
        ok("Migrasyon tamamlandı (migrate_db)")
    except Exception as e:
        err(f"DB şema hatası: {e}")
        sys.exit(1)

    # ── A6: Admin kullanıcı ──────────────────────────────────────────
    section("A6 — Admin Kullanıcı")
    try:
        from database import user_count, user_create
        if user_count() > 0:
            warn("Kullanıcı zaten mevcut — atlandı")
        else:
            print()
            admin_user  = input("  Kullanıcı adı [admin]: ").strip() or "admin"
            admin_email = input("  E-posta       [admin@localhost]: ").strip() or "admin@localhost"
            while True:
                pw1 = getpass.getpass("  Şifre (min 8 karakter): ")
                pw2 = getpass.getpass("  Şifre tekrar           : ")
                if pw1 != pw2:
                    warn("Şifreler eşleşmiyor")
                elif len(pw1) < 8:
                    warn("Şifre çok kısa")
                else:
                    break
            user_create(admin_user, pw1, admin_email, role="admin")
            ok(f"Admin oluşturuldu: {admin_user}")
    except Exception as e:
        err(f"Admin oluşturma hatası: {e}")
        sys.exit(1)

# ════════════════════════════════════════════════════════════════════
# BÖLÜM B — Sistem Servisleri (systemd + Nginx)
# ════════════════════════════════════════════════════════════════════

title("BÖLÜM B — Sistem Servisleri")

if args.skip_system:
    warn("--skip-system ile sistem servisleri atlandı")
else:
    # Windows'ta geteuid() yoktur; platform kontrolü yap
    is_windows = sys.platform == "win32"
    if is_windows:
        is_root = False
    else:
        is_root = (os.geteuid() == 0)

    if is_windows:
        warn("Windows tespit edildi — Nginx/systemd/UFW adımları atlanıyor.")
        warn("Bu adımlar yalnızca Linux (Ubuntu/Debian) sunucularda geçerlidir.")
        warn("Windows/macOS için: python3 setup_all_env.py")
    elif not is_root:
        warn("Nginx ve systemd kurulumu için sudo gerekli.")
        warn("Şu an root değilsiniz — sistem adımları atlanıyor.")
        warn("Sistem servislerini kurmak için: sudo python3 setup_linux.py")
    else:
        # .env'den domain'i oku
        from dotenv import dotenv_values
        env_vals = dotenv_values(ENV_PATH)
        app_base = env_vals.get("APP_BASE_URL", "http://localhost:5002")
        # domain'i URL'den çıkar
        domain_for_nginx = app_base.replace("https://", "").replace("http://", "").split("/")[0]
        if domain_for_nginx in ("localhost", "127.0.0.1", "localhost:5002"):
            domain_for_nginx = "_"  # Nginx catch-all

        # ── B1: Nginx kurulumu ───────────────────────────────────────
        section("B1 — Nginx")
        if not cmd_ok("nginx"):
            info("Nginx yükleniyor...")
            run("apt-get update -qq && apt-get install -y nginx", check=False)

        nginx_conf = f"""\
# MailSender Pro — Nginx Yapılandırması
# setup_full.py tarafından oluşturuldu

server {{
    listen 80;
    server_name {domain_for_nginx};

    # Let's Encrypt doğrulaması
    location /.well-known/acme-challenge/ {{
        root /var/www/html;
    }}

    # HTTP → HTTPS yönlendirme
    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl http2;
    server_name {domain_for_nginx};

    # SSL sertifikaları (Certbot tarafından doldurulur)
    ssl_certificate     /etc/letsencrypt/live/{domain_for_nginx}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain_for_nginx}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Güvenlik header'ları
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    # Flask uygulamasına reverse-proxy
    location / {{
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE (Server-Sent Events) — toplu gönderim canlı akışı için zorunlu
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600;

        # Büyük Excel yüklemeleri için
        client_max_body_size 50M;
    }}
}}
"""
        nginx_conf_path = pathlib.Path("/etc/nginx/sites-available/mailsender")
        nginx_conf_path.write_text(nginx_conf, encoding="utf-8")

        enabled_path = pathlib.Path("/etc/nginx/sites-enabled/mailsender")
        if not enabled_path.exists():
            enabled_path.symlink_to(nginx_conf_path)

        result = run("nginx -t", capture=True, check=False)
        if result.returncode == 0:
            run("systemctl reload nginx", check=False)
            ok(f"Nginx yapılandırıldı: {nginx_conf_path}")
        else:
            warn("Nginx config hatası (SSL sertifikası henüz yok olabilir):")
            print(result.stderr)
            warn("SSL sertifikası aldıktan sonra: sudo systemctl reload nginx")

        # ── B2: Certbot ──────────────────────────────────────────────
        section("B2 — Let's Encrypt SSL")
        if domain_for_nginx == "_":
            warn("Domain belirlenmedi — SSL sertifikası kurulmadı")
            warn("APP_BASE_URL'e gerçek domain ekleyip tekrar çalıştırın")
        elif not cmd_ok("certbot"):
            info("Certbot yükleniyor...")
            run("apt-get install -y certbot python3-certbot-nginx", check=False)
            if cmd_ok("certbot"):
                info(f"SSL sertifikası alınıyor: {domain_for_nginx}")
                result = run(
                    f"certbot --nginx -d {domain_for_nginx} --non-interactive --agree-tos -m admin@{domain_for_nginx}",
                    check=False, capture=True
                )
                if result.returncode == 0:
                    ok("SSL sertifikası başarıyla alındı")
                else:
                    warn("Certbot başarısız — DNS yönlendirmesi tamamlandıktan sonra manuel çalıştırın:")
                    warn(f"  sudo certbot --nginx -d {domain_for_nginx}")
        else:
            warn("Certbot zaten kurulu — otomatik sertifika alınmıyor")
            warn(f"Manuel çalıştır: sudo certbot --nginx -d {domain_for_nginx}")

        # ── B3: systemd — app.py ─────────────────────────────────────
        section("B3 — systemd: mailsender-app.service")
        app_service = textwrap.dedent(f"""\
            [Unit]
            Description=MailSender Pro — Flask Uygulaması
            After=network.target mysql.service mariadb.service
            Wants=mysql.service mariadb.service

            [Service]
            Type=simple
            User={APP_USER}
            WorkingDirectory={BASE_DIR}
            EnvironmentFile={ENV_PATH}
            ExecStart={APP_PY} {BASE_DIR}/app.py
            Restart=on-failure
            RestartSec=5
            StandardOutput=journal
            StandardError=journal
            SyslogIdentifier=mailsender-app

            # Güvenlik sıkılaştırması
            NoNewPrivileges=true
            PrivateTmp=true

            [Install]
            WantedBy=multi-user.target
        """)
        svc_path = pathlib.Path("/etc/systemd/system/mailsender-app.service")
        svc_path.write_text(app_service, encoding="utf-8")
        run("systemctl daemon-reload", check=False)
        run("systemctl enable mailsender-app", check=False)
        run("systemctl restart mailsender-app", check=False)
        ok(f"mailsender-app.service oluşturuldu ve başlatıldı")

        # ── B4: systemd — worker.py ──────────────────────────────────
        section("B4 — systemd: mailsender-worker.service")
        worker_service = textwrap.dedent(f"""\
            [Unit]
            Description=MailSender Pro — Kuyruk Worker (Hosting Modu)
            After=network.target mysql.service mariadb.service
            Wants=mysql.service mariadb.service

            [Service]
            Type=simple
            User={APP_USER}
            WorkingDirectory={BASE_DIR}
            EnvironmentFile={ENV_PATH}
            ExecStart={APP_PY} {BASE_DIR}/worker.py
            Restart=on-failure
            RestartSec=10
            StandardOutput=journal
            StandardError=journal
            SyslogIdentifier=mailsender-worker

            # Güvenlik sıkılaştırması
            NoNewPrivileges=true
            PrivateTmp=true

            [Install]
            WantedBy=multi-user.target
        """)
        worker_svc_path = pathlib.Path("/etc/systemd/system/mailsender-worker.service")
        worker_svc_path.write_text(worker_service, encoding="utf-8")
        run("systemctl daemon-reload", check=False)
        run("systemctl enable mailsender-worker", check=False)
        run("systemctl restart mailsender-worker", check=False)
        ok("mailsender-worker.service oluşturuldu ve başlatıldı")

        # ── B5: UFW (Firewall) ───────────────────────────────────────
        section("B5 — UFW Güvenlik Duvarı")
        if cmd_ok("ufw"):
            run("ufw allow 22/tcp",  check=False)   # SSH
            run("ufw allow 80/tcp",  check=False)   # HTTP
            run("ufw allow 443/tcp", check=False)   # HTTPS
            run("ufw deny 5002/tcp", check=False)   # Flask direkt erişim engelle
            ok("UFW kuralları uygulandı (SSH/HTTP/HTTPS açık, port 5002 kapalı)")
        else:
            warn("ufw bulunamadı — EC2 Security Group'ta port 5002'yi kapatın")

# ════════════════════════════════════════════════════════════════════
# BÖLÜM C — Güvenlik Kontrol Listesi
# ════════════════════════════════════════════════════════════════════

title("BÖLÜM C — Güvenlik Kontrol Listesi")

from dotenv import dotenv_values
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

checks = [
    (bool(env.get("SECRET_KEY")),
     "SECRET_KEY tanımlı",
     "SECRET_KEY eksik — .env dosyasına Fernet key ekleyin"),

    (env.get("APP_BASE_URL", "").startswith("https://") or env.get("FORCE_HTTPS") != "true",
     "APP_BASE_URL ayarlı",
     "APP_BASE_URL .env dosyasında eksik"),

    (env.get("DB_PASSWORD", "") != "" and env.get("DB_PASSWORD") != "GUCLU_BIR_SIFRE_YAZIN",
     "DB_PASSWORD varsayılan değil",
     "DB_PASSWORD değiştirilmemiş — güçlü bir şifre ayarlayın"),

    (env.get("DB_USER", "root") != "root",
     "DB root kullanıcısı kullanılmıyor",
     "DB_USER=root tehlikeli — sınırlı yetkili kullanıcı oluşturun (GUVENLIK_KILAVUZU.md)"),

    (not (BASE_DIR / ".git").exists() or
     not (BASE_DIR / ".gitignore").exists() or
     ".env" in (BASE_DIR / ".gitignore").read_text(),
     ".env git'te değil (.gitignore)",
     ".env dosyası Git'e dahil olabilir — .gitignore'a .env ekleyin"),
]

all_ok = True
for passed, success_msg, fail_msg in checks:
    if passed:
        ok(success_msg)
    else:
        warn(fail_msg)
        all_ok = False

if not all_ok:
    warn("Yukarıdaki uyarıları üretim öncesinde düzeltin")

# ════════════════════════════════════════════════════════════════════
# BÖLÜM D — Hosting Modu (cPanel / Shared Hosting) Notları
# ════════════════════════════════════════════════════════════════════

title("BÖLÜM D — Hosting Modu (Cron) Bilgisi")
print(textwrap.dedent(f"""
  Hosting/cPanel ortamında worker.py cron ile çalışır.
  cPanel → Cron Jobs ekranına şunu ekleyin:

    */5 * * * *  {APP_PY} {BASE_DIR}/worker.py >> {BASE_DIR}/logs/worker.log 2>&1

  Bu ayar her 5 dakikada bir kuyruğu kontrol eder.
  Kuyruk boşsa script anında çıkar (kaynak tüketmez).

  E-posta doğrulama işleri (verifier.py) de aynı worker.py
  üzerinden çalışır — ayrı cron eklemenize gerek yok.
"""))

# ════════════════════════════════════════════════════════════════════
# BÖLÜM E — Özet
# ════════════════════════════════════════════════════════════════════

from dotenv import dotenv_values
env_final = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
app_url_final = env_final.get("APP_BASE_URL", "http://127.0.0.1:5002")

print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════════╗
║   MailSender Pro v2.1.0 — Tam Kurulum Tamamlandı    ║
╚══════════════════════════════════════════════════════╝{RESET}

  Uygulama adresi   : {CYAN}{app_url_final}{RESET}
  Çalışma dizini    : {CYAN}{BASE_DIR}{RESET}
  .env dosyası      : {CYAN}{ENV_PATH}{RESET}

  Servis komutları (systemd):
    {CYAN}sudo systemctl status  mailsender-app{RESET}
    {CYAN}sudo systemctl restart mailsender-app{RESET}
    {CYAN}sudo systemctl status  mailsender-worker{RESET}
    {CYAN}sudo journalctl -u mailsender-app -f{RESET}   (canlı log)

  Güncelleme sonrası:
    {CYAN}git pull && sudo systemctl restart mailsender-app mailsender-worker{RESET}

  Detaylı güvenlik rehberi:
    {CYAN}cat {BASE_DIR}/GUVENLIK_KILAVUZU.md{RESET}
""")
