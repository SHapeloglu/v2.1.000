-- migrate_spam_trap.sql
-- Spam tuzağı domain listesi tablosu
-- Çalıştırma: mysql -u USER -p DBNAME < migrate_spam_trap.sql
-- MySQL 5.7+ uyumlu

CREATE TABLE IF NOT EXISTS `spam_trap_domains` (
    `id`         INT          UNSIGNED NOT NULL AUTO_INCREMENT,
    `domain`     VARCHAR(255) NOT NULL,
    `trap_type`  ENUM('pristine','typo_trap','recycled') NOT NULL DEFAULT 'pristine'
                 COMMENT 'pristine=hiç gerçek kullanıcı olmamış, typo_trap=yanlış yazım tuzağı, recycled=geri dönüştürülmüş',
    `source`     VARCHAR(100) DEFAULT NULL
                 COMMENT 'Kaynağı: spamhaus / surbl / manuel / api',
    `notes`      VARCHAR(500) DEFAULT NULL,
    `added_at`   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY  (`id`),
    UNIQUE  KEY  `uniq_domain` (`domain`),
    INDEX        `idx_trap_type` (`trap_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Spam tuzağı domain listesi — spam_trap.py tarafından okunur';

-- Başlangıç verisi: kamuya açık bilinen tuzak domainleri
INSERT IGNORE INTO `spam_trap_domains` (`domain`, `trap_type`, `source`, `notes`) VALUES
('spamtrap.ro',          'pristine', 'manuel', 'Kamuya açık Spamhaus tuzak domaini'),
('spamtrap.net',         'pristine', 'manuel', 'Kamuya açık tuzak domaini'),
('spamtrap.com',         'pristine', 'manuel', 'Kamuya açık tuzak domaini'),
('trapped.me',           'pristine', 'manuel', 'Honeypot servisi'),
('spamgoes.in',          'pristine', 'manuel', 'Spam araştırma domaini'),
('spamhere.net',         'pristine', 'manuel', 'Spam araştırma domaini'),
('trapthem.net',         'pristine', 'manuel', 'Honeypot servisi'),
('abuse.ro',             'pristine', 'manuel', 'Abuse araştırma domaini'),
('spamhole.com',         'pristine', 'manuel', 'Spam tuzak domaini'),
('honeypot.net',         'pristine', 'manuel', 'Honeypot servisi'),
('project-honeypot.org', 'pristine', 'manuel', 'Project Honeypot — spam araştırma'),
('spambog.com',          'pristine', 'manuel', 'Spam tuzak domaini'),
('spambog.de',           'pristine', 'manuel', 'Spam tuzak domaini (DE)'),
('spambog.ru',           'pristine', 'manuel', 'Spam tuzak domaini (RU)'),
('gmali.com',            'typo_trap','manuel', 'Gmail typo trap'),
('gmaail.com',           'typo_trap','manuel', 'Gmail typo trap'),
('gmaill.com',           'typo_trap','manuel', 'Gmail typo trap'),
('gmails.com',           'typo_trap','manuel', 'Gmail typo trap'),
('yhaoo.com',            'typo_trap','manuel', 'Yahoo typo trap'),
('hotmai1.com',          'typo_trap','manuel', 'Hotmail typo trap (rakam ile)'),
('hotnail.net',          'typo_trap','manuel', 'Hotmail typo trap'),
('outlookk.com',         'typo_trap','manuel', 'Outlook typo trap');
