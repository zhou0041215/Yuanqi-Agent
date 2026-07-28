package com.yuanqi.backend.knowledge;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record KnowledgeDocumentRequest(
        @NotBlank @Size(max = 128) @Pattern(regexp = "[A-Za-z0-9:_-]+") String documentKey,
        @NotBlank @Size(max = 300) String title,
        @NotBlank @Pattern(regexp = "Disease|Symptom|Drug|Department|Exam|Guideline") String entityType,
        @NotBlank @Size(min = 200, max = 20000) String content,
        @NotBlank @Size(max = 1000)
        @Pattern(regexp = "https://.+", message = "Knowledge source must be an HTTPS URL")
        String sourceUri
) {}
