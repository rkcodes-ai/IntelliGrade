# syntax=docker/dockerfile:1
#
# Module 08 production-hardening pass: split build-time and run-time system
# packages (smaller, lower-attack-surface production/worker images — no
# compiler toolchain shipped at runtime) and add the `tesseract-ocr` system
# binary, which was missing from every prior image. `pytesseract` (Module
# 05) is a thin wrapper around that binary — without it, `TesseractProvider`
# fails at OCR time in any real deployment even though the Python package
# imports fine. See `KNOWN_LIMITATIONS.md` for why this was never caught by
# CI (no Docker daemon in the dev sandbox that built Modules 01-07; `docker
# build`/a real container run is required to catch a missing native
# dependency like this).

# ============================================================
# Runtime base — packages every target below needs at RUN time only
# ============================================================
FROM python:3.14-slim AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
        tesseract-ocr \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Build base — adds the compiler toolchain, used only to install Python
# packages; never copied into a runtime image below.
# ============================================================
FROM runtime-base AS build-base

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Dependencies (production set only)
# ============================================================
FROM build-base AS deps

COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install -e .

# ============================================================
# Development image (hot reload, includes dev/test tooling)
# ============================================================
FROM deps AS development

RUN pip install -e ".[dev]"
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================
# Production image — API server
# ============================================================
FROM runtime-base AS production

COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /tmp/intelligrade-uploads && chown -R appuser:appuser /app /tmp/intelligrade-uploads
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ============================================================
# Worker image — Celery worker (Modules 05/06/07's 3 real tasks:
# ocr.process_answer_script, official_document.process, report.generate)
# ============================================================
FROM runtime-base AS worker

COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /tmp/intelligrade-uploads && chown -R appuser:appuser /app /tmp/intelligrade-uploads
USER appuser

# No EXPOSE — a worker doesn't serve HTTP. Liveness is checked via
# `celery inspect ping` (see docker-compose.prod.yml), not a port probe.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD celery -A app.tasks.celery_app inspect ping -d celery@$HOSTNAME || exit 1

CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

# No Celery Beat/scheduler target: no periodic/cron-scheduled task exists in
# this codebase yet (all 3 Celery tasks are triggered by a user action, not
# a schedule) — see docs/deployment-guide.md for what would be needed if a
# future module adds one (e.g. scheduled report generation, cleanup jobs).
