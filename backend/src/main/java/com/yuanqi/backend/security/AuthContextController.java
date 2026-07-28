package com.yuanqi.backend.security;

import com.yuanqi.backend.common.api.ApiResponse;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth/context")
public class AuthContextController {
    private final CurrentUserProvider currentUserProvider;

    public AuthContextController(CurrentUserProvider currentUserProvider) {
        this.currentUserProvider = currentUserProvider;
    }

    @GetMapping
    @PreAuthorize("isAuthenticated()")
    public ApiResponse<AuthContextResponse> current() {
        UserContext user = currentUserProvider.requireCurrentUser();
        Set<String> permissions = SecurityContextHolder.getContext().getAuthentication().getAuthorities().stream()
                .map(authority -> authority.getAuthority())
                .collect(Collectors.toUnmodifiableSet());
        return ApiResponse.success(new AuthContextResponse(
                user.userId(),
                user.tenantId(),
                user.username(),
                user.dataScope(),
                user.departmentIds(),
                permissions
        ));
    }

    public record AuthContextResponse(
            long userId,
            long tenantId,
            String username,
            DataScopeType dataScope,
            Set<Long> departmentIds,
            Set<String> permissions
    ) {
    }
}
