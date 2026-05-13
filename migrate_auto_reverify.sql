-- migrate_auto_reverify.sql
-- Otomatik yeniden doğrulama zamanlamaları tablosu
-- Calistirma: mysql -u USER -p DBNAME < migrate_auto_reverify.sql

CREATE TABLE IF NOT EXISTS `auto_reverify_schedules` (
    `id`              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `table_name`      VARCHAR(200)    NOT NULL  COMMENT 'Yeniden doğrulanacak tablo',
    `email_col`       VARCHAR(200)    NOT NULL  DEFAULT 'email' COMMENT 'E-posta kolonu',
    `mode`            ENUM('format','mx','smtp') NOT NULL DEFAULT 'mx',
    `threads`         TINYINT UNSIGNED NOT NULL DEFAULT 10,
    `interval_days`   SMALLINT UNSIGNED NOT NULL DEFAULT 90
                      COMMENT 'Kaç günde bir çalışsın (min 1, max 365)',
    `target`          ENUM('all','valid_only','invalid_only','unknown_only') NOT NULL DEFAULT 'all'
                      COMMENT 'Hangi adresler yeniden doğrulanacak',
    `is_active`       TINYINT(1)      NOT NULL DEFAULT 1,
    `last_run_at`     DATETIME        DEFAULT NULL COMMENT 'Son çalışma zamanı (UTC)',
    `next_run_at`     DATETIME        DEFAULT NULL COMMENT 'Sonraki çalışma zamanı (UTC)',
    `last_job_id`     BIGINT          DEFAULT NULL COMMENT 'Son oluşturulan verify_job id',
    `created_by_id`   INT             DEFAULT NULL,
    `created_by`      VARCHAR(100)    DEFAULT NULL,
    `created_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY  `uniq_table_col` (`table_name`, `email_col`),
    INDEX       `idx_active_next` (`is_active`, `next_run_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Otomatik e-posta yeniden doğrulama zamanlamaları';
