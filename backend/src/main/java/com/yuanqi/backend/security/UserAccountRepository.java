package com.yuanqi.backend.security;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserAccountRepository extends JpaRepository<UserAccount, Long> {
    Optional<UserAccount> findByTenantIdAndUserId(long tenantId, long userId);
    List<UserAccount> findAllByStatusAndMustChangePasswordTrue(String status);
}
