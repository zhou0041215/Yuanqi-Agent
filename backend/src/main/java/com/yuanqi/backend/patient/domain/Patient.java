package com.yuanqi.backend.patient.domain;

import com.yuanqi.backend.common.persistence.AuditedEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDate;

@Entity
@Table(name = "patient")
public class Patient extends AuditedEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false)
    private long tenantId;

    @Column(name = "patient_no", nullable = false, unique = true, length = 64)
    private String patientNo;

    @Column(nullable = false, length = 200)
    private String name;

    @Column(length = 16)
    private String gender;

    @Column(name = "birth_date")
    private LocalDate birthDate;

    @Column(length = 32)
    private String phone;

    @Column(name = "id_card", length = 32)
    private String idCard;

    @Column(length = 500)
    private String address;

    @Column(name = "emergency_contact", length = 100)
    private String emergencyContact;

    @Column(name = "emergency_phone", length = 32)
    private String emergencyPhone;

    @Column(name = "blood_type", length = 8)
    private String bloodType;

    @Column(name = "allergy_history", columnDefinition = "TEXT")
    private String allergyHistory;

    @Column(name = "medical_history", columnDefinition = "TEXT")
    private String medicalHistory;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private PatientStatus status;

    @Column(name = "owner_id", nullable = false)
    private long ownerId;

    @Column(name = "department_id", nullable = false)
    private long departmentId;

    @Column(nullable = false)
    private boolean deleted;

    protected Patient() {
    }

    public Patient(
            long tenantId,
            String patientNo,
            String name,
            String gender,
            LocalDate birthDate,
            String phone,
            String idCard,
            String address,
            String emergencyContact,
            String emergencyPhone,
            String bloodType,
            String allergyHistory,
            String medicalHistory,
            PatientStatus status,
            long ownerId,
            long departmentId
    ) {
        this.tenantId = tenantId;
        this.patientNo = patientNo;
        this.name = name;
        this.gender = gender;
        this.birthDate = birthDate;
        this.phone = phone;
        this.idCard = idCard;
        this.address = address;
        this.emergencyContact = emergencyContact;
        this.emergencyPhone = emergencyPhone;
        this.bloodType = bloodType;
        this.allergyHistory = allergyHistory;
        this.medicalHistory = medicalHistory;
        this.status = status;
        this.ownerId = ownerId;
        this.departmentId = departmentId;
    }

    public void update(
            String name,
            String gender,
            LocalDate birthDate,
            String phone,
            String idCard,
            String address,
            String emergencyContact,
            String emergencyPhone,
            String bloodType,
            String allergyHistory,
            String medicalHistory,
            PatientStatus status,
            long ownerId,
            long departmentId
    ) {
        this.name = name;
        this.gender = gender;
        this.birthDate = birthDate;
        this.phone = phone;
        this.idCard = idCard;
        this.address = address;
        this.emergencyContact = emergencyContact;
        this.emergencyPhone = emergencyPhone;
        this.bloodType = bloodType;
        this.allergyHistory = allergyHistory;
        this.medicalHistory = medicalHistory;
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

    public long getTenantId() {
        return tenantId;
    }

    public String getPatientNo() {
        return patientNo;
    }

    public String getName() {
        return name;
    }

    public String getGender() {
        return gender;
    }

    public LocalDate getBirthDate() {
        return birthDate;
    }

    public String getPhone() {
        return phone;
    }

    public String getIdCard() {
        return idCard;
    }

    public String getAddress() {
        return address;
    }

    public String getEmergencyContact() {
        return emergencyContact;
    }

    public String getEmergencyPhone() {
        return emergencyPhone;
    }

    public String getBloodType() {
        return bloodType;
    }

    public String getAllergyHistory() {
        return allergyHistory;
    }

    public String getMedicalHistory() {
        return medicalHistory;
    }

    public PatientStatus getStatus() {
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
