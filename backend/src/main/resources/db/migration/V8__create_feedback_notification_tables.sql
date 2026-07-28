CREATE TABLE answer_feedback (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username VARCHAR(200) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    turn_id VARCHAR(64) NOT NULL,
    rating VARCHAR(16) NOT NULL,
    category VARCHAR(32),
    comment VARCHAR(2000),
    status VARCHAR(24) NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    version BIGINT NOT NULL DEFAULT 0,
    UNIQUE KEY uk_feedback_tenant_turn_user (tenant_id, turn_id, user_id),
    KEY idx_feedback_tenant_created (tenant_id, created_at),
    KEY idx_feedback_tenant_status (tenant_id, status)
);

CREATE TABLE user_notification (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    recipient_user_id BIGINT NOT NULL,
    type VARCHAR(32) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content VARCHAR(1000) NOT NULL,
    target_url VARCHAR(500),
    read_at TIMESTAMP(6),
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    version BIGINT NOT NULL DEFAULT 0,
    KEY idx_notification_recipient (tenant_id, recipient_user_id, read_at, created_at)
);
