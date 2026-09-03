"""QuestionPaperSection — a named section (e.g. "Section A") within a QuestionPaper."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionPaperSection(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A section (e.g. "Section A") a `QuestionPaper` is divided into.
    Questions are mapped into a section, in order, via
    `QuestionPaperQuestionMapping` (`app/models/question_paper_question_mapping.py`).

    `question_paper_id` is a raw column only (no `relationship()`), pointing
    at a sibling wave's model (`app/models/question_paper.py`) not yet built
    at the time this file was written — see `QuestionPaperSectionService`'s
    local import of `QuestionPaperRepository`. `ondelete="CASCADE"`: a
    section is meaningless without its parent paper.

    `marks_per_question` is a per-section default (e.g. "each question in
    this section is worth 2 marks"); an individual mapping's
    `marks_override` (on `QuestionPaperQuestionMapping`) takes precedence
    over it for that one question.
    """

    __tablename__ = "question_paper_sections"

    question_paper_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_papers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    marks_per_question: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionPaperSection id={self.id} name={self.name!r}>"
