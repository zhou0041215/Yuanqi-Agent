package com.yuanqi.backend.patient.web.dto;

import com.yuanqi.backend.medicalrecord.web.dto.MedicalRecordResponse;
import com.yuanqi.backend.prescription.web.dto.PrescriptionResponse;
import java.util.List;

public record PatientWorkspaceResponse(
        PatientResponse patient,
        ResponsiblePerson responsiblePerson,
        List<MedicalRecordResponse> medicalRecords,
        List<PrescriptionResponse> prescriptions
) {
    public record ResponsiblePerson(
            long userId,
            String displayName,
            String departmentName,
            String roleCode
    ) {
    }
}
