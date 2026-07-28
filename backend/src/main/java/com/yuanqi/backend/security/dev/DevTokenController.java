package com.yuanqi.backend.security.dev;

import com.yuanqi.backend.common.api.ApiResponse;
import com.yuanqi.backend.security.DataScopeType;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Set;
import org.springframework.context.annotation.Profile;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Profile("dev")
@RestController
@RequestMapping("/api/v1/dev/token")
public class DevTokenController {
    private final JwtEncoder jwtEncoder;
    private final String issuer;
    private final String audience;

    public DevTokenController(
            JwtEncoder jwtEncoder,
            @Value("${security.jwt.issuer}") String issuer,
            @Value("${security.jwt.audience}") String audience
    ) {
        this.jwtEncoder = jwtEncoder;
        this.issuer = issuer;
        this.audience = audience;
    }

    @PostMapping
    public ApiResponse<TokenResponse> create(@Valid @RequestBody TokenRequest request) {
        Instant issuedAt = Instant.now();
        Instant expiresAt = issuedAt.plus(8, ChronoUnit.HOURS);
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(issuer)
                .audience(java.util.List.of(audience))
                .issuedAt(issuedAt)
                .expiresAt(expiresAt)
                .subject(Long.toString(request.userId()))
                .claim("tenant_id", request.tenantId())
                .claim("preferred_username", request.username())
                .claim("data_scope", request.dataScope().name())
                .claim("department_ids", request.departmentIds())
                .claim("permissions", request.permissions())
                .build();
        JwsHeader header = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = jwtEncoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();
        return ApiResponse.success(new TokenResponse(token, "Bearer", expiresAt));
    }

    public record TokenRequest(
            @Positive long userId,
            @Positive long tenantId,
            @NotBlank String username,
            @NotNull DataScopeType dataScope,
            @NotNull Set<@Positive Long> departmentIds,
            @NotNull Set<@NotBlank String> permissions
    ) {
    }

    public record TokenResponse(String accessToken, String tokenType, Instant expiresAt) {
    }
}
