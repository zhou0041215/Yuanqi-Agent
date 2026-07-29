package com.yuanqi.backend.security;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.yuanqi.backend.access.domain.AccessPerson;
import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.common.exception.BusinessException;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ClinicalIdentityServiceTest {
    @Test
    void systemAdministratorCannotWriteClinicalData() {
        ClinicalIdentityService service = serviceFor(1001L, "SYSTEM_ADMIN");

        BusinessException exception = assertThrows(BusinessException.class, () -> service.requireClinicalWriter(
                new UserContext(1001L, "admin", DataScopeType.ALL, Set.of(10L))));

        assertEquals("ACCESS_DENIED", exception.getCode());
    }

    @Test
    void activeClinicalCollaboratorCanWriteClinicalData() {
        ClinicalIdentityService service = serviceFor(1002L, "CLINICAL_COLLABORATOR");

        assertDoesNotThrow(() -> service.requireClinicalWriter(
                new UserContext(1002L, "clinician", DataScopeType.SELF, Set.of(10L))));
    }

    private ClinicalIdentityService serviceFor(long userId, String roleCode) {
        AccessPersonRepository repository = mock(AccessPersonRepository.class);
        AccessPerson person = mock(AccessPerson.class);
        when(person.getUserId()).thenReturn(userId);
        when(person.getDisplayName()).thenReturn("测试人员");
        when(person.getDepartmentId()).thenReturn(10L);
        when(person.getDepartmentName()).thenReturn("内分泌科");
        when(person.getRoleCode()).thenReturn(roleCode);
        when(person.getStatus()).thenReturn("ACTIVE");
        when(repository.findByUserId(userId)).thenReturn(Optional.of(person));
        return new ClinicalIdentityService(repository);
    }
}
