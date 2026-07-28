package com.yuanqi.backend.patient.web;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.patient.service.PatientService;
import com.yuanqi.backend.patient.service.PatientWorkspaceService;
import com.yuanqi.backend.patient.web.dto.CreatePatientRequest;
import com.yuanqi.backend.patient.web.dto.PatientResponse;
import com.yuanqi.backend.patient.web.dto.PatientWorkspaceResponse;
import com.yuanqi.backend.patient.web.dto.UpdatePatientRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/patients")
@Tag(name = "Patients", description = "Patient CRUD constrained by JWT row-level data scope")
public class PatientController {
    private final PatientService patientService;
    private final PatientWorkspaceService patientWorkspaceService;

    public PatientController(PatientService patientService, PatientWorkspaceService patientWorkspaceService) {
        this.patientService = patientService;
        this.patientWorkspaceService = patientWorkspaceService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('patient:read')")
    @Operation(summary = "Search accessible patients")
    public ApiResponse<PageResponse<PatientResponse>> search(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size
    ) {
        return ApiResponse.success(patientService.search(keyword, page, size));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('patient:read')")
    @Operation(summary = "Get one accessible patient")
    public ApiResponse<PatientResponse> get(@PathVariable @Positive long id) {
        return ApiResponse.success(patientService.get(id));
    }

    @GetMapping("/{id}/workspace")
    @PreAuthorize("hasAuthority('patient:read') and hasAuthority('medical-record:read') and hasAuthority('prescription:read')")
    @Operation(summary = "Get an accessible patient workspace")
    public ApiResponse<PatientWorkspaceResponse> workspace(@PathVariable @Positive long id) {
        return ApiResponse.success(patientWorkspaceService.get(id));
    }

    @PostMapping
    @PreAuthorize("hasAuthority('patient:write')")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a patient")
    public ApiResponse<PatientResponse> create(@Valid @RequestBody CreatePatientRequest request) {
        return ApiResponse.success(patientService.create(request));
    }

    @PatchMapping("/{id}")
    @PreAuthorize("hasAuthority('patient:write')")
    @Operation(summary = "Update an accessible patient")
    public ApiResponse<PatientResponse> update(
            @PathVariable @Positive long id,
            @Valid @RequestBody UpdatePatientRequest request
    ) {
        return ApiResponse.success(patientService.update(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('patient:write')")
    @Operation(summary = "Soft-delete an accessible patient")
    public ApiResponse<Void> delete(@PathVariable @Positive long id) {
        patientService.delete(id);
        return ApiResponse.success();
    }
}
