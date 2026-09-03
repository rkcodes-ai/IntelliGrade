"""
Celery task driving AI Reference Answer generation (AI Reference Answer
Builder milestone). Same shape as `app.tasks.ocr_tasks`/
`app.tasks.official_document_tasks`: a synchronous Celery task bridging
into the async service layer via `asyncio.run(...)`.

`ReferenceAnswerService.generate()` already does all the real work
(precondition checks, provider call, persistence, status transitions,
audit logging) and commits its own state changes -- this task is a thin
wrapper that resolves a fresh DB session and calls it, so `POST /ai-
reference-answers` (Phase 11) doesn't block the HTTP request for
however long the configured AI provider takes to respond (Phase 12: "do
not block HTTP requests unnecessarily for long AI operations").
"""

import asyncio
import uuid

from celery import Task

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services.ai_reference_answer_service import ReferenceAnswerService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


# celery ships no py.typed marker, so mypy sees this decorator as untyped.
@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="ai_reference_answer.generate",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=120,
)
def generate_reference_answer_task(
    self: Task,
    institution_id: str,
    extracted_question_id: str,
    actor_id: str | None,
    *,
    force: bool = False,
) -> None:
    """Entry point enqueued by `POST /ai-reference-answers` (Phase 11)."""
    try:
        asyncio.run(_run_generate(institution_id, extracted_question_id, actor_id, force=force))
    except Exception as exc:  # noqa: BLE001 - Celery retry needs the original exception
        logger.error(
            "ai_reference_answer_generation_task_failed",
            extracted_question_id=extracted_question_id,
            error=str(exc),
        )
        raise self.retry(exc=exc) from exc


async def _run_generate(
    institution_id: str, extracted_question_id: str, actor_id: str | None, *, force: bool
) -> None:
    async with AsyncSessionLocal() as session:
        service = ReferenceAnswerService(session)
        await service.generate(
            uuid.UUID(institution_id),
            uuid.UUID(extracted_question_id),
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            force=force,
        )
        # `ReferenceAnswerService.generate()` only flushes its final
        # success-path state change (the API endpoint commits on its own
        # behalf, see `ai_reference_answers.py`) — this task owns its own
        # session lifecycle, so it must commit explicitly or the completed
        # reference is silently lost when the session closes uncommitted.
        await session.commit()
