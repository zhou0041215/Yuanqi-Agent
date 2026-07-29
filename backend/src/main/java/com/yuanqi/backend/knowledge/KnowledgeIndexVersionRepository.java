package com.yuanqi.backend.knowledge;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KnowledgeIndexVersionRepository extends JpaRepository<KnowledgeIndexVersion, Long> {
    List<KnowledgeIndexVersion> findTop20ByOrderByCreatedAtDesc();
    List<KnowledgeIndexVersion> findAllByStatus(String status);
}
