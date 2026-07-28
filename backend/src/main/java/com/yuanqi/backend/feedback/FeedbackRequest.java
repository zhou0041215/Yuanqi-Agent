package com.yuanqi.backend.feedback;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record FeedbackRequest(
        @NotBlank @Size(max = 64) String sessionId,
        @NotBlank @Size(max = 64) String turnId,
        @NotBlank @Pattern(regexp = "UP|DOWN") String rating,
        @Size(max = 32) String category,
        @Size(max = 2000) String comment
) {}
