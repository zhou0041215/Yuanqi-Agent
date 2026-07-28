package com.yuanqi.backend.prescription.repository;

import com.yuanqi.backend.prescription.domain.Prescription;
import java.util.Collection;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.time.LocalDateTime;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface PrescriptionRepository extends JpaRepository<Prescription, Long> {

    List<Prescription> findByPatientIdAndDeletedFalse(long patientId);

    List<Prescription> findByTenantIdAndDeletedFalse(long tenantId);

    boolean existsByTenantIdAndPrescriptionNo(long tenantId, String prescriptionNo);

    @Query("""
            select p from Prescription p
             where p.patientId = :patientId
               and p.tenantId = :tenantId
               and p.deleted = false
               and (
                    :allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds)
                    or exists (
                        select g.id from PatientAccessGrant g
                         where g.tenantId = :tenantId and g.patientId = p.patientId
                           and g.granteeUserId = :userId and g.revokedAt is null
                           and g.validFrom <= :now and g.validUntil > :now
                    )
               )
             order by p.prescriptionDate desc
            """)
    List<Prescription> findAccessibleByPatientId(
            @Param("patientId") long patientId, @Param("tenantId") long tenantId,
            @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds, @Param("now") Instant now
    );

    @Query("""
            select p from Prescription p
             where p.tenantId = :tenantId
               and p.deleted = false
               and (
                    :allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds)
                    or exists (
                        select g.id from PatientAccessGrant g
                         where g.tenantId = :tenantId
                           and g.patientId = p.patientId
                           and g.granteeUserId = :userId
                           and g.revokedAt is null
                           and g.validFrom <= :now
                           and g.validUntil > :now
                    )
               )
               and (
                    :keyword is null
                    or lower(p.prescriptionNo) like lower(concat('%', :keyword, '%'))
                    or lower(p.doctorName) like lower(concat('%', :keyword, '%'))
                    or lower(p.diagnosis) like lower(concat('%', :keyword, '%'))
               )
            """)
    Page<Prescription> findAccessible(
            @Param("tenantId") long tenantId,
            @Param("userId") long userId,
            @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess,
            @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds,
            @Param("now") Instant now,
            @Param("keyword") String keyword,
            Pageable pageable
    );

    @Query("""
            select p from Prescription p
             where p.tenantId = :tenantId
               and p.deleted = false
               and p.prescriptionDate >= :fromDate
               and p.prescriptionDate < :toDateExclusive
               and (:filterDepartments = false or p.departmentId in :requestedDepartmentIds)
               and (
                    :allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :scopeDepartmentIds)
                    or exists (
                        select g.id from PatientAccessGrant g
                         where g.tenantId = :tenantId
                           and g.patientId = p.patientId
                           and g.granteeUserId = :userId
                           and g.revokedAt is null
                           and g.validFrom <= :now
                           and g.validUntil > :now
                    )
               )
            """)
    Page<Prescription> findAccessibleSnapshot(
            @Param("tenantId") long tenantId,
            @Param("userId") long userId,
            @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess,
            @Param("departmentAccess") boolean departmentAccess,
            @Param("scopeDepartmentIds") Collection<Long> scopeDepartmentIds,
            @Param("now") Instant now,
            @Param("fromDate") LocalDateTime fromDate,
            @Param("toDateExclusive") LocalDateTime toDateExclusive,
            @Param("filterDepartments") boolean filterDepartments,
            @Param("requestedDepartmentIds") Collection<Long> requestedDepartmentIds,
            Pageable pageable
    );

    @Query("""
            select p from Prescription p
             where p.id = :id
               and p.tenantId = :tenantId
               and p.deleted = false
               and (
                    :allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds)
                    or exists (
                        select g.id from PatientAccessGrant g
                         where g.tenantId = :tenantId
                           and g.patientId = p.patientId
                           and g.granteeUserId = :userId
                           and g.revokedAt is null
                           and g.validFrom <= :now
                           and g.validUntil > :now
                    )
               )
            """)
    Optional<Prescription> findAccessibleById(
            @Param("id") long id,
            @Param("tenantId") long tenantId,
            @Param("userId") long userId,
            @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess,
            @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds,
            @Param("now") Instant now
    );

    @Query("""
            select p from Prescription p
             where p.id = :id
               and p.tenantId = :tenantId
               and p.deleted = false
               and (
                    :allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds)
               )
            """)
    Optional<Prescription> findWritableById(
            @Param("id") long id,
            @Param("tenantId") long tenantId,
            @Param("userId") long userId,
            @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess,
            @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds
    );
}
