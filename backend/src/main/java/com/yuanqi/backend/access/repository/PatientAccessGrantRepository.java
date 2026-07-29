package com.yuanqi.backend.access.repository;

import com.yuanqi.backend.access.domain.PatientAccessGrant;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface PatientAccessGrantRepository extends JpaRepository<PatientAccessGrant, Long> {
    List<PatientAccessGrant> findAllByOrderByCreatedAtDesc();

    Optional<PatientAccessGrant> findById(long id);

    @Query("""
            select count(g) > 0 from PatientAccessGrant g
             where g.patientId = :patientId
               and g.granteeUserId = :granteeUserId
               and g.revokedAt is null
               and g.validUntil > :now
            """)
    boolean existsCurrentGrant(
            @Param("patientId") long patientId,
            @Param("granteeUserId") long granteeUserId,
            @Param("now") Instant now
    );
}
