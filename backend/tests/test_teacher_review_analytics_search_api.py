"""HTTP-level smoke tests for the Teacher Review Dashboard, Analytics, and
Search endpoints (Module 07, Features 1/7/9) — the underlying aggregation
logic is exercised thoroughly in `test_teacher_review_dashboard_service.py`/
`test_analytics_service.py`/`test_search_service.py`; these tests confirm
the real HTTP/RBAC layer wires up correctly."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user
from tests.module07_helpers import (
    create_exam_hierarchy,
    create_finalizable_exam_session,
    seed_ai_provider,
)
from tests.test_official_exam_documents_api import _login


def _headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_teacher_review_dashboard_endpoint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="trdapi_teacher1", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="TRDAPI1")
    uploader = await create_test_user(db_session, username="trdapi_uploader1")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="trdapi_student1")
    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code="TRDAPI1",
    )
    token = await _login(client, "trdapi_teacher1")
    headers = _headers(token, hierarchy.exam.institution_id)

    dashboard_resp = await client.get("/api/v1/teacher-review/dashboard", headers=headers)
    assert dashboard_resp.status_code == 200
    assert dashboard_resp.json()["completed_reviews_count"] == 1

    queue_resp = await client.get(
        "/api/v1/teacher-review/queue", params={"exam_id": str(hierarchy.exam.id)}, headers=headers
    )
    assert queue_resp.status_code == 200
    assert queue_resp.json()["total"] == 1


async def test_analytics_overview_endpoint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="anlapi_teacher1", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="ANLAPI1")
    uploader = await create_test_user(db_session, username="anlapi_uploader1")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="anlapi_student1")
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("8.00"), Decimal("10.00"))],
        code="ANLAPI1",
    )
    from app.services.exam_result_service import ExamResultService

    await ExamResultService(db_session).finalize_student(
        hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
    )
    token = await _login(client, "anlapi_teacher1")
    headers = _headers(token, hierarchy.exam.institution_id)

    overview_resp = await client.get(
        "/api/v1/analytics/overview", params={"exam_id": str(hierarchy.exam.id)}, headers=headers
    )
    assert overview_resp.status_code == 200
    assert overview_resp.json()["result_count"] == 1

    qw_resp = await client.get(
        "/api/v1/analytics/question-wise",
        params={"exam_id": str(hierarchy.exam.id)},
        headers=headers,
    )
    assert qw_resp.status_code == 200
    assert len(qw_resp.json()["questions"]) == 1


async def test_search_endpoint(client: AsyncClient, db_session: AsyncSession, seed_rbac) -> None:
    await create_test_user(db_session, username="searchapi_teacher1", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="SEARCHAPI1")
    token = await _login(client, "searchapi_teacher1")
    headers = _headers(token, hierarchy.exam.institution_id)

    from app.models.assessment import Assessment
    from app.models.subject import Subject

    assessment = await db_session.get(Assessment, hierarchy.assessment.id)
    subject = await db_session.get(Subject, assessment.subject_id)

    response = await client.get("/api/v1/search", params={"q": subject.name}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == subject.name
    assert any(r["type"] == "subject" for r in body["results"])


async def test_non_privileged_role_cannot_access_analytics_or_dashboard(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="restrictapi_student1", role=seed_rbac["student"])
    hierarchy = await create_exam_hierarchy(db_session, code="RESTRICTAPI1")
    token = await _login(client, "restrictapi_student1")
    headers = _headers(token, hierarchy.exam.institution_id)

    dashboard_resp = await client.get("/api/v1/teacher-review/dashboard", headers=headers)
    assert dashboard_resp.status_code == 403

    analytics_resp = await client.get("/api/v1/analytics/overview", headers=headers)
    assert analytics_resp.status_code == 403

    search_resp = await client.get("/api/v1/search", params={"q": "x"}, headers=headers)
    assert search_resp.status_code == 403
