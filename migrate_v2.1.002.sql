-- ============================================================
-- Migration: v2.1.002 — Günlük Kota Takibi
-- Çalıştırma: MySQL/MariaDB client veya phpMyAdmin
-- Güvenli: IF NOT EXISTS ile — zaten varsa hata vermez
-- ============================================================

-- 1. senders tablosuna daily_limit kolonu ekle
-- 0 = limitsiz, >0 = o kadar mail/gün
ALTER TABLE senders
    ADD COLUMN IF NOT EXISTS daily_limit INT NOT NULL DEFAULT 0
        COMMENT 'Günlük maksimum gönderim (0=limitsiz)';

-- 2. Mevcut sender'lar için varsayılan değer (isteğe göre güncelleyin)
-- Örnek: Tüm API sender'ların limitini 80 yap
-- UPDATE senders SET daily_limit=80 WHERE sender_mode='api';

-- 3. Kontrol
SELECT id, name, sender_mode, daily_limit FROM senders ORDER BY id;

-- ============================================================
-- Migration: v2.1.002 — Warmup Planı
-- ============================================================

-- 2. senders tablosuna warmup kolonları ekle
ALTER TABLE senders
    ADD COLUMN IF NOT EXISTS warmup_enabled TINYINT(1) NOT NULL DEFAULT 0
        COMMENT '1 = warmup planı aktif',
    ADD COLUMN IF NOT EXISTS warmup_start_date DATE NULL
        COMMENT 'Warmup başlangıç tarihi (NULL = bugün başlar)';

-- Warmup aktifleştirme örneği (sender_id=1 için):
-- UPDATE senders SET warmup_enabled=1, warmup_start_date=CURDATE() WHERE id=1;

-- Warmup ilerleme kontrolü:
-- SELECT id, name, warmup_enabled, warmup_start_date,
--        DATEDIFF(CURDATE(), warmup_start_date)+1 AS warmup_day
-- FROM senders WHERE warmup_enabled=1;
