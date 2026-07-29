package com.yuanqi.backend.patient.service;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.patient.domain.Patient;
import com.yuanqi.backend.patient.domain.PatientStatus;
import com.yuanqi.backend.patient.repository.PatientRepository;
import com.yuanqi.backend.patient.web.dto.CreatePatientRequest;
import com.yuanqi.backend.patient.web.dto.PatientResponse;
import com.yuanqi.backend.patient.web.dto.UpdatePatientRequest;
import com.yuanqi.backend.security.ClinicalIdentityService;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import java.util.Collection;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PatientService {
    private final PatientRepository patientRepository;
    private final CurrentUserProvider currentUserProvider;
    private final ClinicalIdentityService clinicalIdentityService;

    public PatientService(
            PatientRepository patientRepository,
            CurrentUserProvider currentUserProvider,
            ClinicalIdentityService clinicalIdentityService
    ) {
        this.patientRepository = patientRepository;
        this.currentUserProvider = currentUserProvider;
        this.clinicalIdentityService = clinicalIdentityService;
    }

    @Transactional(readOnly = true)
    public PageResponse<PatientResponse> search(String keyword, int page, int size) {
        UserContext user = currentUserProvider.requireCurrentUser();
        PageRequest pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Patient> result = patientRepository.findAccessible(
                user.userId(),
                user.hasAllAccess(),
                user.hasSelfAccess(),
                user.hasDepartmentAccess(),
                queryDepartmentIds(user),
                Instant.now(),
                normalizeKeyword(keyword),
                pageable
        );
        return PageResponse.from(result, PatientResponse::from);
    }

    @Transactional(readOnly = true)
    public PatientResponse get(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        return PatientResponse.from(requireReadable(id, user));
    }

    @Transactional(readOnly = true)
    public void assertAccessible(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireReadable(id, user);
    }

    @Transactional
    public PatientResponse create(CreatePatientRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        var responsiblePerson = clinicalIdentityService
                .resolvePatientAssignment(user, request.responsibleUserId());
        String patientNo = generatedPatientNo();
        if (patientRepository.existsByPatientNo(patientNo)) {
            throw BusinessException.conflict("Patient number already exists");
        }
        Patient patient = new Patient(
                patientNo,
                request.name().trim(),
                trimToNull(request.gender()),
                request.birthDate(),
                trimToNull(request.phone()),
                trimToNull(request.idCard()),
                trimToNull(request.address()),
                trimToNull(request.emergencyContact()),
                trimToNull(request.emergencyPhone()),
                trimToNull(request.bloodType()),
                trimToNull(request.allergyHistory()),
                trimToNull(request.medicalHistory()),
                PatientStatus.ACTIVE,
                responsiblePerson.userId(),
                responsiblePerson.departmentId()
        );
        return PatientResponse.from(patientRepository.save(patient));
    }

    @Transactional
    public PatientResponse update(long id, UpdatePatientRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        Patient patient = requireWritable(id, user);
        patient.update(
                request.name() == null ? patient.getName() : request.name().trim(),
                request.gender() == null ? patient.getGender() : trimToNull(request.gender()),
                request.birthDate() == null ? patient.getBirthDate() : request.birthDate(),
                request.phone() == null ? patient.getPhone() : trimToNull(request.phone()),
                request.idCard() == null ? patient.getIdCard() : trimToNull(request.idCard()),
                request.address() == null ? patient.getAddress() : trimToNull(request.address()),
                request.emergencyContact() == null ? patient.getEmergencyContact() : trimToNull(request.emergencyContact()),
                request.emergencyPhone() == null ? patient.getEmergencyPhone() : trimToNull(request.emergencyPhone()),
                request.bloodType() == null ? patient.getBloodType() : trimToNull(request.bloodType()),
                request.allergyHistory() == null ? patient.getAllergyHistory() : trimToNull(request.allergyHistory()),
                request.medicalHistory() == null ? patient.getMedicalHistory() : trimToNull(request.medicalHistory()),
                request.status() == null ? patient.getStatus() : request.status(),
                patient.getOwnerId(),
                patient.getDepartmentId()
        );
        return PatientResponse.from(patientRepository.saveAndFlush(patient));
    }

    @Transactional
    public void delete(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireWritable(id, user).delete();
    }

    private Patient requireReadable(long id, UserContext user) {
        return patientRepository.findAccessibleById(
                        id,
                        user.userId(),
                        user.hasAllAccess(),
                        user.hasSelfAccess(),
                        user.hasDepartmentAccess(),
                        queryDepartmentIds(user),
                        Instant.now()
                )
                .orElseThrow(() -> BusinessException.notFound("Patient"));
    }

    private Patient requireWritable(long id, UserContext user) {
        return patientRepository.findWritableById(
                        id,
                        user.userId(),
                        user.hasAllAccess(),
                        user.hasSelfAccess(),
                        user.hasDepartmentAccess(),
                        queryDepartmentIds(user)
                )
                .orElseThrow(() -> BusinessException.notFound("Patient"));
    }

    private Collection<Long> queryDepartmentIds(UserContext user) {
        return user.departmentIds().isEmpty() ? List.of(-1L) : user.departmentIds();
    }

    private String normalizeKeyword(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private String generatedPatientNo() {
        return "P-" + UUID.randomUUID().toString().replace("-", "")
                .substring(0, 14).toUpperCase(Locale.ROOT);
    }
}
