package com.yuanqi.backend.workflow.web.dto;

import java.time.Instant;

public record WorkflowTaskResponse(
        String taskId,
        String taskName,
        String processInstanceId,
        Instant createdAt,
        long customerId,
        long requestedOwnerId,
        long requesterId,
        String reason
) {
}
