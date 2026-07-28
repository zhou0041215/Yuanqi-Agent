package com.yuanqi.backend.medicalrecord.service;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.medicalrecord.domain.MedicalRecord;
import com.yuanqi.backend.medicalrecord.repository.MedicalRecordRepository;
import com.yuanqi.backend.medicalrecord.web.dto.CreateMedicalRecordRequest;
import com.yuanqi.backend.medicalrecord.web.dto.MedicalRecordResponse;
import com.yuanqi.backend.medicalrecord.web.dto.UpdateMedicalRecordRequest;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.RowScopeGuard;
import com.yuanqi.backend.security.UserContext;
import java.util.Collection;
import java.time.Instant;
import java.util.List;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MedicalRecordService {
    private final MedicalRecordRepository medicalRecordRepository;
    private final CurrentUserProvider currentUserProvider;
    private final RowScopeGuard rowScopeGuard;

    public MedicalRecordService(
            MedicalRecordRepository medicalRecordRepository,
            CurrentUserProvider currentUserProvider,
            RowScopeGuard rowScopeGuard
    ) {
        this.medicalRecordRepository = medicalRecordRepository;
        this.currentUserProvider = currentUserProvider;
        this.rowScopeGuard = rowScopeGuard;
    }

    @Transactional(readOnly = true)
    public PageResponse<MedicalRecordResponse> search(String keyword, int page, int size) {
        UserContext user = currentUserProvider.requireCurrentUser();
        PageRequest pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<MedicalRecord> result = medicalRecordRepository.findAccessible(
                user.tenantId(),
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
        rowScopeGuard.assertAssignable(user, request.ownerId(), request.departmentId());
        String recordNo = request.recordNo().trim();
        if (medicalRecordRepository.existsByTenantIdAndRecordNo(user.tenantId(), recordNo)) {
            throw BusinessException.conflict("Record number already exists in this tenant");
        }
        MedicalRecord medicalRecord = new MedicalRecord(
                user.tenantId(),
                recordNo,
                request.patientId(),
                request.visitDate(),
                request.department().trim(),
                request.doctorName().trim(),
                trimToNull(request.chiefComplaint()),
                trimToNull(request.diagnosis()),
                trimToNull(request.treatmentPlan()),
                trimToNull(request.notes()),
                request.status(),
                request.ownerId(),
                request.departmentId()
        );
        return MedicalRecordResponse.from(medicalRecordRepository.save(medicalRecord));
    }

    @Transactional
    public MedicalRecordResponse update(long id, UpdateMedicalRecordRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        MedicalRecord medicalRecord = requireWritable(id, user);
        long ownerId = request.ownerId() == null ? medicalRecord.getOwnerId() : request.ownerId();
        long departmentId = request.departmentId() == null ? medicalRecord.getDepartmentId() : request.departmentId();
        rowScopeGuard.assertAssignable(user, ownerId, departmentId);
        medicalRecord.update(
                request.patientId() == null ? medicalRecord.getPatientId() : request.patientId(),
                request.visitDate() == null ? medicalRecord.getVisitDate() : request.visitDate(),
                request.department() == null ? medicalRecord.getDepartment() : request.department().trim(),
                request.doctorName() == null ? medicalRecord.getDoctorName() : request.doctorName().trim(),
                request.chiefComplaint() == null ? medicalRecord.getChiefComplaint() : trimToNull(request.chiefComplaint()),
                request.diagnosis() == null ? medicalRecord.getDiagnosis() : trimToNull(request.diagnosis()),
                request.treatmentPlan() == null ? medicalRecord.getTreatmentPlan() : trimToNull(request.treatmentPlan()),
                request.notes() == null ? medicalRecord.getNotes() : trimToNull(request.notes()),
                request.status() == null ? medicalRecord.getStatus() : request.status(),
                ownerId,
                departmentId
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
                        user.tenantId(),
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
                        user.tenantId(),
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
}
