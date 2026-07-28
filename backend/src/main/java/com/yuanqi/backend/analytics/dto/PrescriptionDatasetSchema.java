package com.yuanqi.backend.analytics.dto;

import java.util.List;

public record PrescriptionDatasetSchema(
        String dataset,
        String schemaVersion,
        int maximumRows,
        List<DatasetColumn> columns
) {
    public static PrescriptionDatasetSchema current() {
        return new PrescriptionDatasetSchema(
                "prescriptions",
                "prescriptions-v1",
                10_000,
                List.of(
                        new DatasetColumn("prescription_date", "datetime", false, "Prescription creation time"),
                        new DatasetColumn("total_amount", "decimal", false, "Prescription total amount"),
                        new DatasetColumn("status", "string", false, "Prescription lifecycle status"),
                        new DatasetColumn("department_id", "integer", false, "Owning department identifier")
                )
        );
    }
}
