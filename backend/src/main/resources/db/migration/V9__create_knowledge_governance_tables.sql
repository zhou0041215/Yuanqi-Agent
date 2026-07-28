CREATE TABLE knowledge_document (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    document_key VARCHAR(128) NOT NULL,
    title VARCHAR(300) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    source_uri VARCHAR(1000),
    status VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
    knowledge_version INT NOT NULL DEFAULT 1,
    published_at TIMESTAMP(6),
    published_by BIGINT,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    version BIGINT NOT NULL DEFAULT 0,
    UNIQUE KEY uk_knowledge_tenant_key (tenant_id, document_key),
    KEY idx_knowledge_tenant_status (tenant_id, status, updated_at)
);

CREATE TABLE knowledge_index_version (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    version_name VARCHAR(100) NOT NULL,
    collection_name VARCHAR(100) NOT NULL,
    status VARCHAR(24) NOT NULL,
    document_count INT NOT NULL DEFAULT 0,
    requested_by BIGINT NOT NULL,
    error_message VARCHAR(2000),
    activated_at TIMESTAMP(6),
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    version BIGINT NOT NULL DEFAULT 0,
    UNIQUE KEY uk_index_tenant_version (tenant_id, version_name)
);
