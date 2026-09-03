"""Teacher Review Dashboard schemas (Module 07, Feature 1)."""

import uuid

from app.schemas.base import BaseSchema


class TeacherReviewFilters(BaseSchema):
    """Shared filter set for both the dashboard summary counts and the
    filtered review queue — every field is optional; omitted fields are
    not filtered on."""

    exam_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    student_user_id: uuid.UUID | None = None
    confidence_tier: str | None = None
    review_status: str | None = None
    teacher_id: uuid.UUID | None = None


class TeacherReviewDashboardSummary(BaseSchema):
    pending_review_count: int
    medium_confidence_count: int
    low_confidence_count: int
    completed_reviews_count: int
    auto_accepted_count: int
