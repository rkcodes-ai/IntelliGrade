"""Tests for `TeacherReviewDashboardService` (Module 07, Feature 1)."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pagination import PageParams
from app.schemas.teacher_review import TeacherReviewFilters
from app.services.teacher_review_dashboard_service import TeacherReviewDashboardService
from tests.conftest import create_test_user
from tests.module07_helpers import (
    create_exam_hierarchy,
    create_finalizable_exam_session,
    seed_ai_provider,
)


async def _seed_evaluations_with_statuses(db_session: AsyncSession, code: str):
    hierarchy = await create_exam_hierarchy(db_session, code=code)
    uploader = await create_test_user(db_session, username=f"trd_uploader_{code.lower()}")
    provider = await seed_ai_provider(db_session)

    # One session finalized as teacher_confirmed (via the helper's default).
    confirmed_student = await create_test_user(db_session, username=f"trd_confirmed_{code.lower()}")
    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=confirmed_student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code=f"{code}CONFIRMED",
    )

    # A second session, with one evaluation manually put into pending_review/low tier.
    from app.models.answer_evaluation import AnswerEvaluation

    pending_student = await create_test_user(db_session, username=f"trd_pending_{code.lower()}")
    pending_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=pending_student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code=f"{code}PENDING",
    )
    from sqlalchemy import select

    evaluation = (
        (
            await db_session.execute(
                select(AnswerEvaluation).where(
                    AnswerEvaluation.exam_session_id == pending_session.id
                )
            )
        )
        .scalars()
        .first()
    )
    evaluation.review_status = "pending_review"
    evaluation.confidence_tier = "low"
    evaluation.final_marks = None
    evaluation.reviewed_by = None
    await db_session.commit()

    return hierarchy


async def test_dashboard_summary_buckets_are_independent_counts(db_session: AsyncSession) -> None:
    hierarchy = await _seed_evaluations_with_statuses(db_session, "TRDBUCKETS")
    service = TeacherReviewDashboardService(db_session)

    summary = await service.get_dashboard_summary(
        hierarchy.exam.institution_id, TeacherReviewFilters()
    )

    assert summary.pending_review_count == 1
    assert summary.low_confidence_count == 1
    assert summary.completed_reviews_count == 1  # the teacher_confirmed evaluation


async def test_dashboard_summary_filters_by_exam_id(db_session: AsyncSession) -> None:
    hierarchy_a = await _seed_evaluations_with_statuses(db_session, "TRDFILTERA")
    hierarchy_b = await _seed_evaluations_with_statuses(db_session, "TRDFILTERB")
    service = TeacherReviewDashboardService(db_session)

    summary_a = await service.get_dashboard_summary(
        hierarchy_a.exam.institution_id, TeacherReviewFilters(exam_id=hierarchy_a.exam.id)
    )
    summary_b = await service.get_dashboard_summary(
        hierarchy_b.exam.institution_id, TeacherReviewFilters(exam_id=hierarchy_b.exam.id)
    )

    assert summary_a.pending_review_count == 1
    assert summary_b.pending_review_count == 1


async def test_queue_returns_paginated_evaluations_matching_filters(
    db_session: AsyncSession,
) -> None:
    hierarchy = await _seed_evaluations_with_statuses(db_session, "TRDQUEUE")
    service = TeacherReviewDashboardService(db_session)

    items, total = await service.get_queue(
        hierarchy.exam.institution_id,
        TeacherReviewFilters(review_status="pending_review"),
        PageParams(page=1, page_size=25),
    )

    assert total == 1
    assert items[0].review_status == "pending_review"
