"""ModelAnswer — one accepted-answer variant (e.g. a marking band) for an AnswerKey (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ModelAnswer(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A model answer belongs to exactly one `AnswerKey`. Multiple model
    answers per answer key are allowed on purpose (e.g. different marking
    bands, each worth a different share of the total marks) — there is
    intentionally no uniqueness constraint. `answer_key_id` is a raw column
    only (no `relationship()`) and uses `ondelete="CASCADE"`: a model
    answer is meaningless once its answer key is gone.
    """

    __tablename__ = "model_answers"

    answer_key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    marks_allocated: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ModelAnswer id={self.id} answer_key_id={self.answer_key_id}>"
