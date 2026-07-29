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
@Table(name = "knowledge_index_version")
public class KnowledgeIndexVersion extends AuditedEntity {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "version_name", nullable = false, length = 100)
    private String versionName;
    @Column(name = "collection_name", nullable = false, length = 100)
    private String collectionName;
    @Column(nullable = false, length = 24)
    private String status;
    @Column(name = "document_count", nullable = false)
    private int documentCount;
    @Column(name = "requested_by", nullable = false, updatable = false)
    private long requestedBy;
    @Column(name = "error_message", length = 2000)
    private String errorMessage;
    @Column(name = "activated_at")
    private Instant activatedAt;
    protected KnowledgeIndexVersion() {}
    public KnowledgeIndexVersion(String versionName, String collectionName, long requestedBy) {
        this.versionName = versionName; this.collectionName = collectionName;
        this.requestedBy = requestedBy; this.status = "BUILDING";
    }
    public void complete(int count) { status = "ACTIVE"; documentCount = count; activatedAt = Instant.now(); errorMessage = null; }
    public void fail(String error) { status = "FAILED"; errorMessage = error; }
    public void supersede() {
        if ("ACTIVE".equals(status)) status = "SUPERSEDED";
    }
    public Long getId() { return id; }
    public String getVersionName() { return versionName; }
    public String getCollectionName() { return collectionName; }
    public String getStatus() { return status; }
    public int getDocumentCount() { return documentCount; }
    public long getRequestedBy() { return requestedBy; }
    public String getErrorMessage() { return errorMessage; }
    public Instant getActivatedAt() { return activatedAt; }
}
