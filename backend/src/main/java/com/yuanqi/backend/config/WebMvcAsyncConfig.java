package com.yuanqi.backend.config;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.servlet.config.annotation.AsyncSupportConfigurer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebMvcAsyncConfig implements WebMvcConfigurer {
    private final ThreadPoolTaskExecutor agentTaskExecutor;
    private final long timeoutMillis;

    public WebMvcAsyncConfig(
            @Qualifier("agentTaskExecutor") ThreadPoolTaskExecutor agentTaskExecutor
    ) {
        this.agentTaskExecutor = agentTaskExecutor;
        this.timeoutMillis = 600_000L;
    }

    @Override
    public void configureAsyncSupport(AsyncSupportConfigurer configurer) {
        configurer.setTaskExecutor(agentTaskExecutor);
        configurer.setDefaultTimeout(timeoutMillis);
    }
}
