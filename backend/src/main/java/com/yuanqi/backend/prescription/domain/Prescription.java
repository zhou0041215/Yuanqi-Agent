package com.yuanqi.backend.prescription.domain;

import com.yuanqi.backend.common.persistence.AuditedEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "prescription")
public class Prescription extends AuditedEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;

    @Column(name = "prescription_no", nullable = false, unique = true, length = 64)
    private String prescriptionNo;

    @Column(name = "patient_id", nullable = false)
    private long patientId;

    @Column(name = "record_id")
    private Long recordId;

    @Column(name = "doctor_name", nullable = false, length = 100)
    private String doctorName;

    @Column(name = "prescription_date", nullable = false)
    private LocalDateTime prescriptionDate;

    @Column(columnDefinition = "TEXT")
    private String diagnosis;

    @Column(name = "drugs_json", columnDefinition = "TEXT")
    private String drugsJson;

    @Column(name = "total_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal totalAmount;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private PrescriptionStatus status;

    @Column(columnDefinition = "TEXT")
    private String notes;

    @Column(name = "owner_id", nullable = false)
    private long ownerId;

    @Column(name = "department_id", nullable = false)
    private long departmentId;

    @Column(nullable = false)
    private boolean deleted;

    protected Prescription() {
    }

    public Prescription(
            long tenantId,
            String prescriptionNo,
            long patientId,
            Long recordId,
            String doctorName,
            LocalDateTime prescriptionDate,
            String diagnosis,
            String drugsJson,
            BigDecimal totalAmount,
            PrescriptionStatus status,
            String notes,
            long ownerId,
            long departmentId
    ) {
        this.tenantId = tenantId;
        this.prescriptionNo = prescriptionNo;
        this.patientId = patientId;
        this.recordId = recordId;
        this.doctorName = doctorName;
        this.prescriptionDate = prescriptionDate;
        this.diagnosis = diagnosis;
        this.drugsJson = drugsJson;
        this.totalAmount = totalAmount;
        this.status = status;
        this.notes = notes;
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    public void update(
            long patientId,
            Long recordId,
            String doctorName,
            LocalDateTime prescriptionDate,
            String diagnosis,
            String drugsJson,
            BigDecimal totalAmount,
            PrescriptionStatus status,
            String notes,
            long ownerId,
            long departmentId
    ) {
        this.patientId = patientId;
        this.recordId = recordId;
        this.doctorName = doctorName;
        this.prescriptionDate = prescriptionDate;
        this.diagnosis = diagnosis;
        this.drugsJson = drugsJson;
        this.totalAmount = totalAmount;
        this.status = status;
        this.notes = notes;
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    public void delete() {
        this.deleted = true;
    }

    public Long getId() {
        return id;
    }

    public long getTenantId() {
        return tenantId;
    }

    public String getPrescriptionNo() {
        return prescriptionNo;
    }

    public long getPatientId() {
        return patientId;
    }

    public Long getRecordId() {
        return recordId;
    }

    public String getDoctorName() {
        return doctorName;
    }

    public LocalDateTime getPrescriptionDate() {
        return prescriptionDate;
    }

    public String getDiagnosis() {
        return diagnosis;
    }

    public String getDrugsJson() {
        return drugsJson;
    }

    public BigDecimal getTotalAmount() {
        return totalAmount;
    }

    public PrescriptionStatus getStatus() {
        return status;
    }

    public String getNotes() {
        return notes;
    }

    public long getOwnerId() {
        return ownerId;
    }

    public long getDepartmentId() {
        return departmentId;
    }

    public boolean isDeleted() {
        return deleted;
    }
}
