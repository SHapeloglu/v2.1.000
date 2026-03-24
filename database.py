"""
database.py — MailSender Pro Veritabanı Katmanı
================================================
Tüm MySQL işlemleri bu tek dosyada toplanmıştır.

BÖLÜMLER:
  1. Bağlantı yönetimi   — get_db_config(), get_connection()
  2. Şema + Migrasyon    — SCHEMA, init_db(), migrate_db()
  3. Şifreleme           — encrypt_password(), decrypt_password() [Fernet]
  4. Suppression listesi — add_to_suppression(), is_suppressed(), purge_...()
  5. Unsubscribe token   — generate_unsubscribe_token(), verify_...(), peek_...()
  6. Gönderici CRUD      — get_senders(), save_sender(), delete_sender()
  7. Kural CRUD          — get_rules(), save_rule(), delete_rule()
  8. Gönderim logu       — log_send(), get_send_log(), can_send()
  9. Kullanıcı tablolar  — import_excel_to_table(), list_user_tables()
 10. Kuyruk (hosting)    — queue_create(), queue_get_due(), queue_update_status()
 11. Kullanıcı hesapları — user_create(), user_authenticate(), user_list()
 12. Mail şablonları     — template_create(), template_list(), template_update()

NOTLAR:
  - Tüm bağlantılar finally bloğunda kapatılır (bağlantı sızıntısı yok)
  - Şifreler/tokenlar Fernet (simetrik) ile şifreli saklanır
  - Kullanıcı şifreleri bcrypt (tek yönlü hash) ile saklanır
  - SQL injection koruması: tablo/kolon adları security.safe_identifier() ile doğrulanır
  - autocommit=False: her işlemi manuel commit etmek gerekir
"""
import os           # Ortam değişkenleri (.env okuma)
import datetime     # Tarih/saat işlemleri (timedelta, utcnow)
import time         # Geçici tablo adı için zaman damgası
import base64       # Fernet anahtar normalizasyonu için

from dotenv import load_dotenv  # .env dosyasını os.environ'a yükle
import pandas as pd             # Excel/CSV okuma ve tür çıkarımı

# .env dosyasını yükle — prod'da da çalışır, dosya yoksa sessiz geçer
load_dotenv()

def get_db_config():
    """
    .env dosyasından veritabanı bağlantı parametrelerini okur.
    Eksik değerler için güvenli varsayılanlar döner (localhost, port 3306 vb.).
    """
    return {
        'host':     os.getenv('DB_HOST', 'localhost'),    # MySQL sunucu adresi
        'port':     int(os.getenv('DB_PORT', 3306)),      # Varsayılan MySQL portu
        'user':     os.getenv('DB_USER', 'root'),         # Veritabanı kullanıcısı
        'password': os.getenv('DB_PASSWORD', ''),         # Veritabanı şifresi
        'database': os.getenv('DB_NAME', 'mailsender'),   # Kullanılacak DB adı
    }

def get_connection():
    """
    Yeni bir PyMySQL bağlantısı açar ve döner.

    Önemli ayarlar:
      - DictCursor   : sorgu sonuçları row['kolon'] şeklinde erişilebilir dict olarak gelir
      - autocommit=0 : işlemler manuel commit gerektirir — kazara veri kaybı önlenir
      - utf8mb4      : Türkçe karakter ve emoji desteği
      - DB_SSL=true  : TLS şifreli bağlantı (RDS / üretim ortamı için önerilir)
      - ping(reconnect=True) : kopmuş bağlantıyı otomatik yeniler (uzun süre beklemeler için)
    """
    import pymysql
    cfg = get_db_config()

    # .env'de DB_SSL=true ise şifreli TLS bağlantısı kullan (AWS RDS için önerilir)
    ssl_config = None
    if os.getenv('DB_SSL', 'false').lower() == 'true':
        ssl_config = {'ssl_disabled': False}  # ssl_disabled=False → TLS zorunlu

    conn = pymysql.connect(
        host=cfg['host'], port=cfg['port'],
        user=cfg['user'], password=cfg['password'],
        database=cfg['database'],
        charset='utf8mb4',                           # Türkçe/emoji/özel karakter desteği
        cursorclass=pymysql.cursors.DictCursor,      # Sonuçlar dict olarak gelsin
        autocommit=False,                            # Manuel commit zorunlu
        connect_timeout=10,                          # 10 sn'de bağlanamazsa hata
        ssl=ssl_config,
    )
    conn.ping(reconnect=True)
    return conn

# ── Veritabanı Şeması ────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS kullanılır — tablo varsa atlanır, yoksa oluşturulur.
# Tüm sistem tabloları burada tanımlıdır; uygulama ilk başlatıldığında otomatik kurulur.
SCHEMA = """
CREATE TABLE IF NOT EXISTS senders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(200) NOT NULL,
    sender_mode     ENUM('smtp','ses','api') NOT NULL DEFAULT 'smtp',
    smtp_server     VARCHAR(200),
    smtp_port       INT          DEFAULT 465,
    username        VARCHAR(200),
    password        VARCHAR(500)          COMMENT 'Fernet şifreli SMTP şifresi',
    use_ssl         TINYINT(1)   NOT NULL DEFAULT 1,
    aws_access_key  VARCHAR(500)          COMMENT 'Fernet şifreli AWS Access Key ID',
    aws_secret_key  VARCHAR(500)          COMMENT 'Fernet şifreli AWS Secret Access Key',
    aws_region      VARCHAR(50)  DEFAULT 'us-east-1',
    api_host        VARCHAR(500)          COMMENT 'API sunucu host (örn: api.mailrelay.com)',
    api_endpoint    VARCHAR(500)          COMMENT 'API endpoint yolu (örn: /api/v1/send_emails)',
    api_auth_type   VARCHAR(100)          COMMENT 'Auth header tipi (X-AUTH-TOKEN, Bearer, vb.)',
    api_auth_token  TEXT                  COMMENT 'Fernet şifreli API token',
    api_method      VARCHAR(10)  DEFAULT 'POST'  COMMENT 'HTTP metodu',
    api_payload_tpl TEXT                  COMMENT 'JSON payload template',
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS send_rules (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    sender_id       INT          NOT NULL,
    name            VARCHAR(200) NOT NULL,
    min_interval_h  INT          NOT NULL DEFAULT 0   COMMENT 'Aynı adrese tekrar göndermek için min saat (0=sınırsız)',
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES senders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS send_log (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    sender_id         INT          NOT NULL,
    rule_id           INT,
    recipient         VARCHAR(500) NOT NULL,
    subject           VARCHAR(500) NOT NULL,
    status            ENUM('sent','failed','skipped') NOT NULL,
    error_msg         TEXT,
    message_id        VARCHAR(500)           COMMENT 'API/SES message ID (teslimat takibi)',
    provider          VARCHAR(50)            COMMENT 'smtp|ses|brevo|mailrelay|api',
    sent_by_user_id   INT                    COMMENT 'Gönderimi başlatan kullanıcı ID',
    sent_by_username  VARCHAR(100)           COMMENT 'Gönderimi başlatan kullanıcı adı (snapshot)',
    sent_at           DATETIME     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_recipient  (recipient(100)),
    INDEX idx_sent_at    (sent_at),
    INDEX idx_sender     (sender_id),
    INDEX idx_sent_by    (sent_by_user_id),
    INDEX idx_message_id (message_id(100)),
    FOREIGN KEY (sender_id) REFERENCES senders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT                    COMMENT 'İşlemi yapan kullanıcı ID',
    username    VARCHAR(100)           COMMENT 'Kullanıcı adı (snapshot — kullanıcı silinse bile korunur)',
    action      VARCHAR(100) NOT NULL  COMMENT 'İşlem tipi: user_create, sender_delete, bulk_start vb.',
    target_type VARCHAR(50)            COMMENT 'Hedef varlık türü: user, sender, excel, bulk',
    target_id   VARCHAR(100)           COMMENT 'Hedef varlık ID veya adı',
    detail      TEXT                   COMMENT 'Ek bilgi (JSON veya düz metin)',
    ip_address  VARCHAR(45)            COMMENT 'İstemci IP adresi',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user     (user_id),
    INDEX idx_action   (action),
    INDEX idx_created  (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(100) NOT NULL UNIQUE,
    email       VARCHAR(200),
    password_hash VARCHAR(255) NOT NULL     COMMENT 'bcrypt hash',
    role        ENUM('admin','editor') NOT NULL DEFAULT 'editor',
    is_active   TINYINT(1) NOT NULL DEFAULT 1,
    theme       VARCHAR(50) NOT NULL DEFAULT 'charcoal' COMMENT 'Kullanıcı arayüz teması',
    last_login  DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mail_templates (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    type        ENUM('subject','body') NOT NULL  COMMENT 'Şablon tipi: konu veya mesaj',
    name        VARCHAR(200) NOT NULL             COMMENT 'Şablona verilen isim',
    content     LONGTEXT NOT NULL                 COMMENT 'Şablon içeriği',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS suppression_list (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    email           VARCHAR(500) NOT NULL,
    reason          ENUM('bounce','complaint','unsubscribe','invalid') NOT NULL,
    source          VARCHAR(50),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- API kolonları migrate_db() ile MySQL 5.7 uyumlu şekilde eklenir
-- ALTER TABLE senders ... (migrate_db'ye taşındı)

CREATE TABLE IF NOT EXISTS suppression_domains (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    domain      VARCHAR(253) NOT NULL,
    reason      VARCHAR(100) DEFAULT 'manual',
    note        VARCHAR(500) DEFAULT '',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_domain (domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE IF NOT EXISTS unsubscribe_tokens (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    token       VARCHAR(64) NOT NULL,
    email       VARCHAR(500) NOT NULL,
    used        TINYINT(1) NOT NULL DEFAULT 0,
    expires_at  DATETIME NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_token (token),
    INDEX idx_email (email(100)),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS send_queue (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(200) NOT NULL        COMMENT 'Görev adı',
    sender_id       INT NOT NULL,
    rule_id         INT,
    source_type     ENUM('db','excel') NOT NULL  COMMENT 'Kaynak tipi',
    source_table    VARCHAR(200)                 COMMENT 'DB tablosu',
    source_excel    LONGBLOB                     COMMENT 'Excel dosyası binary',
    email_col       VARCHAR(200) NOT NULL,
    var_cols        TEXT                         COMMENT 'Değişken kolonlar (virgülle)',
    subject_tpl     TEXT NOT NULL,
    body_tpl        LONGTEXT NOT NULL,
    html_mode       TINYINT(1) NOT NULL DEFAULT 1,
    include_unsub   TINYINT(1) NOT NULL DEFAULT 1,
    delay_ms        INT NOT NULL DEFAULT 500,
    attachment_name VARCHAR(500),
    attachment_data LONGBLOB,
    batch_size      INT NOT NULL DEFAULT 0        COMMENT '0 = parçasız',
    batch_wait_min  INT NOT NULL DEFAULT 60,
    status          ENUM('pending','running','paused','done','cancelled') NOT NULL DEFAULT 'pending',
    current_offset  INT NOT NULL DEFAULT 0        COMMENT 'Şu an kaçıncı kayıtta',
    total_count     INT NOT NULL DEFAULT 0,
    sent_count      INT NOT NULL DEFAULT 0,
    failed_count    INT NOT NULL DEFAULT 0,
    skipped_count   INT NOT NULL DEFAULT 0,
    next_run_at     DATETIME                     COMMENT 'Sonraki parti zamanı',
    started_at      DATETIME,
    finished_at     DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_next_run (next_run_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS send_queue_log (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    queue_id    BIGINT NOT NULL,
    email       VARCHAR(500) NOT NULL,
    status      ENUM('sent','failed','skipped') NOT NULL,
    error_msg   TEXT,
    sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_queue  (queue_id),
    INDEX idx_email  (email(100)),
    FOREIGN KEY (queue_id) REFERENCES send_queue(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS email_verify_jobs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_name        VARCHAR(200) NOT NULL           COMMENT 'İş adı',
    table_name      VARCHAR(200) NOT NULL           COMMENT 'Kontrol edilecek kaynak tablo',
    email_col       VARCHAR(200) NOT NULL           COMMENT 'E-posta kolonu adı',
    mode            ENUM('format','mx','smtp') NOT NULL DEFAULT 'mx' COMMENT 'Doğrulama derinliği',
    threads         INT NOT NULL DEFAULT 10         COMMENT 'Paralel thread sayısı',
    status          ENUM('pending','running','done','cancelled') NOT NULL DEFAULT 'pending',
    total_count     INT NOT NULL DEFAULT 0,
    processed_count INT NOT NULL DEFAULT 0,
    valid_count     INT NOT NULL DEFAULT 0,
    invalid_count   INT NOT NULL DEFAULT 0,
    unknown_count   INT NOT NULL DEFAULT 0,
    suppressed_count INT NOT NULL DEFAULT 0         COMMENT 'Suppression listesine eklenen sayısı',
    created_by_id   INT                             COMMENT 'İşi başlatan kullanıcı ID',
    created_by      VARCHAR(100)                    COMMENT 'Kullanıcı adı snapshot',
    started_at      DATETIME,
    finished_at     DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status    (status),
    INDEX idx_table     (table_name),
    INDEX idx_created_by (created_by_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    token      VARCHAR(64)  NOT NULL,
    user_id    INT          NOT NULL,
    username   VARCHAR(100) NOT NULL,
    expires_at DATETIME     NOT NULL,
    used       TINYINT(1)   NOT NULL DEFAULT 0,
    created_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_token (token),
    INDEX idx_user    (user_id),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_settings (
    key_name   VARCHAR(100) NOT NULL PRIMARY KEY,
    value      TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ses_notifications (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    sender_id   INT,
    notif_type  ENUM('Bounce','Complaint','Delivery') NOT NULL,
    recipient   VARCHAR(500) NOT NULL,
    bounce_type VARCHAR(50)  COMMENT 'Permanent/Transient',
    bounce_sub  VARCHAR(50)  COMMENT 'General/NoEmail/Suppressed vb.',
    feedback_id VARCHAR(200),
    raw_json    MEDIUMTEXT,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type      (notif_type),
    INDEX idx_recipient (recipient(100)),
    INDEX idx_received  (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def init_db():
    """
    Şemadaki tüm tabloları oluşturur (IF NOT EXISTS — mevcut tablolara dokunmaz).
    Her uygulama başlangıcında güvenle çağrılabilir.
    Tek bir tablo oluşturulamasa bile diğerleri devam eder.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # SCHEMA'yı ; ile böl ve her ifadeyi ayrı çalıştır
            statements = [s.strip() for s in SCHEMA.strip().split(';') if s.strip()]
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    # Bazı ALTER TABLE eski MySQL'de hata verir — beklenen durum
                    print(f"Statement hatası (beklenen olabilir): {e}")
                    continue
        conn.commit()
        return True, 'Tablolar oluşturuldu.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()



