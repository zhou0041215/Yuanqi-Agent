package com.yuanqi.backend.agent.audit;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "agent_audit_event")
public class AgentAuditEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;

    @Column(name = "actor_user_id", nullable = false, updatable = false)
    private long actorUserId;

    @Column(name = "actor_name", nullable = false, length = 200)
    private String actorName;

    @Column(name = "thread_id", nullable = false, length = 36)
    private String threadId;

    @Column(name = "trace_id", nullable = false, length = 64)
    private String traceId;

    @Column(name = "tool_name", nullable = false, length = 64)
    private String toolName;

    @Column(nullable = false, length = 32)
    private String phase;

    @Column(nullable = false, length = 32)
    private String outcome;

    @Column(name = "risk_level", nullable = false, length = 16)
    private String riskLevel;

    @Column(length = 64)
    private String fingerprint;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    protected AgentAuditEvent() {
    }

    public AgentAuditEvent(
            long tenantId,
            long actorUserId,
            String actorName,
            String threadId,
            String traceId,
            String toolName,
            String phase,
            String outcome,
            String riskLevel,
            String fingerprint,
            Instant occurredAt
    ) {
        this.tenantId = tenantId;
        this.actorUserId = actorUserId;
        this.actorName = actorName;
        this.threadId = threadId;
        this.traceId = traceId;
        this.toolName = toolName;
        this.phase = phase;
        this.outcome = outcome;
        this.riskLevel = riskLevel;
        this.fingerprint = fingerprint;
        this.occurredAt = occurredAt;
    }

    public Long getId() { return id; }
    public long getActorUserId() { return actorUserId; }
    public String getActorName() { return actorName; }
    public String getThreadId() { return threadId; }
    public String getTraceId() { return traceId; }
    public String getToolName() { return toolName; }
    public String getPhase() { return phase; }
    public String getOutcome() { return outcome; }
    public String getRiskLevel() { return riskLevel; }
    public String getFingerprint() { return fingerprint; }
    public Instant getOccurredAt() { return occurredAt; }
}
