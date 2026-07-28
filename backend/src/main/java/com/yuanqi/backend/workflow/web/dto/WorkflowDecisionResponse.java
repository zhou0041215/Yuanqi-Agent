package com.yuanqi.backend.workflow.web.dto;

public record WorkflowDecisionResponse(
        String processInstanceId,
        boolean approved,
        String status
) {
}
