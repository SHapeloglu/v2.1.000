-- suppression_list performans iyileştirmesi
-- email kolonu VARCHAR(500) → VARCHAR(254) (RFC 5321 max)
-- Bu sayede UNIQUE KEY tam index kullanır, prefix index değil
-- Çalıştırma: mysql -u root -p mailsender_pro < migrate_suppression_fix.sql

ALTER TABLE suppression_list
    MODIFY COLUMN email VARCHAR(254) NOT NULL;

-- Doğrulama
SHOW COLUMNS FROM suppression_list WHERE Field = 'email';
