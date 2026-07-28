UPDATE user_account
SET status = 'LOCKED_INITIAL'
WHERE tenant_id = 1
  AND user_id IN (1001, 1002, 1003)
  AND must_change_password = TRUE;
