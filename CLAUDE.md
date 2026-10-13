# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

EduGuard is a behavior analysis and scaffolded intervention system for student-AI learning interactions. It classifies how students use AI (not just what AI answers), assesses risk of shallow learning, and provides scaffolded feedback. A teacher dashboard enables human-in-the-loop review of system judgments.

- **Frontend**: React 19 + TypeScript + Ant Design 5 + ECharts (Vite, pnpm)
- **Backend**: FastAPI + SQLAlchemy 2 + Pydantic (Python 3.12, `.venv`)
- **Database**: SQLite for local dev, PostgreSQL 17 for production (Docker)
- **LLM**: OpenAI-compatible API (DeepSeek by default); gracefully degrades to rule-based classification when unavailable

## Commands

### Quick start (all-in-one)

```powershell
.\start-dev.ps1
```

Starts PostgreSQL + Adminer containers, FastAPI backend, and Vite frontend. Requires `.env` configured and virtual environment + `pnpm install` completed first.

### Backend

```powershell
# Install dependencies
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

# Run dev server (SQLite by default)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
# From backend/ directory:
cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# Run with PostgreSQL (Docker must be running)
docker compose up -d postgres adminer
.\scripts\start_backend_postgres.ps1

# Run all tests
cd backend; ..\.venv\Scripts\python.exe -m pytest

# Alembic (from backend/ directory)
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "change"
..\.venv\Scripts\python.exe -m alembic upgrade head
```

### Frontend

```powershell
cd frontend
pnpm install
pnpm dev        # http://localhost:5173
pnpm build      # production build
pnpm test       # vitest run
```

### Docker Compose (full stack)

```powershell
docker compose up --build
```

### Demo accounts

- Teacher: `teacher` / `teacher123`
- Student: `student` / `student123`

### StudyChat data pipeline

```powershell
# Import (idempotent, SHA-256 anonymized)
.\.venv\Scripts\python.exe scripts\import_studychat.py data\raw\studychat\dialogues.jsonl --source-version v1.1

# Generate 300-sample stratified review set
.\.venv\Scripts\python.exe scripts\prepare_studychat_review.py data\raw\studychat\dialogues.jsonl --output data\processed\studychat_review_300.jsonl --size 300

# Run rule classifier on reviewed data
.\.venv\Scripts\python.exe scripts\predict_studychat_rules.py data\processed\studychat_review_300_reviewed.jsonl --output data\processed\studychat_rules_300.jsonl

# Evaluate
.\.venv\Scripts\python.exe scripts\evaluate_behavior.py data\processed\studychat_rules_300.jsonl --output data\processed\studychat_rules_evaluation_300.json
```

## Architecture

### Core pipeline (student sends a message)

```
POST /api/conversations/{id}/messages
  │
  ├─ 1. Behavior Classification (analysis.py)
  │     Try LLM (OpenAI-compatible JSON output) → fallback to regex rules
  │     Labels: concept_understanding, answer_seeking, debugging_help,
  │             task_clarification, reflection_verification
  │
  ├─ 2. Risk Scoring (risk.py) — purely rule-based, weighted evidence
  │     Positive evidence: explicit_answer_request (+30), repeated (+20),
  │                        missing_attempt (+15), submission_ready (+20)
  │     Negative evidence: personal_attempt (-10), reflection (-15)
  │     Levels: <30 low, <60 medium, ≥60 high
  │
  ├─ 3. Scaffold Strategy (intervention.py)
  │     High risk → guided_questions (no direct answer)
  │     Debugging → debugging_scaffold
  │     Reflection → verification_prompt
  │     Default → concept_prompt
  │
  └─ 4. Tutor Reply (tutor.py) → LLM-generated or hardcoded Chinese fallback

Orchestrated by run_eduguard_tutor() in eduguard_tutor.py
```

### Backend structure

```
backend/app/
  main.py          FastAPI app factory, CORS, lifespan (create_all + seed)
  config.py        Pydantic BaseSettings, reads .env
  db.py            SQLAlchemy engine/session/Base (SQLite check_same_thread=False)
  models.py        13 ORM models (User, Conversation, Message, BehaviorAnalysis,
                   RiskAssessment, RiskEvidence, ScaffoldIntervention, TeacherReview, etc.)
  schemas.py       All Pydantic request/response schemas
  api.py           Single APIRouter with ALL endpoints (~35 routes)
  auth.py          Custom JWT (HMAC-SHA256), PBKDF2 password hashing, role guards
  services/
    analysis.py         Two-tier classifier (LLM + rule fallback)
    risk.py             Weighted evidence scoring
    intervention.py     Strategy selection
    tutor.py            LLM reply generation
    eduguard_tutor.py   Pipeline orchestrator (returns TutorDecision)
    seed.py             Demo data seeder (idempotent, runs on startup)
```

### Key design decisions

- **Monolithic router**: All endpoints in `api.py` — no sub-routers. Routes namespaced by path prefix (`/teacher/...`, `/student/...`).
- **No Alembic migrations in use**: `Base.metadata.create_all()` on startup. Alembic is configured but `versions/` is empty. DB schema changes are applied manually via numbered SQL scripts in `database/init/`.
- **Single-table SQLite for dev**: Default `DATABASE_URL` is SQLite. PostgreSQL used via Docker.
- **LLM is optional**: Leave `LLM_API_KEY` empty and the system uses deterministic regex rules for behavior classification. Risk scoring is always rule-based.
- **Custom auth**: No third-party library. JWT creation/verification and password hashing are hand-rolled.
- **No frontend router**: Navigation is state-driven (`useState` for `view`), not URL-based. Auth persisted to `localStorage`.
- **EduGuard Tutor** is an orchestration layer (not a fine-tuned model) that chains analysis → risk → strategy → reply generation, recording full decision trace for teacher review.

### Database migration scripts (for existing Docker volumes)

Numbered SQL files in `database/init/` execute alphabetically at container init. If a data volume predates a migration, apply manually:

```powershell
Get-Content .\database\init\00X_script.sql -Raw | docker exec -i eduguard-postgres psql -U eduguard -d eduguard
```

Script `006` performs a data migration merging duplicate conversations per student+task pair.
