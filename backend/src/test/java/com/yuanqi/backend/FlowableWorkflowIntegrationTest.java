package com.yuanqi.backend;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@SpringBootTest
@AutoConfigureMockMvc
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class FlowableWorkflowIntegrationTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void currentContextIncludesVerifiedClinicalIdentity() throws Exception {
        mockMvc.perform(get("/api/v1/auth/context")
                        .with(token(1001, "patient:read")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.userId").value(1001))
                .andExpect(jsonPath("$.data.displayName").isNotEmpty())
                .andExpect(jsonPath("$.data.clinicalDepartmentId").value(10))
                .andExpect(jsonPath("$.data.clinicalDepartmentName").isNotEmpty())
                .andExpect(jsonPath("$.data.roleCode").value("SYSTEM_ADMIN"));
    }

    @Test
    void prescriptionStatusChangesOnlyAfterAssignedApproverDecision() throws Exception {
        long patientId = createPatient();
        long prescriptionId = createPrescription(patientId);
        mockMvc.perform(get("/api/v1/analytics/prescriptions/schema")
                        .with(token(1001, "prescription:read")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.schemaVersion").value("prescriptions-v1"));
        mockMvc.perform(post("/api/v1/analytics/prescriptions/snapshot")
                        .with(token(1001, "prescription:read"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fromDate": "2026-07-01",
                                  "toDate": "2026-07-31",
                                  "departmentIds": [10],
                                  "maximumRows": 100
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.rowCount").value(1))
                .andExpect(jsonPath("$.data.rows[0].departmentId").value(10))
                .andExpect(jsonPath("$.data.rows[0].patientId").doesNotExist());
        mockMvc.perform(get("/api/v1/workflows/prescription-status-changes/approvers")
                        .param("prescriptionId", Long.toString(prescriptionId))
                        .with(token(1011, "prescription:write")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(1))
                .andExpect(jsonPath("$.data[0].userId").value(1001))
                .andExpect(jsonPath("$.data[0].roleCode").value("SYSTEM_ADMIN"));
        MvcResult startResult = mockMvc.perform(post("/api/v1/workflows/prescription-status-changes")
                        .with(token(1011, "prescription:write"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "prescriptionId": %d,
                                  "targetStatus": "DISPENSED",
                                  "approverId": 1001,
                                  "reason": "Medication dispensing review"
                                }
                                """.formatted(prescriptionId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.status").value("WAITING_APPROVAL"))
                .andReturn();
        String taskId = objectMapper.readTree(startResult.getResponse().getContentAsByteArray())
                .at("/data/taskId").asText();
        mockMvc.perform(get("/api/v1/workflows/prescription-status-changes/requests/my")
                        .with(token(1011, "prescription:write")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].prescriptionId").value(prescriptionId))
                .andExpect(jsonPath("$.data[0].targetStatus").value("DISPENSED"))
                .andExpect(jsonPath("$.data[0].approverId").value(1001));

        mockMvc.perform(post("/api/v1/workflows/prescription-status-changes")
                        .with(token(1011, "prescription:write"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "prescriptionId": %d,
                                  "targetStatus": "CANCELLED",
                                  "approverId": 1001,
                                  "reason": "Duplicate active approval"
                                }
                                """.formatted(prescriptionId)))
                .andExpect(status().isConflict());

        mockMvc.perform(get("/api/v1/workflows/prescription-status-changes/tasks/my")
                        .with(token(1001, "prescription:write")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].taskId").value(taskId))
                .andExpect(jsonPath("$.data[0].prescriptionId").value(prescriptionId))
                .andExpect(jsonPath("$.data[0].targetStatus").value("DISPENSED"));

        mockMvc.perform(get("/api/v1/prescriptions/{id}", prescriptionId)
                        .with(token(1001, "prescription:read")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("PENDING"));

        mockMvc.perform(post("/api/v1/workflows/prescription-status-changes/tasks/{taskId}/decision", taskId)
                        .with(token(1001, "prescription:write"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"approved\":true,\"comment\":\"Clinical review passed\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("APPROVED"));

        mockMvc.perform(get("/api/v1/prescriptions/{id}", prescriptionId)
                        .with(token(1001, "prescription:read")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("DISPENSED"));
    }

    @Test
    void agentAuditEventsDoNotStoreToolArguments() throws Exception {
        String body = """
                {
                  "threadId": "11111111-1111-4111-8111-111111111111",
                  "traceId": "trace-agent-audit-001",
                  "toolName": "create_prescription",
                  "phase": "WAITING_APPROVAL",
                  "outcome": "PENDING",
                  "riskLevel": "critical",
                  "fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                }
                """;
        mockMvc.perform(post("/api/v1/agent-audit/events")
                        .with(token(1001))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.toolName").value("create_prescription"));

        mockMvc.perform(get("/api/v1/agent-audit/events")
                        .with(token(1001, "agent:audit:read")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].threadId")
                        .value("11111111-1111-4111-8111-111111111111"))
                .andExpect(jsonPath("$.data[0].targetParameters").doesNotExist());
    }

    private long createPatient() throws Exception {
        MvcResult result = mockMvc.perform(post("/api/v1/patients")
                        .with(token(1011, "patient:write"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Workflow patient",
                                  "gender": "UNKNOWN"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.patientNo").isNotEmpty())
                .andExpect(jsonPath("$.data.ownerId").value(1011))
                .andExpect(jsonPath("$.data.departmentId").value(10))
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsByteArray()).at("/data/id").asLong();
    }

    private long createPrescription(long patientId) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/v1/prescriptions")
                        .with(token(1011, "prescription:write"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "patientId": %d,
                                  "prescriptionDate": "2026-07-26T10:00:00",
                                  "totalAmount": 128.50,
                                  "drugsJson": "Demo drug, 10mg, once daily"
                                }
                                """.formatted(patientId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.prescriptionNo").isNotEmpty())
                .andExpect(jsonPath("$.data.ownerId").value(1011))
                .andExpect(jsonPath("$.data.departmentId").value(10))
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsByteArray()).at("/data/id").asLong();
    }

    private RequestPostProcessor token(long userId, String... permissions) {
        return jwt()
                .authorities(Arrays.stream(permissions)
                        .map(SimpleGrantedAuthority::new)
                        .toArray(SimpleGrantedAuthority[]::new))
                .jwt(token -> token
                        .subject(Long.toString(userId))
                        .claim("data_scope", "ALL")
                        .claim("department_ids", List.of(10L))
                        .claim("permissions", List.of(permissions)));
    }
}
