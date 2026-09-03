"""HTTP-level tests for the NotificationEvent endpoints (Module 07, ADR-046)."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.exam_result_service import ExamResultService
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


async def test_publish_creates_notification_and_student_can_list_and_read_it(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="notif_teacher1", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="NOTIFPUB")
    uploader = await create_test_user(db_session, username="notif_uploader1")
    student = await create_test_user(
        db_session, username="notif_student1", role=seed_rbac["student"]
    )
    from app.models.user_institution import UserInstitution

    db_session.add(
        UserInstitution(user_id=student.id, institution_id=hierarchy.exam.institution_id)
    )
    await db_session.commit()
    provider = await seed_ai_provider(db_session)
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code="NOTIFPUB",
    )

    result_service = ExamResultService(db_session)
    result = await result_service.finalize_student(
        hierarchy.exam.institution_id, exam_session.id, actor_id=uploader.id
    )
    await result_service.approve(hierarchy.exam.institution_id, result.id, actor_id=uploader.id)
    await result_service.lock(hierarchy.exam.institution_id, result.id, actor_id=uploader.id)
    await result_service.publish(hierarchy.exam.institution_id, result.id, actor_id=uploader.id)
    await db_session.commit()

    student_token = await _login(client, "notif_student1")
    student_headers = _headers(student_token, hierarchy.exam.institution_id)

    list_resp = await client.get("/api/v1/notifications", headers=student_headers)
    assert list_resp.status_code == 200
    events = list_resp.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "result_published"
    assert events[0]["is_read"] is False

    unread_resp = await client.get("/api/v1/notifications/unread-count", headers=student_headers)
    assert unread_resp.json()["unread_count"] == 1

    read_resp = await client.post(
        f"/api/v1/notifications/{events[0]['id']}/read", headers=student_headers
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True

    unread_after = await client.get("/api/v1/notifications/unread-count", headers=student_headers)
    assert unread_after.json()["unread_count"] == 0
