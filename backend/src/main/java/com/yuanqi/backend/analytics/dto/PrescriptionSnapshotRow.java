package com.yuanqi.backend.analytics.dto;

import com.yuanqi.backend.prescription.domain.Prescription;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public record PrescriptionSnapshotRow(
        LocalDateTime prescriptionDate,
        BigDecimal totalAmount,
        String status,
        long departmentId
) {
    public static PrescriptionSnapshotRow from(Prescription prescription) {
        return new PrescriptionSnapshotRow(
                prescription.getPrescriptionDate(),
                prescription.getTotalAmount(),
                prescription.getStatus().name(),
                prescription.getDepartmentId()
        );
    }
}
