CREATE TABLE access_person (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id       BIGINT       NOT NULL,
    user_id         BIGINT       NOT NULL,
    username        VARCHAR(100) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    department_id   BIGINT       NOT NULL,
    department_name VARCHAR(100) NOT NULL,
    role_code       VARCHAR(40)  NOT NULL,
    data_scope      VARCHAR(20)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_access_person_tenant_user UNIQUE (tenant_id, user_id),
    CONSTRAINT uk_access_person_tenant_username UNIQUE (tenant_id, username),
    INDEX idx_access_person_tenant (tenant_id),
    INDEX idx_access_person_department (tenant_id, department_id)
);

CREATE TABLE patient_access_grant (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id       BIGINT       NOT NULL,
    patient_id      BIGINT       NOT NULL,
    grantee_user_id BIGINT       NOT NULL,
    granted_by      BIGINT       NOT NULL,
    reason          VARCHAR(500) NOT NULL,
    valid_from      TIMESTAMP    NOT NULL,
    valid_until     TIMESTAMP    NOT NULL,
    revoked_at      TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_patient_grant_lookup (tenant_id, grantee_user_id, patient_id),
    INDEX idx_patient_grant_expiry (tenant_id, valid_until),
    CONSTRAINT fk_patient_grant_patient FOREIGN KEY (patient_id) REFERENCES patient(id)
);

CREATE TABLE access_audit_event (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id       BIGINT       NOT NULL,
    actor_user_id   BIGINT       NOT NULL,
    actor_name      VARCHAR(100) NOT NULL,
    action          VARCHAR(100) NOT NULL,
    target_type     VARCHAR(60)  NOT NULL,
    target_label    VARCHAR(200) NOT NULL,
    occurred_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_access_audit_tenant_time (tenant_id, occurred_at)
);

INSERT INTO access_person
    (tenant_id, user_id, username, display_name, department_id, department_name, role_code, data_scope, status)
VALUES
    (1, 1001, 'admin', '林澜', 10, '内分泌科', 'SYSTEM_ADMIN', 'ALL', 'ACTIVE'),
    (1, 1002, 'manager', '周宁', 20, '心内科', 'DEPARTMENT_LEAD', 'DEPARTMENT', 'ACTIVE'),
    (1, 1003, 'staff', '陈昕', 30, '呼吸内科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE');

INSERT INTO access_audit_event
    (tenant_id, actor_user_id, actor_name, action, target_type, target_label, occurred_at)
VALUES
    (1, 1001, '林澜', '查看角色与范围', 'ROLE', '系统管理员', CURRENT_TIMESTAMP),
    (1, 1002, '周宁', '查看患者授权', 'PATIENT_GRANT', '本科室授权记录', CURRENT_TIMESTAMP),
    (1, 1001, '林澜', '查看人员目录', 'PERSON', '内分泌科', CURRENT_TIMESTAMP);
