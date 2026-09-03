# IntelliGrade Backend

FastAPI + SQLAlchemy 2.x (async) + PostgreSQL + Redis + Celery backend for the
IntelliGrade AI Answer Script Evaluation System.

See [docs/architecture.md](../docs/architecture.md) for the full layering
model. This service is a **modular monolith**: layers are separated (API →
Service → Repository → Model) so domains can later be extracted into
microservices without a rewrite.

## Local development (without Docker)

```bash
cd backend
py -m venv .venv
.venv/Scripts/activate        # .venv\Scripts\Activate.ps1 on PowerShell
pip install -e ".[dev]"
cp .env.example .env          # then edit as needed

uvicorn app.main:app --reload
```

Requires a running PostgreSQL and Redis (see root `docker-compose.yml` to run
just those dependencies: `docker compose up -d postgres redis minio`).

## Common commands

| Task                     | Command                                              |
|---------------------------|------------------------------------------------------|
| Run dev server             | `uvicorn app.main:app --reload`                      |
| Run tests                  | `pytest`                                              |
| Format                     | `black app tests alembic`                             |
| Sort imports                | `isort app tests alembic`                             |
| Lint                        | `ruff check app tests alembic`                        |
| Type check                  | `mypy app`                                            |
| New migration (autogenerate)| `alembic revision --autogenerate -m "message"`        |
| Apply migrations            | `alembic upgrade head`                                 |
| Run Celery worker           | `celery -A app.tasks.celery_app worker --loglevel=info`|

## Layout

```
app/
├── main.py            # application factory / entrypoint
├── core/               # config, logging, security, exceptions, RBAC
├── api/                # routers (health = unversioned; v1/ = versioned)
├── db/                 # SQLAlchemy session/base, Redis client
├── middleware/          # request ID, access logs, security headers, rate limit
├── models/              # ORM models (empty — no business tables yet)
├── schemas/              # Pydantic v2 request/response contracts
├── repositories/          # persistence access layer (generic base only)
├── services/               # business logic layer (generic base only)
├── tasks/                   # Celery app skeleton (no tasks registered)
└── utils/                    # pure helpers
```

## Endpoints available today

- `GET /health` — overall status
- `GET /health/live` — liveness probe
- `GET /health/ready` — readiness probe (checks DB + Redis)
- `GET /health/version` — build/version info
- `GET /docs`, `/redoc`, `/openapi.json` — API docs (disabled in production)

No business endpoints exist yet — see the repo root README for the module roadmap.
