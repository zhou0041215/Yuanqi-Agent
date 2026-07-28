package com.yuanqi.backend.workflow;

import com.yuanqi.backend.prescription.domain.PrescriptionStatus;
import com.yuanqi.backend.prescription.service.PrescriptionService;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.JavaDelegate;
import org.springframework.stereotype.Component;

@Component("applyPrescriptionStatusChangeDelegate")
public class ApplyPrescriptionStatusChangeDelegate implements JavaDelegate {
    private final PrescriptionService prescriptionService;

    public ApplyPrescriptionStatusChangeDelegate(PrescriptionService prescriptionService) {
        this.prescriptionService = prescriptionService;
    }

    @Override
    public void execute(DelegateExecution execution) {
        long prescriptionId = requirePositiveLong(execution.getVariable("prescriptionId"));
        PrescriptionStatus targetStatus = PrescriptionStatus.valueOf(
                String.valueOf(execution.getVariable("targetStatus")));
        prescriptionService.applyApprovedStatusChange(prescriptionId, targetStatus);
    }

    private long requirePositiveLong(Object value) {
        if (value instanceof Number number && number.longValue() > 0) {
            return number.longValue();
        }
        throw new IllegalStateException("Invalid workflow variable: prescriptionId");
    }
}
