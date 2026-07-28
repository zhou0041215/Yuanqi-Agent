package com.yuanqi.backend.agent.audit;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record AgentAuditRequest(
        @NotBlank @Pattern(regexp = "[0-9a-fA-F-]{36}") String threadId,
        @NotBlank @Size(max = 64) String traceId,
        @NotBlank @Pattern(regexp = "[a-z][a-z0-9_]{1,63}") String toolName,
        @NotBlank @Pattern(regexp = "[A-Z_]{2,32}") String phase,
        @NotBlank @Pattern(regexp = "[A-Z_]{2,32}") String outcome,
        @NotBlank @Pattern(regexp = "low|medium|high|critical") String riskLevel,
        @Pattern(regexp = "[a-f0-9]{64}") String fingerprint
) {
}
