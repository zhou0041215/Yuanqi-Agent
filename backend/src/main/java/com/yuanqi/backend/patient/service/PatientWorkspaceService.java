package com.yuanqi.backend.patient.service;

import com.yuanqi.backend.access.repository.AccessPersonRepository;
import com.yuanqi.backend.medicalrecord.repository.MedicalRecordRepository;
import com.yuanqi.backend.medicalrecord.web.dto.MedicalRecordResponse;
import com.yuanqi.backend.patient.web.dto.PatientWorkspaceResponse;
import com.yuanqi.backend.prescription.repository.PrescriptionRepository;
import com.yuanqi.backend.prescription.web.dto.PrescriptionResponse;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PatientWorkspaceService {
    private final PatientService patientService;
    private final MedicalRecordRepository medicalRecordRepository;
    private final PrescriptionRepository prescriptionRepository;
    private final CurrentUserProvider currentUserProvider;
    private final AccessPersonRepository personRepository;

    public PatientWorkspaceService(PatientService patientService, MedicalRecordRepository medicalRecordRepository,
                                   PrescriptionRepository prescriptionRepository, CurrentUserProvider currentUserProvider,
                                   AccessPersonRepository personRepository) {
        this.patientService = patientService;
        this.medicalRecordRepository = medicalRecordRepository;
        this.prescriptionRepository = prescriptionRepository;
        this.currentUserProvider = currentUserProvider;
        this.personRepository = personRepository;
    }

    @Transactional(readOnly = true)
    public PatientWorkspaceResponse get(long patientId) {
        var patient = patientService.get(patientId);
        UserContext user = currentUserProvider.requireCurrentUser();
        Instant now = Instant.now();
        List<Long> departments = user.departmentIds().isEmpty() ? List.of(-1L) : List.copyOf(user.departmentIds());
        var records = medicalRecordRepository.findAccessibleByPatientId(patientId, user.userId(),
                user.hasAllAccess(), user.hasSelfAccess(), user.hasDepartmentAccess(), departments, now)
                .stream().map(MedicalRecordResponse::from).toList();
        var prescriptions = prescriptionRepository.findAccessibleByPatientId(patientId, user.userId(),
                user.hasAllAccess(), user.hasSelfAccess(), user.hasDepartmentAccess(), departments, now)
                .stream().map(PrescriptionResponse::from).toList();
        var responsiblePerson = personRepository.findByUserId(patient.ownerId())
                .map(person -> new PatientWorkspaceResponse.ResponsiblePerson(
                        person.getUserId(), person.getDisplayName(), person.getDepartmentName(), person.getRoleCode()))
                .orElse(new PatientWorkspaceResponse.ResponsiblePerson(
                        patient.ownerId(), "未找到负责人", "未登记科室", "UNKNOWN"));
        return new PatientWorkspaceResponse(patient, responsiblePerson, records, prescriptions);
    }
}
