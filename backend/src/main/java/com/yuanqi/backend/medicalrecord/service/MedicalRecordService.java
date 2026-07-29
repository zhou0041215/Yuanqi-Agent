package com.yuanqi.backend.medicalrecord.service;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.medicalrecord.domain.MedicalRecord;
import com.yuanqi.backend.medicalrecord.domain.MedicalRecordStatus;
import com.yuanqi.backend.medicalrecord.repository.MedicalRecordRepository;
import com.yuanqi.backend.medicalrecord.web.dto.CreateMedicalRecordRequest;
import com.yuanqi.backend.medicalrecord.web.dto.MedicalRecordResponse;
import com.yuanqi.backend.medicalrecord.web.dto.UpdateMedicalRecordRequest;
import com.yuanqi.backend.patient.service.PatientService;
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
public class MedicalRecordService {
    private final MedicalRecordRepository medicalRecordRepository;
    private final CurrentUserProvider currentUserProvider;
    private final PatientService patientService;
    private final ClinicalIdentityService clinicalIdentityService;

    public MedicalRecordService(
            MedicalRecordRepository medicalRecordRepository,
            CurrentUserProvider currentUserProvider,
            PatientService patientService,
            ClinicalIdentityService clinicalIdentityService
    ) {
        this.medicalRecordRepository = medicalRecordRepository;
        this.currentUserProvider = currentUserProvider;
        this.patientService = patientService;
        this.clinicalIdentityService = clinicalIdentityService;
    }

    @Transactional(readOnly = true)
    public PageResponse<MedicalRecordResponse> search(String keyword, int page, int size) {
        UserContext user = currentUserProvider.requireCurrentUser();
        PageRequest pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<MedicalRecord> result = medicalRecordRepository.findAccessible(
                user.userId(),
                user.hasAllAccess(),
                user.hasSelfAccess(),
                user.hasDepartmentAccess(),
                queryDepartmentIds(user),
                Instant.now(),
                normalizeKeyword(keyword),
                pageable
        );
        return PageResponse.from(result, MedicalRecordResponse::from);
    }

    @Transactional(readOnly = true)
    public MedicalRecordResponse get(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        return MedicalRecordResponse.from(requireReadable(id, user));
    }

    @Transactional(readOnly = true)
    public void assertAccessible(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireReadable(id, user);
    }

    @Transactional
    public MedicalRecordResponse create(CreateMedicalRecordRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        patientService.assertAccessible(request.patientId());
        var clinician = clinicalIdentityService.requireClinicalWriter(user);
        String recordNo = generatedRecordNo();
        if (medicalRecordRepository.existsByRecordNo(recordNo)) {
            throw BusinessException.conflict("Record number already exists");
        }
        MedicalRecord medicalRecord = new MedicalRecord(
                recordNo,
                request.patientId(),
                request.visitDate(),
                clinician.departmentName(),
                clinician.displayName(),
                trimToNull(request.chiefComplaint()),
                trimToNull(request.diagnosis()),
                trimToNull(request.treatmentPlan()),
                trimToNull(request.notes()),
                MedicalRecordStatus.ACTIVE,
                clinician.userId(),
                clinician.departmentId()
        );
        return MedicalRecordResponse.from(medicalRecordRepository.save(medicalRecord));
    }

    @Transactional
    public MedicalRecordResponse update(long id, UpdateMedicalRecordRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        MedicalRecord medicalRecord = requireWritable(id, user);
        long patientId = request.patientId() == null ? medicalRecord.getPatientId() : request.patientId();
        patientService.assertAccessible(patientId);
        medicalRecord.update(
                patientId,
                request.visitDate() == null ? medicalRecord.getVisitDate() : request.visitDate(),
                medicalRecord.getDepartment(),
                medicalRecord.getDoctorName(),
                request.chiefComplaint() == null ? medicalRecord.getChiefComplaint() : trimToNull(request.chiefComplaint()),
                request.diagnosis() == null ? medicalRecord.getDiagnosis() : trimToNull(request.diagnosis()),
                request.treatmentPlan() == null ? medicalRecord.getTreatmentPlan() : trimToNull(request.treatmentPlan()),
                request.notes() == null ? medicalRecord.getNotes() : trimToNull(request.notes()),
                request.status() == null ? medicalRecord.getStatus() : request.status(),
                medicalRecord.getOwnerId(),
                medicalRecord.getDepartmentId()
        );
        return MedicalRecordResponse.from(medicalRecordRepository.saveAndFlush(medicalRecord));
    }

    @Transactional
    public void delete(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireWritable(id, user).delete();
    }

    private MedicalRecord requireReadable(long id, UserContext user) {
        return medicalRecordRepository.findAccessibleById(
                        id,
                        user.userId(),
                        user.hasAllAccess(),
                        user.hasSelfAccess(),
                        user.hasDepartmentAccess(),
                        queryDepartmentIds(user),
                        Instant.now()
                )
                .orElseThrow(() -> BusinessException.notFound("Medical record"));
    }

    private MedicalRecord requireWritable(long id, UserContext user) {
        return medicalRecordRepository.findWritableById(
                        id,
                        user.userId(),
                        user.hasAllAccess(),
                        user.hasSelfAccess(),
                        user.hasDepartmentAccess(),
                        queryDepartmentIds(user)
                )
                .orElseThrow(() -> BusinessException.notFound("Medical record"));
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

    private String generatedRecordNo() {
        return "MR-" + UUID.randomUUID().toString().replace("-", "")
                .substring(0, 14).toUpperCase(Locale.ROOT);
    }
}
