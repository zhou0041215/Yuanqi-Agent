package com.yuanqi.backend.security;

import com.yuanqi.backend.common.exception.BusinessException;
import org.springframework.stereotype.Component;

@Component
public class RowScopeGuard {

    public void assertAssignable(UserContext user, long ownerId, long departmentId) {
        if (user.hasAllAccess()) {
            return;
        }
        if (!user.departmentIds().contains(departmentId)) {
            throw BusinessException.forbidden("The target department is outside the current data scope");
        }
        if (user.hasSelfAccess() && ownerId != user.userId()) {
            throw BusinessException.forbidden("SELF scope cannot assign the resource to another owner");
        }
    }
}
