BEGIN;

CREATE TABLE IF NOT EXISTS import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL,
    source_version VARCHAR(30) NOT NULL DEFAULT 'unknown',
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    records_seen INTEGER NOT NULL DEFAULT 0,
    records_created INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'eduguard',
    ADD COLUMN IF NOT EXISTS external_record_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS import_batch_id UUID REFERENCES import_batches(id);

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'eduguard',
    ADD COLUMN IF NOT EXISTS external_record_id VARCHAR(255);

ALTER TABLE behavior_analyses
    ADD COLUMN IF NOT EXISTS evidence_text TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE risk_assessments
    ADD COLUMN IF NOT EXISTS trigger_message_id UUID REFERENCES messages(id),
    ADD COLUMN IF NOT EXISTS review_status VARCHAR(30) NOT NULL DEFAULT 'recorded';

CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_source_external
    ON conversations (source, external_record_id)
    WHERE external_record_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_message_source_external
    ON messages (source, external_record_id)
    WHERE external_record_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_import_batches_source
    ON import_batches (source, created_at DESC);

COMMIT;
