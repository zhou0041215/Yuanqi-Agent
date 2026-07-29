package com.yuanqi.backend.medicalrecord.web.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.LocalDateTime;

public record CreateMedicalRecordRequest(
        @Positive long patientId,
        @NotNull LocalDateTime visitDate,
        @Size(max = 65535) String chiefComplaint,
        @Size(max = 65535) String diagnosis,
        @Size(max = 65535) String treatmentPlan,
        @Size(max = 65535) String notes
) {
}
