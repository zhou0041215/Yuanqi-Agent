package com.yuanqi.backend.access.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "access_audit_event")
public class AccessAuditEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "actor_user_id", nullable = false, updatable = false)
    private long actorUserId;

    @Column(name = "actor_name", nullable = false, length = 100)
    private String actorName;

    @Column(nullable = false, length = 100)
    private String action;

    @Column(name = "target_type", nullable = false, length = 60)
    private String targetType;

    @Column(name = "target_label", nullable = false, length = 200)
    private String targetLabel;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    protected AccessAuditEvent() {
    }

    public AccessAuditEvent(
            long actorUserId,
            String actorName,
            String action,
            String targetType,
            String targetLabel,
            Instant occurredAt
    ) {
        this.actorUserId = actorUserId;
        this.actorName = actorName;
        this.action = action;
        this.targetType = targetType;
        this.targetLabel = targetLabel;
        this.occurredAt = occurredAt;
    }

    public long getActorUserId() { return actorUserId; }
    public String getActorName() { return actorName; }
    public String getAction() { return action; }
    public String getTargetType() { return targetType; }
    public String getTargetLabel() { return targetLabel; }
    public Instant getOccurredAt() { return occurredAt; }
}
