package com.yuanqi.backend.medicalrecord.web.dto;

import com.yuanqi.backend.medicalrecord.domain.MedicalRecordStatus;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.LocalDateTime;

public record UpdateMedicalRecordRequest(
        @Positive Long patientId,
        LocalDateTime visitDate,
        @Size(max = 100) String department,
        @Size(max = 100) String doctorName,
        @Size(max = 65535) String chiefComplaint,
        @Size(max = 65535) String diagnosis,
        @Size(max = 65535) String treatmentPlan,
        @Size(max = 65535) String notes,
        MedicalRecordStatus status,
        @Positive Long ownerId,
        @Positive Long departmentId
) {
}
