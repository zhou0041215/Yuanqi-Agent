package com.yuanqi.backend.patient.web.dto;

import com.yuanqi.backend.patient.domain.PatientStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

public record CreatePatientRequest(
        @NotBlank @Size(max = 64) @Pattern(regexp = "[A-Za-z0-9_-]+") String patientNo,
        @NotBlank @Size(max = 200) String name,
        @NotBlank @Size(max = 16) String gender,
        LocalDate birthDate,
        @Size(max = 32) String phone,
        @Size(max = 32) String idCard,
        @Size(max = 500) String address,
        @Size(max = 100) String emergencyContact,
        @Size(max = 32) String emergencyPhone,
        @Size(max = 8) String bloodType,
        String allergyHistory,
        String medicalHistory,
        @NotNull PatientStatus status,
        @Positive long ownerId,
        @Positive long departmentId
) {
}
