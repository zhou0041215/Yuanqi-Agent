package com.yuanqi.backend.access.domain;

import com.yuanqi.backend.security.DataScopeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "access_person")
public class AccessPerson {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;

    @Column(name = "user_id", nullable = false, updatable = false)
    private long userId;

    @Column(nullable = false, length = 100)
    private String username;

    @Column(name = "display_name", nullable = false, length = 100)
    private String displayName;

    @Column(name = "department_id", nullable = false)
    private long departmentId;

    @Column(name = "department_name", nullable = false, length = 100)
    private String departmentName;

    @Column(name = "role_code", nullable = false, length = 40)
    private String roleCode;

    @Enumerated(EnumType.STRING)
    @Column(name = "data_scope", nullable = false, length = 20)
    private DataScopeType dataScope;

    @Column(nullable = false, length = 20)
    private String status;

    protected AccessPerson() {
    }

    public long getUserId() { return userId; }
    public String getUsername() { return username; }
    public String getDisplayName() { return displayName; }
    public long getDepartmentId() { return departmentId; }
    public String getDepartmentName() { return departmentName; }
    public String getRoleCode() { return roleCode; }
    public DataScopeType getDataScope() { return dataScope; }
    public String getStatus() { return status; }
}
