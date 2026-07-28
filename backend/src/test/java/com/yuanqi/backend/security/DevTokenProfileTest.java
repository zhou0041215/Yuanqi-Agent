package com.yuanqi.backend.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.yuanqi.backend.security.dev.DevTokenController;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Profile;

class DevTokenProfileTest {
    @Test
    void developmentTokenControllerIsRestrictedToDevProfile() {
        Profile profile = DevTokenController.class.getAnnotation(Profile.class);
        assertThat(profile).isNotNull();
        assertThat(profile.value()).containsExactly("dev");
    }
}
