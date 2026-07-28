package com.yuanqi.backend.agent.audit;

import com.yuanqi.backend.common.api.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/agent-audit/events")
@Tag(name = "Agent audit", description = "Tenant-scoped, parameter-free Agent tool audit trail")
public class AgentAuditController {
    private final AgentAuditService service;

    public AgentAuditController(AgentAuditService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("isAuthenticated()")
    @Operation(summary = "Record an Agent tool lifecycle event without storing tool parameters")
    public ApiResponse<AgentAuditResponse> record(@Valid @RequestBody AgentAuditRequest request) {
        return ApiResponse.success(service.record(request));
    }

    @GetMapping
    @PreAuthorize("hasAuthority('agent:audit:read')")
    @Operation(summary = "List recent Agent tool lifecycle events for the current tenant")
    public ApiResponse<List<AgentAuditResponse>> recent(
            @RequestParam(defaultValue = "50") @Min(1) @Max(100) int limit
    ) {
        return ApiResponse.success(service.recent(limit));
    }
}
