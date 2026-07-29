package com.yuanqi.backend.agent.audit;

import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentAuditEventRepository extends JpaRepository<AgentAuditEvent, Long> {
    List<AgentAuditEvent> findAllByOrderByOccurredAtDesc(Pageable pageable);
}
