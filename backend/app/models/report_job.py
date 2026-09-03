"""ReportJob — one background report-generation attempt (Module 07). See ADR-045.

Same "system-managed job record" shape as Module 05's `OCRJob`: created
in `"pending"` status, mutated only by the Celery task
(`app/tasks/report_tasks.py`) as it moves through
`pending -> processing -> completed`/`failed`, never via a generic
PATCH/DELETE route.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.academic_base import InstitutionOwnedMixin
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ReportJob(
    UUIDPrimaryKeyMixin,
    InstitutionOwnedMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    One requested report export.

    `report_type` (e.g. `"student"`, `"question_wise"`, `"teacher_review"`,
    `"ai_performance"`, `"institution_summary"`, `"department_summary"`,
    `"course_summary"`) and `format` (`"pdf"`/`"excel"`/`"csv"`) are plain
    strings, not DB enums — same idiom as every other status-style column
    in this codebase. `parameters` holds whatever scoping the report
    needs (exam_id, department_id, ...). `storage_key` is set only once
    `status == "completed"`, pointing at the generated file in the same
    object-storage bucket Module 05's `StorageService` already manages.
    """

    __tablename__ = "report_jobs"

    report_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReportJob id={self.id} report_type={self.report_type!r} status={self.status!r}>"
