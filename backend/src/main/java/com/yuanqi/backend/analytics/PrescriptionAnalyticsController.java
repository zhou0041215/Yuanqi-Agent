package com.yuanqi.backend.analytics;

import com.yuanqi.backend.analytics.dto.PrescriptionAnalysisSnapshot;
import com.yuanqi.backend.analytics.dto.PrescriptionDatasetSchema;
import com.yuanqi.backend.analytics.dto.PrescriptionSnapshotRequest;
import com.yuanqi.backend.common.api.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/analytics/prescriptions")
@Tag(name = "Prescription analytics", description = "De-identified, bounded datasets for the Agent sandbox")
public class PrescriptionAnalyticsController {
    private final PrescriptionAnalyticsService service;

    public PrescriptionAnalyticsController(PrescriptionAnalyticsService service) {
        this.service = service;
    }

    @GetMapping("/schema")
    @PreAuthorize("hasAuthority('prescription:read')")
    @Operation(summary = "Describe the prescription-analysis dataset without returning rows")
    public ApiResponse<PrescriptionDatasetSchema> schema() {
        return ApiResponse.success(service.schema());
    }

    @PostMapping("/snapshot")
    @PreAuthorize("hasAuthority('prescription:read')")
    @Operation(summary = "Create a bounded, de-identified prescription snapshot under JWT row scope")
    public ApiResponse<PrescriptionAnalysisSnapshot> snapshot(
            @Valid @RequestBody PrescriptionSnapshotRequest request
    ) {
        return ApiResponse.success(service.snapshot(request));
    }
}
