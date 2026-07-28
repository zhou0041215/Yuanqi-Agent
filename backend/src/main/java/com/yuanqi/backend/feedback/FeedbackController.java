package com.yuanqi.backend.feedback;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.api.PageResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
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
@RequestMapping("/api/v1/feedback")
public class FeedbackController {
    private final FeedbackService service;

    public FeedbackController(FeedbackService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<FeedbackResponse> submit(@Valid @RequestBody FeedbackRequest request) {
        return ApiResponse.success(service.submit(request));
    }

    @GetMapping
    @PreAuthorize("hasAuthority('feedback:manage')")
    public ApiResponse<PageResponse<FeedbackResponse>> search(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size
    ) {
        return ApiResponse.success(service.search(page, size));
    }

    @PatchMapping("/{id}/resolve")
    @PreAuthorize("hasAuthority('feedback:manage')")
    public ApiResponse<FeedbackResponse> resolve(@PathVariable @Positive long id) {
        return ApiResponse.success(service.resolve(id));
    }
}
