package com.yuanqi.backend.knowledge;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface KnowledgeDocumentRepository extends JpaRepository<KnowledgeDocument, Long>,
        JpaSpecificationExecutor<KnowledgeDocument> {
    Optional<KnowledgeDocument> findByIdAndTenantId(long id, long tenantId);
    boolean existsByTenantIdAndDocumentKey(long tenantId, String documentKey);
    List<KnowledgeDocument> findAllByTenantIdAndStatusOrderByDocumentKey(long tenantId, String status);
}
