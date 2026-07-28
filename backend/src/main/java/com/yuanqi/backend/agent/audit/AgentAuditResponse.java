package com.yuanqi.backend.agent.audit;

import java.time.Instant;

public record AgentAuditResponse(
        long id,
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
    public static AgentAuditResponse from(AgentAuditEvent event) {
        return new AgentAuditResponse(
                event.getId(),
                event.getActorUserId(),
                event.getActorName(),
                event.getThreadId(),
                event.getTraceId(),
                event.getToolName(),
                event.getPhase(),
                event.getOutcome(),
                event.getRiskLevel(),
                event.getFingerprint(),
                event.getOccurredAt()
        );
    }
}
