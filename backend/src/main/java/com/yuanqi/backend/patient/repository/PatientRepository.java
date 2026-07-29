package com.yuanqi.backend.patient.repository;

import com.yuanqi.backend.patient.domain.Patient;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface PatientRepository extends JpaRepository<Patient, Long> {
    boolean existsByPatientNo(String patientNo);
    List<Patient> findAllByDeletedFalseOrderByNameAsc();
    Optional<Patient> findByIdAndDeletedFalse(long id);

    @Query("""
            select p from Patient p
             where p.deleted = false
               and (:allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds)
                    or exists (select g.id from PatientAccessGrant g
                               where g.patientId = p.id and g.granteeUserId = :userId
                                 and g.revokedAt is null and g.validFrom <= :now and g.validUntil > :now))
               and (:keyword is null or lower(p.name) like lower(concat('%', :keyword, '%'))
                    or lower(p.patientNo) like lower(concat('%', :keyword, '%')))
            """)
    Page<Patient> findAccessible(
            @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds, @Param("now") Instant now,
            @Param("keyword") String keyword, Pageable pageable);

    @Query("""
            select p from Patient p
             where p.id = :id and p.deleted = false
               and (:allAccess = true
                    or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds)
                    or exists (select g.id from PatientAccessGrant g
                               where g.patientId = p.id and g.granteeUserId = :userId
                                 and g.revokedAt is null and g.validFrom <= :now and g.validUntil > :now))
            """)
    Optional<Patient> findAccessibleById(
            @Param("id") long id, @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds, @Param("now") Instant now);

    @Query("""
            select p from Patient p
             where p.id = :id and p.deleted = false
               and (:allAccess = true or (:selfAccess = true and p.ownerId = :userId)
                    or (:departmentAccess = true and p.departmentId in :departmentIds))
            """)
    Optional<Patient> findWritableById(
            @Param("id") long id, @Param("userId") long userId, @Param("allAccess") boolean allAccess,
            @Param("selfAccess") boolean selfAccess, @Param("departmentAccess") boolean departmentAccess,
            @Param("departmentIds") Collection<Long> departmentIds);
}
