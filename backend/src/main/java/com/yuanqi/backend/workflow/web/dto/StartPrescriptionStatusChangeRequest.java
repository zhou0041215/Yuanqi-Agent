package com.yuanqi.backend.workflow.web.dto;

import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

public record StartPrescriptionStatusChangeRequest(
        @Positive long prescriptionId,
        @NotNull PrescriptionStatus targetStatus,
        @Positive long approverId,
        @Size(min = 1, max = 1000) String reason
) {
}
