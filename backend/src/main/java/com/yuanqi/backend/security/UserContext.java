package com.yuanqi.backend.security;

import java.util.Set;

public record UserContext(
        long userId,
        String username,
        DataScopeType dataScope,
        Set<Long> departmentIds
) {
    public UserContext {
        departmentIds = Set.copyOf(departmentIds);
    }

    public boolean hasAllAccess() {
        return dataScope == DataScopeType.ALL;
    }

    public boolean hasDepartmentAccess() {
        return dataScope == DataScopeType.DEPARTMENT;
    }

    public boolean hasSelfAccess() {
        return dataScope == DataScopeType.SELF;
    }
}
