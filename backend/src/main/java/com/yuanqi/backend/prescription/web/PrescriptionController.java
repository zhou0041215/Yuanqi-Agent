package com.yuanqi.backend.prescription.web;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.prescription.service.PrescriptionService;
import com.yuanqi.backend.prescription.web.dto.CreatePrescriptionRequest;
import com.yuanqi.backend.prescription.web.dto.PrescriptionResponse;
import com.yuanqi.backend.prescription.web.dto.UpdatePrescriptionRequest;
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
@RequestMapping("/api/v1/prescriptions")
@Tag(name = "Prescriptions", description = "Prescription CRUD constrained by JWT row-level data scope")
public class PrescriptionController {
    private final PrescriptionService prescriptionService;

    public PrescriptionController(PrescriptionService prescriptionService) {
        this.prescriptionService = prescriptionService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('prescription:read')")
    @Operation(summary = "Search accessible prescriptions")
    public ApiResponse<PageResponse<PrescriptionResponse>> search(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size
    ) {
        return ApiResponse.success(prescriptionService.search(keyword, page, size));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAuthority('prescription:read')")
    @Operation(summary = "Get one accessible prescription")
    public ApiResponse<PrescriptionResponse> get(@PathVariable @Positive long id) {
        return ApiResponse.success(prescriptionService.get(id));
    }

    @PostMapping
    @PreAuthorize("hasAuthority('prescription:write')")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a prescription")
    public ApiResponse<PrescriptionResponse> create(@Valid @RequestBody CreatePrescriptionRequest request) {
        return ApiResponse.success(prescriptionService.create(request));
    }

    @PatchMapping("/{id}")
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "Update an accessible prescription")
    public ApiResponse<PrescriptionResponse> update(
            @PathVariable @Positive long id,
            @Valid @RequestBody UpdatePrescriptionRequest request
    ) {
        return ApiResponse.success(prescriptionService.update(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('prescription:write')")
    @Operation(summary = "Soft-delete an accessible prescription")
    public ApiResponse<Void> delete(@PathVariable @Positive long id) {
        prescriptionService.delete(id);
        return ApiResponse.success();
    }
}
