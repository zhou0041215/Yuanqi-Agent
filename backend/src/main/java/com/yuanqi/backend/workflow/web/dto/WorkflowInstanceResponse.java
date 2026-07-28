package com.yuanqi.backend.workflow.web.dto;

public record WorkflowInstanceResponse(
        String processInstanceId,
        String status,
        String taskId,
        String taskName
) {
}
