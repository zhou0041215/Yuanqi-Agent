package com.yuanqi.backend.access.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.yuanqi.backend.access.domain.AccessAuditEvent;
import com.yuanqi.backend.access.domain.AccessPerson;
import com.yuanqi.backend.access.domain.PatientAccessGrant;
import com.yuanqi.backend.access.repository.AccessAuditEventRepository;
import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.access.repository.PatientAccessGrantRepository;
import com.yuanqi.backend.access.web.CreatePatientGrantRequest;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.patient.domain.Patient;
import com.yuanqi.backend.patient.repository.PatientRepository;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.DataScopeType;
import com.yuanqi.backend.security.UserContext;
import java.lang.reflect.Field;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AccessManagementServiceTest {
    private AccessPersonRepository personRepository;
    private AccessAuditEventRepository auditRepository;
    private PatientAccessGrantRepository grantRepository;
    private PatientRepository patientRepository;
    private CurrentUserProvider currentUserProvider;
    private AccessManagementService service;

    @BeforeEach
    void setUp() {
        personRepository = mock(AccessPersonRepository.class);
        auditRepository = mock(AccessAuditEventRepository.class);
        grantRepository = mock(PatientAccessGrantRepository.class);
        patientRepository = mock(PatientRepository.class);
        currentUserProvider = mock(CurrentUserProvider.class);
        service = new AccessManagementService(
                personRepository, auditRepository, grantRepository, patientRepository, currentUserProvider);
    }

    @Test
    void nonAdministratorCannotReadManagementSnapshot() {
        when(currentUserProvider.requireCurrentUser()).thenReturn(
                new UserContext(1002, 1, "manager", DataScopeType.DEPARTMENT, Set.of(20L)));

        BusinessException exception = assertThrows(BusinessException.class, service::snapshot);

        assertEquals("ACCESS_DENIED", exception.getCode());
    }

    @Test
    void grantDurationCannotExceedThirtyDays() {
        when(currentUserProvider.requireCurrentUser()).thenReturn(admin());
        CreatePatientGrantRequest request = new CreatePatientGrantRequest(
                42, 1003, "跨科会诊需要查看患者资料", Instant.now().plus(31, ChronoUnit.DAYS));

        BusinessException exception = assertThrows(BusinessException.class, () -> service.createGrant(request));

        assertEquals("INVALID_GRANT_WINDOW", exception.getCode());
    }

    @Test
    void createGrantUsesVerifiedTenantAndWritesAudit() throws Exception {
        UserContext admin = admin();
        when(currentUserProvider.requireCurrentUser()).thenReturn(admin);
        Patient patient = mock(Patient.class);
        when(patient.getId()).thenReturn(42L);
        when(patient.getPatientNo()).thenReturn("P-42");
        when(patient.getName()).thenReturn("测试患者");
        when(patientRepository.findByIdAndTenantIdAndDeletedFalse(42, 1)).thenReturn(Optional.of(patient));

        AccessPerson grantee = person(1003, "协作人员", "CLINICAL_COLLABORATOR");
        AccessPerson actor = person(1001, "系统管理员", "SYSTEM_ADMIN");
        when(personRepository.findByTenantIdAndUserId(1, 1003)).thenReturn(Optional.of(grantee));
        when(personRepository.findByTenantIdAndUserId(1, 1001)).thenReturn(Optional.of(actor));
        when(grantRepository.existsCurrentGrant(eq(1L), eq(42L), eq(1003L), any())).thenReturn(false);
        when(grantRepository.save(any(PatientAccessGrant.class))).thenAnswer(invocation -> {
            PatientAccessGrant grant = invocation.getArgument(0);
            Field id = PatientAccessGrant.class.getDeclaredField("id");
            id.setAccessible(true);
            id.set(grant, 7L);
            return grant;
        });

        var result = service.createGrant(new CreatePatientGrantRequest(
                42, 1003, "跨科会诊需要查看患者资料", Instant.now().plus(1, ChronoUnit.DAYS)));

        assertEquals(7, result.id());
        assertEquals("ACTIVE", result.status());
        verify(patientRepository).findByIdAndTenantIdAndDeletedFalse(42, 1);
        verify(auditRepository).save(any(AccessAuditEvent.class));
    }

    private UserContext admin() {
        return new UserContext(1001, 1, "admin", DataScopeType.ALL, Set.of(10L));
    }

    private AccessPerson person(long userId, String displayName, String roleCode) {
        AccessPerson person = mock(AccessPerson.class);
        when(person.getUserId()).thenReturn(userId);
        when(person.getDisplayName()).thenReturn(displayName);
        when(person.getRoleCode()).thenReturn(roleCode);
        when(person.getStatus()).thenReturn("ACTIVE");
        return person;
    }
}
