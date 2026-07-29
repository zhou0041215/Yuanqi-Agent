package com.yuanqi.backend.knowledge;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import jakarta.persistence.criteria.Predicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class KnowledgeDocumentService {
    private final KnowledgeDocumentRepository repository;
    private final CurrentUserProvider users;
    public KnowledgeDocumentService(KnowledgeDocumentRepository repository, CurrentUserProvider users) {
        this.repository = repository; this.users = users;
    }

    @Transactional(readOnly = true)
    public PageResponse<KnowledgeDocumentResponse> search(String keyword, String status, int page, int size) {
        UserContext user = users.requireCurrentUser();
        return PageResponse.from(repository.findAll((root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (status != null && !status.isBlank() && !"ALL".equals(status)) {
                predicates.add(cb.equal(root.get("status"), status));
            } else {
                predicates.add(cb.notEqual(root.get("status"), "DELETED"));
            }
            if (keyword != null && !keyword.isBlank()) {
                String pattern = "%" + keyword.trim().toLowerCase() + "%";
                predicates.add(cb.or(cb.like(cb.lower(root.get("title")), pattern),
                        cb.like(cb.lower(root.get("documentKey")), pattern)));
            }
            query.orderBy(cb.desc(root.get("updatedAt")));
            return cb.and(predicates.toArray(Predicate[]::new));
        }, PageRequest.of(page, size)), KnowledgeDocumentResponse::from);
    }

    @Transactional
    public KnowledgeDocumentResponse create(KnowledgeDocumentRequest request) {
        UserContext user = users.requireCurrentUser();
        if (repository.existsByDocumentKey(request.documentKey())) {
            throw BusinessException.conflict("Knowledge document key already exists");
        }
        return KnowledgeDocumentResponse.from(repository.save(new KnowledgeDocument(
                request.documentKey(), request.title(), request.entityType(),
                request.content(), request.sourceUri())));
    }

    @Transactional
    public KnowledgeDocumentResponse update(long id, KnowledgeDocumentRequest request) {
        UserContext user = users.requireCurrentUser();
        KnowledgeDocument document = require(id);
        document.update(request.title(), request.entityType(), request.content(), request.sourceUri());
        return KnowledgeDocumentResponse.from(repository.save(document));
    }

    @Transactional
    public KnowledgeDocumentResponse transition(long id, String action) {
        UserContext user = users.requireCurrentUser();
        KnowledgeDocument document = require(id);
        String next = switch (action) {
            case "submit" -> "REVIEW";
            case "publish" -> "PUBLISHED";
            case "retire" -> "RETIRED";
            case "reject" -> "DRAFT";
            case "restore" -> "DRAFT";
            default -> throw BusinessException.conflict("Unsupported knowledge action");
        };
        if ("restore".equals(action) && !"RETIRED".equals(document.getStatus())) {
            throw BusinessException.conflict("Only retired documents can be restored");
        }
        if (("submit".equals(action) || "publish".equals(action))
                && (document.getSourceUri() == null
                || !document.getSourceUri().startsWith("https://")
                || document.getContent().length() < 200)) {
            throw BusinessException.conflict(
                    "Review and publication require an HTTPS source and at least 200 characters");
        }
        if ("publish".equals(action) && !"REVIEW".equals(document.getStatus())) {
            throw BusinessException.conflict("Only reviewed documents can be published");
        }
        document.transition(next, user.userId());
        return KnowledgeDocumentResponse.from(repository.save(document));
    }

    @Transactional
    public KnowledgeDocumentResponse delete(long id) {
        UserContext user = users.requireCurrentUser();
        KnowledgeDocument document = require(id);
        if (!"DRAFT".equals(document.getStatus()) && !"RETIRED".equals(document.getStatus())) {
            throw BusinessException.conflict("Only draft or retired documents can be deleted");
        }
        document.transition("DELETED", user.userId());
        return KnowledgeDocumentResponse.from(repository.save(document));
    }

    @Transactional(readOnly = true)
    public List<KnowledgeDocumentResponse> published() {
        UserContext user = users.requireCurrentUser();
        return repository.findAllByStatusOrderByDocumentKey("PUBLISHED")
                .stream().map(KnowledgeDocumentResponse::from).toList();
    }

    private KnowledgeDocument require(long id) {
        return repository.findById(id)
                .orElseThrow(() -> BusinessException.notFound("Knowledge document"));
    }
}
