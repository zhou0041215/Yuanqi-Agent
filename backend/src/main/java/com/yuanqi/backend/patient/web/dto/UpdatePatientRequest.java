package com.yuanqi.backend.patient.web.dto;

import com.yuanqi.backend.patient.domain.PatientStatus;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

public record UpdatePatientRequest(
        @Size(min = 1, max = 200) String name,
        @Size(max = 16) String gender,
        LocalDate birthDate,
        @Size(max = 32) String phone,
        @Size(max = 32) String idCard,
        @Size(max = 500) String address,
        @Size(max = 100) String emergencyContact,
        @Size(max = 32) String emergencyPhone,
        @Size(max = 8) String bloodType,
        String allergyHistory,
        String medicalHistory,
        PatientStatus status,
        @Positive Long ownerId,
        @Positive Long departmentId
) {
}
