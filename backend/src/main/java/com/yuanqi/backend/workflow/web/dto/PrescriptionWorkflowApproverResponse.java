package com.yuanqi.backend.workflow.web.dto;

public record PrescriptionWorkflowApproverResponse(
        long userId,
        String displayName,
        String departmentName,
        String roleCode
) {
}
