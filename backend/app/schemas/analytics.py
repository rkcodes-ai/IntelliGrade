"""Analytics Dashboard schemas (Module 07, Feature 7). See ADR-044."""

import uuid
from decimal import Decimal

from app.schemas.base import BaseSchema


class AnalyticsFilters(BaseSchema):
    exam_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None


class ConfidenceDistribution(BaseSchema):
    high: int = 0
    medium: int = 0
    low: int = 0


class AnalyticsOverview(BaseSchema):
    result_count: int
    average_marks: Decimal | None = None
    highest_marks: Decimal | None = None
    lowest_marks: Decimal | None = None
    pass_percentage: Decimal | None = None
    fail_percentage: Decimal | None = None
    confidence_distribution: ConfidenceDistribution
    teacher_override_percentage: Decimal | None = None
    average_ai_vs_teacher_difference: Decimal | None = None


class QuestionPerformance(BaseSchema):
    extracted_question_id: uuid.UUID
    question_number: str
    evaluated_count: int
    max_marks: Decimal
    average_marks: Decimal | None = None
    #: `average_marks / max_marks`, in [0, 1] — the shared signal behind
    #: both "most difficult questions" and "most incorrectly answered
    #: questions" (ADR-044: no separate correctness label exists to tell
    #: these two apart, so both surface the same ascending-ratio sort).
    average_ratio: Decimal | None = None


class QuestionWiseAnalytics(BaseSchema):
    questions: list[QuestionPerformance]
    most_difficult: list[QuestionPerformance]
