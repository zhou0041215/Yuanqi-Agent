package com.yuanqi.backend.analytics.dto;

public record DatasetColumn(
        String name,
        String type,
        boolean nullable,
        String description
) {
}
