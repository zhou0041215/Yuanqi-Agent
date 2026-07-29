package com.yuanqi.backend.feedback;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class FeedbackService {
    private final AnswerFeedbackRepository repository;
    private final CurrentUserProvider currentUserProvider;

    public FeedbackService(AnswerFeedbackRepository repository, CurrentUserProvider currentUserProvider) {
        this.repository = repository;
        this.currentUserProvider = currentUserProvider;
    }

    @Transactional
    public FeedbackResponse submit(FeedbackRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        AnswerFeedback feedback = repository
                .findByTurnIdAndUserId(request.turnId(), user.userId())
                .orElseGet(() -> new AnswerFeedback(
                        user.userId(), user.username(), request.sessionId(), request.turnId(),
                        request.rating(), request.category(), request.comment()
                ));
        return FeedbackResponse.from(repository.save(feedback));
    }

    @Transactional(readOnly = true)
    public PageResponse<FeedbackResponse> search(int page, int size) {
        UserContext user = currentUserProvider.requireCurrentUser();
        return PageResponse.from(
                repository.findAllByOrderByCreatedAtDesc(PageRequest.of(page, size)),
                FeedbackResponse::from
        );
    }

    @Transactional
    public FeedbackResponse resolve(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        AnswerFeedback feedback = repository.findById(id)
                .orElseThrow(() -> BusinessException.notFound("Feedback not found"));
        feedback.resolve();
        return FeedbackResponse.from(repository.save(feedback));
    }
}
