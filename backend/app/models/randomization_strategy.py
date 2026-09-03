"""RandomizationStrategy — how a QuestionPaper (or one of its sections) randomizes at delivery."""

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RandomizationStrategy(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Describes how questions/options are randomized when a paper is
    delivered: e.g. "none", "shuffle_questions", "shuffle_options", or
    "pick_random_subset" (with `config` carrying strategy-specific
    parameters, e.g. `{"subset_size": 5}`).

    A strategy applies either at the whole-paper level (`question_paper_id`
    set) or at one specific section's level (`question_paper_section_id`
    set) as a more specific override under a paper-level default — both may
    be set simultaneously for that reason, but at least one must be (see
    `RandomizationStrategyService.create`'s validation). Both FKs are raw
    columns only (no `relationship()`), pointing at same-wave sibling
    models (`app/models/question_paper.py`, owned by another agent;
    `app/models/question_paper_section.py`, owned by this agent) —
    `ondelete="CASCADE"` on both: a strategy is meaningless once its target
    paper/section is gone.
    """

    __tablename__ = "randomization_strategies"

    question_paper_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_papers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    question_paper_section_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_paper_sections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    strategy_type: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RandomizationStrategy id={self.id} strategy_type={self.strategy_type!r}>"
