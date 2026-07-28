package com.yuanqi.backend.analytics.dto;

import java.util.List;

public record PrescriptionAnalysisSnapshot(
        String schemaVersion,
        int rowCount,
        boolean truncated,
        List<PrescriptionSnapshotRow> rows
) {
}
