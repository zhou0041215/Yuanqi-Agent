CREATE TABLE customer (
    id BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    customer_code VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(100),
    contact_phone VARCHAR(32),
    status VARCHAR(32) NOT NULL,
    owner_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT uk_customer_tenant_code UNIQUE (tenant_id, customer_code),
    INDEX idx_customer_scope (tenant_id, deleted, department_id, owner_id),
    INDEX idx_customer_name (tenant_id, name)
);
