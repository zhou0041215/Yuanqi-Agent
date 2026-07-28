-- Demo directory records for local development. These are not production identities.
INSERT INTO access_person
    (tenant_id, user_id, username, display_name, department_id, department_name, role_code, data_scope, status)
VALUES
    (1, 1010, 'yu_ming_demo', '喻明', 10, '内分泌科', 'DEPARTMENT_LEAD', 'DEPARTMENT', 'ACTIVE'),
    (1, 1011, 'he_yuan_demo', '何远', 10, '内分泌科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE'),
    (1, 1012, 'tang_qi_demo', '唐琪', 20, '心内科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE'),
    (1, 1013, 'shen_chuan_demo', '沈川', 30, '呼吸内科', 'DEPARTMENT_LEAD', 'DEPARTMENT', 'ACTIVE'),
    (1, 1014, 'cheng_xue_demo', '程雪', 30, '呼吸内科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE'),
    (1, 1015, 'luo_min_demo', '罗敏', 40, '普外科', 'DEPARTMENT_LEAD', 'DEPARTMENT', 'ACTIVE'),
    (1, 1016, 'xu_yan_demo', '许言', 40, '普外科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE'),
    (1, 1017, 'li_wei_demo', '黎薇', 50, '药学部', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE'),
    (1, 1018, 'yan_qing_demo', '燕青', 60, '检验科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE'),
    (1, 1019, 'han_zhe_demo', '韩哲', 70, '医学影像科', 'CLINICAL_COLLABORATOR', 'SELF', 'ACTIVE');
