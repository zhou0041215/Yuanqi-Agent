package com.yuanqi.backend.knowledge;

import java.time.Instant;

public record KnowledgeIndexResponse(long id, String versionName, String collectionName, String status,
        int documentCount, long requestedBy, String errorMessage, Instant activatedAt, Instant createdAt) {
    static KnowledgeIndexResponse from(KnowledgeIndexVersion value) {
        return new KnowledgeIndexResponse(value.getId(), value.getVersionName(), value.getCollectionName(),
                value.getStatus(), value.getDocumentCount(), value.getRequestedBy(), value.getErrorMessage(),
                value.getActivatedAt(), value.getCreatedAt());
    }
}
