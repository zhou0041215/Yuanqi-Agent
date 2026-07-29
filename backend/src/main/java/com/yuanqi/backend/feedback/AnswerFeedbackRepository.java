package com.yuanqi.backend.feedback;

import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AnswerFeedbackRepository extends JpaRepository<AnswerFeedback, Long> {
    Optional<AnswerFeedback> findByTurnIdAndUserId(String turnId, long userId);
    Page<AnswerFeedback> findAllByOrderByCreatedAtDesc(Pageable pageable);
}
