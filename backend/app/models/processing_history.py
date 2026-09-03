"""ProcessingHistory — append-only per-stage transition log for an
AnswerScript's pipeline (Module 05)."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ProcessingHistory(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One append-only record of a single pipeline-stage transition (e.g.
    `"upload"` -> `"validation"` -> `"storage"` -> `"preprocessing"` ->
    `"ocr"` -> `"structuring"`) for one `AnswerScript`.

    `answer_script_id` is a raw FK column only (no `relationship()`) --
    `AnswerScript` is a sibling model built directly in this same module
    (not by this delegation), `ondelete="CASCADE"`. Per ADR-030, the
    pipeline's own automatic stage transitions are logged here rather than
    in `AuditLog` (reserved for human-initiated actions) -- rows are
    written internally by pipeline/task code via
    `ProcessingHistoryService.record()`, never through an HTTP route: this
    entity has no create/update/delete endpoint at all (see
    `app/api/v1/endpoints/processing_history.py`).
    """

    __tablename__ = "processing_histories"

    answer_script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_scripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False, default="system")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProcessingHistory id={self.id} "
            f"answer_script_id={self.answer_script_id} stage={self.stage}>"
        )
