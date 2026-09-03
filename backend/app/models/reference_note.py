"""ReferenceNote — a free-form grading note attached to an AnswerKey (Module 04)."""

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ReferenceNote(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A free-form grading note attached to an `AnswerKey` — e.g. a teacher's
    reminder about a common misconception to watch for. `note_type`
    defaults to `"teacher_note"`; `"ai_note"` is a category placeholder per
    ADR-024 for future AI-generated notes — no code writes one yet.
    Multiple notes per answer key are allowed — there is intentionally no
    uniqueness constraint. `answer_key_id` is a raw column only (no
    `relationship()`) and uses `ondelete="CASCADE"`: a reference note is
    meaningless once its answer key is gone.
    """

    __tablename__ = "reference_notes"

    answer_key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(20), nullable=False, default="teacher_note")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReferenceNote id={self.id} answer_key_id={self.answer_key_id}>"
