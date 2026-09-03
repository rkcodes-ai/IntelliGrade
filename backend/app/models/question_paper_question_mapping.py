"""QuestionPaperQuestionMapping — maps a Question into a QuestionPaperSection, in order."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionPaperQuestionMapping(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Places one `Question` into one `QuestionPaperSection`, at a given
    position. `order_index` (a plain column, not a separate table) *is* the
    "Question Ordering" requirement for this wave.

    `question_paper_section_id` is a raw column only (no `relationship()`),
    pointing at a same-wave sibling built by this same agent
    (`app/models/question_paper_section.py`) — `ondelete="CASCADE"`: a
    mapping is meaningless without its section.

    `question_id` points at the real, already-merged `Question`
    (`app/models/question.py`) with `ondelete="RESTRICT"`: a question still
    mapped into a paper must not be deletable out from under it.

    `marks_override`, when set, overrides `Question.marks` for this
    specific paper only (e.g. the question bank says 5 marks, but this
    particular paper awards it 3) — the question's own `marks` column is
    left untouched.
    """

    __tablename__ = "question_paper_question_mappings"
    __table_args__ = (
        UniqueConstraint(
            "question_paper_section_id", "question_id", name="uq_qpqm_section_question"
        ),
    )

    question_paper_section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_paper_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    marks_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<QuestionPaperQuestionMapping id={self.id} "
            f"question_paper_section_id={self.question_paper_section_id} "
            f"question_id={self.question_id}>"
        )
