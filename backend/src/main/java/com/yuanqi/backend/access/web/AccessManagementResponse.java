package com.yuanqi.backend.access.web;

import java.time.Instant;
import java.util.List;

public record AccessManagementResponse(
        List<PersonSummary> people,
        List<RoleSummary> roles,
        List<PatientSummary> patients,
        List<GrantSummary> grants,
        List<AuditSummary> auditEvents
) {
    public record PersonSummary(
            long userId,
            String username,
            String displayName,
            long departmentId,
            String departmentName,
            String roleCode,
            String dataScope,
            String status
    ) {
    }

    public record RoleSummary(String code, String name, String scope, List<String> actions) {
    }

    public record PatientSummary(
            long id,
            String patientNo,
            String name,
            long departmentId,
            long ownerId,
            String status
    ) {
    }

    public record GrantSummary(
            long id,
            long patientId,
            String patientNo,
            String patientName,
            long granteeUserId,
            String granteeName,
            long grantedBy,
            String grantedByName,
            String reason,
            Instant validFrom,
            Instant validUntil,
            Instant revokedAt,
            String status
    ) {
    }

    public record AuditSummary(
            Instant occurredAt,
            long actorUserId,
            String actorName,
            String action,
            String targetType,
            String targetLabel
    ) {
    }
}
