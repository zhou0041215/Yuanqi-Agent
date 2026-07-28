package com.yuanqi.backend.agent;

import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UriComponentsBuilder;

@Component
public class AgentGatewayClient {
    private final HttpClient httpClient;
    private final URI baseUri;
    private final Duration requestTimeout;

    @Autowired
    public AgentGatewayClient(
            @Value("${application.agent.base-url:http://127.0.0.1:8000}") URI baseUri,
            @Value("${application.agent.connect-timeout:5s}") Duration connectTimeout,
            @Value("${application.agent.request-timeout:10m}") Duration requestTimeout
    ) {
        this(
                HttpClient.newBuilder()
                        .connectTimeout(connectTimeout)
                        .version(HttpClient.Version.HTTP_1_1)
                        .build(),
                baseUri,
                requestTimeout
        );
    }

    AgentGatewayClient(HttpClient httpClient, URI baseUri, Duration requestTimeout) {
        this.httpClient = httpClient;
        this.baseUri = baseUri;
        this.requestTimeout = requestTimeout;
    }

    public CompletableFuture<GatewayResponse> exchange(
            String method,
            String path,
            Map<String, List<String>> query,
            byte[] body,
            String authorization,
            String traceId,
            String accept
    ) {
        return exchange(method, path, query, body, authorization, traceId, accept, "application/json");
    }

    public CompletableFuture<GatewayResponse> exchange(
            String method,
            String path,
            Map<String, List<String>> query,
            byte[] body,
            String authorization,
            String traceId,
            String accept,
            String contentType
    ) {
        URI uri = buildUri(path, query);
        HttpRequest.BodyPublisher publisher = body.length == 0
                ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofByteArray(body);
        HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(requestTimeout)
                .header(HttpHeaders.AUTHORIZATION, authorization)
                .header("X-Trace-Id", traceId)
                .header(HttpHeaders.ACCEPT, accept)
                .header(HttpHeaders.CONTENT_TYPE, contentType)
                .method(method, publisher)
                .build();
        return httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofInputStream())
                .thenApply(response -> new GatewayResponse(
                        response.statusCode(),
                        response.headers().firstValue(HttpHeaders.CONTENT_TYPE)
                                .orElse("application/octet-stream"),
                        response.body()
                ));
    }

    private URI buildUri(String path, Map<String, List<String>> query) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromUri(baseUri).path(path);
        query.forEach((name, values) -> values.forEach(value -> builder.queryParam(name, value)));
        return builder.build().encode().toUri();
    }

    public record GatewayResponse(int status, String contentType, InputStream body) {
    }
}
