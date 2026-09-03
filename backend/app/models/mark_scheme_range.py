"""MarkSchemeRange — one question-range -> marks-per-question row from a
mark_scheme-type OfficialExamDocument (Module 06). See ADR-035.

Represents e.g. "Questions 1-12 = 1 mark" as data, never as hardcoded
application logic — `app.services.mark_scheme_service.expand_mark_scheme_ranges`
turns a verified list of these rows into a per-question maximum-marks map,
supporting any examination pattern rather than one hardcoded scheme.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MarkSchemeRange(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One row of a mark scheme, e.g. `question_range_start="1"`,
    `question_range_end="12"`, `marks_per_question=1.00`. Range bounds are
    stored as strings (not integers) to accommodate alphanumeric question
    numbering (`"1a"`) in the source document, though
    `expand_mark_scheme_ranges()` only supports plain-integer ranges in
    this pass — see that function's docstring for the exact limitation.
    """

    __tablename__ = "mark_scheme_ranges"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("official_exam_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    question_range_start: Mapped[str] = mapped_column(String(20), nullable=False)
    question_range_end: Mapped[str] = mapped_column(String(20), nullable=False)
    marks_per_question: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<MarkSchemeRange id={self.id} "
            f"{self.question_range_start}-{self.question_range_end}={self.marks_per_question}>"
        )
