package com.yuanqi.backend.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

class JwtPermissionConverterTest {

    @Test
    void mapsPermissionClaimWithoutAddingAHiddenPrefix() {
        Jwt jwt = Jwt.withTokenValue("test-token")
                .header("alg", "HS256")
                .subject("1001")
                .issuedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(60))
                .claim("scope", "profile")
                .claim("permissions", List.of("patient:read", "prescription:write"))
                .build();

        assertThat(new JwtPermissionConverter().convert(jwt))
                .extracting("authority")
                .containsExactlyInAnyOrder("SCOPE_profile", "patient:read", "prescription:write");
    }
}
