"""ReportJob schemas (Module 07, Feature 8). See ADR-045."""

import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.base import BaseSchema

ReportType = Literal[
    "student",
    "question_wise",
    "teacher_review",
    "ai_performance",
    "institution_summary",
    "department_summary",
    "course_summary",
]
ReportFormat = Literal["pdf", "excel", "csv"]


class ReportGenerateRequest(BaseSchema):
    report_type: ReportType
    format: ReportFormat
    #: Scoping params for the chosen report_type — e.g. `exam_id`,
    #: `exam_session_id`, `subject_id`, `course_id`, `department_id`.
    parameters: dict[str, Any] | None = None


class ReportJobRead(BaseSchema):
    id: uuid.UUID
    institution_id: uuid.UUID
    report_type: ReportType
    format: ReportFormat
    parameters: dict[str, Any] | None = None
    requested_by: uuid.UUID
    status: Literal["pending", "processing", "completed", "failed"]
    storage_key: str | None = None
    failure_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
