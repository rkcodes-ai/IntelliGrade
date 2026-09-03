# Development Guide

## Prerequisites

- Python 3.13+
- Node.js 20+
- Docker + Docker Compose (recommended path)
- (Optional, for local-without-Docker workflows) PostgreSQL 16, Redis 7

## Fastest path: Docker Compose

```bash
cp .env.example .env
docker compose up -d
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173
- MinIO console: http://localhost:9001

Both `backend` and `frontend` services mount your working tree as a volume
and run in their `development` Dockerfile target, so code changes hot-reload
without rebuilding the image.

## Without Docker

Run Postgres/Redis/MinIO however you like (or `docker compose up -d postgres
redis minio` and run the apps natively), then:

```bash
# Backend
cd backend
py -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Day-to-day loop

1. Create a branch (see [branching-strategy.md](branching-strategy.md)).
2. Make your change.
3. `pre-commit run --all-files` (or let the git hook run it) before
   committing — formats and lints both backend and frontend.
4. Run the relevant test suite (`pytest` / `npm run test`).
5. Commit using [Conventional Commits](git-workflow.md#commit-message-format).
6. Open a PR — CI runs `lint.yml`, `test.yml`, `build.yml`, `docker.yml`
   automatically (see [.github/workflows](../.github/workflows)).

## One-time setup: pre-commit hooks

```bash
pip install pre-commit   # or: pipx install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg   # not required — Husky handles commit-msg
npm install               # installs Husky's commit-msg hook (commitlint)
```

## Adding a new backend dependency

Edit `backend/pyproject.toml` `[project.dependencies]` (or `[project.optional-dependencies].dev`
for dev-only tools), then `pip install -e ".[dev]"` again. Do not hand-edit a
`requirements.txt` — `pyproject.toml` is the single source of truth.

## Adding a new frontend dependency

`npm install <package> --workspace=frontend` from the repo root (keeps the
shared root lockfile in sync).
