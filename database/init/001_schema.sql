BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('student', 'teacher', 'admin');
CREATE TYPE message_sender AS ENUM ('student', 'assistant', 'system');
CREATE TYPE analysis_method AS ENUM ('rule', 'llm', 'ml', 'manual');
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high');
CREATE TYPE review_result AS ENUM ('confirmed', 'modified', 'rejected');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    real_name VARCHAR(100) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE class_members (
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (class_id, student_id)
);

CREATE TABLE learning_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    knowledge_points JSONB NOT NULL DEFAULT '[]'::JSONB,
    difficulty SMALLINT CHECK (difficulty BETWEEN 1 AND 5),
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES learning_tasks(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE assignment_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES learning_tasks(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    content_type VARCHAR(150) NOT NULL DEFAULT 'application/octet-stream',
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    content BYTEA NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, task_id)
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender message_sender NOT NULL,
    content TEXT NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (conversation_id, sequence_number)
);

CREATE TABLE behavior_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    behavior_type VARCHAR(50) NOT NULL,
    confidence NUMERIC(5, 4) CHECK (confidence BETWEEN 0 AND 1),
    method analysis_method NOT NULL,
    explanation TEXT NOT NULL,
    model_name VARCHAR(100),
    raw_result JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    system_level risk_level NOT NULL,
    level risk_level NOT NULL,
    score NUMERIC(5, 2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    reasons JSONB NOT NULL DEFAULT '[]'::JSONB,
    assessment_version VARCHAR(30) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_evidences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_assessment_id UUID NOT NULL
        REFERENCES risk_assessments(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    evidence_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    weight NUMERIC(5, 2) CHECK (weight BETWEEN -100 AND 100),
    evidence_data JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scaffold_interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    trigger_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    intervention_level SMALLINT NOT NULL CHECK (intervention_level BETWEEN 1 AND 5),
    strategy_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    generated_by VARCHAR(30) NOT NULL DEFAULT 'system',
    student_response JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE student_reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teacher_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_assessment_id UUID NOT NULL
        REFERENCES risk_assessments(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    result review_result NOT NULL,
    revised_risk_level risk_level,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (result = 'modified' AND revised_risk_level IS NOT NULL)
        OR result <> 'modified'
    )
);

CREATE INDEX idx_classes_teacher_id
    ON classes (teacher_id);
CREATE INDEX idx_class_members_student_id
    ON class_members (student_id);
CREATE INDEX idx_learning_tasks_class_id
    ON learning_tasks (class_id);
CREATE INDEX idx_conversations_student_started
    ON conversations (student_id, started_at DESC);
CREATE INDEX idx_conversations_task_id
    ON conversations (task_id);
CREATE INDEX idx_assignment_submissions_student_id
    ON assignment_submissions (student_id);
CREATE INDEX idx_assignment_submissions_task_id
    ON assignment_submissions (task_id);
CREATE INDEX idx_messages_conversation_created
    ON messages (conversation_id, created_at);
CREATE INDEX idx_behavior_analyses_message_id
    ON behavior_analyses (message_id);
CREATE INDEX idx_behavior_analyses_type
    ON behavior_analyses (behavior_type);
CREATE INDEX idx_risk_assessments_conversation_created
    ON risk_assessments (conversation_id, created_at DESC);
CREATE INDEX idx_risk_assessments_level
    ON risk_assessments (level);
CREATE INDEX idx_risk_evidences_assessment_id
    ON risk_evidences (risk_assessment_id);
CREATE INDEX idx_scaffold_interventions_conversation_id
    ON scaffold_interventions (conversation_id);
CREATE INDEX idx_student_reflections_student_id
    ON student_reflections (student_id);
CREATE INDEX idx_teacher_reviews_assessment_id
    ON teacher_reviews (risk_assessment_id);
CREATE INDEX idx_messages_metadata_gin
    ON messages USING GIN (metadata);
CREATE INDEX idx_learning_tasks_knowledge_points_gin
    ON learning_tasks USING GIN (knowledge_points);

COMMIT;
