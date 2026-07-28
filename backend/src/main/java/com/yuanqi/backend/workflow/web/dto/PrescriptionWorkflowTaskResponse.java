package com.yuanqi.backend.workflow.web.dto;

import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import java.time.Instant;

public record PrescriptionWorkflowTaskResponse(
        String taskId,
        String taskName,
        String processInstanceId,
        Instant createdAt,
        long prescriptionId,
        PrescriptionStatus targetStatus,
        long requesterId,
        String reason
) {
}
