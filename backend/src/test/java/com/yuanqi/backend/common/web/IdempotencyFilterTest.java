package com.yuanqi.backend.common.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

class IdempotencyFilterTest {

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void cachesSuccessfulMutationResponse() throws Exception {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        when(values.setIfAbsent(any(), eq("PROCESSING"), eq(Duration.ofMinutes(2))))
                .thenReturn(true);
        IdempotencyFilter filter = filter(redis);
        MockHttpServletRequest request = mutationRequest();
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = (servletRequest, servletResponse) -> {
            servletResponse.setContentType("application/json");
            servletResponse.getWriter().write("{\"code\":\"OK\"}");
        };

        filter.doFilter(request, response, chain);

        assertThat(response.getContentAsString()).isEqualTo("{\"code\":\"OK\"}");
        verify(values).set(
                startsWith("idempotency:anonymous:"),
                any(String.class),
                eq(Duration.ofHours(24))
        );
    }

    @Test
    void replaysCompletedResponseWithoutCallingBusinessChain() throws Exception {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        when(values.setIfAbsent(any(), eq("PROCESSING"), any(Duration.class))).thenReturn(false);
        String body = "{\"code\":\"OK\",\"data\":{\"id\":7}}";
        String cached = """
                {"status":200,"contentType":"application/json","body":"%s"}
                """.formatted(Base64.getEncoder().encodeToString(body.getBytes(StandardCharsets.UTF_8)));
        when(values.get(any())).thenReturn(cached);
        IdempotencyFilter filter = filter(redis);
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(mutationRequest(), response, chain);

        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(response.getHeader("X-Idempotent-Replay")).isEqualTo("true");
        assertThat(response.getContentAsString()).isEqualTo(body);
        verify(chain, never()).doFilter(any(), any());
    }

    private IdempotencyFilter filter(StringRedisTemplate redis) {
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        return new IdempotencyFilter(
                redis,
                objectMapper,
                Duration.ofMinutes(2),
                Duration.ofHours(24)
        );
    }

    private MockHttpServletRequest mutationRequest() {
        MockHttpServletRequest request = new MockHttpServletRequest("PATCH", "/api/v1/customers/7");
        request.addHeader("Idempotency-Key", "agent-test-12345678");
        return request;
    }
}
