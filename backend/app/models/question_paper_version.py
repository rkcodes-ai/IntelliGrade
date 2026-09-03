"""QuestionPaperVersion — append-only snapshot history for a QuestionPaper (Module 04)."""

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionPaperVersion(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    An append-only snapshot of a `QuestionPaper`'s scalar fields at a point
    in time, taken via `POST /api/v1/question-papers/{id}/versions` (see
    `app/api/v1/endpoints/question_papers.py`). `question_paper_id` uses
    `ondelete="CASCADE"` — history is meaningless without its parent paper.
    `(question_paper_id, version_number)` is unique; `version_number` is
    computed by the service as the parent's current max + 1 (or 1 for the
    first snapshot) — same pattern as the sibling `QuestionVersion` table
    built alongside `Question` in this wave. `snapshot` intentionally only
    captures the parent `QuestionPaper`'s own scalar fields (name,
    total_marks, approval_status, ...) as a plain JSON dict — child
    sections/question mappings are out of this wave's scope and are not
    snapshotted. `changed_by` is nullable (system/migration-seeded rows
    have no human actor) and uses `ondelete="SET NULL"`.
    """

    __tablename__ = "question_paper_versions"
    __table_args__ = (
        UniqueConstraint(
            "question_paper_id", "version_number", name="uq_question_paper_version_number"
        ),
    )

    question_paper_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_papers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<QuestionPaperVersion id={self.id} question_paper_id={self.question_paper_id} "
            f"version_number={self.version_number}>"
        )