def _col_exists(cur, table: str, column: str) -> bool:
    """
    MySQL 5.7 uyumlu kolon varlık kontrolü.
    information_schema sorgusu ile kontrol eder — ADD COLUMN IF NOT EXISTS MySQL 8.0+ gerektirir.
    """
    db_name = get_db_config()['database']
    cur.execute(
        "SELECT COUNT(*) as cnt FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
        (db_name, table, column)
    )
    return cur.fetchone()['cnt'] > 0


def migrate_db():
    """
    Mevcut DB şemasını günceller — yeni kolonları ekler, ENUM genişletir.
    MySQL 5.7 uyumlu: ADD COLUMN IF NOT EXISTS yerine _col_exists() kullanılır.
    Her uygulama başlangıcında güvenle çağrılabilir.
    """
    # (tablo, kolon, ALTER ifadesi) — kolon yoksa ALTER çalıştırılır
    col_migrations = [
        ("senders",  "configuration_set","ALTER TABLE senders ADD COLUMN configuration_set VARCHAR(100) COMMENT 'AWS SES ConfigurationSet adı'"),
        ("senders",  "api_host",        "ALTER TABLE senders ADD COLUMN api_host        VARCHAR(500) COMMENT 'API sunucu host'"),
        ("senders",  "api_endpoint",    "ALTER TABLE senders ADD COLUMN api_endpoint    VARCHAR(500) COMMENT 'API endpoint yolu'"),
        ("senders",  "api_auth_type",   "ALTER TABLE senders ADD COLUMN api_auth_type   VARCHAR(100) COMMENT 'Auth header tipi'"),
        ("senders",  "api_auth_token",  "ALTER TABLE senders ADD COLUMN api_auth_token  TEXT         COMMENT 'Fernet şifreli token'"),
        ("senders",  "api_method",      "ALTER TABLE senders ADD COLUMN api_method      VARCHAR(10)  DEFAULT 'POST'"),
        ("senders",  "api_payload_tpl", "ALTER TABLE senders ADD COLUMN api_payload_tpl TEXT         COMMENT 'JSON payload template'"),
        ("users",    "theme",           "ALTER TABLE users    ADD COLUMN theme           VARCHAR(50)  NOT NULL DEFAULT 'charcoal' COMMENT 'Kullanıcı arayüz teması'"),
        ("send_log", "sent_by_user_id", "ALTER TABLE send_log ADD COLUMN sent_by_user_id INT          COMMENT 'Gönderimi başlatan kullanıcı ID'"),
        ("send_log", "sent_by_username","ALTER TABLE send_log ADD COLUMN sent_by_username VARCHAR(100) COMMENT 'Kullanıcı adı snapshot'"),
        ("send_log", "message_id",      "ALTER TABLE send_log ADD COLUMN message_id   VARCHAR(500) COMMENT 'API/SES message ID'"),
        ("send_log", "provider",        "ALTER TABLE send_log ADD COLUMN provider      VARCHAR(50)  COMMENT 'smtp|ses|brevo|mailrelay|api'"),
        ("email_verify_jobs", "suppressed_count",
         "ALTER TABLE email_verify_jobs ADD COLUMN suppressed_count INT NOT NULL DEFAULT 0 COMMENT 'Suppression eklenen sayı'"),
    ]

    # Koşulsuz çalışan migration'lar (MODIFY, CREATE TABLE vb.)
    always_migrations = [
        # ENUM genişletme: idempotent, tekrar çalışsa da sorun yok
        "ALTER TABLE senders MODIFY COLUMN sender_mode ENUM('smtp','ses','api') NOT NULL DEFAULT 'smtp'",
        # audit_log tablosu
        """CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT, username VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50), target_id VARCHAR(100),
    detail TEXT, ip_address VARCHAR(45),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id), INDEX idx_action (action), INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Kolon kontrollü migration'lar
            for table, col, sql in col_migrations:
                try:
                    if not _col_exists(cur, table, col):
                        cur.execute(sql)
                        print(f"Migration: {table}.{col} eklendi.")
                except Exception as e:
                    print(f"Migration uyarı ({table}.{col}): {e}")

            # Koşulsuz migration'lar
            for sql in always_migrations:
                try:
                    cur.execute(sql)
                except Exception as e:
                    print(f"Migration (beklenen olabilir): {e}")

        conn.commit()
        return True, 'Migration tamamlandı.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def test_connection():
    """Veritabanı bağlantısını test eder. (True, mesaj) veya (False, hata_metni) döner."""
    try:
        conn = get_connection()
        conn.close()
        return True, 'Bağlantı başarılı!'
    except Exception as e:
        return False, str(e)

def _get_fernet_key():

    """SECRET_KEY'den Fernet şifreleme anahtarını yükler veya yeni oluşturur."""
    key = os.getenv('SECRET_KEY', '').strip()
    if not key:
        raise ValueError('SECRET_KEY .env dosyasında tanımlı değil!')
    
    if len(key) == 44:
        try:
            from cryptography.fernet import Fernet
            return Fernet(key.encode())
        except Exception:
            pass
    
    try:
        from cryptography.fernet import Fernet
        key_bytes = key.encode('utf-8')
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b'\0')
        else:
            key_bytes = key_bytes[:32]
        
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except Exception as e:
        raise ValueError(f'Fernet key oluşturulamadı: {e}')

def _fernet():
    """
    Fernet nesnesini döner.
    encrypt_password() ve decrypt_password() bu fonksiyonu kullanır.
    SECRET_KEY tanımlı değilse ValueError fırlatır.
    """
    from cryptography.fernet import Fernet
    try:
        return _get_fernet_key()
    except Exception as e:
        raise ValueError(f'Fernet başlatılamadı: {e}')

