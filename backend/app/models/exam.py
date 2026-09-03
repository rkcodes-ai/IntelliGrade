"""Exam — a scheduled sitting of an Assessment for a Section (Module 04 Assessment Domain)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Exam(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    Base,
):
    """
    A concrete sitting of an `Assessment` for one `Section` on a given date
    (e.g. "Midterm Exam — Data Structures, Section A, on 2026-08-10").

    Both `assessment_id` and `section_id` are raw FK columns only (no
    `relationship()`), matching every other Module 03/04 cross-table
    reference. Both use `ondelete="CASCADE"` — an exam is meaningless
    without its parent assessment or section. No unique constraint: a
    subject/section may legitimately have more than one exam sitting (e.g.
    a re-exam), so uniqueness is intentionally not enforced here.
    `current_version` (via `VersionCounterMixin`) is bumped by
    `ExamService.update` on any content-changing edit.
    """

    __tablename__ = "exams"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Exam id={self.id} name={self.name!r}>"
