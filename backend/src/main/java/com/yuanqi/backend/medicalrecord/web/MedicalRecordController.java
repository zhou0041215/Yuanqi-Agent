package com.yuanqi.backend.medicalrecord.web;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.medicalrecord.service.MedicalRecordService;
import com.yuanqi.backend.medicalrecord.web.dto.CreateMedicalRecordRequest;
import com.yuanqi.backend.medicalrecord.web.dto.MedicalRecordResponse;
import com.yuanqi.backend.medicalrecord.web.dto.UpdateMedicalRecordRequest;
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
@RequestMapping("/api/v1/medical-records")
@Tag(name = "Medical Records", description = "Medical record CRUD constrained by JWT row-level data scope")
public class MedicalRecordController {
    private final MedicalRecordService medicalRecordService;

    public MedicalRecordController(MedicalRecordService medicalRecordService) {
        this.medicalRecordService = medicalRecordService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('medical-record:read')")
    @Operation(summary = "Search accessible medical records")
    public ApiResponse<PageResponse<MedicalRecordResponse>> search(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size
    ) {
        return ApiResponse.success(medicalRecordService.search(keyword, page, size));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('medical-record:read')")
    @Operation(summary = "Get one accessible medical record")
    public ApiResponse<MedicalRecordResponse> get(@PathVariable @Positive long id) {
        return ApiResponse.success(medicalRecordService.get(id));
    }

    @PostMapping
    @PreAuthorize("hasAuthority('medical-record:write')")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a medical record")
    public ApiResponse<MedicalRecordResponse> create(@Valid @RequestBody CreateMedicalRecordRequest request) {
        return ApiResponse.success(medicalRecordService.create(request));
    }

    @PatchMapping("/{id}")
    @PreAuthorize("hasAuthority('medical-record:write')")
    @Operation(summary = "Update an accessible medical record")
    public ApiResponse<MedicalRecordResponse> update(
            @PathVariable @Positive long id,
            @Valid @RequestBody UpdateMedicalRecordRequest request
    ) {
        return ApiResponse.success(medicalRecordService.update(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('medical-record:write')")
    @Operation(summary = "Soft-delete an accessible medical record")
    public ApiResponse<Void> delete(@PathVariable @Positive long id) {
        medicalRecordService.delete(id);
        return ApiResponse.success();
    }
}
