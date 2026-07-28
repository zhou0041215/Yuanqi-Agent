package com.yuanqi.backend.common.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuanqi.backend.common.api.ApiResponse;
import jakarta.servlet.FilterChain;
import jakarta.servlet.AsyncEvent;
import jakarta.servlet.AsyncListener;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;
import java.util.Base64;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingResponseWrapper;

@Component
@Order(Ordered.LOWEST_PRECEDENCE - 100)
public class IdempotencyFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(IdempotencyFilter.class);
    private static final String HEADER = "Idempotency-Key";
    private static final String PROCESSING = "PROCESSING";
    private static final Set<String> MUTATION_METHODS = Set.of("POST", "PUT", "PATCH", "DELETE");

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final Duration processingTtl;
    private final Duration responseTtl;

    public IdempotencyFilter(
            StringRedisTemplate redisTemplate,
            ObjectMapper objectMapper,
            @Value("${application.idempotency.processing-ttl:2m}") Duration processingTtl,
            @Value("${application.idempotency.response-ttl:24h}") Duration responseTtl
    ) {
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.processingTtl = processingTtl;
        this.responseTtl = responseTtl;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !MUTATION_METHODS.contains(request.getMethod()) || request.getHeader(HEADER) == null;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        String idempotencyKey = request.getHeader(HEADER);
        if (idempotencyKey == null || !idempotencyKey.matches("[A-Za-z0-9:_-]{8,128}")) {
            writeError(response, HttpServletResponse.SC_BAD_REQUEST,
                    "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key is invalid");
            return;
        }

        String redisKey = scopedRedisKey(idempotencyKey);
        try {
            String existing = acquireOrRead(redisKey);
            if (existing != null) {
                replayOrReject(response, existing);
                return;
            }
        } catch (RedisConnectionFailureException exception) {
            log.error("Idempotency store is unavailable", exception);
            writeError(response, HttpServletResponse.SC_SERVICE_UNAVAILABLE,
                    "IDEMPOTENCY_STORE_UNAVAILABLE", "Write safety store is unavailable");
            return;
        }

        ContentCachingResponseWrapper wrapped = new ContentCachingResponseWrapper(response);
        try {
            filterChain.doFilter(request, wrapped);
            if (request.isAsyncStarted()) {
                request.getAsyncContext().addListener(new AsyncListener() {
                    @Override
                    public void onComplete(AsyncEvent event) throws IOException {
                        finishResponse(redisKey, wrapped);
                    }
                    @Override
                    public void onTimeout(AsyncEvent event) {
                        redisTemplate.delete(redisKey);
                    }
                    @Override
                    public void onError(AsyncEvent event) {
                        redisTemplate.delete(redisKey);
                    }
                    @Override
                    public void onStartAsync(AsyncEvent event) {
                        // The same listener remains responsible for the original request.
                    }
                });
                return;
            }
            finishResponse(redisKey, wrapped);
        } catch (IOException | ServletException | RuntimeException exception) {
            redisTemplate.delete(redisKey);
            throw exception;
        }
    }

    private void finishResponse(String redisKey, ContentCachingResponseWrapper response) throws IOException {
        if (response.getStatus() >= 200 && response.getStatus() < 300) {
            cacheResponse(redisKey, response);
        } else {
            redisTemplate.delete(redisKey);
        }
        response.copyBodyToResponse();
    }

    private String acquireOrRead(String redisKey) {
        Boolean acquired = redisTemplate.opsForValue().setIfAbsent(redisKey, PROCESSING, processingTtl);
        if (Boolean.TRUE.equals(acquired)) {
            return null;
        }
        String existing = redisTemplate.opsForValue().get(redisKey);
        return existing == null ? PROCESSING : existing;
    }

    private void cacheResponse(String redisKey, ContentCachingResponseWrapper response) {
        try {
            CachedResponse cached = new CachedResponse(
                    response.getStatus(),
                    response.getContentType(),
                    Base64.getEncoder().encodeToString(response.getContentAsByteArray())
            );
            redisTemplate.opsForValue().set(redisKey, objectMapper.writeValueAsString(cached), responseTtl);
        } catch (Exception exception) {
            redisTemplate.delete(redisKey);
            log.error("Unable to cache idempotent response", exception);
        }
    }

    private void replayOrReject(HttpServletResponse response, String existing) throws IOException {
        if (PROCESSING.equals(existing)) {
            writeError(response, HttpServletResponse.SC_CONFLICT,
                    "REQUEST_IN_PROGRESS", "An identical write request is already in progress");
            return;
        }
        try {
            CachedResponse cached = objectMapper.readValue(existing, CachedResponse.class);
            response.setStatus(cached.status());
            response.setContentType(cached.contentType());
            response.setHeader("X-Idempotent-Replay", "true");
            response.getOutputStream().write(Base64.getDecoder().decode(cached.body()));
        } catch (Exception exception) {
            writeError(response, HttpServletResponse.SC_CONFLICT,
                    "INVALID_IDEMPOTENCY_STATE", "Stored idempotency state is invalid");
        }
    }

    private String scopedRedisKey(String key) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication instanceof JwtAuthenticationToken jwt) {
            Object tenantId = jwt.getToken().getClaim("tenant_id");
            return "idempotency:" + tenantId + ":" + jwt.getName() + ":" + key;
        }
        return "idempotency:anonymous:" + key;
    }

    private void writeError(HttpServletResponse response, int status, String code, String message)
            throws IOException {
        response.setStatus(status);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(response.getOutputStream(), ApiResponse.error(code, message, null));
    }

    private record CachedResponse(int status, String contentType, String body) {
    }
}
