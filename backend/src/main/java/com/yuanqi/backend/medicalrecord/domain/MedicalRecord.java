package com.yuanqi.backend.medicalrecord.domain;

import com.yuanqi.backend.common.persistence.AuditedEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

@Entity
@Table(name = "medical_record")
public class MedicalRecord extends AuditedEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "record_no", nullable = false, unique = true, length = 64)
    private String recordNo;

    @Column(name = "patient_id", nullable = false)
    private long patientId;

    @Column(name = "visit_date", nullable = false)
    private LocalDateTime visitDate;

    @Column(nullable = false, length = 100)
    private String department;

    @Column(name = "doctor_name", nullable = false, length = 100)
    private String doctorName;

    @Column(name = "chief_complaint", columnDefinition = "TEXT")
    private String chiefComplaint;

    @Column(columnDefinition = "TEXT")
    private String diagnosis;

    @Column(name = "treatment_plan", columnDefinition = "TEXT")
    private String treatmentPlan;

    @Column(columnDefinition = "TEXT")
    private String notes;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private MedicalRecordStatus status;

    @Column(name = "owner_id", nullable = false)
    private long ownerId;

    @Column(name = "department_id", nullable = false)
    private long departmentId;

    @Column(nullable = false)
    private boolean deleted;

    protected MedicalRecord() {
    }

    public MedicalRecord(
            String recordNo,
            long patientId,
            LocalDateTime visitDate,
            String department,
            String doctorName,
            String chiefComplaint,
            String diagnosis,
            String treatmentPlan,
            String notes,
            MedicalRecordStatus status,
            long ownerId,
            long departmentId
    ) {
        this.recordNo = recordNo;
        this.patientId = patientId;
        this.visitDate = visitDate;
        this.department = department;
        this.doctorName = doctorName;
        this.chiefComplaint = chiefComplaint;
        this.diagnosis = diagnosis;
        this.treatmentPlan = treatmentPlan;
        this.notes = notes;
        this.status = status;
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    public void update(
            long patientId,
            LocalDateTime visitDate,
            String department,
            String doctorName,
            String chiefComplaint,
            String diagnosis,
            String treatmentPlan,
            String notes,
            MedicalRecordStatus status,
            long ownerId,
            long departmentId
    ) {
        this.patientId = patientId;
        this.visitDate = visitDate;
        this.department = department;
        this.doctorName = doctorName;
        this.chiefComplaint = chiefComplaint;
        this.diagnosis = diagnosis;
        this.treatmentPlan = treatmentPlan;
        this.notes = notes;
        this.status = status;
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    public void delete() {
        this.deleted = true;
    }

    public Long getId() {
        return id;
    }

    public String getRecordNo() {
        return recordNo;
    }

    public long getPatientId() {
        return patientId;
    }

    public LocalDateTime getVisitDate() {
        return visitDate;
    }

    public String getDepartment() {
        return department;
    }

    public String getDoctorName() {
        return doctorName;
    }

    public String getChiefComplaint() {
        return chiefComplaint;
    }

    public String getDiagnosis() {
        return diagnosis;
    }

    public String getTreatmentPlan() {
        return treatmentPlan;
    }

    public String getNotes() {
        return notes;
    }

    public MedicalRecordStatus getStatus() {
        return status;
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
