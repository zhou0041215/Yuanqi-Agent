package com.yuanqi.backend.security;

import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
public class AccountAuthController {
    private final AccessPersonRepository people;
    private final UserAccountRepository accounts;
    private final PasswordEncoder encoder;
    private final JwtEncoder jwt;
    private final CurrentUserProvider currentUserProvider;
    private final String issuer;
    private final String audience;

    public AccountAuthController(
            AccessPersonRepository people,
            UserAccountRepository accounts,
            PasswordEncoder encoder,
            JwtEncoder jwt,
            CurrentUserProvider currentUserProvider,
            @Value("${security.jwt.issuer}") String issuer,
            @Value("${security.jwt.audience}") String audience
    ) {
        this.people = people;
        this.accounts = accounts;
        this.encoder = encoder;
        this.jwt = jwt;
        this.currentUserProvider = currentUserProvider;
        this.issuer = issuer;
        this.audience = audience;
    }

    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        var person = people.findAllByTenantIdOrderByDisplayNameAsc(1).stream()
                .filter(candidate -> candidate.getUsername().equals(request.username()))
                .findFirst()
                .orElseThrow(() -> BusinessException.forbidden("Invalid username or password"));
        var account = accounts.findByTenantIdAndUserId(1, person.getUserId())
                .filter(candidate -> "ACTIVE".equals(candidate.getStatus()))
                .orElseThrow(() -> BusinessException.forbidden("Invalid username or password"));
        if (!"ACTIVE".equals(person.getStatus())
                || !encoder.matches(request.password(), account.getPasswordHash())) {
            throw BusinessException.forbidden("Invalid username or password");
        }
        var permissions = new HashSet<>(Set.of(
                "patient:read", "medical-record:read", "prescription:read"));
        if (!"CLINICAL_COLLABORATOR".equals(person.getRoleCode())) {
            permissions.addAll(Set.of(
                    "patient:write", "medical-record:write", "prescription:write"));
        }
        if ("SYSTEM_ADMIN".equals(person.getRoleCode())) {
            permissions.addAll(Set.of(
                    "access:manage", "agent:audit:read", "feedback:manage",
                    "knowledge:manage", "knowledge:publish", "knowledge:index"));
        }
        var now = Instant.now();
        var claims = JwtClaimsSet.builder()
                .issuer(issuer)
                .audience(List.of(audience))
                .subject(Long.toString(person.getUserId()))
                .issuedAt(now)
                .expiresAt(now.plus(8, ChronoUnit.HOURS))
                .claim("tenant_id", 1)
                .claim("preferred_username", person.getUsername())
                .claim("data_scope", person.getDataScope().name())
                .claim("department_ids", Set.of(person.getDepartmentId()))
                .claim("permissions", permissions)
                .build();
        String accessToken = jwt.encode(JwtEncoderParameters.from(
                JwsHeader.with(MacAlgorithm.HS256).build(), claims)).getTokenValue();
        return ApiResponse.success(new LoginResponse(accessToken, account.isMustChangePassword()));
    }

    @PostMapping("/change-password")
    public ApiResponse<Void> changePassword(@Valid @RequestBody ChangePasswordRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        UserAccount account = accounts.findByTenantIdAndUserId(user.tenantId(), user.userId())
                .orElseThrow(() -> BusinessException.notFound("User account"));
        if (!encoder.matches(request.currentPassword(), account.getPasswordHash())) {
            throw BusinessException.forbidden("Current password is incorrect");
        }
        if (encoder.matches(request.newPassword(), account.getPasswordHash())) {
            throw BusinessException.conflict("New password must differ from the current password");
        }
        account.changePassword(encoder.encode(request.newPassword()));
        accounts.save(account);
        return ApiResponse.success(null);
    }

    public record LoginRequest(@NotBlank String username, @NotBlank String password) {}
    public record LoginResponse(String accessToken, boolean mustChangePassword) {}
    public record ChangePasswordRequest(
            @NotBlank String currentPassword,
            @Size(min = 10, max = 72)
            @Pattern(
                    regexp = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[^A-Za-z0-9]).+$",
                    message = "Password must include upper/lower case letters, a number, and a symbol")
            String newPassword
    ) {}
}
