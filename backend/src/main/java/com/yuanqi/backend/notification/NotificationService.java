package com.yuanqi.backend.notification;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class NotificationService {
    private final UserNotificationRepository repository;
    private final CurrentUserProvider currentUserProvider;

    public NotificationService(UserNotificationRepository repository, CurrentUserProvider currentUserProvider) {
        this.repository = repository;
        this.currentUserProvider = currentUserProvider;
    }

    @Transactional(readOnly = true)
    public PageResponse<NotificationResponse> list(int page, int size) {
        UserContext user = currentUserProvider.requireCurrentUser();
        return PageResponse.from(repository.findAllByTenantIdAndRecipientUserIdOrderByCreatedAtDesc(
                user.tenantId(), user.userId(), PageRequest.of(page, size)), NotificationResponse::from);
    }

    @Transactional(readOnly = true)
    public long unreadCount() {
        UserContext user = currentUserProvider.requireCurrentUser();
        return repository.countByTenantIdAndRecipientUserIdAndReadAtIsNull(user.tenantId(), user.userId());
    }

    @Transactional
    public NotificationResponse markRead(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        UserNotification notification = repository.findByIdAndTenantIdAndRecipientUserId(
                        id, user.tenantId(), user.userId())
                .orElseThrow(() -> BusinessException.notFound("Notification not found"));
        notification.markRead();
        return NotificationResponse.from(repository.save(notification));
    }

    @Transactional
    public void send(
            long tenantId,
            long recipientUserId,
            String type,
            String title,
            String content,
            String targetUrl
    ) {
        repository.save(new UserNotification(
                tenantId, recipientUserId, type, title, content, targetUrl));
    }
}
