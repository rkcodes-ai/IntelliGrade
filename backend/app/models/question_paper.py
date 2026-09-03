"""QuestionPaper — a generated/authored paper for an Assessment (Module 04)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.assessment_base import ApprovalWorkflowMixin, VersionCounterMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionPaper(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    VersionCounterMixin,
    ApprovalWorkflowMixin,
    Base,
):
    """
    A concrete question paper generated/authored for an `Assessment`.

    There is intentionally no separate `status` column: `approval_status`
    (from `ApprovalWorkflowMixin`) already models this entity's full
    lifecycle (draft -> pending_review -> approved/rejected -> archived) —
    see `app/services/question_paper_service.py` for the state-transition
    rules, mirroring `Question`/`app/services/question_service.py` exactly.

    `assessment_id` points at a Module 04 Wave 1 entity (`app/models/
    assessment.py`) and uses `ondelete="CASCADE"` — a paper is meaningless
    without its assessment. `blueprint_id` (same-wave sibling,
    `app/models/question_blueprint.py`) and `template_id` (Wave 1,
    `app/models/question_paper_template.py`) are both optional — a paper
    may be authored freehand without a blueprint or template — and use
    `ondelete="SET NULL"` so deleting either lookup does not cascade-delete
    an already-generated paper, it just detaches the reference.
    `current_version` (via `VersionCounterMixin`) is bumped by
    `QuestionPaperService.update` on any content-changing edit, and is
    also the "which snapshot is current" pointer alongside the append-only
    `QuestionPaperVersion` history table.
    """

    __tablename__ = "question_papers"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_blueprints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_paper_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionPaper id={self.id} approval_status={self.approval_status!r}>"
