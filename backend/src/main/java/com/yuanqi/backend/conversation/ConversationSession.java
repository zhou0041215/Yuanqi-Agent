package com.yuanqi.backend.conversation;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "conversation_session")
public class ConversationSession {
    @Id
    @Column(length = 64)
    private String id;
    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;
    @Column(name = "owner_user_id", nullable = false, updatable = false)
    private long ownerUserId;
    @Column(nullable = false, length = 120)
    private String title;
    @Column(name = "turns_json", nullable = false, columnDefinition = "MEDIUMTEXT")
    private String turnsJson;
    @Column(nullable = false)
    private boolean favorite;
    @Column(nullable = false)
    private boolean archived;
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected ConversationSession() {}

    public ConversationSession(
            String id, long tenantId, long ownerUserId, String title, String turnsJson,
            boolean favorite, boolean archived, Instant createdAt
    ) {
        this.id = id;
        this.tenantId = tenantId;
        this.ownerUserId = ownerUserId;
        update(title, turnsJson, favorite, archived);
        this.createdAt = createdAt;
    }

    public void update(String title, String turnsJson, boolean favorite, boolean archived) {
        this.title = title;
        this.turnsJson = turnsJson;
        this.favorite = favorite;
        this.archived = archived;
        this.updatedAt = Instant.now();
    }

    public String getId() { return id; }
    public String getTitle() { return title; }
    public String getTurnsJson() { return turnsJson; }
    public boolean isFavorite() { return favorite; }
    public boolean isArchived() { return archived; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
}
