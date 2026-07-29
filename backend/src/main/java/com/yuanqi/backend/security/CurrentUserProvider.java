package com.yuanqi.backend.security;

import com.yuanqi.backend.common.exception.BusinessException;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

@Component
public class CurrentUserProvider {

    public UserContext requireCurrentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (!(authentication instanceof JwtAuthenticationToken jwtAuthentication) || !authentication.isAuthenticated()) {
            throw BusinessException.unauthorized("A verified JWT is required");
        }

        long userId = parsePositiveLong(jwtAuthentication.getToken().getSubject(), "sub");
        DataScopeType scope = parseScope(jwtAuthentication.getToken().getClaimAsString("data_scope"));
        Set<Long> departmentIds = parseLongSet(jwtAuthentication.getToken().getClaim("department_ids"));
        String username = jwtAuthentication.getToken().getClaimAsString("preferred_username");
        if (username == null || username.isBlank()) {
            username = jwtAuthentication.getName();
        }
        return new UserContext(userId, username, scope, departmentIds);
    }

    private long parseLong(Object value, String claimName) {
        try {
            if (value instanceof Number number) {
                return number.longValue();
            }
            if (value instanceof String text && !text.isBlank()) {
                return Long.parseLong(text);
            }
        } catch (NumberFormatException ignored) {
            // Converted below into a stable authentication error.
        }
        throw BusinessException.unauthorized("JWT claim '" + claimName + "' is missing or invalid");
    }

    private long parsePositiveLong(Object value, String claimName) {
        long parsed = parseLong(value, claimName);
        if (parsed <= 0) {
            throw BusinessException.unauthorized("JWT claim '" + claimName + "' must be positive");
        }
        return parsed;
    }

    private DataScopeType parseScope(String value) {
        if (value == null) {
            throw BusinessException.unauthorized("JWT claim 'data_scope' is missing");
        }
        try {
            return DataScopeType.valueOf(value.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException exception) {
            throw BusinessException.unauthorized("JWT claim 'data_scope' is invalid");
        }
    }

    private Set<Long> parseLongSet(Object value) {
        if (!(value instanceof Collection<?> values)) {
            return Set.of();
        }
        Set<Long> result = new LinkedHashSet<>();
        for (Object item : values) {
            result.add(parsePositiveLong(item, "department_ids"));
        }
        return result;
    }
}
