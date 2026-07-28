package com.yuanqi.backend.security;

import jakarta.persistence.criteria.Predicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.jpa.domain.Specification;

public final class ScopedSpecifications {
    private ScopedSpecifications() {
    }

    public static <T> Specification<T> accessible(UserContext user) {
        return (root, query, criteriaBuilder) -> {
            List<Predicate> mandatory = new ArrayList<>();
            mandatory.add(criteriaBuilder.equal(root.get("tenantId"), user.tenantId()));
            mandatory.add(criteriaBuilder.isFalse(root.get("deleted")));

            if (user.hasAllAccess()) {
                return criteriaBuilder.and(mandatory.toArray(Predicate[]::new));
            }
            Predicate rowScope;
            if (user.hasSelfAccess()) {
                rowScope = criteriaBuilder.equal(root.get("ownerId"), user.userId());
            } else if (user.departmentIds().isEmpty()) {
                rowScope = criteriaBuilder.disjunction();
            } else {
                rowScope = root.get("departmentId").in(user.departmentIds());
            }
            mandatory.add(rowScope);
            return criteriaBuilder.and(mandatory.toArray(Predicate[]::new));
        };
    }

    public static <T> Specification<T> idEquals(long id) {
        return (root, query, criteriaBuilder) -> criteriaBuilder.equal(root.get("id"), id);
    }

    public static <T> Specification<T> keywordContains(String keyword, String... attributes) {
        if (keyword == null || keyword.isBlank()) {
            return (root, query, criteriaBuilder) -> criteriaBuilder.conjunction();
        }
        String pattern = "%" + keyword.trim().toLowerCase() + "%";
        return (root, query, criteriaBuilder) -> {
            Predicate[] matches = new Predicate[attributes.length];
            for (int index = 0; index < attributes.length; index++) {
                matches[index] = criteriaBuilder.like(criteriaBuilder.lower(root.get(attributes[index])), pattern);
            }
            return criteriaBuilder.or(matches);
        };
    }
}
