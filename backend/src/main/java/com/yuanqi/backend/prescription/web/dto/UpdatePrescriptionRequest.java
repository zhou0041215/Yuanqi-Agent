package com.yuanqi.backend.prescription.web.dto;

import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public record UpdatePrescriptionRequest(
        @Positive Long patientId,
        Long recordId,
        @Size(min = 1, max = 100) String doctorName,
        LocalDateTime prescriptionDate,
        String diagnosis,
        String drugsJson,
        @Positive BigDecimal totalAmount,
        PrescriptionStatus status,
        String notes,
        @Positive Long ownerId,
        @Positive Long departmentId
) {
}
