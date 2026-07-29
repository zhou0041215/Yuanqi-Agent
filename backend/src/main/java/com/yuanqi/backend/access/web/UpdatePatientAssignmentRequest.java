package com.yuanqi.backend.access.web;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

public record UpdatePatientAssignmentRequest(
        @Positive long responsibleUserId,
        @NotBlank @Size(min = 5, max = 500) String reason
) {
}