def encrypt_password(plain: str) -> str:
    """
    Düz metin şifreyi Fernet ile şifreler.
    Boş string gelirse boş string döner.
    Şifreleme başarısız olursa düz metin döner (log basılır — uyarı).
    """
    if not plain:
        return ''  # Boş şifre şifrelenmez
    try:
        return _fernet().encrypt(plain.encode()).decode()
    except Exception as e:
        print(f"Şifreleme hatası: {e}")
        return plain  # Şifreleme başarısız — düz metin saklanır (güvensiz ama çalışır)

def decrypt_password(enc: str) -> str:
    """
    Fernet şifreli metni çözer.
    Çözülemeyen değerler (eski kayıtlar, düz metin) olduğu gibi döner.
    """
    if not enc:
        return ''  # Boş değer döner
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except Exception as e:
        # Eski kayıtlar düz metin olabilir — olduğu gibi döndür
        print(f"Şifre çözme hatası: {e}, düz metin olarak kullanılıyor")
        return enc

def add_to_suppression(email, reason, source=None):
    """
    E-postayı suppression listesine ekler.
    ON DUPLICATE KEY UPDATE: zaten varsa reason/source güncellenir, tarih yenilenir.
    reason: 'bounce' | 'complaint' | 'unsubscribe' | 'invalid'
    source: hangi sistemden geldiği ('ses', 'smtp', 'manual', vb.)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO suppression_list (email, reason, source)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                reason = VALUES(reason),
                source = VALUES(source),
                created_at = CURRENT_TIMESTAMP
            """, (email, reason, source))
        conn.commit()
        return True
    except Exception as e:
        print(f"Suppression ekleme hatası: {e}")
        return False
    finally:
        conn.close()

def is_suppressed(email):
    """
    E-posta suppression listesinde veya domain bloklama listesinde ise True döner.
    Gönderim öncesi kontrol için kullanılır.
    İki kontrol:
      1. suppression_list — tam adres eşleşmesi
      2. suppression_domains — adresin domain'i bloklu mu?
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1. Tam adres kontrolü
            cur.execute(
                "SELECT COUNT(*) as cnt FROM suppression_list WHERE email=%s",
                (email,)
            )
            if cur.fetchone()['cnt'] > 0:
                return True
            # 2. Domain kontrolü
            domain = email.split('@')[-1].lower().strip() if '@' in email else ''
            if domain:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM suppression_domains WHERE domain=%s",
                    (domain,)
                )
                if cur.fetchone()['cnt'] > 0:
                    return True
            return False
    except Exception:
        return False
    finally:
        conn.close()


def get_suppression_domains(search=None):
    """Domain bloklama listesini döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if search:
                cur.execute(
                    "SELECT * FROM suppression_domains WHERE domain LIKE %s ORDER BY created_at DESC",
                    (f'%{search}%',)
                )
            else:
                cur.execute("SELECT * FROM suppression_domains ORDER BY created_at DESC")
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r.get('created_at'), datetime.datetime):
                    r['created_at'] = r['created_at'].strftime('%d.%m.%Y %H:%M')
            return rows
    finally:
        conn.close()


def add_suppression_domain(domain, reason='manual', note=''):
    """Domain'i bloklama listesine ekler. Zaten varsa günceller."""
    domain = domain.strip().lower().lstrip('@')
    if not domain or '.' not in domain:
        return False, 'Geçersiz domain formatı.'
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO suppression_domains (domain, reason, note)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                reason = VALUES(reason),
                note   = VALUES(note),
                created_at = CURRENT_TIMESTAMP
            """, (domain, reason, note or ''))
        conn.commit()
        return True, f'{domain} eklendi.'
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_suppression_domain(domain):
    """Domain'i bloklama listesinden kaldırır."""
    domain = domain.strip().lower().lstrip('@')
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM suppression_domains WHERE domain=%s", (domain,))
        conn.commit()
        return True, 'Silindi.'
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# ── Unsubscribe Token ──────────────────────────────────────────────────
def generate_unsubscribe_token(email: str) -> str:
    """E-posta adresi için tek kullanımlık güvenli token üretir ve DB'ye kaydeder. 7 gün geçerli."""
    import secrets
    conn = get_connection()
    try:
        token = secrets.token_urlsafe(32)
        expires = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM unsubscribe_tokens WHERE email=%s AND used=0", (email,))
            cur.execute(
                "INSERT INTO unsubscribe_tokens (token, email, expires_at) VALUES (%s, %s, %s)",
                (token, email, expires)
            )
        conn.commit()
        return token
    except Exception as e:
        print(f"Token üretme hatası: {e}")
        conn.rollback()
        return ''
    finally:
        conn.close()

def verify_unsubscribe_token(token: str):
    """Token geçerliyse email adresini döner, değilse None döner. Token'ı kullanıldı olarak işaretler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email FROM unsubscribe_tokens WHERE token=%s AND used=0 AND expires_at > UTC_TIMESTAMP()",
                (token,)
            )
            row = cur.fetchone()
            if not row:
                return None
            email = row['email']
            cur.execute("UPDATE unsubscribe_tokens SET used=1 WHERE token=%s", (token,))
        conn.commit()
        return email
    except Exception as e:
        print(f"Token doğrulama hatası: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def peek_unsubscribe_token(token: str):
    """Token'a ait e-posta adresini token'ı tüketmeden döner (onay ekranı için)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email FROM unsubscribe_tokens WHERE token=%s AND used=0 AND expires_at > UTC_TIMESTAMP()",
                (token,)
            )
            row = cur.fetchone()
            return row['email'] if row else None
    except Exception as e:
        print(f"Token peek hatası: {e}")
        return None
    finally:
        conn.close()

def get_senders(active_only=False):
    """
    Tüm göndericileri döner. Şifreler şifreli gelir (decode edilmez).
    active_only=True → sadece is_active=1 olan göndericiler.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT * FROM senders WHERE is_active=1 ORDER BY name")
            else:
                cur.execute("SELECT * FROM senders ORDER BY name")
            return cur.fetchall()
    finally:
        conn.close()

def get_sender(sender_id):

    """ID'ye göre tek gönderici kaydını döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM senders WHERE id=%s", (sender_id,))
            row = cur.fetchone()
            if row:
                if row.get('password'):
                    row['password'] = decrypt_password(row['password'])
                if row.get('aws_access_key'):
                    row['aws_access_key'] = decrypt_password(row['aws_access_key'])
                if row.get('aws_secret_key'):
                    row['aws_secret_key'] = decrypt_password(row['aws_secret_key'])
                if row.get('api_auth_token'):
                    row['api_auth_token'] = decrypt_password(row['api_auth_token'])
                if row.get('api_payload_tpl') and isinstance(row['api_payload_tpl'], str):
                    import json as _json
                    try:
                        row['api_payload_tpl'] = _json.loads(row['api_payload_tpl'])
                    except Exception:
                        pass
            return row
    finally:
        conn.close()

def save_sender(data, sender_id=None):

    """Yeni gönderici oluşturur veya mevcutu günceller."""
    conn = get_connection()
    try:
        mode = data.get('sender_mode', 'smtp')

        with conn.cursor() as cur:
            if sender_id:
                fields = ["name=%s", "email=%s", "sender_mode=%s", "use_ssl=%s", "is_active=%s"]
                params = [data['name'], data['email'], mode,
                          data.get('use_ssl', 1), data.get('is_active', 1)]

                if mode == 'smtp':
                    fields += ["smtp_server=%s", "smtp_port=%s", "username=%s"]
                    params += [data.get('smtp_server',''), data.get('smtp_port', 465), data.get('username','')]
                    if data.get('password'):
                        fields.append("password=%s")
                        params.append(encrypt_password(data['password']))
                    fields += ["aws_access_key=NULL", "aws_secret_key=NULL", "aws_region=NULL",
                               "api_host=NULL", "api_endpoint=NULL", "api_auth_type=NULL",
                               "api_auth_token=NULL", "api_method=NULL", "api_payload_tpl=NULL"]
                elif mode == 'ses':
                    fields.append("aws_region=%s")
                    params.append(data.get('aws_region', 'us-east-1'))
                    if data.get('aws_access_key'):
                        fields.append("aws_access_key=%s")
                        params.append(encrypt_password(data['aws_access_key']))
                    if data.get('aws_secret_key'):
                        fields.append("aws_secret_key=%s")
                        params.append(encrypt_password(data['aws_secret_key']))
                    fields += ["smtp_server=NULL", "smtp_port=NULL", "username=NULL", "password=NULL",
                               "api_host=NULL", "api_endpoint=NULL", "api_auth_type=NULL",
                               "api_auth_token=NULL", "api_method=NULL", "api_payload_tpl=NULL"]
                else:  # api
                    import json as _json
                    fields += ["api_host=%s", "api_endpoint=%s", "api_auth_type=%s", "api_method=%s"]
                    params += [data.get('api_host',''), data.get('api_endpoint',''),
                               data.get('api_auth_type','X-AUTH-TOKEN'), data.get('api_method','POST')]
                    if data.get('api_auth_token'):
                        fields.append("api_auth_token=%s")
                        params.append(encrypt_password(data['api_auth_token']))
                    tpl = data.get('api_payload_tpl')
                    if tpl is not None:
                        fields.append("api_payload_tpl=%s")
                        params.append(_json.dumps(tpl, ensure_ascii=False) if isinstance(tpl, dict) else tpl)
                    fields += ["smtp_server=NULL", "smtp_port=NULL", "username=NULL", "password=NULL",
                               "aws_access_key=NULL", "aws_secret_key=NULL", "aws_region=NULL"]

                params.append(sender_id)
                cur.execute(f"UPDATE senders SET {', '.join(fields)} WHERE id=%s", params)

            else:
                import json as _json
                if mode == 'smtp':
                    cur.execute("""
                        INSERT INTO senders
                            (name, email, sender_mode, smtp_server, smtp_port, username,
                             password, use_ssl, is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        data['name'], data['email'], mode,
                        data.get('smtp_server',''), data.get('smtp_port', 465), data.get('username',''),
                        encrypt_password(data.get('password', '')),
                        data.get('use_ssl', 1), data.get('is_active', 1)
                    ))
                elif mode == 'ses':
                    cur.execute("""
                        INSERT INTO senders
                            (name, email, sender_mode, aws_access_key, aws_secret_key,
                             aws_region, use_ssl, is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        data['name'], data['email'], mode,
                        encrypt_password(data.get('aws_access_key', '')),
                        encrypt_password(data.get('aws_secret_key', '')),
                        data.get('aws_region', 'us-east-1'),
                        data.get('use_ssl', 1), data.get('is_active', 1)
                    ))
                else:  # api
                    tpl = data.get('api_payload_tpl')
                    tpl_str = _json.dumps(tpl, ensure_ascii=False) if isinstance(tpl, dict) else (tpl or '')
                    cur.execute("""
                        INSERT INTO senders
                            (name, email, sender_mode, api_host, api_endpoint,
                             api_auth_type, api_auth_token, api_method, api_payload_tpl,
                             is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        data['name'], data['email'], mode,
                        data.get('api_host',''), data.get('api_endpoint',''),
                        data.get('api_auth_type','X-AUTH-TOKEN'),
                        encrypt_password(data.get('api_auth_token','')),
                        data.get('api_method','POST'), tpl_str,
                        data.get('is_active', 1)
                    ))
                sender_id = cur.lastrowid

        conn.commit()
        return True, sender_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_sender(sender_id):
    """
    Göndericini siler.
    FOREIGN KEY ON DELETE CASCADE sayesinde ilgili kurallar ve loglar otomatik silinir.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM senders WHERE id=%s", (sender_id,))
        conn.commit()
        return True, 'Silindi.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_rules():

    """Tüm gönderim kurallarını listeler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.*, s.name as sender_name, s.email as sender_email
                           FROM send_rules r JOIN senders s ON r.sender_id=s.id
                           ORDER BY r.name""")
            return cur.fetchall()
    finally:
        conn.close()

