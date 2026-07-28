package com.yuanqi.backend.feedback;

import com.yuanqi.backend.common.persistence.AuditedEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "answer_feedback")
public class AnswerFeedback extends AuditedEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;
    @Column(name = "user_id", nullable = false, updatable = false)
    private long userId;
    @Column(nullable = false, length = 200)
    private String username;
    @Column(name = "session_id", nullable = false, length = 64)
    private String sessionId;
    @Column(name = "turn_id", nullable = false, length = 64)
    private String turnId;
    @Column(nullable = false, length = 16)
    private String rating;
    @Column(length = 32)
    private String category;
    @Column(length = 2000)
    private String comment;
    @Column(nullable = false, length = 24)
    private String status;

    protected AnswerFeedback() {}

    public AnswerFeedback(long tenantId, long userId, String username, String sessionId, String turnId,
                          String rating, String category, String comment) {
        this.tenantId = tenantId;
        this.userId = userId;
        this.username = username;
        this.sessionId = sessionId;
        this.turnId = turnId;
        this.rating = rating;
        this.category = category;
        this.comment = comment;
        this.status = "OPEN";
    }

    public Long getId() { return id; }
    public long getUserId() { return userId; }
    public String getUsername() { return username; }
    public String getSessionId() { return sessionId; }
    public String getTurnId() { return turnId; }
    public String getRating() { return rating; }
    public String getCategory() { return category; }
    public String getComment() { return comment; }
    public String getStatus() { return status; }
    public void resolve() { status = "RESOLVED"; }
}
