-- Local-development account store. Passwords are BCrypt hashes; never store plaintext passwords.
CREATE TABLE user_account (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id             BIGINT       NOT NULL,
    user_id               BIGINT       NOT NULL,
    password_hash         VARCHAR(100) NOT NULL,
    must_change_password  BOOLEAN      NOT NULL DEFAULT TRUE,
    status                VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_account_tenant_user UNIQUE (tenant_id, user_id)
);

-- Development-only initial password for demo accounts: 123456.
-- All rows are flagged to require a password change once account login is enabled.
INSERT INTO user_account (tenant_id, user_id, password_hash, must_change_password, status)
VALUES
    (1, 1001, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1010, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1011, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1012, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1013, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1014, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1015, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1016, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1017, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1018, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE'),
    (1, 1019, '$2a$10$1YdXf0is/20.p/k02QDCbeH3OI6eyty23ChISlGVqIqHqh.OSM.oy', TRUE, 'ACTIVE');
