-- YuanQi acceptance-data cleanup.
-- Run only against a non-production database after automated/manual acceptance.
-- Stable seeded demo accounts and curated knowledge documents are intentionally retained.
START TRANSACTION;

DELETE FROM user_notification
WHERE title LIKE '[ACCEPTANCE]%'
   OR content LIKE '%[ACCEPTANCE]%';

DELETE FROM answer_feedback
WHERE session_id LIKE 'acceptance-%'
   OR turn_id LIKE 'acceptance-%';

DELETE FROM agent_audit_event
WHERE thread_id LIKE 'acceptance-%'
   OR trace_id LIKE 'acceptance-%';

DELETE FROM prescription
WHERE prescription_no LIKE 'AT-%'
   OR prescription_no LIKE 'TEST-%';

DELETE FROM medical_record
WHERE record_no LIKE 'AT-%'
   OR record_no LIKE 'TEST-%';

DELETE FROM patient
WHERE patient_no LIKE 'AT-%'
   OR patient_no LIKE 'TEST-%';

COMMIT;
