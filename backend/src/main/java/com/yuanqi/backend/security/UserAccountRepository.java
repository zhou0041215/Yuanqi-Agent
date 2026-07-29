package com.yuanqi.backend.security;

import java.util.Optional;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserAccountRepository extends JpaRepository<UserAccount, Long> {
    Optional<UserAccount> findByUserId(long userId);
    List<UserAccount> findAllByStatusAndMustChangePasswordTrue(String status);
}
