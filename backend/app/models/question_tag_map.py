"""QuestionTagMap — lightweight junction table between `Question` and `QuestionTag` (Module 04)."""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class QuestionTagMap(UUIDPrimaryKeyMixin, InstitutionOwnedMixin, TimestampMixin, Base):
    """
    Maps a `Question` to a `QuestionTag` (a sibling Module 04 lookup table
    built in the same wave, `app/models/question_tag.py`, referenced here
    only by FK string — see `app/models/question.py`'s docstring for why).

    Deliberately lightweight: only `UUIDPrimaryKeyMixin`, `InstitutionOwnedMixin`,
    `TimestampMixin`, `Base` — no `AuditActorMixin`/`SoftDeleteMixin`, mirroring
    Module 03's `UserInstitution` precedent (`app/models/user_institution.py`):
    a tag mapping either exists or it doesn't, so there is nothing to
    soft-delete and no separate "who edited this row" to track beyond when
    it was created.
    """

    __tablename__ = "question_tag_maps"
    __table_args__ = (
        UniqueConstraint("question_id", "tag_id", name="uq_question_tag_map_question_tag"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionTagMap question_id={self.question_id} tag_id={self.tag_id}>"
