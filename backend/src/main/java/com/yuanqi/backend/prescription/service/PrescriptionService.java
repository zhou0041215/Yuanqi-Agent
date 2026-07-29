package com.yuanqi.backend.prescription.service;

import com.yuanqi.backend.common.api.PageResponse;
import com.yuanqi.backend.common.exception.BusinessException;
import com.yuanqi.backend.medicalrecord.service.MedicalRecordService;
import com.yuanqi.backend.patient.service.PatientService;
import com.yuanqi.backend.prescription.domain.Prescription;
import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import com.yuanqi.backend.prescription.repository.PrescriptionRepository;
import com.yuanqi.backend.prescription.web.dto.CreatePrescriptionRequest;
import com.yuanqi.backend.prescription.web.dto.PrescriptionResponse;
import com.yuanqi.backend.prescription.web.dto.UpdatePrescriptionRequest;
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
public class PrescriptionService {
    private final PrescriptionRepository prescriptionRepository;
    private final CurrentUserProvider currentUserProvider;
    private final PatientService patientService;
    private final MedicalRecordService medicalRecordService;
    private final ClinicalIdentityService clinicalIdentityService;

    public PrescriptionService(
            PrescriptionRepository prescriptionRepository,
            CurrentUserProvider currentUserProvider,
            PatientService patientService,
            MedicalRecordService medicalRecordService,
            ClinicalIdentityService clinicalIdentityService
    ) {
        this.prescriptionRepository = prescriptionRepository;
        this.currentUserProvider = currentUserProvider;
        this.patientService = patientService;
        this.medicalRecordService = medicalRecordService;
        this.clinicalIdentityService = clinicalIdentityService;
    }

    @Transactional(readOnly = true)
    public PageResponse<PrescriptionResponse> search(String keyword, int page, int size) {
        UserContext user = currentUserProvider.requireCurrentUser();
        PageRequest pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Prescription> result = prescriptionRepository.findAccessible(
                user.userId(),
                user.hasAllAccess(),
                user.hasSelfAccess(),
                user.hasDepartmentAccess(),
                queryDepartmentIds(user),
                Instant.now(),
                normalizeKeyword(keyword),
                pageable
        );
        return PageResponse.from(result, PrescriptionResponse::from);
    }

    @Transactional(readOnly = true)
    public PrescriptionResponse get(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        return PrescriptionResponse.from(requireReadable(id, user));
    }

    @Transactional(readOnly = true)
    public void assertAccessible(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireReadable(id, user);
    }

    @Transactional
    public PrescriptionResponse create(CreatePrescriptionRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        patientService.assertAccessible(request.patientId());
        assertRecordBelongsToPatient(request.recordId(), request.patientId());
        var clinician = clinicalIdentityService.requireClinicalWriter(user);
        String prescriptionNo = generatedPrescriptionNo();
        if (prescriptionRepository.existsByPrescriptionNo(prescriptionNo)) {
            throw BusinessException.conflict("Prescription number already exists");
        }
        Prescription prescription = new Prescription(
                prescriptionNo,
                request.patientId(),
                request.recordId(),
                clinician.displayName(),
                request.prescriptionDate(),
                trimToNull(request.diagnosis()),
                trimToNull(request.drugsJson()),
                request.totalAmount(),
                PrescriptionStatus.PENDING,
                trimToNull(request.notes()),
                clinician.userId(),
                clinician.departmentId()
        );
        return PrescriptionResponse.from(prescriptionRepository.save(prescription));
    }

    @Transactional
    public PrescriptionResponse update(long id, UpdatePrescriptionRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        Prescription prescription = requireWritable(id, user);
        long patientId = request.patientId() == null ? prescription.getPatientId() : request.patientId();
        patientService.assertAccessible(patientId);
        Long recordId = request.recordId() == null ? prescription.getRecordId() : request.recordId();
        assertRecordBelongsToPatient(recordId, patientId);
        prescription.update(
                patientId,
                recordId,
                prescription.getDoctorName(),
                request.prescriptionDate() == null ? prescription.getPrescriptionDate() : request.prescriptionDate(),
                request.diagnosis() == null ? prescription.getDiagnosis() : trimToNull(request.diagnosis()),
                request.drugsJson() == null ? prescription.getDrugsJson() : trimToNull(request.drugsJson()),
                request.totalAmount() == null ? prescription.getTotalAmount() : request.totalAmount(),
                request.status() == null ? prescription.getStatus() : request.status(),
                request.notes() == null ? prescription.getNotes() : trimToNull(request.notes()),
                prescription.getOwnerId(),
                prescription.getDepartmentId()
        );
        return PrescriptionResponse.from(prescriptionRepository.saveAndFlush(prescription));
    }

    @Transactional
    public void delete(long id) {
        UserContext user = currentUserProvider.requireCurrentUser();
        requireWritable(id, user).delete();
    }

    @Transactional
    public PrescriptionResponse applyApprovedStatusChange(long id, PrescriptionStatus targetStatus) {
        UserContext user = currentUserProvider.requireCurrentUser();
        Prescription prescription = requireWritable(id, user);
        if (prescription.getStatus() != PrescriptionStatus.PENDING) {
            throw BusinessException.conflict(
                    "Prescription status changed while approval was pending");
        }
        if (targetStatus == PrescriptionStatus.PENDING) {
            throw BusinessException.conflict("Approved target status must change the prescription");
        }
        prescription.update(
                prescription.getPatientId(),
                prescription.getRecordId(),
                prescription.getDoctorName(),
                prescription.getPrescriptionDate(),
                prescription.getDiagnosis(),
                prescription.getDrugsJson(),
                prescription.getTotalAmount(),
                targetStatus,
                prescription.getNotes(),
                prescription.getOwnerId(),
                prescription.getDepartmentId()
        );
        return PrescriptionResponse.from(prescriptionRepository.saveAndFlush(prescription));
    }

    private Prescription requireReadable(long id, UserContext user) {
        return prescriptionRepository.findAccessibleById(
                        id,
                        user.userId(),
                        user.hasAllAccess(),
                        user.hasSelfAccess(),
                        user.hasDepartmentAccess(),
                        queryDepartmentIds(user),
                        Instant.now()
                )
                .orElseThrow(() -> BusinessException.notFound("Prescription"));
    }

    private Prescription requireWritable(long id, UserContext user) {
        return prescriptionRepository.findWritableById(
                        id,
                        user.userId(),
                        user.hasAllAccess(),
                        user.hasSelfAccess(),
                        user.hasDepartmentAccess(),
                        queryDepartmentIds(user)
                )
                .orElseThrow(() -> BusinessException.notFound("Prescription"));
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

    private void assertRecordBelongsToPatient(Long recordId, long patientId) {
        if (recordId == null) {
            return;
        }
        if (medicalRecordService.get(recordId).patientId() != patientId) {
            throw BusinessException.conflict("The medical record does not belong to the selected patient");
        }
    }

    private String generatedPrescriptionNo() {
        return "RX-" + UUID.randomUUID().toString().replace("-", "")
                .substring(0, 14).toUpperCase(Locale.ROOT);
    }
}
