package com.yuanqi.backend.workflow;

import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.notification.NotificationService;
import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import com.yuanqi.backend.prescription.service.PrescriptionService;
import com.yuanqi.backend.prescription.web.dto.PrescriptionResponse;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import com.yuanqi.backend.workflow.web.dto.PrescriptionWorkflowTaskResponse;
import com.yuanqi.backend.workflow.web.dto.PrescriptionWorkflowApproverResponse;
import com.yuanqi.backend.workflow.web.dto.PrescriptionWorkflowRequestResponse;
import com.yuanqi.backend.workflow.web.dto.StartPrescriptionStatusChangeRequest;
import com.yuanqi.backend.workflow.web.dto.WorkflowDecisionRequest;
import com.yuanqi.backend.workflow.web.dto.WorkflowDecisionResponse;
import com.yuanqi.backend.workflow.web.dto.WorkflowInstanceResponse;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.flowable.engine.RuntimeService;
import org.flowable.engine.TaskService;
import org.flowable.engine.runtime.ProcessInstance;
import org.flowable.task.api.Task;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PrescriptionStatusWorkflowService {
    private static final String PROCESS_KEY = "prescriptionStatusChange";
    private static final int MAX_TASKS = 100;

    private final RuntimeService runtimeService;
    private final TaskService taskService;
    private final CurrentUserProvider currentUserProvider;
    private final PrescriptionService prescriptionService;
    private final NotificationService notificationService;
    private final AccessPersonRepository accessPersonRepository;

    public PrescriptionStatusWorkflowService(
            RuntimeService runtimeService,
            TaskService taskService,
            CurrentUserProvider currentUserProvider,
            PrescriptionService prescriptionService,
            NotificationService notificationService,
            AccessPersonRepository accessPersonRepository
    ) {
        this.runtimeService = runtimeService;
        this.taskService = taskService;
        this.currentUserProvider = currentUserProvider;
        this.prescriptionService = prescriptionService;
        this.notificationService = notificationService;
        this.accessPersonRepository = accessPersonRepository;
    }

    @Transactional
    public WorkflowInstanceResponse start(StartPrescriptionStatusChangeRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        PrescriptionResponse prescription = prescriptionService.get(request.prescriptionId());
        String businessKey = "prescription:" + request.prescriptionId();
        if (prescription.status() != PrescriptionStatus.PENDING) {
            throw BusinessException.conflict("Only pending prescriptions can enter status approval");
        }
        if (request.targetStatus() == PrescriptionStatus.PENDING) {
            throw BusinessException.conflict("Target status must change the prescription");
        }
        if (request.approverId() == user.userId()) {
            throw BusinessException.conflict("Requester and approver must be different users");
        }
        if (approvers(request.prescriptionId()).stream()
                .noneMatch(candidate -> candidate.userId() == request.approverId())) {
            throw BusinessException.conflict(
                    "Approver must be an active eligible user with access to this prescription");
        }
        if (runtimeService.createProcessInstanceQuery()
                .processDefinitionKey(PROCESS_KEY)
                .processInstanceBusinessKey(businessKey)
                .active()
                .count() > 0) {
            throw BusinessException.conflict(
                    "An active prescription status approval already exists");
        }

        Map<String, Object> variables = new HashMap<>();
        variables.put("requesterId", user.userId());
        variables.put("prescriptionId", request.prescriptionId());
        variables.put("targetStatus", request.targetStatus().name());
        variables.put("approverId", request.approverId());
        variables.put("reason", request.reason().trim());

        ProcessInstance process = runtimeService.createProcessInstanceBuilder()
                .processDefinitionKey(PROCESS_KEY)
                .businessKey(businessKey)
                .variables(variables)
                .start();
        Task task = taskService.createTaskQuery()
                .processInstanceId(process.getProcessInstanceId())
                .singleResult();
        if (task == null) {
            throw new IllegalStateException("Approval task was not created");
        }
        notificationService.send(
                request.approverId(),
                "APPROVAL_REQUIRED",
                "新的处方审批任务",
                "处方 " + prescription.prescriptionNo() + " 申请变更为 "
                        + request.targetStatus().name() + "。原因：" + request.reason().trim(),
                "/?view=approval");
        return new WorkflowInstanceResponse(
                process.getProcessInstanceId(), "WAITING_APPROVAL", task.getId(), task.getName());
    }

    @Transactional(readOnly = true)
    public List<PrescriptionWorkflowTaskResponse> myTasks() {
        UserContext user = currentUserProvider.requireCurrentUser();
        return taskService.createTaskQuery()
                .processDefinitionKey(PROCESS_KEY)
                .taskAssignee(Long.toString(user.userId()))
                .active()
                .orderByTaskCreateTime()
                .desc()
                .listPage(0, MAX_TASKS)
                .stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<PrescriptionWorkflowApproverResponse> approvers(long prescriptionId) {
        UserContext user = currentUserProvider.requireCurrentUser();
        PrescriptionResponse prescription = prescriptionService.get(prescriptionId);
        return accessPersonRepository.findAllByOrderByDisplayNameAsc().stream()
                .filter(person -> person.getUserId() != user.userId())
                .filter(person -> "ACTIVE".equals(person.getStatus()))
                .filter(person -> "SYSTEM_ADMIN".equals(person.getRoleCode()))
                .filter(person -> person.getDataScope() == com.yuanqi.backend.security.DataScopeType.ALL)
                .map(person -> new PrescriptionWorkflowApproverResponse(
                        person.getUserId(),
                        person.getDisplayName(),
                        person.getDepartmentName(),
                        person.getRoleCode()))
                .toList();
    }

    @Transactional(readOnly = true)
    public List<PrescriptionWorkflowRequestResponse> myRequests() {
        UserContext user = currentUserProvider.requireCurrentUser();
        return runtimeService.createProcessInstanceQuery()
                .processDefinitionKey(PROCESS_KEY)
                .variableValueEquals("requesterId", user.userId())
                .active()
                .listPage(0, MAX_TASKS)
                .stream()
                .map(process -> {
                    Map<String, Object> variables = runtimeService.getVariables(process.getId());
                    return new PrescriptionWorkflowRequestResponse(
                            process.getId(),
                            positiveLong(variables.get("prescriptionId")),
                            PrescriptionStatus.valueOf(String.valueOf(variables.get("targetStatus"))),
                            positiveLong(variables.get("approverId")),
                            String.valueOf(variables.get("reason")),
                            process.getStartTime().toInstant());
                })
                .toList();
    }

    @Transactional
    public WorkflowDecisionResponse decide(String taskId, WorkflowDecisionRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        Task task = taskService.createTaskQuery()
                .processDefinitionKey(PROCESS_KEY)
                .taskId(taskId)
                .taskAssignee(Long.toString(user.userId()))
                .active()
                .singleResult();
        if (task == null) {
            throw BusinessException.notFound("Workflow task");
        }
        Map<String, Object> variables = runtimeService.getVariables(task.getProcessInstanceId());
        taskService.complete(task.getId(), Map.of(
                "approved", request.approved(),
                "approvalComment", normalizeComment(request.comment())
        ));
        notificationService.send(
                positiveLong(variables.get("requesterId")),
                request.approved() ? "APPROVAL_APPROVED" : "APPROVAL_REJECTED",
                request.approved() ? "处方变更已批准" : "处方变更已驳回",
                "处方 ID " + positiveLong(variables.get("prescriptionId"))
                        + " 的状态变更申请已"
                        + (request.approved() ? "批准" : "驳回")
                        + (normalizeComment(request.comment()).isBlank()
                                ? "" : "。意见：" + normalizeComment(request.comment())),
                "/?view=approval");
        return new WorkflowDecisionResponse(
                task.getProcessInstanceId(),
                request.approved(),
                request.approved() ? "APPROVED" : "REJECTED"
        );
    }

    private PrescriptionWorkflowTaskResponse toResponse(Task task) {
        Map<String, Object> variables = runtimeService.getVariables(task.getProcessInstanceId());
        return new PrescriptionWorkflowTaskResponse(
                task.getId(),
                task.getName(),
                task.getProcessInstanceId(),
                task.getCreateTime().toInstant(),
                positiveLong(variables.get("prescriptionId")),
                PrescriptionStatus.valueOf(String.valueOf(variables.get("targetStatus"))),
                positiveLong(variables.get("requesterId")),
                String.valueOf(variables.getOrDefault("reason", ""))
        );
    }

    private long positiveLong(Object value) {
        if (value instanceof Number number && number.longValue() > 0) {
            return number.longValue();
        }
        throw new IllegalStateException("Workflow contains an invalid identity variable");
    }

    private String normalizeComment(String value) {
        return value == null || value.isBlank() ? "" : value.trim();
    }
}
