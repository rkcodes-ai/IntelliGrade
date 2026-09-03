"""HTTP-level tests for the Result Finalization/Locking endpoints
(Module 07, Feature 4/5, ADR-042)."""

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


async def test_finalize_student_via_api_and_full_lifecycle(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="erapi_teacher1", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="ERAPI1")
    uploader = await create_test_user(db_session, username="erapi_uploader1")
    student = await create_test_user(db_session, username="erapi_student1")
    provider = await seed_ai_provider(db_session)
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code="ERAPI1",
    )
    token = await _login(client, "erapi_teacher1")
    headers = _headers(token, hierarchy.exam.institution_id)

    finalize_resp = await client.post(
        "/api/v1/exam-results/finalize-student",
        json={"exam_session_id": str(exam_session.id)},
        headers=headers,
    )
    assert finalize_resp.status_code == 200
    result_id = finalize_resp.json()["id"]
    assert finalize_resp.json()["status"] == "under_review"

    approve_resp = await client.post(f"/api/v1/exam-results/{result_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    lock_resp = await client.post(f"/api/v1/exam-results/{result_id}/lock", headers=headers)
    assert lock_resp.status_code == 200
    assert lock_resp.json()["status"] == "locked"

    publish_resp = await client.post(f"/api/v1/exam-results/{result_id}/publish", headers=headers)
    assert publish_resp.status_code == 200
    assert publish_resp.json()["status"] == "published"

    get_resp = await client.get(f"/api/v1/exam-results/{result_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "published"


async def test_lock_rejects_wrong_prior_status(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="erapi_teacher2", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="ERAPI2")
    uploader = await create_test_user(db_session, username="erapi_uploader2")
    student = await create_test_user(db_session, username="erapi_student2")
    provider = await seed_ai_provider(db_session)
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code="ERAPI2",
    )
    token = await _login(client, "erapi_teacher2")
    headers = _headers(token, hierarchy.exam.institution_id)

    finalize_resp = await client.post(
        "/api/v1/exam-results/finalize-student",
        json={"exam_session_id": str(exam_session.id)},
        headers=headers,
    )
    result_id = finalize_resp.json()["id"]

    lock_resp = await client.post(f"/api/v1/exam-results/{result_id}/lock", headers=headers)
    assert lock_resp.status_code == 409


async def test_unlock_requires_dedicated_permission_not_granted_to_teacher(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    hierarchy = await create_exam_hierarchy(db_session, code="ERAPI3")
    teacher = await create_test_user(
        db_session, username="erapi_teacher3", role=seed_rbac["teacher"]
    )

    from app.models.user_institution import UserInstitution

    db_session.add(
        UserInstitution(user_id=teacher.id, institution_id=hierarchy.exam.institution_id)
    )
    await db_session.commit()

    token = await _login(client, "erapi_teacher3")
    headers = _headers(token, hierarchy.exam.institution_id)

    response = await client.post(f"/api/v1/exam-results/{uuid.uuid4()}/unlock", headers=headers)
    # Permission check runs before the not-found lookup — teacher lacks
    # exam_results:unlock entirely (ADR-042's deliberate withholding).
    assert response.status_code == 403


async def test_finalize_batch_via_api(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="erapi_teacher4", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="ERAPI4")
    uploader = await create_test_user(db_session, username="erapi_uploader4")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="erapi_student4")

    from tests.module07_helpers import enroll_student

    await enroll_student(db_session, hierarchy, student_user_id=student.id, roll_number="ERAPI4-01")
    await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code="ERAPI4",
    )

    token = await _login(client, "erapi_teacher4")
    headers = _headers(token, hierarchy.exam.institution_id)

    response = await client.post(
        "/api/v1/exam-results/finalize-batch",
        json={"exam_id": str(hierarchy.exam.id), "batch_id": str(hierarchy.batch.id)},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["succeeded_count"] == 1


async def test_bulk_approve_lock_publish_via_api(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """Regression test (Module 09 audit): `/bulk/approve|lock|publish` were
    registered AFTER `/{entity_id}/approve|lock|publish` in the router, so
    Starlette's ordered route matching swallowed `bulk` as a literal
    `entity_id` and FastAPI's UUID coercion 422'd before ever reaching
    `bulk_transition()` — silently breaking Feature 11 end-to-end despite
    `bulk_transition()` itself being covered by
    `test_exam_result_service.py`. This test exercises the real HTTP
    routes (not just the service method) so a future route-ordering
    regression fails loudly here instead of shipping unnoticed again."""
    await create_test_user(db_session, username="erapi_teacher6", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="ERAPI6")
    uploader = await create_test_user(db_session, username="erapi_uploader6")
    provider = await seed_ai_provider(db_session)
    student = await create_test_user(db_session, username="erapi_student6")
    exam_session = await create_finalizable_exam_session(
        db_session,
        hierarchy,
        student_user_id=student.id,
        uploader_id=uploader.id,
        ai_provider_id=provider.id,
        question_marks=[(Decimal("9.00"), Decimal("10.00"))],
        code="ERAPI6",
    )
    token = await _login(client, "erapi_teacher6")
    headers = _headers(token, hierarchy.exam.institution_id)

    finalize_resp = await client.post(
        "/api/v1/exam-results/finalize-student",
        json={"exam_session_id": str(exam_session.id)},
        headers=headers,
    )
    assert finalize_resp.status_code == 200

    body = {"exam_id": str(hierarchy.exam.id)}

    approve_resp = await client.post(
        "/api/v1/exam-results/bulk/approve", json=body, headers=headers
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["succeeded_count"] == 1

    lock_resp = await client.post("/api/v1/exam-results/bulk/lock", json=body, headers=headers)
    assert lock_resp.status_code == 200, lock_resp.text
    assert lock_resp.json()["succeeded_count"] == 1

    publish_resp = await client.post(
        "/api/v1/exam-results/bulk/publish", json=body, headers=headers
    )
    assert publish_resp.status_code == 200, publish_resp.text
    assert publish_resp.json()["succeeded_count"] == 1


async def test_non_privileged_role_cannot_finalize(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="erapi_student5", role=seed_rbac["student"])
    hierarchy = await create_exam_hierarchy(db_session, code="ERAPI5")
    token = await _login(client, "erapi_student5")
    headers = _headers(token, hierarchy.exam.institution_id)

    response = await client.post(
        "/api/v1/exam-results/finalize-student",
        json={"exam_session_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 403
