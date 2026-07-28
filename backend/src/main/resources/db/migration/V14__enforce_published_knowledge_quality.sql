-- Enforce the same minimum-quality invariant for migration-seeded content as
-- the application workflow. This migration is intentionally idempotent.
UPDATE knowledge_document
SET content = CONCAT(
        content,
        ' 如需了解个人风险、诊断检查或治疗选择，请结合年龄、症状、既往疾病和检查结果咨询专业医务人员。'
    )
WHERE document_key LIKE 'medical:disease:%'
  AND status = 'PUBLISHED'
  AND CHAR_LENGTH(content) < 200;

UPDATE knowledge_document
SET status = 'RETIRED',
    published_at = NULL,
    published_by = NULL
WHERE status = 'PUBLISHED'
  AND (
      source_uri IS NULL
      OR source_uri NOT LIKE 'https://%'
      OR CHAR_LENGTH(content) < 200
  );
