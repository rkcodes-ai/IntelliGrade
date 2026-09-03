"""QuestionBlueprintSection — one distribution row of a QuestionBlueprint (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionBlueprintSection(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    A single row of a `QuestionBlueprint`'s distribution, e.g. "10 easy MCQ
    questions worth 1 mark each". `blueprint_id` points at a same-wave
    sibling (`app/models/question_blueprint.py`) and uses
    `ondelete="CASCADE"` — a section is meaningless without its blueprint.

    The four lookup FKs (`question_category_id`, `difficulty_level_id`,
    `bloom_level_id`, `question_type_id`) are all nullable: a section may
    constrain by any subset of category/difficulty/bloom/type, or leave any
    of them unset to mean "any" for that dimension. Each uses
    `ondelete="RESTRICT"` — a lookup value still referenced by a section
    must not be deletable out from under it, same convention as
    `Question.question_category_id` et al.
    """

    __tablename__ = "question_blueprint_sections"

    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_blueprints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    difficulty_level_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("difficulty_levels.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    bloom_level_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bloom_taxonomy_levels.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    question_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_types.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    number_of_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    marks_per_question: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionBlueprintSection id={self.id} blueprint_id={self.blueprint_id}>"
