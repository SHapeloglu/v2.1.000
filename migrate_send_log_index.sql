-- send_log performans iyileştirmesi
-- sender_id + sent_at composite index — can_send() ve tarih filtreli sorgular için
-- Çalıştırma: mysql -u root -p mailsender_pro < migrate_send_log_index.sql

ALTER TABLE send_log
    ADD INDEX idx_sender_sent_at (sender_id, sent_at);

-- Doğrulama
SHOW INDEX FROM send_log WHERE Key_name = 'idx_sender_sent_at';
