package com.yuanqi.backend.security;

import com.yuanqi.backend.access.domain.AccessPerson;
import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.common.exception.BusinessException;
import org.springframework.stereotype.Service;

/**
 * Resolves the clinical identity used for ownership, attribution, and location.
 * The browser can display this information, but it never decides the persisted values.
 */
@Service
public class ClinicalIdentityService {
    private final AccessPersonRepository personRepository;

    public ClinicalIdentityService(AccessPersonRepository personRepository) {
        this.personRepository = personRepository;
    }

    public ClinicalIdentity current(UserContext user) {
        return resolve(user, user.userId());
    }

    public ClinicalIdentity requireClinicalWriter(UserContext user) {
        ClinicalIdentity clinician = current(user);
        if (!"DEPARTMENT_LEAD".equals(clinician.roleCode())
                && !"CLINICAL_COLLABORATOR".equals(clinician.roleCode())) {
            throw BusinessException.forbidden("Only an active clinical user can create medical records or prescriptions");
        }
        return clinician;
    }

    public ClinicalIdentity resolvePatientAssignment(UserContext user, Long requestedResponsibleUserId) {
        long responsibleUserId = requestedResponsibleUserId == null
                ? user.userId()
                : requestedResponsibleUserId;
        if (user.hasSelfAccess() && responsibleUserId != user.userId()) {
            throw BusinessException.forbidden("SELF scope cannot assign a patient to another responsible person");
        }
        ClinicalIdentity responsiblePerson = resolve(user, responsibleUserId);
        if ("SYSTEM_ADMIN".equals(responsiblePerson.roleCode())) {
            throw BusinessException.forbidden("A system administrator cannot be assigned as a patient's responsible clinician");
        }
        return responsiblePerson;
    }

    private ClinicalIdentity resolve(UserContext user, long userId) {
        AccessPerson person = personRepository.findByUserId(userId)
                .filter(candidate -> "ACTIVE".equals(candidate.getStatus()))
                .orElseThrow(() -> BusinessException.forbidden("Current clinical identity is unavailable or inactive"));
        if (!user.hasAllAccess() && !user.departmentIds().contains(person.getDepartmentId())) {
            throw BusinessException.forbidden("Clinical identity is outside the current department scope");
        }
        return new ClinicalIdentity(
                person.getUserId(),
                person.getDisplayName(),
                person.getDepartmentId(),
                person.getDepartmentName(),
                person.getRoleCode()
        );
    }

    public record ClinicalIdentity(
            long userId,
            String displayName,
            long departmentId,
            String departmentName,
            String roleCode
    ) {
    }
}
