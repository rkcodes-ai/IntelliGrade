"""QuestionApproval — formal approve/reject decision audit trail for `Question` (Module 04)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionApproval(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One row per approve/reject decision made against a `Question` (and,
    optionally, a specific `QuestionVersion` snapshot of it) — the formal
    editorial gate, distinct from informal `QuestionReview` peer feedback.

    Read/audit-trail table: rows are inserted via `QuestionApprovalService`,
    either through its `create()` endpoint-facing method or the flatter
    `record()` convenience wrapper meant for another service to call.
    `QuestionService.approve()`/`reject()` (`app/services/question_service.py`,
    already-merged Wave 1 code, intentionally not modified here) do not yet
    call `record()` to insert a row automatically — wiring that up is a
    follow-up integration step (see `QuestionApprovalService`'s docstring).

    `reviewed_at` mirrors `TimestampMixin.created_at`'s idiom: a DB-level
    `server_default=func.now()`, not set from application code.
    """

    __tablename__ = "question_approvals"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionApproval id={self.id} decision={self.decision!r}>"
