package com.yuanqi.backend.prescription.web.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public record CreatePrescriptionRequest(
        @Positive long patientId,
        Long recordId,
        @NotNull LocalDateTime prescriptionDate,
        String diagnosis,
        @NotBlank @Size(max = 65535) String drugsJson,
        @NotNull @Positive BigDecimal totalAmount,
        String notes
) {
}
