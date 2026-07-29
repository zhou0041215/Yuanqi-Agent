package com.yuanqi.backend.access.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "patient_access_grant")
public class PatientAccessGrant {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "patient_id", nullable = false, updatable = false)
    private long patientId;

    @Column(name = "grantee_user_id", nullable = false, updatable = false)
    private long granteeUserId;

    @Column(name = "granted_by", nullable = false, updatable = false)
    private long grantedBy;

    @Column(nullable = false, length = 500)
    private String reason;

    @Column(name = "valid_from", nullable = false, updatable = false)
    private Instant validFrom;

    @Column(name = "valid_until", nullable = false, updatable = false)
    private Instant validUntil;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected PatientAccessGrant() {
    }

    public PatientAccessGrant(
            long patientId,
            long granteeUserId,
            long grantedBy,
            String reason,
            Instant validFrom,
            Instant validUntil
    ) {
        this.patientId = patientId;
        this.granteeUserId = granteeUserId;
        this.grantedBy = grantedBy;
        this.reason = reason;
        this.validFrom = validFrom;
        this.validUntil = validUntil;
        this.createdAt = validFrom;
    }

    public void revoke(Instant revokedAt) {
        this.revokedAt = revokedAt;
    }

    public Long getId() { return id; }
    public long getPatientId() { return patientId; }
    public long getGranteeUserId() { return granteeUserId; }
    public long getGrantedBy() { return grantedBy; }
    public String getReason() { return reason; }
    public Instant getValidFrom() { return validFrom; }
    public Instant getValidUntil() { return validUntil; }
    public Instant getRevokedAt() { return revokedAt; }
    public Instant getCreatedAt() { return createdAt; }
}
