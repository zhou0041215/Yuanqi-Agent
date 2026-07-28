package com.yuanqi.backend.workflow.web.dto;

import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import java.time.Instant;

public record PrescriptionWorkflowRequestResponse(
        String processInstanceId,
        long prescriptionId,
        PrescriptionStatus targetStatus,
        long approverId,
        String reason,
        Instant createdAt
) {
}
