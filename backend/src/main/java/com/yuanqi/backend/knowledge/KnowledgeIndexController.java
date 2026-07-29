package com.yuanqi.backend.knowledge;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.util.List;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/knowledge-index-versions")
@PreAuthorize("hasAuthority('knowledge:index')")
public class KnowledgeIndexController {
    private final KnowledgeIndexVersionRepository repository;
    private final CurrentUserProvider users;
    public KnowledgeIndexController(KnowledgeIndexVersionRepository repository, CurrentUserProvider users) {
        this.repository = repository; this.users = users;
    }
    @GetMapping @Transactional(readOnly = true)
    public ApiResponse<List<KnowledgeIndexResponse>> list() {
        UserContext user = users.requireCurrentUser();
        return ApiResponse.success(repository.findTop20ByOrderByCreatedAtDesc()
                .stream().map(KnowledgeIndexResponse::from).toList());
    }
    @PostMapping @Transactional
    public ApiResponse<KnowledgeIndexResponse> start(@Valid @RequestBody KnowledgeIndexRequest request) {
        UserContext user = users.requireCurrentUser();
        return ApiResponse.success(KnowledgeIndexResponse.from(repository.save(new KnowledgeIndexVersion(
                request.versionName(), request.collectionName(), user.userId()))));
    }
    @PatchMapping("/{id}/complete") @Transactional
    public ApiResponse<KnowledgeIndexResponse> complete(@PathVariable @Positive long id,
            @RequestParam @Min(0) int documentCount) {
        UserContext user = users.requireCurrentUser();
        KnowledgeIndexVersion value = repository.findById(id)
                .orElseThrow(() -> BusinessException.notFound("Knowledge index version"));
        repository.findAllByStatus("ACTIVE").stream()
                .filter(current -> !current.getId().equals(value.getId()))
                .forEach(KnowledgeIndexVersion::supersede);
        value.complete(documentCount);
        return ApiResponse.success(KnowledgeIndexResponse.from(repository.save(value)));
    }
    @PatchMapping("/{id}/fail") @Transactional
    public ApiResponse<KnowledgeIndexResponse> fail(
            @PathVariable @Positive long id,
            @RequestParam @Size(max = 1000) String error) {
        UserContext user = users.requireCurrentUser();
        KnowledgeIndexVersion value = repository.findById(id)
                .orElseThrow(() -> BusinessException.notFound("Knowledge index version"));
        value.fail(error);
        return ApiResponse.success(KnowledgeIndexResponse.from(repository.save(value)));
    }
}
