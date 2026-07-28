package com.yuanqi.backend.notification;

import com.yuanqi.backend.common.persistence.AuditedEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "user_notification")
public class UserNotification extends AuditedEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;
    @Column(name = "recipient_user_id", nullable = false, updatable = false)
    private long recipientUserId;
    @Column(nullable = false, length = 32)
    private String type;
    @Column(nullable = false, length = 200)
    private String title;
    @Column(nullable = false, length = 1000)
    private String content;
    @Column(name = "target_url", length = 500)
    private String targetUrl;
    @Column(name = "read_at")
    private Instant readAt;

    protected UserNotification() {}

    public UserNotification(long tenantId, long recipientUserId, String type, String title, String content, String targetUrl) {
        this.tenantId = tenantId;
        this.recipientUserId = recipientUserId;
        this.type = type;
        this.title = title;
        this.content = content;
        this.targetUrl = targetUrl;
    }

    public Long getId() { return id; }
    public String getType() { return type; }
    public String getTitle() { return title; }
    public String getContent() { return content; }
    public String getTargetUrl() { return targetUrl; }
    public Instant getReadAt() { return readAt; }
    public void markRead() { readAt = Instant.now(); }
}
