"""AlternativeAnswer — an accepted alternative answer for an AnswerKey (Module 04)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AlternativeAnswer(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An alternative acceptable answer for an `AnswerKey`. Multiple
    alternatives per answer key are allowed — there is intentionally no
    uniqueness constraint. `is_exact_match` distinguishes an alternative
    that must match verbatim from one that only needs to match
    semantically; the actual matching logic is out of scope for this
    entity — it is a plain boolean flag for a future evaluation feature to
    consume. `answer_key_id` is a raw column only (no `relationship()`)
    and uses `ondelete="CASCADE"`: an alternative answer is meaningless
    once its answer key is gone.
    """

    __tablename__ = "alternative_answers"

    answer_key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_exact_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AlternativeAnswer id={self.id} answer_key_id={self.answer_key_id}>"
