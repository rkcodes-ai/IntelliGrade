"""QuestionVersion — append-only snapshot history for `Question` (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionVersion(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An immutable snapshot of a `Question`'s graded content, taken on demand
    via `POST /api/v1/questions/{question_id}/versions`
    (`QuestionVersionService.create_snapshot`) — never edited after
    creation, only ever soft-deleted/restored for consistency with the rest
    of the codebase.

    `version_number` is unique per `question_id` and assigned as
    `max(existing version_number for this question) + 1` (1 for the first
    snapshot) by `QuestionVersionRepository.get_next_version_number`,
    independent of `Question.current_version` (the cheap live counter from
    `VersionCounterMixin`) — see `QuestionVersionService.create_snapshot`'s
    docstring for why.

    `question_text`/`marks`/`difficulty_level_id` are snapshots copied from
    the live `Question` row at the moment this version was created, not
    live references — that is the entire point of a history table.
    """

    __tablename__ = "question_versions"
    __table_args__ = (
        UniqueConstraint(
            "question_id", "version_number", name="uq_question_version_question_version_number"
        ),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    difficulty_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("difficulty_levels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<QuestionVersion id={self.id} question_id={self.question_id} "
            f"version_number={self.version_number}>"
        )
