"""Tests for `AnalyticsService` (Module 07, Feature 7, ADR-044)."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import AnalyticsFilters
from app.services.analytics_service import AnalyticsService
from app.services.exam_result_service import ExamResultService
from tests.conftest import create_test_user
from tests.module07_helpers import (
    create_exam_hierarchy,
    create_finalizable_exam_session,
    seed_ai_provider,
)


async def test_overview_computes_marks_stats_and_pass_fail(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(
        db_session,
        code="ANLOVERVIEW",
        maximum_marks=Decimal("10.00"),
        passing_marks=Decimal("4.00"),
    )
    uploader = await create_test_user(db_session, username="anl_uploader1")
    provider = await seed_ai_provider(db_session)
    result_service = ExamResultService(db_session)

    # Student A: 9/10 -> pass. Student B: 2/10 -> fail.
    student_a = await create_test_user(db_session, username="anl_student_a")
    session_a = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student_a.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code="ANLA",
    )
    await result_service.finalize_student(
        hierarchy.exam.institution_id, session_a.id, actor_id=uploader.id
    )

    student_b = await create_test_user(db_session, username="anl_student_b")
    session_b = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student_b.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("2.00"), Decimal("10.00"))],
        code="ANLB",
    )
    await result_service.finalize_student(
        hierarchy.exam.institution_id, session_b.id, actor_id=uploader.id
    )

    analytics = AnalyticsService(db_session)
    overview = await analytics.get_overview(
        hierarchy.exam.institution_id, AnalyticsFilters(exam_id=hierarchy.exam.id)
    )

    assert overview.result_count == 2
    assert overview.highest_marks == Decimal("9.00")
    assert overview.lowest_marks == Decimal("2.00")
    assert overview.average_marks == Decimal("5.50")
    assert overview.pass_percentage == Decimal("50")
    assert overview.fail_percentage == Decimal("50")


async def test_overview_confidence_distribution_and_override_percentage(
    db_session: AsyncSession,
) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ANLCONF")
    uploader = await create_test_user(db_session, username="anl_uploader2")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="anl_student_conf")

    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00")), (Decimal("6.00"), Decimal("10.00"))],
        code="ANLCONF",
    )

    from sqlalchemy import select

    from app.models.answer_evaluation import AnswerEvaluation

    evaluations = (
        (
            await db_session.execute(
                select(AnswerEvaluation).where(AnswerEvaluation.exam_session_id == exam_session.id)
            )
        )
        .scalars()
        .all()
    )
    evaluations[0].review_status = "teacher_overridden"
    evaluations[0].suggested_marks = Decimal("5.00")
    evaluations[0].final_marks = Decimal("8.00")
    await db_session.commit()

    analytics = AnalyticsService(db_session)
    overview = await analytics.get_overview(
        hierarchy.exam.institution_id, AnalyticsFilters(exam_id=hierarchy.exam.id)
    )

    assert overview.confidence_distribution.high == 2
    assert overview.teacher_override_percentage == Decimal("50")
    assert overview.average_ai_vs_teacher_difference == Decimal("1.50")  # (3.00 + 0.00) / 2


async def test_question_wise_ranks_most_difficult_ascending(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ANLQW")
    uploader = await create_test_user(db_session, username="anl_uploader3")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="anl_student_qw")

    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00")), (Decimal("2.00"), Decimal("10.00"))],
        code="ANLQW",
    )

    analytics = AnalyticsService(db_session)
    data = await analytics.get_question_wise(hierarchy.exam.institution_id, hierarchy.exam.id)

    assert len(data.questions) == 2
    assert (
        data.most_difficult[0].average_ratio < data.most_difficult[-1].average_ratio
        if len(data.most_difficult) > 1
        else True
    )
    assert data.most_difficult[0].average_marks == Decimal("2.00")


async def test_overview_returns_none_stats_when_no_results(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ANLEMPTY")
    analytics = AnalyticsService(db_session)
    overview = await analytics.get_overview(
        hierarchy.exam.institution_id, AnalyticsFilters(exam_id=hierarchy.exam.id)
    )
    assert overview.result_count == 0
    assert overview.average_marks is None
    assert overview.pass_percentage is None