def get_rule(rule_id):

    """ID'ye göre tek kural kaydını döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM send_rules WHERE id=%s", (rule_id,))
            return cur.fetchone()
    finally:
        conn.close()

def save_rule(data, rule_id=None):

    """Yeni kural oluşturur veya mevcutu günceller."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if rule_id:
                cur.execute("UPDATE send_rules SET name=%s,sender_id=%s,min_interval_h=%s,is_active=%s WHERE id=%s",
                            (data['name'],data['sender_id'],data['min_interval_h'],data['is_active'],rule_id))
            else:
                cur.execute("INSERT INTO send_rules (name,sender_id,min_interval_h,is_active) VALUES (%s,%s,%s,%s)",
                            (data['name'],data['sender_id'],data['min_interval_h'],data.get('is_active',1)))
                rule_id = cur.lastrowid
        conn.commit()
        return True, rule_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_rule(rule_id):

    """Gönderim kuralını siler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM send_rules WHERE id=%s", (rule_id,))
        conn.commit()
        return True, 'Silindi.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def log_send(sender_id, rule_id, recipient, subject, status, error_msg=None,
             user_id=None, username=None, message_id=None, provider=None):
    """
    Gönderim sonucunu send_log tablosuna kaydeder.
    status:     'sent' | 'failed' | 'skipped'
    message_id: API/SES'ten dönen mesaj ID (teslimat takibi için)
    provider:   'smtp' | 'ses' | 'brevo' | 'mailrelay' | 'api'
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO send_log
                    (sender_id, rule_id, recipient, subject, status, error_msg,
                     message_id, provider, sent_by_user_id, sent_by_username)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (sender_id, rule_id, recipient, subject, status, error_msg,
                 message_id, provider, user_id, username)
            )
        conn.commit()
    except Exception as e:
        print(f"Log kaydı hatası: {e}")
    finally:
        conn.close()


def audit(user_id, username, action, target_type=None, target_id=None,
          detail=None, ip_address=None):
    """
    Kullanıcı eylemini audit_log tablosuna kaydeder.
    Hata olsa bile sessizce geçer — audit kaydı kritik değil, işlem durmamalı.

    action örnekleri:
      user_create, user_update, user_delete
      sender_create, sender_update, sender_delete
      excel_upload, bulk_start, bulk_stop
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO audit_log
                    (user_id, username, action, target_type, target_id, detail, ip_address)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (user_id, username, action, target_type,
                 str(target_id) if target_id is not None else None,
                 detail, ip_address)
            )
        conn.commit()
    except Exception as e:
        print(f"Audit log hatası: {e}")
    finally:
        conn.close()

def get_last_sent(sender_id, recipient):
    """
    Belirli gönderici ve alıcı için en son başarılı gönderimin zamanını döner.
    can_send() tarafından min_interval_h kontrolü için çağrılır.
    Hiç gönderilmemişse None döner.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT sent_at FROM send_log
                           WHERE sender_id=%s AND recipient=%s AND status='sent'
                           ORDER BY sent_at DESC LIMIT 1""",
                        (sender_id, recipient))
            row = cur.fetchone()
            return row['sent_at'] if row else None
    finally:
        conn.close()

def can_send(sender_id, recipient, min_interval_h):
    """
    Gönderimin yapılıp yapılamayacağını kontrol eder.
    Sırasıyla:
      1. Suppression listesi kontrolü (bounce/şikayet/abonelik iptal)
      2. min_interval_h=0 ise kısıtsız izin
      3. Son gönderimden yeterli saat geçmiş mi kontrolü
    Döner: (True, None) veya (False, neden_string)
    """
    # Suppression kontrolü — listede varsa asla gönderme
    if is_suppressed(recipient):
        return False, "Bu e-posta adresi bastırma listesinde (bounce, complaint veya unsubscribe)"

    # Sıfır saat = kısıtlama yok, her zaman gönderebilir
    if min_interval_h == 0:
        return True, None

    last = get_last_sent(sender_id, recipient)
    if last is None:
        return True, None  # Daha hiç gönderilmemiş — izin ver

    # Kaç saat geçtiğini hesapla
    delta = datetime.datetime.now() - last
    hours_passed = delta.total_seconds() / 3600

    if hours_passed >= min_interval_h:
        return True, None  # Yeterli süre geçmiş

    # Henüz erken — kaç saat daha bekleyeceğini söyle
    remaining = min_interval_h - hours_passed
    return False, f"{remaining:.1f} saat sonra gönderilebilir (son: {last.strftime('%d.%m.%Y %H:%M')})" 

def get_send_log(page=1, per_page=50, sender_id=None, status=None, search=None):

    """Gönderim loglarını filtreli ve sayfalı döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            wheres, params = [], []
            if sender_id: 
                wheres.append("l.sender_id=%s")
                params.append(sender_id)
            if status:    
                wheres.append("l.status=%s")
                params.append(status)
            if search:    
                wheres.append("l.recipient LIKE %s")
                params.append(f'%{search}%')
            
            where_clause = ('WHERE ' + ' AND '.join(wheres)) if wheres else ''
            
            cur.execute(f"SELECT COUNT(*) as cnt FROM send_log l {where_clause}", params)
            total = cur.fetchone()['cnt']
            
            offset = (page-1)*per_page
            cur.execute(f"""SELECT l.*, s.name as sender_name, s.sender_mode, s.api_host FROM send_log l
                            LEFT JOIN senders s ON l.sender_id=s.id
                            {where_clause}
                            ORDER BY l.sent_at DESC LIMIT %s OFFSET %s""",
                        params + [per_page, offset])
            rows = cur.fetchall()
            return rows, total
    finally:
        conn.close()

