package com.yuanqi.backend.notification;

import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserNotificationRepository extends JpaRepository<UserNotification, Long> {
    Page<UserNotification> findAllByTenantIdAndRecipientUserIdOrderByCreatedAtDesc(
            long tenantId, long recipientUserId, Pageable pageable);
    Optional<UserNotification> findByIdAndTenantIdAndRecipientUserId(long id, long tenantId, long recipientUserId);
    long countByTenantIdAndRecipientUserIdAndReadAtIsNull(long tenantId, long recipientUserId);
}
