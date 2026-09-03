"""ExamResult — per-`ExamSession` finalization/locking state (Module 07). See ADR-042.

Root entity for Result Finalization/Locking. One row per `ExamSession`,
created lazily by the first finalization action (an exam session with no
finalized result simply has no row here yet — same lazy-creation
precedent as `AnswerEvaluation`, ADR-038). `total_max_marks`/`total_marks`
are snapshots computed at finalization time by summing the session's
`AnswerEvaluation` rows, not a live view — a later answer-evaluation edit
must not silently change an already-finalized total.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExamResult(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One student's finalized/locked result for one `Exam` (via `ExamSession`).

    `status` moves through the validated state machine
    `draft -> under_review -> approved -> locked -> published`, with an
    explicit `unlock` transition back to `draft` gated on a dedicated
    permission (see `app/services/exam_result_service.py`). Unique on
    `exam_session_id` — one result per student sitting.
    """

    __tablename__ = "exam_results"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    total_max_marks: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    total_marks: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    finalized_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unlocked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ExamResult id={self.id} exam_session_id={self.exam_session_id} "
            f"status={self.status!r}>"
        )
