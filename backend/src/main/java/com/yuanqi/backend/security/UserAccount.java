package com.yuanqi.backend.security;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "user_account")
public class UserAccount {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "tenant_id")
    private long tenantId;
    @Column(name = "user_id")
    private long userId;
    @Column(name = "password_hash")
    private String passwordHash;
    @Column(name = "must_change_password")
    private boolean mustChangePassword;
    private String status;

    protected UserAccount() {}

    public long getUserId() { return userId; }
    public String getPasswordHash() { return passwordHash; }
    public boolean isMustChangePassword() { return mustChangePassword; }
    public String getStatus() { return status; }

    public void changePassword(String encodedPassword) {
        passwordHash = encodedPassword;
        mustChangePassword = false;
    }

    public void activateWithInitialPassword(String encodedPassword) {
        passwordHash = encodedPassword;
        mustChangePassword = true;
        status = "ACTIVE";
    }
}
