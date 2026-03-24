-- MailSender Pro - API Gönderici Migration
-- MySQL 5.7+ uyumlu

DROP PROCEDURE IF EXISTS migrate_api_columns;

DELIMITER $$

CREATE PROCEDURE migrate_api_columns()
BEGIN
    -- api_host
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='senders' AND COLUMN_NAME='api_host') THEN
        ALTER TABLE senders ADD COLUMN api_host VARCHAR(500) COMMENT 'API sunucu host';
    END IF;

    -- api_endpoint
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='senders' AND COLUMN_NAME='api_endpoint') THEN
        ALTER TABLE senders ADD COLUMN api_endpoint VARCHAR(500) COMMENT 'API endpoint';
    END IF;

    -- api_auth_type
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='senders' AND COLUMN_NAME='api_auth_type') THEN
        ALTER TABLE senders ADD COLUMN api_auth_type VARCHAR(100) COMMENT 'Auth header tipi';
    END IF;

    -- api_auth_token
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='senders' AND COLUMN_NAME='api_auth_token') THEN
        ALTER TABLE senders ADD COLUMN api_auth_token TEXT COMMENT 'Fernet şifreli API token';
    END IF;

    -- api_method
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='senders' AND COLUMN_NAME='api_method') THEN
        ALTER TABLE senders ADD COLUMN api_method VARCHAR(10) DEFAULT 'POST';
    END IF;

    -- api_payload_tpl
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='senders' AND COLUMN_NAME='api_payload_tpl') THEN
        ALTER TABLE senders ADD COLUMN api_payload_tpl TEXT COMMENT 'JSON payload template';
    END IF;

    -- sender_mode ENUM'una api ekle
    ALTER TABLE senders MODIFY COLUMN sender_mode ENUM('smtp','ses','api') NOT NULL DEFAULT 'smtp';

END$$

DELIMITER ;

CALL migrate_api_columns();
DROP PROCEDURE IF EXISTS migrate_api_columns;

-- Sonuç kontrolü
SELECT COLUMN_NAME, COLUMN_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'senders'
  AND COLUMN_NAME IN ('sender_mode','api_host','api_endpoint','api_auth_type','api_auth_token','api_method','api_payload_tpl')
ORDER BY ORDINAL_POSITION;
