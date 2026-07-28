package com.yuanqi.backend.security;

import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Set;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;

public class JwtPermissionConverter implements Converter<Jwt, Collection<GrantedAuthority>> {
    private final JwtGrantedAuthoritiesConverter scopeConverter = new JwtGrantedAuthoritiesConverter();

    @Override
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        Set<GrantedAuthority> authorities = new LinkedHashSet<>(scopeConverter.convert(jwt));
        Object claim = jwt.getClaim("permissions");
        if (claim instanceof Collection<?> permissions) {
            permissions.stream()
                    .filter(String.class::isInstance)
                    .map(String.class::cast)
                    .map(String::trim)
                    .filter(permission -> !permission.isEmpty())
                    .map(SimpleGrantedAuthority::new)
                    .forEach(authorities::add);
        } else if (claim instanceof String permissions) {
            for (String permission : permissions.split("[\\s,]+")) {
                if (!permission.isBlank()) {
                    authorities.add(new SimpleGrantedAuthority(permission.trim()));
                }
            }
        }
        return authorities;
    }
}
