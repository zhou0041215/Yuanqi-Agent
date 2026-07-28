package com.yuanqi.backend.conversation;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/conversations")
public class ConversationSessionController {
    private final ConversationSessionRepository repository;
    private final CurrentUserProvider users;
    private final ObjectMapper objectMapper;

    public ConversationSessionController(
            ConversationSessionRepository repository,
            CurrentUserProvider users,
            ObjectMapper objectMapper
    ) {
        this.repository = repository;
        this.users = users;
        this.objectMapper = objectMapper;
    }

    @GetMapping
    @Transactional(readOnly = true)
    public ApiResponse<List<Response>> list() {
        UserContext user = users.requireCurrentUser();
        return ApiResponse.success(repository
                .findTop50ByTenantIdAndOwnerUserIdOrderByUpdatedAtDesc(
                        user.tenantId(), user.userId())
                .stream().map(this::response).toList());
    }

    @PutMapping("/{id}")
    @Transactional
    public ApiResponse<Response> save(
            @PathVariable @Size(max = 64) String id,
            @Valid @RequestBody SaveRequest request
    ) {
        UserContext user = users.requireCurrentUser();
        String turns = serialize(request.turns());
        if (turns.length() > 1_500_000) {
            throw BusinessException.conflict("Conversation is too large to synchronize");
        }
        ConversationSession session = repository
                .findByIdAndTenantIdAndOwnerUserId(id, user.tenantId(), user.userId())
                .orElseGet(() -> new ConversationSession(
                        id, user.tenantId(), user.userId(), request.title(), turns,
                        request.favorite(), request.archived(),
                        Instant.ofEpochMilli(request.createdAt())));
        session.update(
                request.title().trim(), turns, request.favorite(), request.archived());
        return ApiResponse.success(response(repository.save(session)));
    }

    @DeleteMapping("/{id}")
    @Transactional
    public ApiResponse<Void> delete(@PathVariable String id) {
        UserContext user = users.requireCurrentUser();
        ConversationSession session = repository
                .findByIdAndTenantIdAndOwnerUserId(id, user.tenantId(), user.userId())
                .orElseThrow(() -> BusinessException.notFound("Conversation"));
        repository.delete(session);
        return ApiResponse.success(null);
    }

    private Response response(ConversationSession session) {
        try {
            return new Response(
                    session.getId(), session.getTitle(),
                    objectMapper.readTree(session.getTurnsJson()),
                    session.isFavorite(), session.isArchived(),
                    session.getCreatedAt().toEpochMilli(), session.getUpdatedAt().toEpochMilli());
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Stored conversation JSON is invalid", exception);
        }
    }

    private String serialize(JsonNode turns) {
        if (!turns.isArray()) throw BusinessException.conflict("Conversation turns must be an array");
        try {
            return objectMapper.writeValueAsString(turns);
        } catch (JsonProcessingException exception) {
            throw BusinessException.conflict("Conversation turns are invalid");
        }
    }

    public record SaveRequest(
            @NotBlank @Size(max = 120) String title,
            JsonNode turns,
            boolean favorite,
            boolean archived,
            long createdAt
    ) {}
    public record Response(
            String id, String title, JsonNode turns, boolean favorite, boolean archived,
            long createdAt, long updatedAt
    ) {}
}
