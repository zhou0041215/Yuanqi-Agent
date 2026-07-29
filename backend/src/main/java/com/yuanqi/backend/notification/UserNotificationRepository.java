package com.yuanqi.backend.notification;

import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserNotificationRepository extends JpaRepository<UserNotification, Long> {
    Page<UserNotification> findAllByRecipientUserIdOrderByCreatedAtDesc(long recipientUserId, Pageable pageable);
    Optional<UserNotification> findByIdAndRecipientUserId(long id, long recipientUserId);
    long countByRecipientUserIdAndReadAtIsNull(long recipientUserId);
}
