package com.yuanqi.backend.security;

import java.security.SecureRandom;
import java.util.Base64;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@Profile("dev")
public class DevAccountInitializer implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(DevAccountInitializer.class);
    private final UserAccountRepository accounts;
    private final PasswordEncoder encoder;

    public DevAccountInitializer(UserAccountRepository accounts, PasswordEncoder encoder) {
        this.accounts = accounts;
        this.encoder = encoder;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        var locked = accounts.findAllByStatusAndMustChangePasswordTrue("LOCKED_INITIAL");
        if (locked.isEmpty()) return;
        byte[] random = new byte[15];
        new SecureRandom().nextBytes(random);
        String initialPassword = "Yq!" + Base64.getUrlEncoder().withoutPadding().encodeToString(random);
        locked.forEach(account -> account.activateWithInitialPassword(encoder.encode(initialPassword)));
        accounts.saveAll(locked);
        log.warn("DEV ONLY: initial account password for this database is [{}]. Change it at first login.",
                initialPassword);
    }
}
