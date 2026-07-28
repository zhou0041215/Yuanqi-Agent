package com.yuanqi.backend.knowledge;

import com.yuanqi.backend.common.persistence.AuditedEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "knowledge_document")
public class KnowledgeDocument extends AuditedEntity {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;
    @Column(name = "document_key", nullable = false, length = 128)
    private String documentKey;
    @Column(nullable = false, length = 300)
    private String title;
    @Column(name = "entity_type", nullable = false, length = 32)
    private String entityType;
    @Column(nullable = false, columnDefinition = "MEDIUMTEXT")
    private String content;
    @Column(name = "source_uri", length = 1000)
    private String sourceUri;
    @Column(nullable = false, length = 24)
    private String status;
    @Column(name = "knowledge_version", nullable = false)
    private int knowledgeVersion;
    @Column(name = "published_at")
    private Instant publishedAt;
    @Column(name = "published_by")
    private Long publishedBy;

    protected KnowledgeDocument() {}
    public KnowledgeDocument(long tenantId, String key, String title, String entityType, String content, String sourceUri) {
        this.tenantId = tenantId; this.documentKey = key; this.title = title;
        this.entityType = entityType; this.content = content; this.sourceUri = sourceUri;
        this.status = "DRAFT"; this.knowledgeVersion = 1;
    }
    public void update(String title, String entityType, String content, String sourceUri) {
        if ("PUBLISHED".equals(status)) knowledgeVersion++;
        this.title = title; this.entityType = entityType; this.content = content; this.sourceUri = sourceUri;
        this.status = "DRAFT"; this.publishedAt = null; this.publishedBy = null;
    }
    public void transition(String next, long actor) {
        status = next;
        if ("PUBLISHED".equals(next)) { publishedAt = Instant.now(); publishedBy = actor; }
    }
    public Long getId() { return id; }
    public String getDocumentKey() { return documentKey; }
    public String getTitle() { return title; }
    public String getEntityType() { return entityType; }
    public String getContent() { return content; }
    public String getSourceUri() { return sourceUri; }
    public String getStatus() { return status; }
    public int getKnowledgeVersion() { return knowledgeVersion; }
    public Instant getPublishedAt() { return publishedAt; }
    public Long getPublishedBy() { return publishedBy; }
}
