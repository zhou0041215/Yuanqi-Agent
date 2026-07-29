package com.yuanqi.backend.medicalrecord.repository;

import com.yuanqi.backend.medicalrecord.domain.MedicalRecord;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface MedicalRecordRepository extends JpaRepository<MedicalRecord, Long> {
    boolean existsByRecordNo(String recordNo);
    List<MedicalRecord> findByPatientIdAndDeletedFalse(long patientId);
    List<MedicalRecord> findByDeletedFalse();

    @Query("""
            select m from MedicalRecord m where m.patientId = :patientId and m.deleted = false
              and (:allAccess = true or (:selfAccess = true and m.ownerId = :userId)
                   or (:departmentAccess = true and m.departmentId in :departmentIds)
                   or exists (select g.id from PatientAccessGrant g where g.patientId = m.patientId
                              and g.granteeUserId = :userId and g.revokedAt is null
                              and g.validFrom <= :now and g.validUntil > :now)) order by m.visitDate desc
            """)
    List<MedicalRecord> findAccessibleByPatientId(
            @Param("patientId") long patientId, @Param("userId") long userId,
            @Param("allAccess") boolean allAccess, @Param("selfAccess") boolean selfAccess,
            @Param("departmentAccess") boolean departmentAccess, @Param("departmentIds") Collection<Long> departmentIds,
            @Param("now") Instant now);

    @Query("""
            select m from MedicalRecord m where m.deleted = false
              and (:allAccess = true or (:selfAccess = true and m.ownerId = :userId)
                   or (:departmentAccess = true and m.departmentId in :departmentIds)
                   or exists (select g.id from PatientAccessGrant g where g.patientId = m.patientId
                              and g.granteeUserId = :userId and g.revokedAt is null
                              and g.validFrom <= :now and g.validUntil > :now))
              and (:keyword is null or lower(m.recordNo) like lower(concat('%', :keyword, '%'))
                   or lower(m.doctorName) like lower(concat('%', :keyword, '%'))
                   or lower(m.department) like lower(concat('%', :keyword, '%')))
            """)
    Page<MedicalRecord> findAccessible(
            @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds, @Param("now") Instant now,
            @Param("keyword") String keyword, Pageable pageable);

    @Query("""
            select m from MedicalRecord m where m.id = :id and m.deleted = false
              and (:allAccess = true or (:selfAccess = true and m.ownerId = :userId)
                   or (:departmentAccess = true and m.departmentId in :departmentIds)
                   or exists (select g.id from PatientAccessGrant g where g.patientId = m.patientId
                              and g.granteeUserId = :userId and g.revokedAt is null
                              and g.validFrom <= :now and g.validUntil > :now))
            """)
    Optional<MedicalRecord> findAccessibleById(
            @Param("id") long id, @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds, @Param("now") Instant now);

    @Query("""
            select m from MedicalRecord m where m.id = :id and m.deleted = false
              and (:allAccess = true or (:selfAccess = true and m.ownerId = :userId)
                   or (:departmentAccess = true and m.departmentId in :departmentIds))
            """)
    Optional<MedicalRecord> findWritableById(
            @Param("id") long id, @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds);
}
