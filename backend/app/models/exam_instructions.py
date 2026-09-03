"""ExamInstructions — an ordered instruction block shown to candidates of an Exam.

Module 04 Assessment Domain.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExamInstructions(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One block of instructions text for an `Exam` (e.g. "Bring your ID card",
    "No calculators allowed"). Multiple instruction blocks per exam are
    allowed — there is no unique constraint — ordered for display by
    `display_order` (ascending, smallest first).

    `exam_id` is a raw FK column only (no `relationship()`) — `Exam` is a
    same-wave sibling model (`app/models/exam.py`) built by this same task.
    `ondelete="CASCADE"` because an instruction block is meaningless without
    its parent exam.
    """

    __tablename__ = "exam_instructions"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instructions_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExamInstructions id={self.id} exam_id={self.exam_id}>"
