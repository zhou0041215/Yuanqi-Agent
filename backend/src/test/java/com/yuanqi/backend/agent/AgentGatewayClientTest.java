package com.yuanqi.backend.agent;

import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AgentGatewayClientTest {
    private HttpServer server;
    private URI baseUri;

    @BeforeEach
    void startServer() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        baseUri = URI.create("http://127.0.0.1:" + server.getAddress().getPort());
        server.start();
    }

    @AfterEach
    void stopServer() {
        server.stop(0);
    }

    @Test
    void forwardsJwtTraceQueryAndStreamingBodyWithoutRewritingPayload() throws Exception {
        AtomicReference<String> authorization = new AtomicReference<>();
        AtomicReference<String> traceId = new AtomicReference<>();
        AtomicReference<String> query = new AtomicReference<>();
        AtomicReference<String> requestBody = new AtomicReference<>();
        byte[] sse = "event: text\ndata: {\"text\":\"ok\"}\n\n".getBytes(StandardCharsets.UTF_8);

        server.createContext("/api/v1/agent/stream", exchange -> {
            authorization.set(exchange.getRequestHeaders().getFirst("Authorization"));
            traceId.set(exchange.getRequestHeaders().getFirst("X-Trace-Id"));
            query.set(exchange.getRequestURI().getRawQuery());
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            exchange.getResponseHeaders().set("Content-Type", "text/event-stream; charset=utf-8");
            exchange.sendResponseHeaders(200, sse.length);
            exchange.getResponseBody().write(sse);
            exchange.close();
        });

        AgentGatewayClient client = new AgentGatewayClient(
                HttpClient.newHttpClient(),
                baseUri,
                Duration.ofSeconds(5)
        );
        byte[] body = "{\"message\":\"糖尿病\"}".getBytes(StandardCharsets.UTF_8);

        AgentGatewayClient.GatewayResponse response = client.exchange(
                "POST",
                "/api/v1/agent/stream",
                Map.of("mode", List.of("medical")),
                body,
                "Bearer signed-jwt",
                "trace-gateway-001",
                "text/event-stream"
        ).join();

        assertThat(response.status()).isEqualTo(200);
        assertThat(response.contentType()).startsWith("text/event-stream");
        assertThat(response.body().readAllBytes()).isEqualTo(sse);
        assertThat(authorization.get()).isEqualTo("Bearer signed-jwt");
        assertThat(traceId.get()).isEqualTo("trace-gateway-001");
        assertThat(query.get()).isEqualTo("mode=medical");
        assertThat(requestBody.get()).isEqualTo("{\"message\":\"糖尿病\"}");
    }
}
