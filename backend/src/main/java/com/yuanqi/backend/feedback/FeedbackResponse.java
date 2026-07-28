package com.yuanqi.backend.feedback;

import java.time.Instant;

public record FeedbackResponse(
        long id, long userId, String username, String sessionId, String turnId,
        String rating, String category, String comment, String status,
        Instant createdAt, Instant updatedAt
) {
    static FeedbackResponse from(AnswerFeedback feedback) {
        return new FeedbackResponse(
                feedback.getId(), feedback.getUserId(), feedback.getUsername(),
                feedback.getSessionId(), feedback.getTurnId(), feedback.getRating(),
                feedback.getCategory(), feedback.getComment(), feedback.getStatus(),
                feedback.getCreatedAt(), feedback.getUpdatedAt()
        );
    }
}
