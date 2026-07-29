package com.yuanqi.backend.conversation;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConversationSessionRepository extends JpaRepository<ConversationSession, String> {
    List<ConversationSession> findTop50ByOwnerUserIdOrderByUpdatedAtDesc(long ownerUserId);
    Optional<ConversationSession> findByIdAndOwnerUserId(String id, long ownerUserId);
}
