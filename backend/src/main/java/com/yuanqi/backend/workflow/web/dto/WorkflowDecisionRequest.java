package com.yuanqi.backend.workflow.web.dto;

import jakarta.validation.constraints.Size;

public record WorkflowDecisionRequest(
        boolean approved,
        @Size(max = 1000) String comment
) {
}
