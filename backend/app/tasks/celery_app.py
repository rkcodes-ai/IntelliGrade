"""
Celery application skeleton.

Redis (already provisioned via Docker Compose) is used as both broker and
result backend. No tasks are registered in Module 01 — future modules add
`@celery_app.task` functions under `app/tasks/` (e.g. `ocr_tasks.py`,
`evaluation_tasks.py`, `notification_tasks.py`) and list their modules in
`include=[...]` below.

Run a worker locally with:
    celery -A app.tasks.celery_app worker --loglevel=info

`app.tasks.redis_resp2_transport` is imported for its side effect (it
registers the `redis2://` kombu transport alias `Settings.
redis_uri_for_db()` uses) — must happen before `Celery(...)` below
resolves `broker`/`backend` into a live connection. See that module's
docstring for why this exists (RESP2 compatibility with any Redis server
older than 6.0 — the OCR Six-Provider milestone's real-infrastructure
verification found the local dev Redis is a 3.0.504 build, which rejects
modern `redis-py`'s default RESP3 handshake attempt outright).
"""

from celery import Celery

import app.tasks.redis_resp2_transport  # noqa: F401 - side-effecting import, see docstring
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "intelligrade",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # Every module that adds a real `@celery_app.task` must be listed here —
    # a standalone `celery worker` process only registers tasks from modules
    # it actually imports; the API process registers tasks fine either way
    # because it imports these modules directly to call `.delay()`, which
    # masked this list being incomplete until Module 08's production-
    # readiness review caught it (a real worker would have raised
    # `NotRegistered` for the two modules that were missing).
    include=[
        "app.tasks.ocr_tasks",  # Module 05
        "app.tasks.official_document_tasks",  # Module 06
        "app.tasks.report_tasks",  # Module 07
        "app.tasks.reference_answer_tasks",  # AI Reference Answer Builder milestone
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    # Bounds how long a worker/producer will keep retrying an unreachable
    # broker before giving up loudly, instead of the client default of
    # retrying indefinitely — a dead Redis instance must produce a clear,
    # timely error (surfaced in logs / to whatever called `.delay()`), never
    # an indefinite hang. `broker_connection_timeout` bounds each individual
    # TCP connect attempt; `broker_connection_max_retries` bounds the total
    # number of attempts across the exponential backoff Celery already does.
    broker_connection_timeout=5,
    broker_connection_max_retries=5,
)
