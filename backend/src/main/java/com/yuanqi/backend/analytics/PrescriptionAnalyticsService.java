package com.yuanqi.backend.analytics;

import com.yuanqi.backend.analytics.dto.PrescriptionAnalysisSnapshot;
import com.yuanqi.backend.analytics.dto.PrescriptionDatasetSchema;
import com.yuanqi.backend.analytics.dto.PrescriptionSnapshotRequest;
import com.yuanqi.backend.analytics.dto.PrescriptionSnapshotRow;
import com.yuanqi.backend.prescription.domain.Prescription;
import com.yuanqi.backend.prescription.repository.PrescriptionRepository;
import com.yuanqi.backend.security.CurrentUserProvider;
import com.yuanqi.backend.security.UserContext;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PrescriptionAnalyticsService {
    private final PrescriptionRepository repository;
    private final CurrentUserProvider currentUserProvider;

    public PrescriptionAnalyticsService(
            PrescriptionRepository repository,
            CurrentUserProvider currentUserProvider
    ) {
        this.repository = repository;
        this.currentUserProvider = currentUserProvider;
    }

    public PrescriptionDatasetSchema schema() {
        return PrescriptionDatasetSchema.current();
    }

    @Transactional(readOnly = true)
    public PrescriptionAnalysisSnapshot snapshot(PrescriptionSnapshotRequest request) {
        UserContext user = currentUserProvider.requireCurrentUser();
        int requestedRows = request.maximumRows();
        Collection<Long> scopeDepartments = user.departmentIds().isEmpty()
                ? List.of(-1L) : user.departmentIds();
        Collection<Long> requestedDepartments = request.departmentIds().isEmpty()
                ? List.of(-1L) : request.departmentIds();
        List<Prescription> matched = repository.findAccessibleSnapshot(
                user.userId(),
                user.hasAllAccess(),
                user.hasSelfAccess(),
                user.hasDepartmentAccess(),
                scopeDepartments,
                Instant.now(),
                request.fromDate().atStartOfDay(),
                request.toDate().plusDays(1).atStartOfDay(),
                !request.departmentIds().isEmpty(),
                requestedDepartments,
                PageRequest.of(
                        0,
                        requestedRows + 1,
                        Sort.by(Sort.Direction.ASC, "prescriptionDate").and(Sort.by("id"))
                )
        ).getContent();
        boolean truncated = matched.size() > requestedRows;
        List<PrescriptionSnapshotRow> rows = matched.stream()
                .limit(requestedRows)
                .map(PrescriptionSnapshotRow::from)
                .toList();
        return new PrescriptionAnalysisSnapshot(
                PrescriptionDatasetSchema.current().schemaVersion(),
                rows.size(),
                truncated,
                rows
        );
    }
}
