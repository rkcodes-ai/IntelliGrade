"""QuestionPaperTemplate management API tests: CRUD, tenancy, soft-delete/restore, bulk-create."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_institution(client: AsyncClient, token: str, code: str = "ACME") -> str:
    response = await client.post(
        "/api/v1/institutions",
        json={"name": f"Institution {code}", "code": code, "institution_type": "university"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    result: str = response.json()["id"]
    return result


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Standard Midterm Layout",
        "description": "Default layout for department midterms",
        "header_text": "<<Institution Name>> — Midterm Examination",
        "footer_text": "Page <<page>> of <<total_pages>>",
        "instructions_text": "Answer all questions. Each question carries equal marks.",
    }
    payload.update(overrides)
    return payload


async def test_create_question_paper_template_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin1", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin1")
    institution_id = await _create_institution(client, token, code="INST1")

    response = await client.post(
        "/api/v1/question-paper-templates",
        json=_payload(),
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Standard Midterm Layout"
    assert body["institution_id"] == institution_id
    assert body["is_active"] is True


async def test_create_question_paper_template_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin2", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin2")

    response = await client.post(
        "/api/v1/question-paper-templates", json=_payload(), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_question_paper_template_rejects_duplicate_name(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin3", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin3")
    institution_id = await _create_institution(client, token, code="INST3")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    first = await client.post("/api/v1/question-paper-templates", json=_payload(), headers=headers)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/question-paper-templates",
        json=_payload(description="A different description"),
        headers=headers,
    )
    assert second.status_code == 409


async def test_non_admin_cannot_create_question_paper_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptstudent1", role=seed_rbac["student"])
    token = await _login(client, "qptstudent1")
    await create_test_user(db_session, username="qptadmin4", role=seed_rbac["super_admin"])
    admin_token = await _login(client, "qptadmin4")
    institution_id = await _create_institution(client, admin_token, code="INST4")

    response = await client.post(
        "/api/v1/question-paper-templates",
        json=_payload(),
        headers={**auth_headers(token), "X-Institution-Id": institution_id},
    )

    assert response.status_code == 403


async def test_question_paper_template_is_isolated_across_institutions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin5", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin5")
    institution_a = await _create_institution(client, token, code="INSTA")
    institution_b = await _create_institution(client, token, code="INSTB")

    created = await client.post(
        "/api/v1/question-paper-templates",
        json=_payload(),
        headers={**auth_headers(token), "X-Institution-Id": institution_a},
    )
    assert created.status_code == 201
    template_id = created.json()["id"]

    cross_tenant_get = await client.get(
        f"/api/v1/question-paper-templates/{template_id}",
        headers={**auth_headers(token), "X-Institution-Id": institution_b},
    )
    assert cross_tenant_get.status_code == 404


async def test_get_update_and_list_question_paper_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin6", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin6")
    institution_id = await _create_institution(client, token, code="INST6")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post(
        "/api/v1/question-paper-templates", json=_payload(), headers=headers
    )
    template_id = created.json()["id"]

    get_response = await client.get(
        f"/api/v1/question-paper-templates/{template_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Standard Midterm Layout"

    update_response = await client.patch(
        f"/api/v1/question-paper-templates/{template_id}",
        json={"footer_text": "Confidential — Page <<page>>"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["footer_text"] == "Confidential — Page <<page>>"

    list_response = await client.get("/api/v1/question-paper-templates", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] >= 1
    assert any(item["id"] == template_id for item in body["items"])


async def test_soft_delete_then_restore_question_paper_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin7", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin7")
    institution_id = await _create_institution(client, token, code="INST7")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    created = await client.post(
        "/api/v1/question-paper-templates", json=_payload(), headers=headers
    )
    template_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    update_response = await client.patch(
        f"/api/v1/question-paper-templates/{template_id}",
        json={"description": "Updated description"},
        headers=headers,
    )
    assert update_response.status_code == 200
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert update_response.json()["updated_at"] >= original_updated_at

    delete_response = await client.delete(
        f"/api/v1/question-paper-templates/{template_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/question-paper-templates/{template_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/question-paper-templates/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == template_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-paper-templates/{template_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/question-paper-templates/{template_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_question_paper_template_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin8", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin8")
    institution_id = await _create_institution(client, token, code="INST8")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.get(f"/api/v1/question-paper-templates/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_list_question_paper_templates_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin9", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin9")
    institution_id = await _create_institution(client, token, code="INST9")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    for i in range(5):
        response = await client.post(
            "/api/v1/question-paper-templates",
            json=_payload(name=f"Template {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get(
        "/api/v1/question-paper-templates?page=1&page_size=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5
    assert body["total_pages"] >= 3


async def test_bulk_create_question_paper_templates_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin10", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin10")
    institution_id = await _create_institution(client, token, code="INST10")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    seed = await client.post(
        "/api/v1/question-paper-templates", json=_payload(name="Duplicate Name"), headers=headers
    )
    assert seed.status_code == 201

    response = await client.post(
        "/api/v1/question-paper-templates/bulk",
        json=[
            _payload(name="Bulk One"),
            _payload(name="Duplicate Name"),  # conflicts with the seeded template
            _payload(name="Bulk Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1
    assert body["errors"][0]["name"] == "Duplicate Name"


async def test_create_question_paper_template_rejects_empty_name(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin11", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin11")
    institution_id = await _create_institution(client, token, code="INST11")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post(
        "/api/v1/question-paper-templates", json=_payload(name=""), headers=headers
    )

    assert response.status_code == 422


async def test_update_question_paper_template_rejects_duplicate_name(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin14", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin14")
    institution_id = await _create_institution(client, token, code="INST14")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    first = await client.post(
        "/api/v1/question-paper-templates", json=_payload(name="Layout One"), headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/question-paper-templates", json=_payload(name="Layout Two"), headers=headers
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-paper-templates/{second_id}",
        json={"name": "Layout One"},
        headers=headers,
    )

    assert update_response.status_code == 409


async def test_export_question_paper_templates_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin12", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin12")
    institution_id = await _create_institution(client, token, code="INST12")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.get("/api/v1/question-paper-templates/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_paper_templates_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qptadmin13", role=seed_rbac["super_admin"])
    token = await _login(client, "qptadmin13")
    institution_id = await _create_institution(client, token, code="INST13")
    headers = {**auth_headers(token), "X-Institution-Id": institution_id}

    response = await client.post("/api/v1/question-paper-templates/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"
