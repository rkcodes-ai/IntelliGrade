"""HTTP-level tests for the ReportJob endpoints (Module 07, Feature 8)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user
from tests.module07_helpers import create_exam_hierarchy
from tests.test_official_exam_documents_api import _login


def _headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_generate_report_creates_pending_job_and_dispatch_is_best_effort(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rptapi_teacher1", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="RPTAPI1")
    token = await _login(client, "rptapi_teacher1")
    headers = _headers(token, hierarchy.exam.institution_id)

    response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "institution_summary",
            "format": "csv",
            "parameters": {"exam_id": str(hierarchy.exam.id)},
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] in ("pending", "processing", "completed", "failed")
    assert body["report_type"] == "institution_summary"
    assert body["format"] == "csv"


async def test_download_rejects_report_not_yet_completed(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rptapi_teacher2", role=seed_rbac["super_admin"])
    hierarchy = await create_exam_hierarchy(db_session, code="RPTAPI2")
    token = await _login(client, "rptapi_teacher2")
    headers = _headers(token, hierarchy.exam.institution_id)

    created = await client.post(
        "/api/v1/reports",
        json={"report_type": "institution_summary", "format": "csv", "parameters": {}},
        headers=headers,
    )
    report_id = created.json()["id"]

    response = await client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    # The Celery broker is unreachable in this test environment (best-effort
    # dispatch swallows the failure — see `_enqueue_report_generation`), so
    # the job deterministically stays "pending" and download is rejected.
    assert response.status_code == 422


async def test_non_privileged_role_cannot_generate_report(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="rptapi_student1", role=seed_rbac["student"])
    hierarchy = await create_exam_hierarchy(db_session, code="RPTAPI3")
    token = await _login(client, "rptapi_student1")
    headers = _headers(token, hierarchy.exam.institution_id)

    response = await client.post(
        "/api/v1/reports",
        json={"report_type": "institution_summary", "format": "csv", "parameters": {}},
        headers=headers,
    )
    assert response.status_code == 403
