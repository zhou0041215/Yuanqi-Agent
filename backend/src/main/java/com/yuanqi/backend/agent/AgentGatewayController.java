package com.yuanqi.backend.agent;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.patient.service.PatientService;
import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@RestController
@RequestMapping("/api/v1")
public class AgentGatewayController {
    private static final Pattern TRACE_ID = Pattern.compile("[A-Za-z0-9-]{8,64}");
    private static final int MAX_BUFFERED_RESPONSE_BYTES = 5_000_000;
    private static final int MAX_REPORT_BYTES = 10 * 1024 * 1024;

    private final AgentGatewayClient client;
    private final Executor agentTaskExecutor;
    private final ObjectMapper objectMapper;
    private final PatientService patientService;

    public AgentGatewayController(
            AgentGatewayClient client,
            @Qualifier("agentTaskExecutor") Executor agentTaskExecutor,
            ObjectMapper objectMapper,
            PatientService patientService
    ) {
        this.client = client;
        this.agentTaskExecutor = agentTaskExecutor;
        this.objectMapper = objectMapper;
        this.patientService = patientService;
    }

    @PostMapping(
            value = "/agent/stream",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.TEXT_EVENT_STREAM_VALUE
    )
    public CompletableFuture<ResponseEntity<StreamingResponseBody>> stream(
            @RequestBody byte[] body,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        byte[] verifiedBody = verifiedAgentBody(body);
        return proxyStream(
                "/api/v1/agent/stream",
                verifiedBody,
                authorization,
                normalizedTraceId(traceId)
        );
    }

    byte[] verifiedAgentBody(byte[] body) {
        try {
            JsonNode parsed = objectMapper.readTree(body);
            if (!(parsed instanceof ObjectNode root)) {
                throw invalidAgentRequest("Agent request must be a JSON object");
            }
            JsonNode suppliedContext = root.get("patientContext");
            if (suppliedContext == null || suppliedContext.isNull()) {
                root.remove("patientContext");
                return objectMapper.writeValueAsBytes(root);
            }
            if (!suppliedContext.isObject()
                    || !suppliedContext.path("patientId").isIntegralNumber()
                    || !suppliedContext.path("patientId").canConvertToLong()
                    || suppliedContext.path("patientId").longValue() <= 0) {
                throw invalidAgentRequest("Patient context is invalid");
            }
            long patientId = suppliedContext.path("patientId").longValue();
            var patient = patientService.get(patientId);
            ObjectNode verifiedContext = objectMapper.createObjectNode();
            verifiedContext.put("patientId", patient.id());
            verifiedContext.put("patientNo", patient.patientNo());
            verifiedContext.put("name", patient.name());
            root.set("patientContext", verifiedContext);
            return objectMapper.writeValueAsBytes(root);
        } catch (IOException exception) {
            throw invalidAgentRequest("Agent request contains invalid JSON");
        }
    }

    private BusinessException invalidAgentRequest(String message) {
        return new BusinessException("INVALID_AGENT_REQUEST", message, HttpStatus.BAD_REQUEST);
    }

