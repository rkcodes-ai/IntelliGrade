"""
OCRProvider API tests: global catalog read/update, single-default and
enabled-implies-implemented business rules (ADR-028).

`OCRProvider` rows are normally seeded by migration -- tests create them
directly via the ORM instead (see the module 05 delegation notes).
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.ocr_provider import OCRProvider
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


async def _create_institution(db_session: AsyncSession, *, code: str) -> Institution:
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(institution)
    return institution


async def _create_provider(
    db_session: AsyncSession, *, code: str, **overrides: object
) -> OCRProvider:
    defaults: dict[str, object] = {
        "code": code,
        "name": code.title(),
        "description": f"{code} OCR engine",
        "is_enabled": False,
        "is_implemented": False,
        "is_default": False,
    }
    defaults.update(overrides)
    provider = OCRProvider(**defaults)  # type: ignore[arg-type]
    db_session.add(provider)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


async def test_list_ocr_providers_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin1", role=seed_rbac["super_admin"])
    await _create_provider(db_session, code="tesseract")
    token = await _login(client, "ocpadmin1")

    response = await client.get("/api/v1/ocr-providers", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_read_ocr_providers(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpstudent1", role=seed_rbac["student"])
    institution = await _create_institution(db_session, code="OCPSTU")
    token = await _login(client, "ocpstudent1")

    response = await client.get(
        "/api/v1/ocr-providers", headers=_institution_headers(token, institution.id)
    )

    assert response.status_code == 403


async def test_get_nonexistent_ocr_provider_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin2", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCP404")
    token = await _login(client, "ocpadmin2")

    response = await client.get(
        f"/api/v1/ocr-providers/{uuid.uuid4()}",
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 404


async def test_ocr_provider_list_and_get_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin3", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCPRT")
    provider = await _create_provider(db_session, code="easyocr_rt", is_implemented=True)
    token = await _login(client, "ocpadmin3")
    headers = _institution_headers(token, institution.id)

    get_response = await client.get(f"/api/v1/ocr-providers/{provider.id}", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["code"] == "easyocr_rt"
    assert body["is_implemented"] is True
    assert body["is_enabled"] is False
    assert body["is_default"] is False

    list_response = await client.get("/api/v1/ocr-providers", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == str(provider.id) for item in list_response.json()["items"])


async def test_get_ocr_provider_health_runs_real_adapter_check(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """`code` must be one of the six real registry codes (see
    `app.services.ocr.registry`) -- unlike the other tests in this file,
    which use arbitrary codes since they never leave the DB layer, this
    endpoint resolves `code` to a real adapter class and calls its actual
    `health_check()`."""
    await create_test_user(db_session, username="ocpadmin_health", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCPHEALTH")
    provider = await _create_provider(
        db_session, code="tesseract", is_implemented=True, is_enabled=True, is_default=True
    )
    token = await _login(client, "ocpadmin_health")
    headers = _institution_headers(token, institution.id)

    response = await client.get(f"/api/v1/ocr-providers/{provider.id}/health", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider_code"] == "tesseract"
    assert isinstance(body["installed"], bool)
    assert isinstance(body["ready"], bool)


async def test_list_ocr_providers_pagination_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin4", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCPPAGE")
    for i in range(5):
        await _create_provider(db_session, code=f"provider_page_{i}")
    token = await _login(client, "ocpadmin4")
    headers = _institution_headers(token, institution.id)

    response = await client.get("/api/v1/ocr-providers?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_update_ocr_provider_enforces_single_default(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin5", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCPDEF")
    provider_a = await _create_provider(
        db_session, code="provider_default_a", is_implemented=True, is_default=True
    )
    provider_b = await _create_provider(db_session, code="provider_default_b", is_implemented=True)
    token = await _login(client, "ocpadmin5")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ocr-providers/{provider_b.id}", json={"is_default": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["is_default"] is True

    get_a = await client.get(f"/api/v1/ocr-providers/{provider_a.id}", headers=headers)
    assert get_a.status_code == 200
    assert get_a.json()["is_default"] is False


async def test_update_ocr_provider_rejects_enabling_unimplemented_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin6", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCPUNIMPL")
    provider = await _create_provider(db_session, code="unimplemented_engine", is_implemented=False)
    token = await _login(client, "ocpadmin6")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ocr-providers/{provider.id}", json={"is_enabled": True}, headers=headers
    )

    assert response.status_code == 422


async def test_update_ocr_provider_allows_enabling_implemented_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpadmin7", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="OCPIMPL")
    provider = await _create_provider(db_session, code="implemented_engine", is_implemented=True)
    token = await _login(client, "ocpadmin7")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ocr-providers/{provider.id}", json={"is_enabled": True}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["is_enabled"] is True


async def test_non_super_admin_cannot_update_ocr_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocpiadmin1", role=seed_rbac["institution_admin"])
    institution = await _create_institution(db_session, code="OCPFORBID")
    provider = await _create_provider(db_session, code="forbidden_engine", is_implemented=True)
    token = await _login(client, "ocpiadmin1")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ocr-providers/{provider.id}", json={"is_enabled": True}, headers=headers
    )

    assert response.status_code == 403
