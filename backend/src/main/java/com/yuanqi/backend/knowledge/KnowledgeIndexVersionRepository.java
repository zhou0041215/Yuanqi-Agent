package com.yuanqi.backend.knowledge;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KnowledgeIndexVersionRepository extends JpaRepository<KnowledgeIndexVersion, Long> {
    Optional<KnowledgeIndexVersion> findByIdAndTenantId(long id, long tenantId);
    List<KnowledgeIndexVersion> findTop20ByTenantIdOrderByCreatedAtDesc(long tenantId);
    List<KnowledgeIndexVersion> findAllByTenantIdAndStatus(long tenantId, String status);
}
