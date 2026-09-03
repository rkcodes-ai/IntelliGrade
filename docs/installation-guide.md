# Installation Guide — IntelliGrade v1.0

Two install paths: **Docker Compose** (recommended, fewer moving parts)
and **without Docker** (for active development — hot reload, direct
debugger access). Both are covered below. For deploying to a real
production environment rather than installing locally, see
`docs/deployment-checklist.md` and `docs/production-checklist.md`
instead of this document.

## Prerequisites

| Tool | Docker path | Without-Docker path |
|---|---|---|
| Docker + Docker Compose | Required | Not needed |
| Python 3.13 | Not needed | Required |
| Node.js 20+ | Not needed | Required |
| PostgreSQL 16+ | Not needed (runs in Compose) | Required, running locally |
| Redis 6+ | Not needed (runs in Compose) | Required, running locally |
| MinIO (or S3-compatible storage) | Not needed (runs in Compose) | Required, running locally |
| Tesseract OCR | Bundled in the backend image | Required, installed locally (see below) |

## Path A — Docker Compose (recommended)

```bash
git clone <this-repository>
cd intelligrade
cp .env.example .env
docker compose up -d --build
```

- Backend API docs: <http://localhost:8000/docs>
- Frontend: <http://localhost:5173>
- MinIO console: <http://localhost:9001>

Verify it's healthy:

```bash
curl http://localhost:8000/health/ready
```

Should report `{"status":"ready",...}` once Postgres/Redis are up (may
take a few seconds after `docker compose up`).

Run migrations if this is a fresh database (the dev compose does not
auto-migrate):

```bash
docker compose exec backend alembic upgrade head
```

This is the **local development** Docker stack (`docker-compose.yml`) —
for a real production deployment, use `docker-compose.prod.yml` instead;
see `docs/deployment-checklist.md`.

## Path B — Without Docker

### 1. Install and start PostgreSQL, Redis, and MinIO locally

Use your OS's package manager or official installers. Create a database
and user matching `backend/.env.example`'s defaults (or your own values,
updated in `backend/.env`).

### 2. Install Tesseract OCR

- **Linux/macOS**: install the `tesseract-ocr` package via your package
  manager (e.g. `apt install tesseract-ocr`, `brew install tesseract`).
- **Windows**: install via the official installer or `winget install
  UB-Mannheim.TesseractOCR`, then set `TESSERACT_CMD` in `backend/.env`
  to the installed binary path (e.g.
  `C:\Program Files\Tesseract-OCR\tesseract.exe`).

### 3. Backend setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # edit with your local Postgres/Redis/MinIO values
alembic upgrade head
uvicorn app.main:app --reload
```

Verify: `curl http://localhost:8000/health/ready`

### 4. Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local   # defaults usually work for local dev
npm run dev
```

Verify: open <http://localhost:5173> in a browser.

### 5. (Optional) Celery worker, for background job processing

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
```

Without a running worker, OCR/document-ingestion/report-generation
requests are still accepted but stay `pending` until a worker picks them
up (a deliberate best-effort design — see `docs/ocr-pipeline-guide.md`).

## Verifying the install worked

1. `curl http://localhost:8000/health/ready` → `{"status":"ready",...}`
2. Open the frontend, log in (seed a user first if this is a genuinely
   fresh database — see `docs/development-guide.md` for seeding notes)
3. `curl http://localhost:8000/openapi.json | python -m json.tool | head`
   → should return a real OpenAPI schema

## Something didn't work

See `docs/troubleshooting-guide.md` for common installation problems
(Tesseract not found, database connection refused, port already in use,
etc.).

## Next steps

- Day-to-day development loop: `docs/development-guide.md`
- Running the test suites: `docs/development-guide.md`,
  `TESTING_STATUS.md`
- Setting up your first institution: `docs/administrator-manual.md`
- Deploying to production (this guide covers local install only): see
  `docs/deployment-checklist.md` and `docs/production-checklist.md`.
