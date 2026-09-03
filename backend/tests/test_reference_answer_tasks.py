"""Tests for `app.tasks.reference_answer_tasks` — the Celery task wrapper
around `ReferenceAnswerService.generate()` (Phase 12, AI Reference Answer
Builder milestone). Runs `_run_generate` directly (bypassing Celery
itself), same reason `tests/test_report_tasks.py`/`tests/test_ocr_tasks.py`/
`tests/test_official_document_tasks.py` do."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_reference_answer import AIReferenceAnswer
from tests.conftest import create_test_user
from tests.test_ai_reference_answers_api import _seed_verified_question_and_model_answer
from tests.test_answer_evaluation_model_answer_scoping import (
    _create_exam_under,
    _create_institution,
    _seed_ai_provider,
)


@pytest.fixture(autouse=True)
def _bridge_reference_task_session(monkeypatch: pytest.MonkeyPatch, db_engine) -> None:
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr("app.tasks.reference_answer_tasks.AsyncSessionLocal", session_factory)


async def test_run_generate_creates_a_reference_answer(db_session: AsyncSession) -> None:
    from app.tasks.reference_answer_tasks import _run_generate

    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="RTASKGEN")
    uploader = await create_test_user(db_session, username="rtask_uploader")
    exam = await _create_exam_under(db_session, institution, code="RTASKGENEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    await _run_generate(str(institution.id), str(question.id), None, force=False)

    query = select(AIReferenceAnswer).where(
        AIReferenceAnswer.extracted_question_id == question.id,
        AIReferenceAnswer.is_current.is_(True),
    )
    reference = (await db_session.execute(query)).scalars().first()
    assert reference is not None
    assert reference.status == "pending_verification"


async def test_run_generate_with_force_creates_a_new_version(db_session: AsyncSession) -> None:
    from app.tasks.reference_answer_tasks import _run_generate

    await _seed_ai_provider(db_session)
    institution = await _create_institution(db_session, code="RTASKFORCE")
    uploader = await create_test_user(db_session, username="rtask_uploader_force")
    exam = await _create_exam_under(db_session, institution, code="RTASKFORCEEXAM")
    question, _, _ = await _seed_verified_question_and_model_answer(
        db_session, exam=exam, uploader=uploader
    )
    await db_session.commit()
    await db_session.refresh(question)

    await _run_generate(str(institution.id), str(question.id), None, force=False)
    await _run_generate(str(institution.id), str(question.id), None, force=True)

    query = select(AIReferenceAnswer).where(AIReferenceAnswer.extracted_question_id == question.id)
    references = (await db_session.execute(query)).scalars().all()
    assert len(references) == 2
    versions = sorted(r.version for r in references)
    assert versions == [1, 2]


async def test_run_generate_raises_for_missing_question(db_session: AsyncSession) -> None:
    from app.core.exceptions import NotFoundError
    from app.tasks.reference_answer_tasks import _run_generate

    institution = await _create_institution(db_session, code="RTASKMISS")
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await _run_generate(str(institution.id), str(uuid.uuid4()), None, force=False)
