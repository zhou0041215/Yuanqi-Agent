CREATE TABLE agent_audit_event (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id       BIGINT       NOT NULL,
    actor_user_id   BIGINT       NOT NULL,
    actor_name      VARCHAR(200) NOT NULL,
    thread_id       VARCHAR(36)  NOT NULL,
    trace_id        VARCHAR(64)  NOT NULL,
    tool_name       VARCHAR(64)  NOT NULL,
    phase           VARCHAR(32)  NOT NULL,
    outcome         VARCHAR(32)  NOT NULL,
    risk_level      VARCHAR(16)  NOT NULL,
    fingerprint     VARCHAR(64),
    occurred_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_agent_audit_tenant_time (tenant_id, occurred_at),
    INDEX idx_agent_audit_thread (tenant_id, thread_id)
);
