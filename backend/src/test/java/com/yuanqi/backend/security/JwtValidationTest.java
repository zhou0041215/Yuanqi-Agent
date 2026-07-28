package com.yuanqi.backend.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwtValidationException;
import org.springframework.security.oauth2.jwt.JwsHeader;

class JwtValidationTest {
    private final SecurityConfig config = new SecurityConfig();
    private final SecretKey key = new SecretKeySpec(
            "0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8),
            "HmacSHA256"
    );

    @Test
    void decoderRequiresConfiguredIssuerAndAudience() {
        JwtEncoder encoder = config.jwtEncoder(key);
        JwtDecoder decoder = config.jwtDecoder(key, "yuanqi", "yuanqi-api");

        String valid = encode(encoder, "yuanqi", List.of("yuanqi-api"));
        assertEquals("1001", decoder.decode(valid).getSubject());

        String wrongAudience = encode(encoder, "yuanqi", List.of("another-api"));
        assertThrows(JwtValidationException.class, () -> decoder.decode(wrongAudience));

        String wrongIssuer = encode(encoder, "untrusted", List.of("yuanqi-api"));
        assertThrows(JwtValidationException.class, () -> decoder.decode(wrongIssuer));
    }

    private String encode(JwtEncoder encoder, String issuer, List<String> audience) {
        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(issuer)
                .audience(audience)
                .issuedAt(now)
                .expiresAt(now.plusSeconds(300))
                .subject("1001")
                .build();
        return encoder.encode(JwtEncoderParameters.from(
                JwsHeader.with(MacAlgorithm.HS256).build(),
                claims
        )).getTokenValue();
    }
}