def clear_send_log(sender_id=None):
    """
    Gönderim loglarını siler.
    sender_id verilirse → sadece o göndericinin kayıtları silinir.
    sender_id verilmezse → tüm send_log tablosu temizlenir.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if sender_id:
                cur.execute("DELETE FROM send_log WHERE sender_id=%s", (sender_id,))
            else:
                cur.execute("DELETE FROM send_log")
            deleted = cur.rowcount
        conn.commit()
        return True, f'{deleted} kayıt silindi.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_log_summary():
    """
    Tüm gönderim loglarından tek satır özet istatistik döner.
    Bugün, bu ay ve tüm zamanlar için ayrı ayrı hesaplar.
    Gönderim geçmişi sayfasındaki özet kart için kullanılır.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    -- Tüm zamanlar
                    COUNT(*) as total_all,
                    SUM(CASE WHEN status='sent'    THEN 1 ELSE 0 END) as sent_all,
                    SUM(CASE WHEN status='failed'  THEN 1 ELSE 0 END) as failed_all,
                    SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped_all,
                    -- Bu ay
                    SUM(CASE WHEN YEAR(sent_at)=YEAR(UTC_TIMESTAMP())
                             AND MONTH(sent_at)=MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as total_month,
                    SUM(CASE WHEN status='sent'
                             AND YEAR(sent_at)=YEAR(UTC_TIMESTAMP())
                             AND MONTH(sent_at)=MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as sent_month,
                    SUM(CASE WHEN status='failed'
                             AND YEAR(sent_at)=YEAR(UTC_TIMESTAMP())
                             AND MONTH(sent_at)=MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as failed_month,
                    SUM(CASE WHEN status='skipped'
                             AND YEAR(sent_at)=YEAR(UTC_TIMESTAMP())
                             AND MONTH(sent_at)=MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as skipped_month,
                    -- Bugün
                    SUM(CASE WHEN DATE(sent_at)=DATE(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as total_today,
                    SUM(CASE WHEN status='sent'
                             AND DATE(sent_at)=DATE(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as sent_today,
                    SUM(CASE WHEN status='failed'
                             AND DATE(sent_at)=DATE(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as failed_today,
                    -- Son gönderim
                    MAX(sent_at) as last_sent_at,
                    -- Kaç farklı gönderici kullanıldı
                    COUNT(DISTINCT sender_id) as sender_count
                FROM send_log
            """)
            r = cur.fetchone()
            if not r or not r['total_all']:
                return None

            # Yüzde hesaplama yardımcısı — sıfıra bölme korumalı
            def pct(a, b):
                return round(a / b * 100, 1) if b else 0

            return {
                'total_all':     int(r['total_all']    or 0),
                'sent_all':      int(r['sent_all']     or 0),
                'failed_all':    int(r['failed_all']   or 0),
                'skipped_all':   int(r['skipped_all']  or 0),
                'success_pct':   pct(r['sent_all'],    r['total_all']),
                'total_month':   int(r['total_month']  or 0),
                'sent_month':    int(r['sent_month']   or 0),
                'failed_month':  int(r['failed_month'] or 0),
                'skipped_month': int(r['skipped_month']or 0),
                'success_pct_month': pct(r['sent_month'], r['total_month']),
                'total_today':   int(r['total_today']  or 0),
                'sent_today':    int(r['sent_today']   or 0),
                'failed_today':  int(r['failed_today'] or 0),
                'sender_count':  int(r['sender_count'] or 0),
                'last_sent_at':  r['last_sent_at'].strftime('%d.%m.%Y %H:%M') if r['last_sent_at'] else None,
            }
    except Exception as e:
        print(f"Log summary hatası: {e}")
        return None
    finally:
        conn.close()


def get_sender_monthly_stats():
    """Her gönderici için bu ayki ve toplam gönderim istatistiklerini döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    sender_id,
                    COUNT(*) as total_all,
                    SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as sent_all,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_all,
                    SUM(CASE WHEN
                        YEAR(sent_at) = YEAR(UTC_TIMESTAMP()) AND
                        MONTH(sent_at) = MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as total_month,
                    SUM(CASE WHEN
                        status='sent' AND
                        YEAR(sent_at) = YEAR(UTC_TIMESTAMP()) AND
                        MONTH(sent_at) = MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as sent_month,
                    SUM(CASE WHEN
                        status='failed' AND
                        YEAR(sent_at) = YEAR(UTC_TIMESTAMP()) AND
                        MONTH(sent_at) = MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as failed_month,
                    SUM(CASE WHEN
                        status='skipped' AND
                        YEAR(sent_at) = YEAR(UTC_TIMESTAMP()) AND
                        MONTH(sent_at) = MONTH(UTC_TIMESTAMP())
                        THEN 1 ELSE 0 END) as skipped_month,
                    MAX(sent_at) as last_sent_at
                FROM send_log
                GROUP BY sender_id
            """)
            rows = cur.fetchall()
            result = {}
            for r in rows:
                result[r['sender_id']] = {
                    'total_all':    int(r['total_all'] or 0),
                    'sent_all':     int(r['sent_all'] or 0),
                    'failed_all':   int(r['failed_all'] or 0),
                    'total_month':  int(r['total_month'] or 0),
                    'sent_month':   int(r['sent_month'] or 0),
                    'failed_month': int(r['failed_month'] or 0),
                    'skipped_month':int(r['skipped_month'] or 0),
                    'last_sent_at': r['last_sent_at'].strftime('%d.%m.%Y %H:%M') if r['last_sent_at'] else None,
                }
            return result
    except Exception as e:
        print(f"Monthly stats hatası: {e}")
        return {}
    finally:
        conn.close()

_SYSTEM_TABLES = {'senders', 'send_rules', 'send_log', 'suppression_list', 'audit_log', 'users', 'mail_templates', 'email_verify_jobs', 'unsubscribe_tokens', 'app_settings', 'password_reset_tokens', 'send_queue', 'send_queue_log', 'ses_notifications'}

def table_exists(table_name):
    """
    Tablonun mevcut veritabanında var olup olmadığını kontrol eder.
    information_schema sorgusu ile güvenilir kontrol yapar.
    Döner: (True/False, None veya hata_metni)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """, (get_db_config()['database'], table_name))
            row = cur.fetchone()
            return row['cnt'] > 0, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def _row_get(row: dict, key: str) -> any:
    """DictCursor sütun adlarını MySQL sürümüne göre büyük/küçük harf döndürebilir.
    Her iki durumu da dene."""
    return row.get(key) or row.get(key.upper()) or row.get(key.lower())

def list_user_tables():
    """
    Sistem tabloları (_SYSTEM_TABLES) hariç tüm kullanıcı tablolarını listeler.
    Her tablo için satır sayısı ve sütun listesi döner.
    Bulk-send sayfasında kaynak tablo seçimi için kullanılır.
    Döner: (True, [{name, row_count, columns}]) veya (False, hata_metni)
    """
    conn = get_connection()
    try:
        db_name = get_db_config()['database']
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (db_name,))
            rows = cur.fetchall()
            tnames = [
                _row_get(r, 'table_name')
                for r in rows
                if _row_get(r, 'table_name') not in _SYSTEM_TABLES
            ]

        tables = []
        for tname in tnames:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM `{tname}`")
                cnt = cur.fetchone()['cnt']
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (db_name, tname))
                cols = [_row_get(r, 'column_name') for r in cur.fetchall()]
            tables.append({'name': tname, 'row_count': cnt, 'columns': cols})
        return True, tables
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_table_preview(table_name):
    """
    Tablonun ilk 5 satırını (önizleme) ve toplam kayıt sayısını döner.
    Sistem tabloları bu fonksiyonla sorgulanamaz (güvenlik).
    Boş tablo ise sütun bilgisi information_schema'dan alınır.
    Döner: (True, {columns, preview, total}) veya (False, hata_metni)
    """
    if table_name in _SYSTEM_TABLES:
        return False, 'Sistem tabloları kaynak olarak kullanılamaz.' 
    try:
        from security import safe_identifier
        safe_identifier(table_name)
    except ValueError as e:
        return False, str(e)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
            total = cur.fetchone()['cnt']
            cur.execute(f"SELECT * FROM `{table_name}` LIMIT 5")
            rows = cur.fetchall()
            if rows:
                columns = list(rows[0].keys())
            else:
                # Tablo boşsa sütun bilgisini information_schema'dan al
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = DATABASE() AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                columns = [_row_get(r, 'column_name') for r in cur.fetchall()]
            preview = [{k: ('' if v is None else str(v)) for k, v in r.items()} for r in rows]
        return True, {'columns': columns, 'preview': preview, 'total': total}
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_table_rows(table_name, only_valid=False, only_unchecked=False):
    """
    Tablonun satırlarını döner.

    only_valid=True     → sadece is_valid=1 satırlar (toplu gönderimde filtre)
    only_unchecked=True → sadece is_valid IS NULL satırlar (doğrulama işinde
                          zaten doğrulanmış adresleri tekrar işlemez)

    is_valid kolonu yoksa her iki filtre de görmezden gelinir — tüm satırlar döner.
    Döner: (True, rows) veya (False, hata_metni)
    """
    if table_name in _SYSTEM_TABLES:
        return False, 'Sistem tabloları kaynak olarak kullanılamaz.'
    try:
        from security import safe_identifier
        safe_identifier(table_name)
    except ValueError as e:
        return False, str(e)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # is_valid kolonu var mı kontrol et
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name=%s AND column_name='is_valid'",
                (table_name,)
            )
            has_valid_col = cur.fetchone()['cnt'] > 0

            if only_valid and has_valid_col:
                # Toplu gönderim: sadece doğrulanmış adresler
                cur.execute(f"SELECT * FROM `{table_name}` WHERE is_valid = 1")
            elif only_unchecked and has_valid_col:
                # Doğrulama işi: daha önce doğrulanmamış adresler
                # is_valid IS NULL → henüz kontrol edilmemiş
                cur.execute(f"SELECT * FROM `{table_name}` WHERE is_valid IS NULL")
            else:
                cur.execute(f"SELECT * FROM `{table_name}`")
            rows = cur.fetchall()
        return True, rows
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_table_valid_counts(table_name):
    """
    is_valid kolonuna göre adres dağılımını döner.
    is_valid kolonu yoksa None döner.
    """
    if table_name in _SYSTEM_TABLES:
        return None
    try:
        from security import safe_identifier
        safe_identifier(table_name)
    except ValueError:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name=%s AND column_name='is_valid'",
                (table_name,)
            )
            if cur.fetchone()['cnt'] == 0:
                return None  # kolon yok
            cur.execute(f"""
                SELECT
                    SUM(CASE WHEN is_valid = 1    THEN 1 ELSE 0 END) as valid_count,
                    SUM(CASE WHEN is_valid = 0    THEN 1 ELSE 0 END) as invalid_count,
                    SUM(CASE WHEN is_valid = -1   THEN 1 ELSE 0 END) as risky_count,
                    SUM(CASE WHEN is_valid IS NULL THEN 1 ELSE 0 END) as unchecked_count,
                    COUNT(*) as total
                FROM `{table_name}`
            """)
            row = cur.fetchone()
            return {
                'valid':     int(row['valid_count']     or 0),
                'invalid':   int(row['invalid_count']   or 0),
                'risky':     int(row['risky_count']     or 0),
                'unchecked': int(row['unchecked_count'] or 0),
                'total':     int(row['total']           or 0),
            }
    except Exception:
        return None
    finally:
        conn.close()

def import_excel_to_table(df, table_name, column_mappings, action='new'):

    """Excel dosyasındaki veriyi DB tablosuna aktarır."""
    try:
        from security import safe_identifier
        safe_identifier(table_name)
        for col in column_mappings.values():
            safe_identifier(col)
    except ValueError as e:
        return False, 0, str(e)
    conn = get_connection()
    try:
        df = df.replace({pd.NA: None, float('nan'): None})
        
        with conn.cursor() as cur:
            exists, _ = table_exists(table_name)
            
            if action == 'overwrite' and exists:
                cur.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                exists = False
            
            if not exists:
                create_table_sql = generate_create_table_sql(table_name, df, column_mappings)
                cur.execute(create_table_sql)
            
            db_columns = list(column_mappings.values())
            
            if action == 'append_dedupe' and exists:
                temp_table = f"temp_{table_name}_{int(time.time())}"
                insert_temp_data_sql = generate_create_table_sql(temp_table, df, column_mappings)
                cur.execute(insert_temp_data_sql)

                insert_data(cur, temp_table, df, column_mappings)
                
                join_conditions = ' AND '.join([f"t.`{col}` = m.`{col}`" for col in db_columns])
                
                cur.execute(f"""
                    INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in db_columns])})
                    SELECT {', '.join([f'`{col}`' for col in db_columns])}
                    FROM `{temp_table}` t
                    WHERE NOT EXISTS (
                        SELECT 1 FROM `{table_name}` m 
                        WHERE {join_conditions}
                    )
                """)
                inserted = cur.rowcount
                
                cur.execute(f"DROP TABLE `{temp_table}`")
            else:
                inserted = insert_data(cur, table_name, df, column_mappings)
            
            conn.commit()
            
            if action == 'append_dedupe' and exists:
                return True, inserted, f"{inserted} yeni kayıt eklendi (tekrarlayanlar atlandı)"
            elif action == 'append' and exists:
                return True, inserted, f"{inserted} kayıt mevcut tabloya eklendi"
            else:
                return True, inserted, f"{inserted} kayıt '{table_name}' tablosuna aktarıldı"
            
    except Exception as e:
        conn.rollback()
        return False, 0, str(e)
    finally:
        conn.close()

def generate_create_table_sql(table_name, df, column_mappings):

    """DataFrame sütunlarından CREATE TABLE SQL'i üretir."""
    columns = []
    
    for excel_col, db_col in column_mappings.items():
        if excel_col not in df.columns:
            continue
            
        series = df[excel_col]
        if pd.api.types.is_integer_dtype(series):
            col_type = "BIGINT"
        elif pd.api.types.is_float_dtype(series):
            col_type = "DOUBLE"
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_type = "DATETIME"
        elif pd.api.types.is_bool_dtype(series):
            col_type = "BOOLEAN"
        else:
            max_len = series.astype(str).str.len().max()
            if pd.isna(max_len) or max_len < 1:
                col_type = "TEXT"
            elif max_len <= 255:
                # Biraz pay bırak ama TEXT'e geçme
                col_type = f"VARCHAR({min(int(max_len) * 2 or 50, 255)})"
            else:
                col_type = "TEXT"
        
        columns.append(f"`{db_col}` {col_type}")
    
    create_sql = f"""
        CREATE TABLE `{table_name}` (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            {', '.join(columns)},
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    return create_sql

def insert_data(cursor, table_name, df, column_mappings):

    """DataFrame satırlarını tabloya toplu INSERT yapar."""
    db_columns = list(column_mappings.values())
    placeholders = ', '.join(['%s'] * len(db_columns))
    columns_str = ', '.join([f'`{col}`' for col in db_columns])
    
    sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
    
    rows = []
    for _, row in df.iterrows():
        values = []
        for excel_col in column_mappings.keys():
            if excel_col in df.columns:
                val = row[excel_col]
                if pd.isna(val):
                    values.append(None)
                else:
                    values.append(val)
            else:
                values.append(None)
        rows.append(values)
    
    cursor.executemany(sql, rows)
    return cursor.rowcount

# ── Suppression List Yönetimi ──────────────────────────────────────────
def get_suppression_list(page=1, per_page=50, search=None, reason=None):
    """Suppression listesini filtreli ve sayfalı döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            wheres, params = [], []
            if search:
                wheres.append("email LIKE %s")
                params.append(f'%{search}%')
            if reason:
                wheres.append("reason = %s")
                params.append(reason)
            where_clause = ('WHERE ' + ' AND '.join(wheres)) if wheres else ''

            cur.execute(f"SELECT COUNT(*) as cnt FROM suppression_list {where_clause}", params)
            total = cur.fetchone()['cnt']

            offset = (page - 1) * per_page
            cur.execute(
                f"SELECT * FROM suppression_list {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [per_page, offset]
            )
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r.get('created_at'), datetime.datetime):
                    r['created_at'] = r['created_at'].strftime('%d.%m.%Y %H:%M')
            return rows, total
    except Exception as e:
        return [], 0
    finally:
        conn.close()

def delete_suppression(email):
    """Suppression listesinden e-postayı kaldırır. Döner: (True/False, mesaj)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM suppression_list WHERE email=%s", (email,))
        conn.commit()
        return True, 'Silindi.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def purge_suppressed_from_table(table_name, email_col):
    """Suppression listesindeki e-postaları verilen tablodan siler.
    Önce hosting DB'den listeyi çeker, yoksa local suppression_list'e bakar.
    """
    if table_name in _SYSTEM_TABLES:
        return False, 0, 'Sistem tabloları değiştirilemez.'
    try:
        from security import safe_identifier
        safe_identifier(table_name)
        safe_identifier(email_col)
    except ValueError as e:
        return False, 0, str(e)

    # Suppression listesini al — önce hosting'den dene
    suppressed_emails = set()
    unsub_app_url = os.getenv('UNSUB_APP_URL', '').rstrip('/')
    api_key       = os.getenv('UNSUB_API_KEY', '')
    if unsub_app_url:
        try:
            import urllib.request, json as _j
            req = urllib.request.Request(
                f"{unsub_app_url}/api/suppression-list",
                headers={'X-API-Key': api_key},
                method='GET'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _j.loads(resp.read())
                if data.get('success'):
                    suppressed_emails = {r['email'].lower() for r in data.get('data', [])}
                    print(f"Hosting'den {len(suppressed_emails)} suppression kaydı alındı.")
        except Exception as e:
            print(f"Hosting suppression listesi alınamadı, local'e bakılıyor: {e}")

    # Hosting'den alınamazsa local suppression_list'e bak
    if not suppressed_emails:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM suppression_list")
                suppressed_emails = {r['email'].lower() for r in cur.fetchall()}
        finally:
            conn.close()

    if not suppressed_emails:
        return True, 0, 'Suppression listesi boş, silinecek kayıt yok.'

    # Local tablodan suppression'daki adresleri sil
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(suppressed_emails))
            cur.execute(
                f"DELETE FROM `{table_name}` WHERE LOWER(`{email_col}`) IN ({placeholders})",
                list(suppressed_emails)
            )
            deleted = cur.rowcount
        conn.commit()
        return True, deleted, f'{deleted} kayıt silindi.'
    except Exception as e:
        conn.rollback()
        return False, 0, str(e)
    finally:
        conn.close()

def get_suppression_stats():

    """Suppression listesi sebep bazlı istatistiklerini döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT reason, COUNT(*) as cnt
                FROM suppression_list
                GROUP BY reason
            """)
            rows = cur.fetchall()
            stats = {r['reason']: r['cnt'] for r in rows}
            cur.execute("SELECT COUNT(*) as cnt FROM suppression_list")
            stats['total'] = cur.fetchone()['cnt']
        return stats
    except Exception:
        return {'total': 0}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
#  KUYRUK FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════

def queue_create(name, sender_id, rule_id, source_type, email_col, var_cols,
                 subject_tpl, body_tpl, html_mode, include_unsub, delay_ms,
                 batch_size, batch_wait_min,
                 source_table=None, source_excel=None,
                 attachment_name=None, attachment_data=None):
    """Kuyruğa yeni görev ekler, görev ID döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO send_queue
                    (name, sender_id, rule_id, source_type, source_table, source_excel,
                     email_col, var_cols, subject_tpl, body_tpl, html_mode, include_unsub,
                     delay_ms, attachment_name, attachment_data,
                     batch_size, batch_wait_min, status, next_run_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',UTC_TIMESTAMP())
            """, (name, sender_id, rule_id, source_type, source_table,
                  source_excel, email_col, var_cols, subject_tpl, body_tpl,
                  int(html_mode), int(include_unsub), delay_ms,
                  attachment_name, attachment_data,
                  batch_size, batch_wait_min))
            qid = cur.lastrowid
        conn.commit()
        return qid
    finally:
        conn.close()


def queue_list(limit=50):
    """Son görevleri döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT q.*, s.name as sender_name, s.email as sender_email
                FROM send_queue q
                LEFT JOIN senders s ON s.id = q.sender_id
                ORDER BY q.created_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            for r in rows:
                for k in ('started_at','finished_at','next_run_at','created_at'):
                    if isinstance(r.get(k), datetime.datetime):
                        r[k] = r[k].isoformat()
                r.pop('source_excel', None)
                r.pop('attachment_data', None)
                r.pop('body_tpl', None)
            return rows
    finally:
        conn.close()


def queue_get(qid):
    """Tek görevi tam haliyle döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM send_queue WHERE id=%s", (qid,))
            return cur.fetchone()
    finally:
        conn.close()


def queue_update_status(qid, status, **kwargs):
    """Görev durumunu günceller. kwargs: current_offset, sent_count, vb."""
    fields = ['status=%s']
    vals   = [status]
    for k, v in kwargs.items():
        fields.append(f'{k}=%s')
        vals.append(v)
    if status == 'running' and 'started_at' not in kwargs:
        fields.append('started_at=UTC_TIMESTAMP()')
    if status in ('done', 'cancelled') and 'finished_at' not in kwargs:
        fields.append('finished_at=UTC_TIMESTAMP()')
    vals.append(qid)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE send_queue SET {','.join(fields)} WHERE id=%s", vals)
        conn.commit()
    finally:
        conn.close()


def queue_log_item(qid, email, status, error_msg=None):
    """Tek mail sonucunu queue_log'a yazar."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO send_queue_log (queue_id, email, status, error_msg)
                VALUES (%s,%s,%s,%s)
            """, (qid, email, status, error_msg))
        conn.commit()
    finally:
        conn.close()


def queue_get_progress(qid):
    """UI polling için ilerleme bilgisi döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, status, total_count, current_offset,
                       sent_count, failed_count, skipped_count,
                       next_run_at, started_at, finished_at, batch_size, batch_wait_min
                FROM send_queue WHERE id=%s
            """, (qid,))
            row = cur.fetchone()
            if not row:
                return None
            for k in ('next_run_at','started_at','finished_at'):
                if isinstance(row.get(k), datetime.datetime):
                    row[k] = row[k].isoformat()
            # Son 20 log satırı
            cur.execute("""
                SELECT email, status, error_msg, sent_at
                FROM send_queue_log
                WHERE queue_id=%s ORDER BY id DESC LIMIT 20
            """, (qid,))
            logs = cur.fetchall()
            for l in logs:
                if isinstance(l.get('sent_at'), datetime.datetime):
                    l['sent_at'] = l['sent_at'].isoformat()
            row['recent_logs'] = list(reversed(logs))
            return row
    finally:
        conn.close()


def queue_cancel(qid):
    """
    Görevi iptal eder.
    Sadece pending/running/paused görevler iptal edilebilir.
    'done' veya zaten 'cancelled' olana dokunulmaz.
    Döner: True (başarılı) veya False (görev bulunamadı/uygun durum değil)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE send_queue SET status='cancelled', finished_at=UTC_TIMESTAMP() WHERE id=%s AND status IN ('pending','running','paused')",
                (qid,)
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def queue_get_due():
    """
    Şu an işlenmesi gereken görevleri döner.
    Koşullar:
      - Durum 'pending' veya 'paused' olmalı
      - next_run_at geçmiş olmalı (zamanı gelmiş)
    En fazla 5 görev döner — cron her 5 dakikada çalışırken paralel yükü sınırlar.
    Sıralama: en eski next_run_at önce işlenir (FIFO).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM send_queue
                WHERE status IN ('pending','paused')
                  AND next_run_at <= UTC_TIMESTAMP()
                ORDER BY next_run_at ASC
                LIMIT 5
            """)
            return cur.fetchall()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
#  KULLANICI FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════

def _hash_password(password: str) -> str:
    """
    Şifreyi bcrypt ile hashler.
    bcrypt.gensalt() her seferinde farklı salt üretir — rainbow table saldırılarına karşı.
    Dönen string: '$2b$12$...' formatında 60 karakter bcrypt hash.
    """
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _check_password(password: str, hashed: str) -> bool:

    """Şifreyi bcrypt hash ile doğrular."""
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def user_authenticate(username: str, password: str):
    """Kullanıcı adı/şifre doğrular. Başarılıysa user dict döner, değilse None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s AND is_active=1", (username,))
            user = cur.fetchone()
        if not user or not _check_password(password, user['password_hash']):
            return None
        # last_login güncelle
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET last_login=UTC_TIMESTAMP() WHERE id=%s", (user['id'],))
        conn.commit()
        return user
    finally:
        conn.close()

def user_create(username: str, password: str, email: str = '', role: str = 'editor'):

    """Yeni kullanıcı oluşturur, şifreyi bcrypt ile hashler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (%s,%s,%s,%s)",
                (username, email, _hash_password(password), role)
            )
        conn.commit()
        return True, "Kullanıcı oluşturuldu."
    except Exception as e:
        conn.rollback()
        if 'Duplicate' in str(e):
            return False, "Bu kullanıcı adı zaten kullanılıyor."
        return False, str(e)
    finally:
        conn.close()

def user_list():

    """Tüm aktif kullanıcıları listeler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email, role, is_active, theme, last_login, created_at FROM users ORDER BY id")
            rows = cur.fetchall()
            for r in rows:
                for k in ('last_login', 'created_at'):
                    if isinstance(r.get(k), datetime.datetime):
                        r[k] = r[k].isoformat()
            return rows
    finally:
        conn.close()

def user_update(uid: int, **kwargs):
    """role, email, is_active, password güncelleyebilir."""
    if 'password' in kwargs:
        kwargs['password_hash'] = _hash_password(kwargs.pop('password'))
    if not kwargs:
        return False, "Güncellenecek alan yok."
    fields = ', '.join(f"{k}=%s" for k in kwargs)
    vals   = list(kwargs.values()) + [uid]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {fields} WHERE id=%s", vals)
        conn.commit()
        return True, "Güncellendi."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def user_delete(uid: int):

    """Kullanıcıyı is_active=0 yaparak pasifleştirir."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Son admin silinemesin
            cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role='admin' AND is_active=1 AND id!=%s", (uid,))
            row = cur.fetchone()
            if row['cnt'] == 0:
                cur.execute("SELECT role FROM users WHERE id=%s", (uid,))
                u = cur.fetchone()
                if u and u['role'] == 'admin':
                    return False, "Son admin silinemez."
            cur.execute("DELETE FROM users WHERE id=%s", (uid,))
        conn.commit()
        return True, "Silindi."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def user_count():

    """Aktif kullanıcı sayısını döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM users")
            return cur.fetchone()['cnt']
    finally:
        conn.close()


def user_set_theme(uid: int, theme: str):
    """Kullanıcının seçtiği temayı DB'ye kaydeder."""
    VALID = {"charcoal","black","lavender","mint","sage","coral","teal"}
    if theme not in VALID:
        return False, "Geçersiz tema adı."
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET theme=%s WHERE id=%s", (theme, uid))
        conn.commit()
        return True, "Tema kaydedildi."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
#  SES BOUNCE / COMPLAINT BİLDİRİMLERİ
# ══════════════════════════════════════════════════════════════════════

def ses_notification_save(notif_type, recipient, bounce_type=None,
                          bounce_sub=None, feedback_id=None,
                          sender_id=None, raw_json=None):
    """SNS'ten gelen bounce/complaint/delivery bildirimini kaydeder."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ses_notifications
                (sender_id, notif_type, recipient, bounce_type, bounce_sub, feedback_id, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (sender_id, notif_type, recipient, bounce_type,
                  bounce_sub, feedback_id, raw_json))
        conn.commit()
    except Exception as e:
        print(f"ses_notification_save hatası: {e}")
    finally:
        conn.close()


def ses_reputation_stats(sender_id=None, days=7):
    """
    Son N günün bounce/complaint oranını hesaplar.
    sender_id=None → tüm SES göndericiler.
    Döner: {total, bounces, complaints, bounce_rate, complaint_rate}
    AWS limitleri: bounce < %5, complaint < %0.1
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            since = (datetime.datetime.utcnow()
                     - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            # Toplam gönderim (send_log'dan)
            if sender_id:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM send_log "
                    "WHERE sender_id=%s AND status='sent' AND sent_at >= %s",
                    (sender_id, since)
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM send_log "
                    "WHERE status='sent' AND sent_at >= %s", (since,)
                )
            total = cur.fetchone()['cnt'] or 0

            # Bounce sayısı
            q = ("SELECT COUNT(*) as cnt FROM ses_notifications "
                 "WHERE notif_type='Bounce' AND received_at >= %s")
            params = [since]
            if sender_id:
                q += " AND sender_id=%s"
                params.append(sender_id)
            cur.execute(q, params)
            bounces = cur.fetchone()['cnt'] or 0

            # Complaint sayısı
            q = ("SELECT COUNT(*) as cnt FROM ses_notifications "
                 "WHERE notif_type='Complaint' AND received_at >= %s")
            params = [since]
            if sender_id:
                q += " AND sender_id=%s"
                params.append(sender_id)
            cur.execute(q, params)
            complaints = cur.fetchone()['cnt'] or 0

        bounce_rate    = round(bounces    / total * 100, 3) if total else 0
        complaint_rate = round(complaints / total * 100, 3) if total else 0
        return {
            'total':          total,
            'bounces':        bounces,
            'complaints':     complaints,
            'bounce_rate':    bounce_rate,
            'complaint_rate': complaint_rate,
            'bounce_ok':      bounce_rate    < 5.0,
            'complaint_ok':   complaint_rate < 0.1,
            'days':           days,
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
#  UYGULAMA AYARLARI (app_settings tablosu)
# ══════════════════════════════════════════════════════════════════════

def setting_get(key: str, default=None):
    """Bir ayarı okur. Yoksa default döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key_name=%s", (key,))
            row = cur.fetchone()
            return row['value'] if row else default
    finally:
        conn.close()


def setting_set(key: str, value: str):
    """Bir ayarı kaydeder (INSERT OR UPDATE)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (key_name, value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE value=VALUES(value), updated_at=NOW()",
                (key, value)
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"setting_set hatası: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def smtp_skip_domains_get() -> list[str]:
    """
    SMTP doğrulamasından muaf tutulacak domainleri döner.
    DB'de kayıt yoksa verifier.py'deki varsayılan listeyi kullanır.
    """
    import json
    val = setting_get('smtp_skip_domains')
    if val is None:
        return []   # Boş → verifier.py varsayılanları kullanır
    try:
        domains = json.loads(val)
        return [d.strip().lower() for d in domains if d.strip()]
    except Exception:
        return [d.strip().lower() for d in val.split(',') if d.strip()]


def smtp_skip_domains_set(domains: list[str]) -> bool:
    """SMTP muaf domain listesini kaydeder."""
    import json
    clean = sorted({d.strip().lower() for d in domains if d.strip()})
    return setting_set('smtp_skip_domains', json.dumps(clean))


# ══════════════════════════════════════════════════════════════════════
#  E-POSTA DOĞRULAMA İŞ FONKSİYONLARI (email_verify_jobs tablosu)
# ══════════════════════════════════════════════════════════════════════

def verify_job_create(job_name, table_name, email_col, mode='mx', threads=10,
                      user_id=None, username=None):
    """Yeni doğrulama işi oluşturur, toplam satır sayısını tablondan okur."""
    try:
        from security import safe_identifier
        safe_identifier(table_name)
        # email_col: tire ve boşluğu alt çizgiye çevir, sonra kontrol et
        # Örn: "e-posta" → "e_posta", "E Posta" → "E_Posta"
        email_col_safe = email_col.replace('-', '_').replace(' ', '_')
        safe_identifier(email_col_safe)
        email_col = email_col_safe
    except ValueError as e:
        return False, f"Geçersiz kolon adı '{email_col}': {e}"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # is_valid kolonu var mı kontrol et
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name=%s AND column_name='is_valid'",
                (table_name,)
            )
            has_valid_col = cur.fetchone()['cnt'] > 0

            if has_valid_col:
                # Sadece henüz doğrulanmamış (is_valid IS NULL) adresleri say
                # Daha önce doğrulanmışları tekrar işlemeyeceğiz
                cur.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}` WHERE is_valid IS NULL")
            else:
                # is_valid kolonu yok — tüm satırlar işlenecek
                cur.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
            total = cur.fetchone()['cnt']
            cur.execute(
                """INSERT INTO email_verify_jobs
                   (job_name, table_name, email_col, mode, threads, total_count,
                    created_by_id, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (job_name, table_name, email_col, mode, threads, total,
                 user_id, username)
            )
            job_id = cur.lastrowid
        conn.commit()
        return True, job_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def verify_job_update(job_id, **kwargs):
    """İş durumunu ve istatistiklerini günceller."""
    if not kwargs:
        return
    fields = ', '.join(f"{k}=%s" for k in kwargs)
    vals   = list(kwargs.values()) + [job_id]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE email_verify_jobs SET {fields} WHERE id=%s", vals)
        conn.commit()
    except Exception as e:
        print(f"verify_job_update hatası: {e}")
    finally:
        conn.close()


def export_verified_table(source_table, new_table_name, include_risky=False):
    """
    Doğrulanmış (is_valid=1) adresleri kaynak tablodan yeni bir tabloya kopyalar.
    include_risky=True ise is_valid=-1 (riskli) adresler de dahil edilir.

    Döner: (True, satır_sayısı) veya (False, hata_metni)
    """
    try:
        from security import safe_identifier
        safe_identifier(source_table)
        safe_identifier(new_table_name)
    except ValueError as e:
        return False, str(e)

    # Hedef tablo sistem tablosu olmamalı
    if new_table_name in _SYSTEM_TABLES:
        return False, f"'{new_table_name}' sistem tablosu adıdır, kullanılamaz."

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Kaynak tabloda is_valid kolonu var mı?
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name=%s AND column_name='is_valid'",
                (source_table,)
            )
            if cur.fetchone()['cnt'] == 0:
                return False, "Kaynak tabloda is_valid kolonu yok. Önce Liste Temizleme yapın."

            # Hedef tablo zaten varsa hata ver
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_schema=DATABASE() AND table_name=%s",
                (new_table_name,)
            )
            if cur.fetchone()['cnt'] > 0:
                return False, f"'{new_table_name}' tablosu zaten mevcut. Farklı bir isim seçin."

            # Filtre koşulu: sadece geçerli veya geçerli+riskli
            if include_risky:
                where_clause = "WHERE is_valid IN (1, -1)"
                filter_label = "geçerli+riskli"
            else:
                where_clause = "WHERE is_valid = 1"
                filter_label = "geçerli"

            # CREATE TABLE ... AS SELECT ile kopyala
            # is_valid kolonu yeni tabloya da taşınır (referans için)
            cur.execute(f"""
                CREATE TABLE `{new_table_name}`
                AS SELECT * FROM `{source_table}` {where_clause}
            """)

            # Kaç satır kopyalandı?
            cur.execute(f"SELECT COUNT(*) as cnt FROM `{new_table_name}`")
            row_count = cur.fetchone()['cnt']

        conn.commit()
        return True, row_count

    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def verify_job_list():
    """Tüm doğrulama işlerini (en yeniden eskiye) listeler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM email_verify_jobs
                ORDER BY created_at DESC
                LIMIT 100
            """)
            rows = cur.fetchall()
            for r in rows:
                for k in ('started_at', 'finished_at', 'created_at'):
                    if isinstance(r.get(k), datetime.datetime):
                        r[k] = r[k].isoformat()
            return rows
    finally:
        conn.close()


def verify_job_list_pending():
    """
    Worker için: status='pending' olan işleri döner (eski→yeni sıra).
    Aynı anda yalnızca bir iş çalıştığından sadece pending alınır;
    running olanlar worker yeniden başlamadıkça dokunulmaz.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM email_verify_jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            return cur.fetchall()
    finally:
        conn.close()


def verify_job_get(job_id):
    """Tek bir doğrulama işini döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM email_verify_jobs WHERE id=%s", (job_id,))
            r = cur.fetchone()
            if r:
                for k in ('started_at', 'finished_at', 'created_at'):
                    if isinstance(r.get(k), datetime.datetime):
                        r[k] = r[k].isoformat()
            return r
    finally:
        conn.close()


def verify_job_cancel(job_id):
    """Çalışan veya bekleyen bir işi iptal eder."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE email_verify_jobs SET status='cancelled' WHERE id=%s AND status IN ('pending','running')",
                (job_id,)
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def verify_job_add_is_valid_column(table_name, email_col):
    """
    Kullanıcı tablosuna is_valid kolonu ekler (yoksa).
    is_valid: NULL=kontrol edilmedi, 1=geçerli, 0=geçersiz, -1=bilinmiyor
    """
    try:
        from security import safe_identifier
        safe_identifier(table_name)
        safe_identifier(email_col)
    except ValueError as e:
        return False, str(e)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # MySQL 5.7 uyumlu: önce kolon varlığını kontrol et
            db_name = get_db_config()['database']
            cur.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s AND column_name='is_valid'",
                (db_name, table_name)
            )
            if cur.fetchone()['cnt'] == 0:
                cur.execute(f"""
                    ALTER TABLE `{table_name}`
                    ADD COLUMN is_valid TINYINT(1) DEFAULT NULL
                    COMMENT 'E-posta geçerliliği: 1=geçerli 0=geçersiz -1=bilinmiyor NULL=kontrol edilmedi'
                """)
        conn.commit()
        return True, 'Kolon eklendi.'
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def verify_job_mark_email(table_name, email_col, email, is_valid_val):
    """Tek satıra is_valid değeri yazar. (Geriye dönük uyumluluk için korundu)"""
    verify_job_mark_emails_bulk(table_name, email_col, [(email, is_valid_val, '')])


def verify_job_mark_emails_bulk(table_name, email_col, results):
    """
    Toplu is_valid güncellemesi — tek SQL ile tüm batch yazılır.
    results: [(email, is_valid_val, status), ...]
    1000 mail için 1000 ayrı UPDATE yerine tek CASE WHEN sorgusu kullanır.
    """
    if not results:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # CASE WHEN ile tek sorguda toplu güncelleme
            # UPDATE t SET is_valid = CASE WHEN email=? THEN ? ... END WHERE email IN (?,?,...)
            case_parts = ' '.join(
                f"WHEN `{email_col}`=%s THEN %s"
                for _ in results
            )
            in_placeholders = ','.join(['%s'] * len(results))
            sql = (
                f"UPDATE `{table_name}` SET is_valid = CASE {case_parts} "
                f"ELSE is_valid END "
                f"WHERE `{email_col}` IN ({in_placeholders})"
            )
            # Parametreler: CASE için (email, val) çiftleri + IN için emailler
            params = []
            for email, iv, _ in results:
                params.extend([email, iv])
            for email, iv, _ in results:
                params.append(email)
            cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        print(f"verify_job_mark_emails_bulk hatası: {e}")
        conn.rollback()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
#  ŞİFRE SIFIRLAMA TOKEN FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════

def password_reset_create_token(user_id: int, username: str) -> str:
    """
    Kullanıcı için şifre sıfırlama tokeni oluşturur.
    Önceki kullanılmamış tokenler silinir. Token 1 saat geçerlidir.
    """
    import secrets
    token = secrets.token_urlsafe(32)
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Önceki geçersiz tokenları temizle
            cur.execute(
                "DELETE FROM password_reset_tokens WHERE user_id=%s",
                (user_id,)
            )
            cur.execute(
                "INSERT INTO password_reset_tokens (token, user_id, username, expires_at) VALUES (%s,%s,%s,%s)",
                (token, user_id, username, expires.strftime('%Y-%m-%d %H:%M:%S'))
            )
        conn.commit()
        return token
    finally:
        conn.close()


def password_reset_verify_token(token: str):
    """
    Token geçerli ve kullanılmamışsa (user_id, username) döner.
    Geçersiz/süresi dolmuş/kullanılmışsa None döner.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM password_reset_tokens WHERE token=%s AND used=0",
                (token,)
            )
            row = cur.fetchone()
            if not row:
                return None
            expires = row['expires_at']
            if isinstance(expires, str):
                expires = datetime.datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.utcnow() > expires:
                return None  # Süresi dolmuş
            return row
    finally:
        conn.close()


def password_reset_use_token(token: str, new_password_hash: str) -> bool:
    """
    Tokeni kullanılmış olarak işaretler ve kullanıcı şifresini günceller.
    Tek işlemde (transaction) yapar.
    """
    row = password_reset_verify_token(token)
    if not row:
        return False
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE password_reset_tokens SET used=1 WHERE token=%s",
                (token,)
            )
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (new_password_hash, row['user_id'])
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"password_reset_use_token hatası: {e}")
        return False
    finally:
        conn.close()


def get_user_by_username(username: str):
    """Kullanıcı adına göre kullanıcı kaydını döner. Bulunamazsa None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s AND is_active=1", (username,))
            return cur.fetchone()
    finally:
        conn.close()


def get_user_by_email(email: str):
    """E-posta adresine göre aktif kullanıcı kaydını döner. Bulunamazsa None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s AND is_active=1", (email,))
            return cur.fetchone()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
#  ŞABLON FONKSİYONLARI (mail_templates tablosu)
# ══════════════════════════════════════════════════════════════════════

def template_list(tpl_type=None):
    """
    Kayıtlı şablonları listeler.
    tpl_type: 'subject', 'body' veya None (tümü)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if tpl_type:
                # Belirli tip için filtrele
                cur.execute(
                    "SELECT * FROM mail_templates WHERE type=%s ORDER BY name",
                    (tpl_type,)
                )
            else:
                # Tüm şablonları getir
                cur.execute("SELECT * FROM mail_templates ORDER BY type, name")
            rows = cur.fetchall()
            # Datetime alanlarını string'e çevir
            for r in rows:
                for k in ('created_at', 'updated_at'):
                    if isinstance(r.get(k), datetime.datetime):
                        r[k] = r[k].isoformat()
            return rows
    finally:
        conn.close()


def template_get(tpl_id):
    """Tek şablonu ID'ye göre getirir."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mail_templates WHERE id=%s", (tpl_id,))
            return cur.fetchone()
    finally:
        conn.close()


def template_create(tpl_type, name, content):
    """Yeni şablon oluşturur, yeni ID'yi döner."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mail_templates (type, name, content) VALUES (%s,%s,%s)",
                (tpl_type, name.strip(), content)
            )
            new_id = cur.lastrowid
        conn.commit()
        return True, new_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def template_update(tpl_id, name=None, content=None):
    """Şablonu günceller."""
    fields, vals = [], []
    if name    is not None: fields.append("name=%s");    vals.append(name.strip())
    if content is not None: fields.append("content=%s"); vals.append(content)
    if not fields:
        return False, "Güncellenecek alan yok."
    vals.append(tpl_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE mail_templates SET {','.join(fields)} WHERE id=%s", vals)
        conn.commit()
        return True, "Güncellendi."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def template_delete(tpl_id):
    """Şablonu siler."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mail_templates WHERE id=%s", (tpl_id,))
        conn.commit()
        return True, "Silindi."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
