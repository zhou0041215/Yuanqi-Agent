package com.yuanqi.backend.knowledge;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record KnowledgeIndexRequest(
        @NotBlank @Size(max = 100) @Pattern(regexp = "[A-Za-z0-9._-]+") String versionName,
        @NotBlank @Size(max = 100) @Pattern(regexp = "[A-Za-z0-9_-]+") String collectionName
) {}
