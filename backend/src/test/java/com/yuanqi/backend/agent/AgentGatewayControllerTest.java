package com.yuanqi.backend.agent;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.patient.domain.PatientStatus;
import com.yuanqi.backend.patient.service.PatientService;
import com.yuanqi.backend.patient.web.dto.PatientResponse;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AgentGatewayControllerTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private PatientService patientService;
    private AgentGatewayController controller;

    @BeforeEach
    void setUp() {
        patientService = mock(PatientService.class);
        controller = new AgentGatewayController(
                mock(AgentGatewayClient.class),
                Runnable::run,
                objectMapper,
                patientService
        );
    }

    @Test
    void replacesClientPatientLabelsWithVerifiedBusinessData() throws Exception {
        when(patientService.get(7L)).thenReturn(patient());

        byte[] verified = controller.verifiedAgentBody("""
                {
                  "message": "创建处方",
                  "patientContext": {
                    "patientId": 7,
                    "patientNo": "伪造编号",
                    "name": "伪造姓名"
                  }
                }
                """.getBytes(StandardCharsets.UTF_8));

        JsonNode context = objectMapper.readTree(verified).path("patientContext");
        assertEquals(7L, context.path("patientId").longValue());
        assertEquals("P-0007", context.path("patientNo").textValue());
        assertEquals("张三", context.path("name").textValue());
        verify(patientService).get(7L);
    }

    @Test
    void leavesGlobalKnowledgeRequestWithoutPatientContext() throws Exception {
        byte[] verified = controller.verifiedAgentBody(
                "{\"message\":\"高血压有哪些症状\"}".getBytes(StandardCharsets.UTF_8));

        assertFalse(objectMapper.readTree(verified).has("patientContext"));
        verifyNoInteractions(patientService);
    }

    @Test
    void rejectsMalformedPatientContextBeforeCallingAgent() {
        BusinessException exception = assertThrows(
                BusinessException.class,
                () -> controller.verifiedAgentBody("""
                        {
                          "message": "创建处方",
                          "patientContext": {"patientId": "7"}
                        }
                        """.getBytes(StandardCharsets.UTF_8))
        );

        assertEquals("INVALID_AGENT_REQUEST", exception.getCode());
        verifyNoInteractions(patientService);
    }

    private PatientResponse patient() {
        Instant now = Instant.parse("2026-07-30T00:00:00Z");
        return new PatientResponse(
                7L,
                "P-0007",
                "张三",
                "MALE",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                PatientStatus.ACTIVE,
                1001L,
                10L,
                now,
                now,
                0L
        );
    }
}
