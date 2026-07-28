package com.yuanqi.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

@EnableJpaAuditing
@SpringBootApplication
public class YuanQiBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(YuanQiBackendApplication.class, args);
    }
}
