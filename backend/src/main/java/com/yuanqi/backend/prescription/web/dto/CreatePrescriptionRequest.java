package com.yuanqi.backend.prescription.web.dto;

import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public record CreatePrescriptionRequest(
        @NotBlank @Size(max = 64) @Pattern(regexp = "[A-Za-z0-9_-]+") String prescriptionNo,
        @Positive long patientId,
        Long recordId,
        @NotBlank @Size(max = 100) String doctorName,
        @NotNull LocalDateTime prescriptionDate,
        String diagnosis,
        String drugsJson,
        @NotNull @Positive BigDecimal totalAmount,
        @NotNull PrescriptionStatus status,
        String notes,
        @Positive long ownerId,
        @Positive long departmentId
) {
}
