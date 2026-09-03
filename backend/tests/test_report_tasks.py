"""Tests for `app.tasks.report_tasks` — real PDF/Excel/CSV generation
(Module 07, Feature 8, ADR-045). Runs `_run_report_generation` directly
(bypassing Celery itself, same reason `tests/test_ocr_tasks.py` and
`tests/test_official_document_tasks.py` do), against the real
`reportlab`/`openpyxl`/`csv` libraries and the fake in-memory storage
bucket every Module 05/06/07 test relies on."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.report_job import ReportJob
from app.services.exam_result_service import ExamResultService
from tests.conftest import _FAKE_BUCKET, create_test_user
from tests.module07_helpers import (
    create_exam_hierarchy,
    create_finalizable_exam_session,
    seed_ai_provider,
)


@pytest.fixture(autouse=True)
def _bridge_report_task_session(monkeypatch: pytest.MonkeyPatch, db_engine) -> None:
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr("app.tasks.report_tasks.AsyncSessionLocal", session_factory)


async def _create_report_job(
    db_session: AsyncSession, *, institution_id, requested_by, report_type, format_, parameters
) -> ReportJob:
    job = ReportJob(
        institution_id=institution_id,
        report_type=report_type,
        format=format_,
        parameters=parameters,
        requested_by=requested_by,
        status="pending",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.mark.parametrize("format_,magic_bytes", [("pdf", b"%PDF"), ("excel", b"PK"), ("csv", None)])
async def test_generate_report_task_produces_real_file_for_each_format(
    db_session: AsyncSession, format_: str, magic_bytes: bytes | None
) -> None:
    from app.tasks.report_tasks import _run_report_generation

    hierarchy = await create_exam_hierarchy(db_session, code=f"RPT{format_.upper()}")
    uploader = await create_test_user(db_session, username=f"rpt_uploader_{format_}")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username=f"rpt_student_{format_}")
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code=f"RPT{format_.upper()}",
    )
    result_service = ExamResultService(db_session)
    await result_service.finalize_student(
        hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
    )

    job = await _create_report_job(
        db_session,
        institution_id=hierarchy.exam.institution_id,
        requested_by=uploader.id,
        report_type="institution_summary",
        format_=format_,
        parameters={"exam_id": str(hierarchy.exam.id)},
    )

    await _run_report_generation(str(job.id))

    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.storage_key is not None
    content = _FAKE_BUCKET[job.storage_key]
    assert len(content) > 0
    if magic_bytes is not None:
        assert content.startswith(magic_bytes)
    else:
        text = content.decode("utf-8")
        assert "Result Count" in text


@pytest.mark.parametrize(
    "report_type",
    ["student", "teacher_review", "ai_performance", "department_summary", "course_summary"],
)
async def test_generate_report_task_resolves_every_report_type(
    db_session: AsyncSession, report_type: str
) -> None:
    from app.tasks.report_tasks import _run_report_generation

    hierarchy = await create_exam_hierarchy(db_session, code=f"RPTTYPE{report_type[:6].upper()}")
    uploader = await create_test_user(db_session, username=f"rpt_uploader_{report_type}")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username=f"rpt_student_{report_type}")
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code=f"RPTTYPE{report_type[:6].upper()}",
    )
    result_service = ExamResultService(db_session)
    await result_service.finalize_student(
        hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
    )

    parameters = {"exam_id": str(hierarchy.exam.id)}
    if report_type == "student":
        parameters = {"exam_session_id": str(exam_session.id)}

    job = await _create_report_job(
        db_session,
        institution_id=hierarchy.exam.institution_id,
        requested_by=uploader.id,
        report_type=report_type,
        format_="csv",
        parameters=parameters,
    )

    await _run_report_generation(str(job.id))

    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.storage_key is not None
    content = _FAKE_BUCKET[job.storage_key]
    assert len(content) > 0


async def test_generate_report_task_marks_failed_on_missing_parameter(
    db_session: AsyncSession,
) -> None:
    from app.tasks.report_tasks import _run_report_generation

    hierarchy = await create_exam_hierarchy(db_session, code="RPTFAIL")
    uploader = await create_test_user(db_session, username="rpt_uploader_fail")

    job = await _create_report_job(
        db_session,
        institution_id=hierarchy.exam.institution_id,
        requested_by=uploader.id,
        report_type="question_wise",
        format_="pdf",
        parameters={},  # missing required exam_id
    )

    with pytest.raises(ValueError):
        await _run_report_generation(str(job.id))

    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.failure_reason is not None


async def test_generate_report_task_returns_early_for_missing_job() -> None:
    from app.tasks.report_tasks import _run_report_generation

    await _run_report_generation(str(uuid.uuid4()))
