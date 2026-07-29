package com.yuanqi.backend.knowledge;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface KnowledgeDocumentRepository extends JpaRepository<KnowledgeDocument, Long>,
        JpaSpecificationExecutor<KnowledgeDocument> {
    boolean existsByDocumentKey(String documentKey);
    List<KnowledgeDocument> findAllByStatusOrderByDocumentKey(String status);
}
