"""ExtractedQuestion — one OCR/AI-extracted question from a
question_paper-type OfficialExamDocument, awaiting/holding teacher
verification (Module 06). See ADR-035/ADR-037."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractedQuestion(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One question extracted from a `document_type="question_paper"`
    `OfficialExamDocument`. `question_text` is **mutable** — it starts as
    the OCR/AI-extracted text and is overwritten in place when a teacher
    edits/confirms it during verification; `raw_ocr_text` is the
    immutable original extraction, kept for reference/audit even after
    `question_text` has been edited.

    `linked_question_id` is a **nullable, optional** FK into Module 04's
    `questions.id` bank (`ondelete="SET NULL"`) — per ADR-037, evaluation
    never requires this to be populated; it exists only for institutions
    that deliberately choose to promote a verified question into the
    reusable bank as a separate action.

    Unique on `(document_id, question_number)` — one row per question
    number per document.
    """

    __tablename__ = "extracted_questions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "question_number", name="uq_extracted_question_document_number"
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("official_exam_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    question_number: Mapped[str] = mapped_column(String(20), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    final_marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExtractedQuestion id={self.id} question_number={self.question_number!r}>"
