package com.yuanqi.backend.access.repository;

import com.yuanqi.backend.access.domain.AccessAuditEvent;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AccessAuditEventRepository extends JpaRepository<AccessAuditEvent, Long> {
    List<AccessAuditEvent> findAllByTenantIdOrderByOccurredAtDesc(long tenantId, Pageable pageable);
}
