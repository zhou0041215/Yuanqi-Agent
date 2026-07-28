ALTER TABLE customer
    ADD CONSTRAINT uk_customer_tenant_id UNIQUE (tenant_id, id);

CREATE TABLE sales_order (
    id BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    order_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    order_date DATE NOT NULL,
    total_amount DECIMAL(19, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(32) NOT NULL,
    owner_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT uk_sales_order_tenant_no UNIQUE (tenant_id, order_no),
    CONSTRAINT fk_sales_order_customer FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customer (tenant_id, id),
    INDEX idx_sales_order_scope (tenant_id, deleted, department_id, owner_id),
    INDEX idx_sales_order_customer (tenant_id, customer_id)
);

CREATE TABLE business_contract (
    id BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    contract_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    total_amount DECIMAL(19, 2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    owner_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT uk_contract_tenant_no UNIQUE (tenant_id, contract_no),
    CONSTRAINT fk_contract_customer FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customer (tenant_id, id),
    INDEX idx_contract_scope (tenant_id, deleted, department_id, owner_id),
    INDEX idx_contract_customer (tenant_id, customer_id)
);

CREATE TABLE work_order (
    id BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    ticket_no VARCHAR(64) NOT NULL,
    customer_id BIGINT,
    subject VARCHAR(200) NOT NULL,
    description VARCHAR(4000) NOT NULL,
    priority VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    owner_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT uk_work_order_tenant_no UNIQUE (tenant_id, ticket_no),
    CONSTRAINT fk_work_order_customer FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customer (tenant_id, id),
    INDEX idx_work_order_scope (tenant_id, deleted, department_id, owner_id),
    INDEX idx_work_order_customer (tenant_id, customer_id)
);
