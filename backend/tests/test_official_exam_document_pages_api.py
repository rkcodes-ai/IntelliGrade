"""OfficialExamDocumentPage API tests (read-only)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.official_exam_document_page import OfficialExamDocumentPage
from tests.conftest import auth_headers, create_test_user
from tests.test_official_exam_documents_api import _create_exam, _login, _upload_files


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def test_list_official_exam_document_pages_filters_by_document_id(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedpadmin1", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="PAGELIST")
    token = await _login(client, "oedpadmin1")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=headers,
    )
    document_id = created.json()["id"]

    page = OfficialExamDocumentPage(
        institution_id=exam.institution_id,
        document_id=uuid.UUID(document_id),
        page_number=1,
        storage_key="some/key.png",
        status="ocr_complete",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    response = await client.get(
        f"/api/v1/official-exam-document-pages?document_id={document_id}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(page.id)
    assert body["items"][0]["page_number"] == 1


async def test_get_official_exam_document_page(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedpadmin2", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="PAGEGET")
    token = await _login(client, "oedpadmin2")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/official-exam-documents",
        data={"exam_id": str(exam.id), "document_type": "question_paper"},
        files=_upload_files(),
        headers=headers,
    )
    document_id = created.json()["id"]

    page = OfficialExamDocumentPage(
        institution_id=exam.institution_id, document_id=uuid.UUID(document_id), page_number=1
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    response = await client.get(f"/api/v1/official-exam-document-pages/{page.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(page.id)


async def test_get_nonexistent_official_exam_document_page_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedpadmin3", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="PAGE404")
    token = await _login(client, "oedpadmin3")

    response = await client.get(
        f"/api/v1/official-exam-document-pages/{uuid.uuid4()}",
        headers=_institution_headers(token, exam.institution_id),
    )
    assert response.status_code == 404


async def test_non_privileged_role_cannot_list_document_pages(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="oedpstudent1", role=seed_rbac["student"])
    exam = await _create_exam(db_session, code="PAGEFORBID")
    token = await _login(client, "oedpstudent1")

    response = await client.get(
        "/api/v1/official-exam-document-pages",
        headers=_institution_headers(token, exam.institution_id),
    )
    assert response.status_code == 403
