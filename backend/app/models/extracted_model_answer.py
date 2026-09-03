"""ExtractedModelAnswer — one OCR/AI-extracted model answer from a
model_answer-type OfficialExamDocument, awaiting/holding teacher
verification (Module 06). See ADR-035/ADR-037."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractedModelAnswer(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One model answer extracted from a `document_type="model_answer"`
    `OfficialExamDocument`. `question_number` is a plain join key back to
    `ExtractedQuestion` (matched at the service layer against the sibling
    `question_paper`-type document for the same `Exam` — not a hard FK,
    since the two documents are uploaded and OCR'd independently and
    either may arrive first).

    `answer_text` is mutable (teacher-editable during verification);
    `raw_ocr_text` is the immutable original extraction. `linked_answer_key_id`
    is a nullable, optional FK into Module 04's `answer_keys.id`
    (`ondelete="SET NULL"`) — same "never required by evaluation" rule as
    `ExtractedQuestion.linked_question_id`, per ADR-037.
    """

    __tablename__ = "extracted_model_answers"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "question_number", name="uq_extracted_model_answer_document_number"
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("official_exam_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_answer_key_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    question_number: Mapped[str] = mapped_column(String(20), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExtractedModelAnswer id={self.id} question_number={self.question_number!r}>"
