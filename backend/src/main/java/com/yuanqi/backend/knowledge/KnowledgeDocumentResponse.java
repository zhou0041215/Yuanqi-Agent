package com.yuanqi.backend.knowledge;

import java.time.Instant;

public record KnowledgeDocumentResponse(
        long id, String documentKey, String title, String entityType, String content,
        String sourceUri, String status, int knowledgeVersion, Instant publishedAt,
        Long publishedBy, Instant createdAt, Instant updatedAt
) {
    static KnowledgeDocumentResponse from(KnowledgeDocument document) {
        return new KnowledgeDocumentResponse(
                document.getId(), document.getDocumentKey(), document.getTitle(), document.getEntityType(),
                document.getContent(), document.getSourceUri(), document.getStatus(), document.getKnowledgeVersion(),
                document.getPublishedAt(), document.getPublishedBy(), document.getCreatedAt(), document.getUpdatedAt());
    }
}
