package com.yuanqi.backend.patient.web.dto;

import com.yuanqi.backend.patient.domain.Patient;
import com.yuanqi.backend.patient.domain.PatientStatus;
import java.time.Instant;
import java.time.LocalDate;

public record PatientResponse(
        long id,
        String patientNo,
        String name,
        String gender,
        LocalDate birthDate,
        String phone,
        String idCard,
        String address,
        String emergencyContact,
        String emergencyPhone,
        String bloodType,
        String allergyHistory,
        String medicalHistory,
        PatientStatus status,
        long ownerId,
        long departmentId,
        Instant createdAt,
        Instant updatedAt,
        long version
) {
    public static PatientResponse from(Patient patient) {
        return new PatientResponse(
                patient.getId(),
                patient.getPatientNo(),
                patient.getName(),
                patient.getGender(),
                patient.getBirthDate(),
                patient.getPhone(),
                patient.getIdCard(),
                patient.getAddress(),
                patient.getEmergencyContact(),
                patient.getEmergencyPhone(),
                patient.getBloodType(),
                patient.getAllergyHistory(),
                patient.getMedicalHistory(),
                patient.getStatus(),
                patient.getOwnerId(),
                patient.getDepartmentId(),
                patient.getCreatedAt(),
                patient.getUpdatedAt(),
                patient.getVersion()
        );
    }
}
