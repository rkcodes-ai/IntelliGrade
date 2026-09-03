"""ExamSession — one student's attempt at an Exam (Module 04 Assessment Domain)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExamSession(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One student's attempt at an `Exam` — a student has exactly one session
    per exam, enforced by the `(exam_id, student_user_id)` unique
    constraint (and re-checked, with a clean 409, at the service layer
    before it would otherwise surface as a raw integrity error — see
    `ExamSessionService.create`).

    `exam_id` is a raw FK column only (no `relationship()`) — `Exam` is a
    same-wave sibling model (`app/models/exam.py`) — with
    `ondelete="CASCADE"` (a session is meaningless without its exam).
    `student_user_id` points at `app/models/user.py` with
    `ondelete="RESTRICT"` — a student account must not be deletable while
    exam session history still references it. `status` is a plain string
    (`Literal["not_started", "in_progress", "submitted", "evaluated",
    "absent"]` at the Pydantic schema layer), no DB `CHECK` constraint,
    same idiom as Module 03's `AcademicYear.status`.
    """

    __tablename__ = "exam_sessions"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_user_id", name="uq_exam_session_exam_student"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExamSession id={self.id} exam_id={self.exam_id}>"
