"""
Assessment Domain (Module 04) shared model mixins.

New file — does not modify `app/models/base.py` or `app/models/academic_base.py`.
Every Assessment Domain table composes `InstitutionOwnedMixin` (imported
from `app.models.academic_base`, not duplicated) for tenancy, exactly like
Module 03 — see ADR-020. This module adds the one genuinely new
cross-cutting concern Module 04 introduces: an approval workflow.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class VersionCounterMixin:
    """
    A cheap `current_version` counter satisfying the blanket "version
    support" requirement for entities that don't have a full history
    table. Incremented by the service layer on each content-changing
    update — see ADR-023. Entities with a real history table (`Question`,
    `QuestionPaper`) also use this as the "which snapshot is current"
    pointer alongside their `*Version` table.
    """

    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ApprovalWorkflowMixin:
    """
    Draft -> pending_review -> approved/rejected -> archived lifecycle,
    shared by every content entity that goes through editorial review
    (see ADR-022). `approval_status` is a plain string, `Literal`-typed at
    the Pydantic schema level — same idiom as Module 03's
    `AcademicYear.status` (no DB CHECK constraint, so new statuses never
    require a migration).
    """

    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
