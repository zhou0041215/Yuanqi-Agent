package com.yuanqi.backend.medicalrecord.web.dto;

import com.yuanqi.backend.medicalrecord.domain.MedicalRecordStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.LocalDateTime;

public record CreateMedicalRecordRequest(
        @NotBlank @Size(max = 64) @Pattern(regexp = "[A-Za-z0-9_-]+") String recordNo,
        @Positive long patientId,
        @NotNull LocalDateTime visitDate,
        @NotBlank @Size(max = 100) String department,
        @NotBlank @Size(max = 100) String doctorName,
        @Size(max = 65535) String chiefComplaint,
        @Size(max = 65535) String diagnosis,
        @Size(max = 65535) String treatmentPlan,
        @Size(max = 65535) String notes,
        @NotNull MedicalRecordStatus status,
        @Positive long ownerId,
        @Positive long departmentId
) {
}
