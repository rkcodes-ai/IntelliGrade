"""Tests for `ExamResultService` — the Result Finalization/Locking state
machine (Module 07, ADR-042)."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.services.answer_evaluation_service import AnswerEvaluationService
from app.services.exam_result_service import ExamResultService
from app.services.notification_service import NotificationService
from tests.conftest import create_test_user
from tests.module07_helpers import (
    create_exam_hierarchy,
    create_finalizable_exam_session,
    enroll_student,
    seed_ai_provider,
)


async def test_finalize_student_computes_totals_and_moves_to_under_review(
    db_session: AsyncSession,
) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSFIN")
    uploader = await create_test_user(db_session, username="ers_uploader_fin")
    student = await create_test_user(db_session, username="ers_student_fin")
    provider = await seed_ai_provider(db_session)

    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00")), (Decimal("7.00"), Decimal("10.00"))],
        code="FIN",
    )

    service = ExamResultService(db_session)
    result = await service.finalize_student(
        hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
    )

    assert result.status == "under_review"
    assert result.total_max_marks == Decimal("20.00")
    assert result.total_marks == Decimal("15.00")
    assert result.finalized_by == uploader.id
    assert result.finalized_at is not None


async def test_finalize_student_rejects_unresolved_evaluations(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSUNRESOLVED")
    uploader = await create_test_user(db_session, username="ers_uploader_unresolved")
    student = await create_test_user(db_session, username="ers_student_unresolved")
    provider = await seed_ai_provider(db_session)

    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code="UNRESOLVED",
    )
    # Force one evaluation back into an unresolved state.
    from sqlalchemy import select

    from app.models.answer_evaluation import AnswerEvaluation

    evaluation = (
        (
            await db_session.execute(
                select(AnswerEvaluation).where(AnswerEvaluation.exam_session_id == exam_session.id)
            )
        )
        .scalars()
        .first()
    )
    evaluation.final_marks = None
    await db_session.commit()

    service = ExamResultService(db_session)
    with pytest.raises(ValidationAppError):
        await service.finalize_student(
            hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
        )


async def test_finalize_student_rejects_session_with_no_evaluations(
    db_session: AsyncSession,
) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSNOEVAL")
    uploader = await create_test_user(db_session, username="ers_uploader_noeval")
    student = await create_test_user(db_session, username="ers_student_noeval")

    from app.models.exam_session import ExamSession

    exam_session = ExamSession(
        institution_id=hierarchy.exam.institution_id,
        exam_id=hierarchy.exam.id,
        student_user_id=student.id,
    )
    db_session.add(exam_session)
    await db_session.commit()
    await db_session.refresh(exam_session)

    service = ExamResultService(db_session)
    with pytest.raises(ValidationAppError):
        await service.finalize_student(
            hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
        )


async def _finalized_result(db_session: AsyncSession, code: str):
    hierarchy = await create_exam_hierarchy(db_session, code=code)
    uploader = await create_test_user(db_session, username=f"ers_uploader_{code.lower()}")
    student = await create_test_user(db_session, username=f"ers_student_{code.lower()}")
    provider = await seed_ai_provider(db_session)
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code=code,
    )
    service = ExamResultService(db_session)
    result = await service.finalize_student(
        hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
    )
    return service, hierarchy, result, uploader, student, exam_session


async def test_full_lifecycle_approve_lock_publish(db_session: AsyncSession) -> None:
    service, hierarchy, result, uploader, student, exam_session = await _finalized_result(
        db_session, "ERSLIFECYCLE"
    )
    institution_id = hierarchy.exam.institution_id

    approved = await service.approve(institution_id, result.id, actor_id=uploader.id)
    assert approved.status == "approved"

    locked = await service.lock(institution_id, result.id, actor_id=uploader.id)
    assert locked.status == "locked"

    # Locked: further answer-evaluation edits must be rejected (ADR-042).
    from sqlalchemy import select

    from app.models.answer_evaluation import AnswerEvaluation

    evaluation = (
        (
            await db_session.execute(
                select(AnswerEvaluation).where(AnswerEvaluation.exam_session_id == exam_session.id)
            )
        )
        .scalars()
        .first()
    )
    eval_service = AnswerEvaluationService(db_session)
    with pytest.raises(ConflictError):
        await eval_service.evaluate_question(
            institution_id,
            exam_session_id=exam_session.id,
            extracted_question_id=evaluation.extracted_question_id,
            actor_id=uploader.id,
        )

    published = await service.publish(institution_id, result.id, actor_id=uploader.id)
    assert published.status == "published"
    assert published.published_by == uploader.id

    notification_service = NotificationService(db_session)
    events = await notification_service.list_for_current_user(institution_id, student.id)
    assert any(e.event_type == "result_published" for e in events)


async def test_transition_rejects_out_of_order(db_session: AsyncSession) -> None:
    service, hierarchy, result, uploader, _student, _exam_session = await _finalized_result(
        db_session, "ERSOUTOFORDER"
    )
    institution_id = hierarchy.exam.institution_id

    with pytest.raises(ConflictError):
        await service.lock(institution_id, result.id, actor_id=uploader.id)  # not approved yet

    with pytest.raises(ConflictError):
        await service.publish(institution_id, result.id, actor_id=uploader.id)  # not locked yet


async def test_unlock_returns_result_to_draft_and_reallows_edits(db_session: AsyncSession) -> None:
    service, hierarchy, result, uploader, _student, exam_session = await _finalized_result(
        db_session, "ERSUNLOCK"
    )
    institution_id = hierarchy.exam.institution_id
    await service.approve(institution_id, result.id, actor_id=uploader.id)
    locked = await service.lock(institution_id, result.id, actor_id=uploader.id)
    assert locked.status == "locked"

    unlocked = await service.unlock(institution_id, result.id, actor_id=uploader.id)
    assert unlocked.status == "draft"
    assert unlocked.unlocked_by == uploader.id


async def test_unlock_rejects_non_locked_result(db_session: AsyncSession) -> None:
    service, hierarchy, result, uploader, _student, _exam_session = await _finalized_result(
        db_session, "ERSUNLOCKBAD"
    )
    with pytest.raises(ConflictError):
        await service.unlock(hierarchy.exam.institution_id, result.id, actor_id=uploader.id)


async def test_finalize_exam_bulk_finalizes_all_sessions(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSBULKEXAM")
    uploader = await create_test_user(db_session, username="ers_uploader_bulkexam")
    provider = await seed_ai_provider(db_session)

    session_ids = []
    for i in range(3):
        student = await create_test_user(db_session, username=f"ers_bulkexam_student_{i}")
        exam_session = await create_finalizable_exam_session(
            db_session,
            hierarchy,
            student_user_id=student.id,
            uploader_id=uploader.id,
            ai_provider_id=provider.id,
            question_marks=[(Decimal("5.00"), Decimal("10.00"))],
            code=f"BULKEXAM{i}",
        )
        session_ids.append(exam_session.id)

    service = ExamResultService(db_session)
    result = await service.finalize_exam(
        hierarchy.exam.institution_id, hierarchy.exam.id, actor_id=uploader.id
    )
    assert result.succeeded_count == 3
    assert result.failed == []


async def test_finalize_batch_only_finalizes_enrolled_students(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSBATCH")
    uploader = await create_test_user(db_session, username="ers_uploader_batch")
    provider = await seed_ai_provider(db_session)

    enrolled_student = await create_test_user(db_session, username="ers_batch_enrolled")
    await enroll_student(
        db_session, hierarchy, student_user_id=enrolled_student.id, roll_number="ERSBATCH-01"
    )
    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=enrolled_student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("6.00"), Decimal("10.00"))],
        code="BATCHENROLLED",
    )

    not_enrolled_student = await create_test_user(db_session, username="ers_batch_not_enrolled")
    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=not_enrolled_student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("6.00"), Decimal("10.00"))],
        code="BATCHNOTENROLLED",
    )

    service = ExamResultService(db_session)
    result = await service.finalize_batch(
        hierarchy.exam.institution_id, hierarchy.exam.id, hierarchy.batch.id, actor_id=uploader.id
    )
    assert result.succeeded_count == 1


async def test_finalize_student_rejects_unknown_exam_session(db_session: AsyncSession) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSNOTFOUND")
    uploader = await create_test_user(db_session, username="ers_uploader_notfound")
    service = ExamResultService(db_session)
    with pytest.raises(NotFoundError):
        await service.finalize_student(
            hierarchy.exam.institution_id, __import__("uuid").uuid4(), actor_id=uploader.id
        )


async def test_bulk_transition_approve_reports_unfinalized_sessions(
    db_session: AsyncSession,
) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERSBULKTRANS")
    uploader = await create_test_user(db_session, username="ers_uploader_bulktrans")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="ers_bulktrans_student")

    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("6.00"), Decimal("10.00"))],
        code="BULKTRANS",
    )
    # Not finalized yet — bulk_transition("approve") must report it as failed, not raise.

    service = ExamResultService(db_session)
    result = await service.bulk_transition(
        hierarchy.exam.institution_id, hierarchy.exam.id, action="approve", actor_id=uploader.id
    )
    assert result.succeeded_count == 0
    assert len(result.failed) == 1
