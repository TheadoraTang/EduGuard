BEGIN;

CREATE TABLE IF NOT EXISTS assignment_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES learning_tasks(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    content_type VARCHAR(150) NOT NULL DEFAULT 'application/octet-stream',
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    content BYTEA NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_submission_student_task UNIQUE (student_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_assignment_submissions_student_id
    ON assignment_submissions (student_id);
CREATE INDEX IF NOT EXISTS idx_assignment_submissions_task_id
    ON assignment_submissions (task_id);

DO $$
DECLARE
    group_row RECORD;
BEGIN
    FOR group_row IN
        SELECT
            student_id,
            task_id,
            (ARRAY_AGG(id ORDER BY started_at, id))[1] AS canonical_id,
            ARRAY_AGG(id ORDER BY started_at, id) AS conversation_ids
        FROM conversations
        WHERE source = 'eduguard'
        GROUP BY student_id, task_id
        HAVING COUNT(*) > 1
    LOOP
        WITH ordered_messages AS (
            SELECT
                m.id,
                ROW_NUMBER() OVER (
                    ORDER BY c.started_at, m.sequence_number, m.created_at, m.id
                ) AS new_sequence
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.conversation_id = ANY(group_row.conversation_ids)
        )
        UPDATE messages m
        SET sequence_number = 1000000 + ordered_messages.new_sequence
        FROM ordered_messages
        WHERE m.id = ordered_messages.id;

        UPDATE messages
        SET conversation_id = group_row.canonical_id
        WHERE conversation_id = ANY(group_row.conversation_ids)
          AND conversation_id <> group_row.canonical_id;

        WITH resequenced_messages AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    ORDER BY sequence_number, created_at, id
                ) AS new_sequence
            FROM messages
            WHERE conversation_id = group_row.canonical_id
        )
        UPDATE messages m
        SET sequence_number = resequenced_messages.new_sequence
        FROM resequenced_messages
        WHERE m.id = resequenced_messages.id;

        UPDATE risk_assessments
        SET conversation_id = group_row.canonical_id
        WHERE conversation_id = ANY(group_row.conversation_ids)
          AND conversation_id <> group_row.canonical_id;

        UPDATE scaffold_interventions
        SET conversation_id = group_row.canonical_id
        WHERE conversation_id = ANY(group_row.conversation_ids)
          AND conversation_id <> group_row.canonical_id;

        UPDATE student_reflections
        SET conversation_id = group_row.canonical_id
        WHERE conversation_id = ANY(group_row.conversation_ids)
          AND conversation_id <> group_row.canonical_id;

        DELETE FROM conversations
        WHERE id = ANY(group_row.conversation_ids)
          AND id <> group_row.canonical_id;
    END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_eduguard_conversation_student_task
    ON conversations (student_id, task_id)
    WHERE source = 'eduguard';

COMMIT;
