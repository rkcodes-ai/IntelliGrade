"""
AIProvider API tests: global catalog read/update, single-default and
enabled-implies-implemented business rules.

`AIProvider` rows are normally seeded by migration -- tests create them
directly via the ORM instead (see the module 06 delegation notes).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.ai_providers import router as ai_providers_router
from app.core.config import get_settings
from app.main import app as fastapi_app
from app.models.ai_provider import AIProvider
from app.models.institution import Institution
from tests.conftest import auth_headers, create_test_user


@pytest.fixture(scope="module", autouse=True)
def _mount_ai_providers_router():
    """
    `app/api/v1/router.py` is merged centrally by the Module 06 orchestrator
    once every task's endpoints exist -- this task must not edit it. Until
    that merge lands, mount this router directly onto the live app for the
    duration of this test module so these tests exercise a real
    request/response cycle, then unmount it, leaving the app exactly as it
    was for every other test module.
    """
    settings = get_settings()
    prefix = f"{settings.API_V1_PREFIX}/ai-providers"
    already_mounted = any(
        getattr(route, "path", "").startswith(prefix) for route in fastapi_app.routes
    )
    if already_mounted:
        yield
        return
    original_routes = list(fastapi_app.routes)
    fastapi_app.include_router(ai_providers_router, prefix=settings.API_V1_PREFIX)
    yield
    fastapi_app.router.routes = original_routes


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
) -> AIProvider:
    defaults: dict[str, object] = {
        "code": code,
        "name": code.title(),
        "description": f"{code} AI engine",
        "is_enabled": False,
        "is_implemented": False,
        "is_default": False,
    }
    defaults.update(overrides)
    provider = AIProvider(**defaults)  # type: ignore[arg-type]
    db_session.add(provider)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


async def test_list_ai_providers_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin1", role=seed_rbac["super_admin"])
    await _create_provider(db_session, code="lexical_heuristic")
    token = await _login(client, "aipadmin1")

    response = await client.get("/api/v1/ai-providers", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_read_ai_providers(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipstudent1", role=seed_rbac["student"])
    institution = await _create_institution(db_session, code="AIPSTU")
    token = await _login(client, "aipstudent1")

    response = await client.get(
        "/api/v1/ai-providers", headers=_institution_headers(token, institution.id)
    )

    assert response.status_code == 403


async def test_get_nonexistent_ai_provider_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin2", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="AIP404")
    token = await _login(client, "aipadmin2")

    response = await client.get(
        f"/api/v1/ai-providers/{uuid.uuid4()}",
        headers=_institution_headers(token, institution.id),
    )

    assert response.status_code == 404


async def test_ai_provider_list_and_get_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin3", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="AIPRT")
    provider = await _create_provider(db_session, code="lexical_heuristic_rt", is_implemented=True)
    token = await _login(client, "aipadmin3")
    headers = _institution_headers(token, institution.id)

    get_response = await client.get(f"/api/v1/ai-providers/{provider.id}", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["code"] == "lexical_heuristic_rt"
    assert body["is_implemented"] is True
    assert body["is_enabled"] is False
    assert body["is_default"] is False

    list_response = await client.get("/api/v1/ai-providers", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == str(provider.id) for item in list_response.json()["items"])


async def test_list_ai_providers_pagination_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin4", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="AIPPAGE")
    for i in range(5):
        await _create_provider(db_session, code=f"provider_page_{i}")
    token = await _login(client, "aipadmin4")
    headers = _institution_headers(token, institution.id)

    response = await client.get("/api/v1/ai-providers?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_update_ai_provider_enforces_single_default(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin5", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="AIPDEF")
    provider_a = await _create_provider(
        db_session, code="provider_default_a", is_implemented=True, is_default=True
    )
    provider_b = await _create_provider(db_session, code="provider_default_b", is_implemented=True)
    token = await _login(client, "aipadmin5")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ai-providers/{provider_b.id}", json={"is_default": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["is_default"] is True

    get_a = await client.get(f"/api/v1/ai-providers/{provider_a.id}", headers=headers)
    assert get_a.status_code == 200
    assert get_a.json()["is_default"] is False


async def test_update_ai_provider_rejects_enabling_unimplemented_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin6", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="AIPUNIMPL")
    provider = await _create_provider(db_session, code="unimplemented_engine", is_implemented=False)
    token = await _login(client, "aipadmin6")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ai-providers/{provider.id}", json={"is_enabled": True}, headers=headers
    )

    assert response.status_code == 422


async def test_update_ai_provider_allows_enabling_implemented_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipadmin7", role=seed_rbac["super_admin"])
    institution = await _create_institution(db_session, code="AIPIMPL")
    provider = await _create_provider(db_session, code="implemented_engine", is_implemented=True)
    token = await _login(client, "aipadmin7")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ai-providers/{provider.id}", json={"is_enabled": True}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["is_enabled"] is True


async def test_non_super_admin_cannot_update_ai_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aipiadmin1", role=seed_rbac["institution_admin"])
    institution = await _create_institution(db_session, code="AIPFORBID")
    provider = await _create_provider(db_session, code="forbidden_engine", is_implemented=True)
    token = await _login(client, "aipiadmin1")
    headers = _institution_headers(token, institution.id)

    response = await client.patch(
        f"/api/v1/ai-providers/{provider.id}", json={"is_enabled": True}, headers=headers
    )

    assert response.status_code == 403
