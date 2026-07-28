package com.yuanqi.backend.access.repository;

import com.yuanqi.backend.access.domain.AccessPerson;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AccessPersonRepository extends JpaRepository<AccessPerson, Long> {
    List<AccessPerson> findAllByTenantIdOrderByDisplayNameAsc(long tenantId);

    Optional<AccessPerson> findByTenantIdAndUserId(long tenantId, long userId);
}
