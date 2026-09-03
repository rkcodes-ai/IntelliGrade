"""OCRJob — one queued/running/completed OCR execution attempt against an
AnswerScript (Module 05)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OCRJob(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One OCR execution attempt (`"queued"` -> `"running"` ->
    `"completed"`/`"failed"`/`"cancelled"`) against a single `AnswerScript`.

    `answer_script_id` is a raw FK column only (no `relationship()`) --
    `AnswerScript` is a sibling model built directly in this same module
    (not by this delegation), `ondelete="CASCADE"` (a job is meaningless
    without its parent script). `ocr_provider_id` points at the global
    `OCRProvider` catalog with `ondelete="RESTRICT"` -- a provider must not
    be deletable while job history still references it. `status` is a
    plain string (`Literal["queued", "running", "completed", "failed",
    "cancelled"]` at the Pydantic schema layer), no DB `CHECK` constraint,
    same idiom as `ExamSession.status`.

    `POST /api/v1/ocr-jobs` only persists this row in `"queued"` status --
    it deliberately does not import anything from `app.tasks` or enqueue a
    Celery task itself; that wiring (a `celery_app.send_task(...)` call
    that then populates `celery_task_id`) is added centrally later by
    someone else, once the actual OCR Celery task exists. There is no
    `PATCH`/`DELETE`/restore route -- this is a system-managed job record,
    mutated only via the explicit `POST /{id}/cancel` action (see
    `OCRJobService.cancel`).
    """

    __tablename__ = "ocr_jobs"

    answer_script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_scripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ocr_provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # --- Provider fallback (Six-Provider OCR milestone, Phase 12) ---
    # `ocr_provider_id` above always reflects the provider that actually
    # produced this job's result. `requested_ocr_provider_id` is only
    # populated when that differs from what was originally resolved (a
    # fallback happened) -- NULL is the common case ("ran exactly as
    # requested"), not a second copy of `ocr_provider_id` on every row.
    # `fallback_reason` is the original provider's real error message, so
    # a fallback is always visible/auditable, never silent.
    requested_ocr_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_providers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(155), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OCRJob id={self.id} answer_script_id={self.answer_script_id} status={self.status}>"
        )
