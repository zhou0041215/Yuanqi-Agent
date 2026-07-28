package com.yuanqi.backend.access.web;

import jakarta.validation.constraints.Future;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.Instant;

public record CreatePatientGrantRequest(
        @Positive long patientId,
        @Positive long granteeUserId,
        @NotBlank @Size(min = 5, max = 500) String reason,
        @NotNull @Future Instant validUntil
) {
}
