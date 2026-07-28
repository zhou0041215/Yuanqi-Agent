package com.yuanqi.backend.knowledge;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.api.PageResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/knowledge-documents")
public class KnowledgeDocumentController {
    private final KnowledgeDocumentService service;
    public KnowledgeDocumentController(KnowledgeDocumentService service) { this.service = service; }

    @GetMapping
    @PreAuthorize("hasAuthority('knowledge:manage')")
    public ApiResponse<PageResponse<KnowledgeDocumentResponse>> search(
            @RequestParam(required = false) String keyword, @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return ApiResponse.success(service.search(keyword, status, page, size));
    }
    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasAuthority('knowledge:manage')")
    public ApiResponse<KnowledgeDocumentResponse> create(@Valid @RequestBody KnowledgeDocumentRequest request) {
        return ApiResponse.success(service.create(request));
    }
    @PutMapping("/{id}")
    @PreAuthorize("hasAuthority('knowledge:manage')")
    public ApiResponse<KnowledgeDocumentResponse> update(@PathVariable @Positive long id,
            @Valid @RequestBody KnowledgeDocumentRequest request) {
        return ApiResponse.success(service.update(id, request));
    }
    @PatchMapping("/{id}/{action}")
    @PreAuthorize("hasAuthority('knowledge:publish')")
    public ApiResponse<KnowledgeDocumentResponse> transition(@PathVariable @Positive long id,
            @PathVariable @Pattern(regexp = "submit|publish|retire|reject|restore") String action) {
        return ApiResponse.success(service.transition(id, action));
    }
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAuthority('knowledge:manage')")
    public ApiResponse<KnowledgeDocumentResponse> delete(@PathVariable @Positive long id) {
        return ApiResponse.success(service.delete(id));
    }
    @GetMapping("/published")
    @PreAuthorize("hasAuthority('knowledge:index')")
    public ApiResponse<List<KnowledgeDocumentResponse>> published() {
        return ApiResponse.success(service.published());
    }
}
