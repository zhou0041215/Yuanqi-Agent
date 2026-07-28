package com.yuanqi.backend.patient.web.dto;

import com.yuanqi.backend.medicalrecord.web.dto.MedicalRecordResponse;
import com.yuanqi.backend.prescription.web.dto.PrescriptionResponse;
import java.util.List;

public record PatientWorkspaceResponse(
        PatientResponse patient,
        List<MedicalRecordResponse> medicalRecords,
        List<PrescriptionResponse> prescriptions
) {
}
