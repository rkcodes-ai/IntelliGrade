"""QuestionTag — a free-form label attached to Questions (no code, unlike its
sibling lookup entities — tags are identified by name only).

Module 04 Assessment Domain.
"""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionTag(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """A question tag belongs to exactly one institution; name is unique per institution."""

    __tablename__ = "question_tags"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_question_tag_institution_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionTag id={self.id} name={self.name!r}>"
