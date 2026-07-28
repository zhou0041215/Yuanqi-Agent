package com.yuanqi.backend.prescription.web.dto;

import com.yuanqi.backend.prescription.domain.Prescription;
import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDateTime;

public record PrescriptionResponse(
        long id,
        String prescriptionNo,
        long patientId,
        Long recordId,
        String doctorName,
        LocalDateTime prescriptionDate,
        String diagnosis,
        String drugsJson,
        BigDecimal totalAmount,
        PrescriptionStatus status,
        String notes,
        long ownerId,
        long departmentId,
        Instant createdAt,
        Instant updatedAt,
        long version
) {
    public static PrescriptionResponse from(Prescription prescription) {
        return new PrescriptionResponse(
                prescription.getId(),
                prescription.getPrescriptionNo(),
                prescription.getPatientId(),
                prescription.getRecordId(),
                prescription.getDoctorName(),
                prescription.getPrescriptionDate(),
                prescription.getDiagnosis(),
                prescription.getDrugsJson(),
                prescription.getTotalAmount(),
                prescription.getStatus(),
                prescription.getNotes(),
                prescription.getOwnerId(),
                prescription.getDepartmentId(),
                prescription.getCreatedAt(),
                prescription.getUpdatedAt(),
                prescription.getVersion()
        );
    }
}