    @PostMapping(
            value = "/agent/threads/{threadId}/resume/stream",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.TEXT_EVENT_STREAM_VALUE
    )
    public CompletableFuture<ResponseEntity<StreamingResponseBody>> resumeStream(
            @PathVariable UUID threadId,
            @RequestBody byte[] body,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyStream(
                "/api/v1/agent/threads/" + threadId + "/resume/stream",
                body,
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @GetMapping("/agent/tools")
    public CompletableFuture<ResponseEntity<byte[]>> tools(
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyJson(
                "/api/v1/agent/tools",
                Map.of(),
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @PostMapping(
            value = "/medical-reports/analyze",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public CompletableFuture<ResponseEntity<byte[]>> analyzeMedicalReport(
            @RequestParam("file") MultipartFile file,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) throws IOException {
        String normalizedTraceId = normalizedTraceId(traceId);
        if (file.isEmpty() || file.getSize() > MAX_REPORT_BYTES) {
            return CompletableFuture.completedFuture(
                    ResponseEntity.badRequest()
                            .contentType(MediaType.APPLICATION_JSON)
                            .body("{\"code\":\"INVALID_REPORT_SIZE\",\"message\":\"报告文件应大于 0 且不超过 10 MB\"}"
                                    .getBytes(StandardCharsets.UTF_8))
            );
        }
        String boundary = "YuanQiReport" + UUID.randomUUID().toString().replace("-", "");
        byte[] multipartBody = buildMultipartBody(file, boundary);
        return client.exchange(
                        "POST",
                        "/api/v1/medical-reports/analyze",
                        Map.of(),
                        multipartBody,
                        authorization,
                        normalizedTraceId,
                        MediaType.APPLICATION_JSON_VALUE,
                        "multipart/form-data; boundary=" + boundary
                )
                .thenApplyAsync(response -> {
                    try (var input = response.body()) {
                        byte[] payload = input.readNBytes(MAX_BUFFERED_RESPONSE_BYTES + 1);
                        if (payload.length > MAX_BUFFERED_RESPONSE_BYTES) {
                            return gatewayJsonError(normalizedTraceId, "Agent response is too large");
                        }
                        return ResponseEntity.status(response.status())
                                .contentType(parseMediaType(response.contentType()))
                                .header("X-Trace-Id", normalizedTraceId)
                                .body(payload);
                    } catch (IOException exception) {
                        return gatewayJsonError(normalizedTraceId, "Unable to read Agent response");
                    }
                }, agentTaskExecutor)
                .exceptionally(error -> gatewayJsonError(normalizedTraceId, "Agent service is unavailable"));
    }

    @GetMapping("/kg/search")
    public CompletableFuture<ResponseEntity<byte[]>> searchKnowledge(
            @RequestParam(defaultValue = "") String q,
            @RequestParam(defaultValue = "10") int limit,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyJson(
                "/api/v1/kg/search",
                Map.of("q", List.of(q), "limit", List.of(Integer.toString(limit))),
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @GetMapping("/kg/departments")
    public CompletableFuture<ResponseEntity<byte[]>> departments(
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyJson(
                "/api/v1/kg/departments",
                Map.of(),
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @GetMapping("/kg/graph")
    public CompletableFuture<ResponseEntity<byte[]>> graph(
            @RequestParam(defaultValue = "") String name,
            @RequestParam(defaultValue = "1") int depth,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyJson(
                "/api/v1/kg/graph",
                Map.of("name", List.of(name), "depth", List.of(Integer.toString(depth))),
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @GetMapping("/kg/overview")
    public CompletableFuture<ResponseEntity<byte[]>> overview(
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyJson(
                "/api/v1/kg/overview",
                Map.of(),
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @GetMapping("/kg/department")
    public CompletableFuture<ResponseEntity<byte[]>> department(
            @RequestParam(defaultValue = "") String name,
            @RequestParam(defaultValue = "200") int limit,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return proxyJson(
                "/api/v1/kg/department",
                Map.of("name", List.of(name), "limit", List.of(Integer.toString(limit))),
                authorization,
                normalizedTraceId(traceId)
        );
    }

    @PostMapping(value = "/kg/index/rebuild", produces = MediaType.APPLICATION_JSON_VALUE)
    public CompletableFuture<ResponseEntity<byte[]>> rebuildKnowledgeIndex(
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorization,
            @RequestHeader(value = "X-Trace-Id", required = false) String traceId
    ) {
        return client.exchange(
                        "POST",
                        "/api/v1/kg/index/rebuild",
                        Map.of(),
                        new byte[0],
                        authorization,
                        normalizedTraceId(traceId),
                        MediaType.APPLICATION_JSON_VALUE
                )
                .thenApplyAsync(response -> {
                    try (var input = response.body()) {
                        return ResponseEntity.status(response.status())
                                .contentType(parseMediaType(response.contentType()))
                                .body(input.readNBytes(MAX_BUFFERED_RESPONSE_BYTES));
                    } catch (IOException exception) {
                        return gatewayJsonError(normalizedTraceId(traceId), "Unable to read Agent response");
                    }
                }, agentTaskExecutor)
                .exceptionally(error -> gatewayJsonError(normalizedTraceId(traceId), "Agent service is unavailable"));
    }

    private CompletableFuture<ResponseEntity<StreamingResponseBody>> proxyStream(
            String path,
            byte[] body,
            String authorization,
            String traceId
    ) {
        return client.exchange(
                        "POST",
                        path,
                        Map.of(),
                        body,
                        authorization,
                        traceId,
                        MediaType.TEXT_EVENT_STREAM_VALUE
                )
                .thenApply(response -> {
                    StreamingResponseBody responseBody = output -> {
                            try (var input = response.body()) {
                                input.transferTo(output);
                                output.flush();
                            }
                        };
                    return ResponseEntity.status(response.status())
                            .contentType(parseMediaType(response.contentType()))
                            .header("X-Trace-Id", traceId)
                            .body(responseBody);
                })
                .exceptionally(error -> gatewayStreamError(traceId));
    }

    private CompletableFuture<ResponseEntity<byte[]>> proxyJson(
            String path,
            Map<String, List<String>> query,
            String authorization,
            String traceId
    ) {
        return client.exchange(
                        "GET",
                        path,
                        query,
                        new byte[0],
                        authorization,
                        traceId,
                        MediaType.APPLICATION_JSON_VALUE
                )
                .thenApplyAsync(response -> {
                    try (var input = response.body()) {
                        byte[] payload = input.readNBytes(MAX_BUFFERED_RESPONSE_BYTES + 1);
                        if (payload.length > MAX_BUFFERED_RESPONSE_BYTES) {
                            return gatewayJsonError(traceId, "Agent response is too large");
                        }
                        return ResponseEntity.status(response.status())
                                .contentType(parseMediaType(response.contentType()))
                                .header("X-Trace-Id", traceId)
                                .body(payload);
                    } catch (IOException exception) {
                        return gatewayJsonError(traceId, "Unable to read Agent response");
                    }
                }, agentTaskExecutor)
                .exceptionally(error -> gatewayJsonError(traceId, "Agent service is unavailable"));
    }

    private static ResponseEntity<StreamingResponseBody> gatewayStreamError(String traceId) {
        StreamingResponseBody body = output -> output.write(
                "event: error\ndata: {\"code\":\"AGENT_UNAVAILABLE\",\"message\":\"Agent service is unavailable\"}\n\n"
                        .getBytes(StandardCharsets.UTF_8)
        );
        return ResponseEntity.status(502)
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .header("X-Trace-Id", traceId)
                .body(body);
    }

    private static ResponseEntity<byte[]> gatewayJsonError(String traceId, String message) {
        String json = "{\"code\":\"AGENT_GATEWAY_ERROR\",\"message\":\"" + message + "\"}";
        return ResponseEntity.status(502)
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Trace-Id", traceId)
                .body(json.getBytes(StandardCharsets.UTF_8));
    }

    private static String normalizedTraceId(String traceId) {
        return traceId != null && TRACE_ID.matcher(traceId).matches()
                ? traceId
                : UUID.randomUUID().toString();
    }

    private static MediaType parseMediaType(String value) {
        try {
            return MediaType.parseMediaType(value);
        } catch (IllegalArgumentException ignored) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }

    private static byte[] buildMultipartBody(MultipartFile file, String boundary) throws IOException {
        String originalName = file.getOriginalFilename() == null ? "medical-report" : file.getOriginalFilename();
        String safeName = originalName.replaceAll("[\\r\\n\"\\\\]", "_");
        String contentType = file.getContentType() == null
                ? MediaType.APPLICATION_OCTET_STREAM_VALUE
                : file.getContentType().replaceAll("[\\r\\n]", "");
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        output.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        output.write(("Content-Disposition: form-data; name=\"file\"; filename=\"" + safeName + "\"\r\n")
                .getBytes(StandardCharsets.UTF_8));
        output.write(("Content-Type: " + contentType + "\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        output.write(file.getBytes());
        output.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return output.toByteArray();
    }
}
