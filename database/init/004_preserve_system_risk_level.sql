BEGIN;

ALTER TABLE risk_assessments
    ADD COLUMN IF NOT EXISTS system_level risk_level;

UPDATE risk_assessments
SET system_level = level
WHERE system_level IS NULL;

ALTER TABLE risk_assessments
    ALTER COLUMN system_level SET NOT NULL;

COMMIT;
