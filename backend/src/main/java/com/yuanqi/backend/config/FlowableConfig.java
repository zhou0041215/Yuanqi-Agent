package com.yuanqi.backend.config;

import org.flowable.spring.boot.ProcessEngineConfigurationConfigurer;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class FlowableConfig {

    @Bean
    @ConditionalOnProperty(name = "application.flowable.database-type")
    public ProcessEngineConfigurationConfigurer processEngineDatabaseTypeConfigurer(
            @Value("${application.flowable.database-type}") String databaseType
    ) {
        return configuration -> configuration.setDatabaseType(databaseType);
    }
}
