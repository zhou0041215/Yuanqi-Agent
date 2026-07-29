package com.yuanqi.backend.access.service;

import com.yuanqi.backend.access.domain.AccessAuditEvent;
import com.yuanqi.backend.access.domain.AccessPerson;
import com.yuanqi.backend.access.domain.PatientAccessGrant;
import com.yuanqi.backend.access.repository.AccessAuditEventRepository;
import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.access.repository.PatientAccessGrantRepository;
import com.yuanqi.backend.access.web.AccessManagementResponse;
import com.yuanqi.backend.access.web.CreatePatientGrantRequest;
import com.yuanqi.backend.access.web.UpdatePatientAssignmentRequest;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.patient.domain.Patient;
import com.yuanqi.backend.patient.repository.PatientRepository;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.ClinicalIdentityService;
import com.yuanqi.backend.security.UserContext;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.Map;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AccessManagementService {
    private final AccessPersonRepository personRepository;
    private final AccessAuditEventRepository auditRepository;
    private final PatientAccessGrantRepository grantRepository;
    private final PatientRepository patientRepository;
    private final CurrentUserProvider currentUserProvider;
    private final ClinicalIdentityService clinicalIdentityService;

    public AccessManagementService(
            AccessPersonRepository personRepository,
            AccessAuditEventRepository auditRepository,
            PatientAccessGrantRepository grantRepository,
            PatientRepository patientRepository,
            CurrentUserProvider currentUserProvider,
            ClinicalIdentityService clinicalIdentityService
    ) {
        this.personRepository = personRepository;
        this.auditRepository = auditRepository;
        this.grantRepository = grantRepository;
        this.patientRepository = patientRepository;
        this.currentUserProvider = currentUserProvider;
        this.clinicalIdentityService = clinicalIdentityService;
    }

    @Transactional(readOnly = true)
    public AccessManagementResponse snapshot() {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireAdministrator(user);
        var personEntities = personRepository.findAllByOrderByDisplayNameAsc();
        var people = personEntities.stream()
                .map(person -> new AccessManagementResponse.PersonSummary(
                        person.getUserId(), person.getUsername(), person.getDisplayName(),
                        person.getDepartmentId(), person.getDepartmentName(), person.getRoleCode(),
                        person.getDataScope().name(), person.getStatus()))
                .toList();
        var patients = patientRepository.findAllByDeletedFalseOrderByNameAsc();
        Map<Long, Patient> patientsById = patients.stream()
                .collect(Collectors.toMap(Patient::getId, Function.identity()));
        Map<Long, AccessPerson> peopleById = personEntities.stream()
                .collect(Collectors.toMap(AccessPerson::getUserId, Function.identity()));
        Instant now = Instant.now();
        var grants = grantRepository.findAllByOrderByCreatedAtDesc().stream()
                .map(grant -> toGrantSummary(grant, patientsById, peopleById, now))
                .toList();
        var audits = auditRepository
                .findAllByOrderByOccurredAtDesc(PageRequest.of(0, 50)).stream()
                .map(event -> new AccessManagementResponse.AuditSummary(
                        event.getOccurredAt(), event.getActorUserId(), event.getActorName(),
                        event.getAction(), event.getTargetType(), event.getTargetLabel()))
                .toList();
        var patientSummaries = patients.stream()
                .map(patient -> new AccessManagementResponse.PatientSummary(
                        patient.getId(), patient.getPatientNo(), patient.getName(), patient.getDepartmentId(),
                        patient.getOwnerId(), patient.getStatus().name()))
                .toList();
        return new AccessManagementResponse(people, roles(), patientSummaries, grants, audits);
    }

    @Transactional
    public AccessManagementResponse.GrantSummary createGrant(CreatePatientGrantRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireAdministrator(user);
        Instant now = Instant.now();
        if (!request.validUntil().isAfter(now.plus(14, ChronoUnit.MINUTES))) {
            throw invalidGrant("Grant must remain valid for at least 15 minutes");
        }
        if (request.validUntil().isAfter(now.plus(30, ChronoUnit.DAYS))) {
            throw invalidGrant("Grant duration cannot exceed 30 days");
        }

        Patient patient = patientRepository
                .findByIdAndDeletedFalse(request.patientId())
                .orElseThrow(() -> BusinessException.notFound("Patient"));
        AccessPerson grantee = personRepository
                .findByUserId(request.granteeUserId())
                .filter(person -> "ACTIVE".equals(person.getStatus()))
                .orElseThrow(() -> BusinessException.notFound("Active grantee"));
        if (grantRepository.existsCurrentGrant(
                patient.getId(), grantee.getUserId(), now)) {
            throw BusinessException.conflict("An active grant already exists for this patient and user");
        }

        PatientAccessGrant grant = grantRepository.save(new PatientAccessGrant(
                patient.getId(), grantee.getUserId(), user.userId(),
                request.reason().trim(), now, request.validUntil()));
        AccessPerson actor = currentActor(user);
        auditRepository.save(new AccessAuditEvent(
                user.userId(), actor.getDisplayName(), "创建患者授权", "PATIENT_GRANT",
                patient.getName() + " → " + grantee.getDisplayName(), now));
        Map<Long, AccessPerson> people = new HashMap<>();
        people.put(grantee.getUserId(), grantee);
        people.put(actor.getUserId(), actor);
        return toGrantSummary(
                grant,
                Map.of(patient.getId(), patient),
                people,
                now
        );
    }

    @Transactional
    public AccessManagementResponse.GrantSummary revokeGrant(long grantId) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireAdministrator(user);
        PatientAccessGrant grant = grantRepository.findById(grantId)
                .orElseThrow(() -> BusinessException.notFound("Patient grant"));
        if (grant.getRevokedAt() != null) {
            throw BusinessException.conflict("Patient grant has already been revoked");
        }
        Instant now = Instant.now();
        grant.revoke(now);
        Patient patient = patientRepository
                .findByIdAndDeletedFalse(grant.getPatientId())
                .orElseThrow(() -> BusinessException.notFound("Patient"));
        AccessPerson grantee = personRepository
                .findByUserId(grant.getGranteeUserId())
                .orElseThrow(() -> BusinessException.notFound("Grantee"));
        AccessPerson actor = currentActor(user);
        auditRepository.save(new AccessAuditEvent(
                user.userId(), actor.getDisplayName(), "撤销患者授权", "PATIENT_GRANT",
                patient.getName() + " → " + grantee.getDisplayName(), now));
        Map<Long, AccessPerson> people = new HashMap<>();
        people.put(grantee.getUserId(), grantee);
        people.put(actor.getUserId(), actor);
        return toGrantSummary(
                grantRepository.saveAndFlush(grant),
                Map.of(patient.getId(), patient),
                people,
                now
        );
    }

    @Transactional
    public AccessManagementResponse.PatientSummary updatePatientAssignment(
            long patientId,
            UpdatePatientAssignmentRequest request
    ) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireAdministrator(user);
        Patient patient = patientRepository.findByIdAndDeletedFalse(patientId)
                .orElseThrow(() -> BusinessException.notFound("Patient"));
        var responsiblePerson = clinicalIdentityService
                .resolvePatientAssignment(user, request.responsibleUserId());
        patient.assignResponsiblePerson(responsiblePerson.userId(), responsiblePerson.departmentId());
        patientRepository.saveAndFlush(patient);

        AccessPerson actor = currentActor(user);
        auditRepository.save(new AccessAuditEvent(
                user.userId(), actor.getDisplayName(), "调整患者负责人", "PATIENT_ASSIGNMENT",
                patient.getName() + " → " + responsiblePerson.displayName() + "（" + request.reason().trim() + "）",
                Instant.now()));
        return new AccessManagementResponse.PatientSummary(
                patient.getId(), patient.getPatientNo(), patient.getName(), patient.getDepartmentId(),
                patient.getOwnerId(), patient.getStatus().name());
    }

    private void requireAdministrator(UserContext user) {
        if (!user.hasAllAccess()) {
            throw BusinessException.forbidden("Access management requires ALL data scope");
        }
    }

    private AccessPerson currentActor(UserContext user) {
        return personRepository.findByUserId(user.userId())
                .filter(person -> "ACTIVE".equals(person.getStatus()))
                .filter(person -> "SYSTEM_ADMIN".equals(person.getRoleCode()))
                .orElseThrow(() -> BusinessException.forbidden("Current user is not an active access administrator"));
    }

    private AccessManagementResponse.GrantSummary toGrantSummary(
            PatientAccessGrant grant,
            Map<Long, Patient> patients,
            Map<Long, AccessPerson> people,
            Instant now
    ) {
        Patient patient = patients.get(grant.getPatientId());
        AccessPerson grantee = people.get(grant.getGranteeUserId());
        AccessPerson grantor = people.get(grant.getGrantedBy());
        String status = grant.getRevokedAt() != null
                ? "REVOKED"
                : grant.getValidUntil().isAfter(now) ? "ACTIVE" : "EXPIRED";
        return new AccessManagementResponse.GrantSummary(
                grant.getId(), grant.getPatientId(),
                patient == null ? "-" : patient.getPatientNo(),
                patient == null ? "已删除患者" : patient.getName(),
                grant.getGranteeUserId(), grantee == null ? "未知人员" : grantee.getDisplayName(),
                grant.getGrantedBy(), grantor == null ? "未知人员" : grantor.getDisplayName(),
                grant.getReason(), grant.getValidFrom(), grant.getValidUntil(), grant.getRevokedAt(), status);
    }

    private BusinessException invalidGrant(String message) {
        return new BusinessException("INVALID_GRANT_WINDOW", message, HttpStatus.BAD_REQUEST);
    }

    private List<AccessManagementResponse.RoleSummary> roles() {
        return List.of(
                new AccessManagementResponse.RoleSummary("SYSTEM_ADMIN", "系统管理员", "全域数据与系统配置",
                        List.of("维护人员", "配置角色", "查看审计记录")),
                new AccessManagementResponse.RoleSummary("DEPARTMENT_LEAD", "科室负责人", "本科室患者与业务数据",
                        List.of("维护本科室协作", "发起临时授权", "查看本科室记录")),
                new AccessManagementResponse.RoleSummary("CLINICAL_COLLABORATOR", "临床协作人员", "本人授权范围内的数据",
                        List.of("查看已授权患者", "提交协作申请"))
        );
    }
}
