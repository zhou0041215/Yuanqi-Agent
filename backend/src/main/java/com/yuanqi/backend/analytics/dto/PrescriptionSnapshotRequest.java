package com.yuanqi.backend.analytics.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.Set;

public record PrescriptionSnapshotRequest(
        @NotNull LocalDate fromDate,
        @NotNull LocalDate toDate,
        @Size(max = 50) Set<@Min(1) Long> departmentIds,
        @Min(1) @Max(10_000) Integer maximumRows
) {
    public PrescriptionSnapshotRequest {
        departmentIds = departmentIds == null ? Set.of() : Set.copyOf(departmentIds);
        maximumRows = maximumRows == null ? 5_000 : maximumRows;
    }

    @AssertTrue(message = "Analysis date range must be ordered and no longer than 366 days")
    public boolean isDateRangeValid() {
        return fromDate != null
                && toDate != null
                && !fromDate.isAfter(toDate)
                && ChronoUnit.DAYS.between(fromDate, toDate) <= 366;
    }
}
