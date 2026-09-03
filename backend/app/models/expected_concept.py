"""ExpectedConcept — a concept a grader expects a correct answer to demonstrate (Module 04)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExpectedConcept(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A concept expected to be demonstrated in a correct answer, attached to
    exactly one of an `AnswerKey` (`answer_key_id`) or a `RubricCriterion`
    (`rubric_criterion_id`) — never both, never neither. Same validation
    idiom as `ExpectedKeyword` (see that model's docstring): enforced at the
    service layer, not the database. Both FKs cascade: a concept tied to a
    deleted answer key or criterion is meaningless.
    """

    __tablename__ = "expected_concepts"

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
    concept_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExpectedConcept id={self.id} concept_name={self.concept_name!r}>"
