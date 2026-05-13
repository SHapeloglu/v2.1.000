-- migrate_greylist_retry.sql
-- Greylisting retry kuyrugu tablosu
-- Calistirma: mysql -u USER -p DBNAME < migrate_greylist_retry.sql

CREATE TABLE IF NOT EXISTS `greylist_retry_queue` (
    `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `email`       VARCHAR(254)    NOT NULL  COMMENT 'Dogrulanacak adres',
    `table_name`  VARCHAR(200)    NOT NULL  COMMENT 'Kaynak tablo',
    `email_col`   VARCHAR(200)    NOT NULL  COMMENT 'E-posta kolonu',
    `job_id`      BIGINT          DEFAULT NULL COMMENT 'Kaynak verify job ID',
    `mx_server`   VARCHAR(255)    DEFAULT NULL COMMENT 'MX sunucusu (tekrar baglanti icin)',
    `attempt`     TINYINT         NOT NULL DEFAULT 1 COMMENT 'Kacinci deneme (max 3)',
    `status`      ENUM('pending','done','exhausted') NOT NULL DEFAULT 'pending',
    `retry_after` DATETIME        NOT NULL  COMMENT 'Bu zamandan once deneme yapma',
    `last_result` VARCHAR(50)     DEFAULT NULL COMMENT 'Son SMTP sonucu: valid/invalid/unknown/no_mx',
    `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_status_retry` (`status`, `retry_after`),
    INDEX `idx_email`        (`email`(100)),
    INDEX `idx_job`          (`job_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Greylisting retry kuyrugu - unknown SMTP sonuclari icin';
