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
