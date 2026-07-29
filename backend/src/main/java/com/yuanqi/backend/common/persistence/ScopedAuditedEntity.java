package com.yuanqi.backend.common.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.MappedSuperclass;

@MappedSuperclass
public abstract class ScopedAuditedEntity extends AuditedEntity {
    @Column(name = "owner_id", nullable = false)
    private long ownerId;

    @Column(name = "department_id", nullable = false)
    private long departmentId;

    @Column(nullable = false)
    private boolean deleted;

    protected void initializeScope(long ownerId, long departmentId) {
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    protected void changeAssignment(long ownerId, long departmentId) {
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    public void delete() {
        this.deleted = true;
    }

    public long getOwnerId() {
        return ownerId;
    }

    public long getDepartmentId() {
        return departmentId;
    }

    public boolean isDeleted() {
        return deleted;
    }
}
