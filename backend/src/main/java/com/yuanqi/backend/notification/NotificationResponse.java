package com.yuanqi.backend.notification;

import java.time.Instant;

public record NotificationResponse(
        long id, String type, String title, String content, String targetUrl,
        Instant readAt, Instant createdAt
) {
    static NotificationResponse from(UserNotification notification) {
        return new NotificationResponse(
                notification.getId(), notification.getType(), notification.getTitle(),
                notification.getContent(), notification.getTargetUrl(), notification.getReadAt(),
                notification.getCreatedAt()
        );
    }
}
