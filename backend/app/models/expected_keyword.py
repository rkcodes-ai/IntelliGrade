"""ExpectedKeyword — a keyword a grader (human or AI) expects in a correct answer (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExpectedKeyword(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A keyword expected in a correct answer, attached to exactly one of an
    `AnswerKey` (`answer_key_id`) or a `RubricCriterion`
    (`rubric_criterion_id`) — never both, never neither. Enforced at the
    service layer (`ExpectedKeywordService.create`/`update`), not the
    database, since a portable CHECK constraint can't cleanly express
    "exactly one of two nullable FKs" across SQLite and PostgreSQL. Both FKs
    cascade: a keyword tied to a deleted answer key or criterion is
    meaningless.
    """

    __tablename__ = "expected_keywords"

    answer_key_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_keys.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rubric_criterion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rubric_criteria.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True, default=Decimal("1.0")
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExpectedKeyword id={self.id} keyword={self.keyword!r}>"
