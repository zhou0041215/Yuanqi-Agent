package com.yuanqi.backend.medicalrecord.web.dto;

import com.yuanqi.backend.medicalrecord.domain.MedicalRecord;
import com.yuanqi.backend.medicalrecord.domain.MedicalRecordStatus;
import java.time.Instant;
import java.time.LocalDateTime;

public record MedicalRecordResponse(
        long id,
        String recordNo,
        long patientId,
        LocalDateTime visitDate,
        String department,
        String doctorName,
        String chiefComplaint,
        String diagnosis,
        String treatmentPlan,
        String notes,
        MedicalRecordStatus status,
        long ownerId,
        long departmentId,
        Instant createdAt,
        Instant updatedAt,
        long version
) {
    public static MedicalRecordResponse from(MedicalRecord medicalRecord) {
        return new MedicalRecordResponse(
                medicalRecord.getId(),
                medicalRecord.getRecordNo(),
                medicalRecord.getPatientId(),
                medicalRecord.getVisitDate(),
                medicalRecord.getDepartment(),
                medicalRecord.getDoctorName(),
                medicalRecord.getChiefComplaint(),
                medicalRecord.getDiagnosis(),
                medicalRecord.getTreatmentPlan(),
                medicalRecord.getNotes(),
                medicalRecord.getStatus(),
                medicalRecord.getOwnerId(),
                medicalRecord.getDepartmentId(),
                medicalRecord.getCreatedAt(),
                medicalRecord.getUpdatedAt(),
                medicalRecord.getVersion()
        );
    }
}
