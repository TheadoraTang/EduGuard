# EduGuard

EduGuard is a student-AI learning interaction analysis and scaffolded intervention system. It focuses on how students use AI while learning, then gives teachers an explainable evidence chain for review and intervention.

The project is a full-stack demo system: React frontend, FastAPI backend, PostgreSQL/SQLite persistence, behavior analysis, risk assessment, and teacher-in-the-loop review.

## Core Features

- Student workspace for assigned learning tasks and multi-turn AI tutoring.
- Teacher dashboard for classes, students, tasks, risk records, and review decisions.
- Behavior classification with rule fallback, optional ML classifier, and optional OpenAI-compatible LLM classification.
- Explainable risk scoring with behavior labels, evidence items, and scaffolded intervention decisions.
- EduGuard Tutor response generation that avoids directly giving submit-ready answers in high-risk cases.
- Demo accounts and seed data for quick local presentation.
- StudyChat and MathDial data-processing scripts for evaluation and annotation workflows.

## Repository Layout

```text
backend/          FastAPI API, SQLAlchemy models, services, tests, Alembic config
frontend/         React 19 + TypeScript + Ant Design + ECharts UI
database/         PostgreSQL initialization and migration helper SQL
data/demo/        Versioned, sanitized demo data
data/README.md    Data policy and local dataset notes
docs/             Project architecture and annotation guides
docs/coursework/  Assignment brief, proposal, paper drafts, templates, reports
evaluation/       MathTutorBench evaluation helper
prompts/          Behavior-classification prompt templates
scripts/          Data import, evaluation, report, and local startup scripts
```

Local-only directories such as `.venv/`, `node_modules/`, `output/`, `tmp/`, raw datasets, generated datasets, local databases, and IDE files are ignored by Git.

## Requirements

- Python 3.10+; Python 3.12 is recommended for local development.
- Node.js 22+.
- pnpm 11+ for frontend development. `npm` is also used by `start-dev.ps1`.
- Docker Desktop for PostgreSQL/Adminer and full Docker Compose runs.

## Configuration

Copy the environment template before running the system:

```powershell
Copy-Item .env.example .env
```

Important variables:

```dotenv
POSTGRES_DB=eduguard
POSTGRES_USER=eduguard
POSTGRES_PASSWORD=replace_with_a_secure_password
POSTGRES_PORT=5433
BACKEND_PORT=8000
FRONTEND_PORT=5173

DATABASE_URL=sqlite:///./eduguard.db
FRONTEND_ORIGIN=http://localhost:5173

LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
BEHAVIOR_CLASSIFIER_MODE=ml
BEHAVIOR_CLASSIFIER_PATH=data/models/studychat_behavior_tfidf_logreg.joblib
JWT_SECRET=replace_with_a_long_random_secret
```

Leave `LLM_API_KEY` empty to run with deterministic local fallbacks. Fill `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` to use a DeepSeek, OpenAI, Qwen, or other OpenAI-compatible endpoint.

## Quick Start

Create and prepare the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Install frontend dependencies:

```powershell
Set-Location frontend
pnpm install
Set-Location ..
```

Start PostgreSQL/Adminer, the FastAPI backend, and the Vite frontend from the repository root:

```powershell
.\start-dev.ps1
```

Open:

- Frontend: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Adminer: <http://localhost:8080>

Press `Ctrl+C` to stop the frontend and backend. PostgreSQL continues running in Docker so local data is preserved.

## Demo Accounts

- Teacher: `teacher` / `teacher123`
- Student: `student` / `student123`

Change demo passwords and `JWT_SECRET` before any real deployment.

## Manual Local Run

Run only PostgreSQL and Adminer:

```powershell
docker compose up -d postgres adminer
```

Run the backend with SQLite:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Run the backend against Docker PostgreSQL:

```powershell
.\scripts\start_backend_postgres.ps1
```

Run the frontend:

```powershell
Set-Location frontend
pnpm dev
```

## Docker Compose

After `.env` is configured, the whole stack can be started with:

```powershell
docker compose up --build
```

Services:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000/docs>
- Adminer: <http://localhost:8080>
- PostgreSQL container host: `postgres`
- PostgreSQL host port: configured by `POSTGRES_PORT`, default `5433`

## Testing

Backend tests:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
```

Frontend tests:

```powershell
Set-Location frontend
pnpm test
```

Frontend production build:

```powershell
Set-Location frontend
pnpm build
```

## Data Notes

Raw StudyChat and MathDial files should stay outside Git under `data/raw/`. Generated intermediate data belongs under `data/processed/` or `output/`, both ignored by Git. Only sanitized demo samples under `data/demo/` are intended to be versioned.

StudyChat is CC BY 4.0. When using it in reports or papers, cite the StudyChat dataset and paper by McNichols, Ikram, and Lan. Do not treat original StudyChat labels as direct evidence of real student risk without review.

## Coursework Materials

Course-specific materials have been moved out of the repository root:

- `docs/coursework/assignment/`: final assignment requirements.
- `docs/coursework/proposal/`: original project-direction notes.
- `docs/coursework/paper/`: paper drafts and Word templates.
- `docs/coursework/reports/`: experiment narratives, dataset reports, and evaluation summaries.

These files document the academic process behind the project. The runnable system is centered on `backend/`, `frontend/`, `database/`, `data/demo/`, `prompts/`, and `scripts/`.
