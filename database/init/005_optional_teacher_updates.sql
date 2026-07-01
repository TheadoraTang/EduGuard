BEGIN;

ALTER TABLE risk_assessments
    ALTER COLUMN review_status SET DEFAULT 'recorded';

UPDATE risk_assessments
SET review_status = 'recorded'
WHERE review_status = 'pending';

COMMIT;
