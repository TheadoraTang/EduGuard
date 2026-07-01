BEGIN;

ALTER TABLE risk_evidences
    DROP CONSTRAINT IF EXISTS risk_evidences_weight_check;

ALTER TABLE risk_evidences
    ADD CONSTRAINT risk_evidences_weight_check
    CHECK (weight BETWEEN -100 AND 100);

COMMIT;
