package com.yuanqi.backend.agent.audit;

import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import java.time.Instant;
import java.util.List;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AgentAuditService {
    private final AgentAuditEventRepository repository;
    private final CurrentUserProvider currentUserProvider;

    public AgentAuditService(
            AgentAuditEventRepository repository,
            CurrentUserProvider currentUserProvider
    ) {
        this.repository = repository;
        this.currentUserProvider = currentUserProvider;
    }

    @Transactional
    public AgentAuditResponse record(AgentAuditRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        AgentAuditEvent event = new AgentAuditEvent(
                user.userId(),
                user.username(),
                request.threadId(),
                request.traceId(),
                request.toolName(),
                request.phase(),
                request.outcome(),
                request.riskLevel(),
                request.fingerprint(),
                Instant.now()
        );
        return AgentAuditResponse.from(repository.save(event));
    }

    @Transactional(readOnly = true)
    public List<AgentAuditResponse> recent(int limit) {
        UserContext user = currentUserProvider.requireCurrentUser();
        return repository.findAllByOrderByOccurredAtDesc(PageRequest.of(0, limit))
                .stream()
                .map(AgentAuditResponse::from)
                .toList();
    }
}
