package com.yuanqi.backend.workflow.web;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.workflow.PrescriptionStatusWorkflowService;
import com.yuanqi.backend.workflow.web.dto.PrescriptionWorkflowTaskResponse;
import com.yuanqi.backend.workflow.web.dto.PrescriptionWorkflowApproverResponse;
import com.yuanqi.backend.workflow.web.dto.PrescriptionWorkflowRequestResponse;
import com.yuanqi.backend.workflow.web.dto.StartPrescriptionStatusChangeRequest;
import com.yuanqi.backend.workflow.web.dto.WorkflowDecisionRequest;
import com.yuanqi.backend.workflow.web.dto.WorkflowDecisionResponse;
import com.yuanqi.backend.workflow.web.dto.WorkflowInstanceResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Pattern;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/workflows/prescription-status-changes")
@Tag(name = "Prescription workflows", description = "Flowable approvals for high-risk prescription state changes")
public class PrescriptionStatusWorkflowController {
    private final PrescriptionStatusWorkflowService workflowService;

    public PrescriptionStatusWorkflowController(PrescriptionStatusWorkflowService workflowService) {
        this.workflowService = workflowService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "Start a prescription status change approval")
    public ApiResponse<WorkflowInstanceResponse> start(
            @Valid @RequestBody StartPrescriptionStatusChangeRequest request
    ) {
        return ApiResponse.success(workflowService.start(request));
    }

    @GetMapping("/tasks/my")
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "List current user's prescription approval tasks")
    public ApiResponse<List<PrescriptionWorkflowTaskResponse>> myTasks() {
        return ApiResponse.success(workflowService.myTasks());
    }

    @GetMapping("/approvers")
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "List eligible approvers for an accessible prescription")
    public ApiResponse<List<PrescriptionWorkflowApproverResponse>> approvers(
            @jakarta.validation.constraints.Positive
            @org.springframework.web.bind.annotation.RequestParam long prescriptionId
    ) {
        return ApiResponse.success(workflowService.approvers(prescriptionId));
    }

    @GetMapping("/requests/my")
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "List current user's active prescription status requests")
    public ApiResponse<List<PrescriptionWorkflowRequestResponse>> myRequests() {
        return ApiResponse.success(workflowService.myRequests());
    }

    @PostMapping("/tasks/{taskId}/decision")
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "Approve or reject an assigned prescription status task")
    public ApiResponse<WorkflowDecisionResponse> decide(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9-]{1,128}") String taskId,
            @Valid @RequestBody WorkflowDecisionRequest request
    ) {
        return ApiResponse.success(workflowService.decide(taskId, request));
    }
}
