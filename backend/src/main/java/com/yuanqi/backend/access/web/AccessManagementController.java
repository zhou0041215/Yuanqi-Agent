package com.yuanqi.backend.access.web;

import com.yuanqi.backend.access.service.AccessManagementService;
import com.yuanqi.backend.common.api.ApiResponse;
import org.springframework.security.access.prepost.PreAuthorize;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import org.springframework.http.HttpStatus;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/access-management")
public class AccessManagementController {
    private final AccessManagementService service;

    public AccessManagementController(AccessManagementService service) {
        this.service = service;
    }

    @GetMapping("/snapshot")
    @PreAuthorize("hasAuthority('access:manage')")
    public ApiResponse<AccessManagementResponse> snapshot() {
        return ApiResponse.success(service.snapshot());
    }

    @PostMapping("/grants")
    @PreAuthorize("hasAuthority('access:manage')")
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<AccessManagementResponse.GrantSummary> createGrant(
            @Valid @RequestBody CreatePatientGrantRequest request
    ) {
        return ApiResponse.success(service.createGrant(request));
    }

    @PatchMapping("/patients/{id}/assignment")
    @PreAuthorize("hasAuthority('access:manage')")
    public ApiResponse<AccessManagementResponse.PatientSummary> updatePatientAssignment(
            @PathVariable @Positive long id,
            @Valid @RequestBody UpdatePatientAssignmentRequest request
    ) {
        return ApiResponse.success(service.updatePatientAssignment(id, request));
    }

    @DeleteMapping("/grants/{id}")
    @PreAuthorize("hasAuthority('access:manage')")
    public ApiResponse<AccessManagementResponse.GrantSummary> revokeGrant(
            @PathVariable @Positive long id
    ) {
        return ApiResponse.success(service.revokeGrant(id));
    }
}
