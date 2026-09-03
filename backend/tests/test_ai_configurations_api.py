"""AIConfiguration API tests: CRUD, tenancy, and provider/assessment validation business rules."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.ai_configurations import router as ai_configurations_router
from app.core.config import get_settings
from app.main import app as fastapi_app
from app.models.ai_provider import AIProvider
from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from tests.conftest import auth_headers, create_test_user


@pytest.fixture(scope="module", autouse=True)
def _mount_ai_configurations_router():
    """
    `app/api/v1/router.py` is merged centrally by the Module 06 orchestrator
    once every task's endpoints exist -- this task must not edit it. Until
    that merge lands, mount this router directly onto the live app for the
    duration of this test module so these tests exercise a real
    request/response cycle, then unmount it, leaving the app exactly as it
    was for every other test module.
    """
    settings = get_settings()
    prefix = f"{settings.API_V1_PREFIX}/ai-configurations"
    already_mounted = any(
        getattr(route, "path", "").startswith(prefix) for route in fastapi_app.routes
    )
    if already_mounted:
        yield
        return
    original_routes = list(fastapi_app.routes)
    fastapi_app.include_router(ai_configurations_router, prefix=settings.API_V1_PREFIX)
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


async def _create_assessment(db_session: AsyncSession, *, code: str) -> Assessment:
    """Builds the full Module 03/04 parent chain an `Assessment` needs, mirroring
    `tests/test_ocr_configurations_api.py`'s `_create_assessment` helper."""
    institution = Institution(
        name=f"Institution {code}", code=f"I-{code}", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    campus = Campus(institution_id=institution.id, name=f"Campus {code}", code=f"C-{code}")
    db_session.add(campus)
    await db_session.flush()

    department = Department(
        institution_id=institution.id, campus_id=campus.id, name=f"Dept {code}", code=f"D-{code}"
    )
    db_session.add(department)
    await db_session.flush()

    program = Program(
        institution_id=institution.id,
        department_id=department.id,
        name=f"Program {code}",
        code=f"P-{code}",
        degree_type="ug",
        duration_years=4,
        total_semesters=8,
    )
    db_session.add(program)
    await db_session.flush()

    course = Course(
        institution_id=institution.id,
        program_id=program.id,
        name=f"Course {code}",
        code=f"CO-{code}",
    )
    db_session.add(course)
    await db_session.flush()

    subject_category = SubjectCategory(
        institution_id=institution.id, code=f"CAT-{code}", name=f"Category {code}"
    )
    db_session.add(subject_category)
    await db_session.flush()

    subject = Subject(
        institution_id=institution.id,
        course_id=course.id,
        subject_category_id=subject_category.id,
        code=f"SUB-{code}",
        name=f"Subject {code}",
        credits=Decimal("4.0"),
        semester_number=1,
    )
    db_session.add(subject)
    await db_session.flush()

    assessment_type = AssessmentType(
        institution_id=institution.id, code=f"AT-{code}", name=f"Type {code}"
    )
    db_session.add(assessment_type)
    await db_session.flush()

    assessment_status = AssessmentStatus(
        institution_id=institution.id, code=f"AS-{code}", name=f"Status {code}"
    )
    db_session.add(assessment_status)
    await db_session.flush()

    assessment = Assessment(
        institution_id=institution.id,
        subject_id=subject.id,
        assessment_type_id=assessment_type.id,
        assessment_status_id=assessment_status.id,
        name=f"Assessment {code}",
    )
    db_session.add(assessment)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(assessment)
    return assessment


async def _create_provider(
    db_session: AsyncSession, *, code: str, **overrides: object
) -> AIProvider:
    defaults: dict[str, object] = {
        "code": code,
        "name": code.title(),
        "is_enabled": True,
        "is_implemented": True,
        "is_default": False,
    }
    defaults.update(overrides)
    provider = AIProvider(**defaults)  # type: ignore[arg-type]
    db_session.add(provider)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


def _payload(ai_provider_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ai_provider_id": str(ai_provider_id),
        "provider_config": {"model": "lexical-v1"},
    }
    payload.update(overrides)
    return payload


async def test_create_ai_configuration_as_institution_wide_default(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin1", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="CREATE")
    provider = await _create_provider(db_session, code="lexical_heuristic_c1")
    token = await _login(client, "aicadmin1")

    response = await client.post(
        "/api/v1/ai-configurations",
        json=_payload(provider.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["assessment_id"] is None
    assert body["ai_provider_id"] == str(provider.id)
    assert body["provider_config"] == {"model": "lexical-v1"}
    assert body["is_active"] is True


async def test_create_ai_configuration_scoped_to_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin2", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="SCOPED")
    provider = await _create_provider(db_session, code="lexical_heuristic_c2")
    token = await _login(client, "aicadmin2")

    response = await client.post(
        "/api/v1/ai-configurations",
        json=_payload(provider.id, assessment_id=str(assessment.id)),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    assert response.json()["assessment_id"] == str(assessment.id)


async def test_create_ai_configuration_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin3", role=seed_rbac["super_admin"])
    provider = await _create_provider(db_session, code="lexical_heuristic_c3")
    token = await _login(client, "aicadmin3")

    response = await client.post(
        "/api/v1/ai-configurations", json=_payload(provider.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_ai_configuration_rejects_nonexistent_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin4", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADPROVIDER")
    token = await _login(client, "aicadmin4")

    response = await client.post(
        "/api/v1/ai-configurations",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_create_ai_configuration_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin5", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADASSESSMENT")
    provider = await _create_provider(db_session, code="lexical_heuristic_c5")
    token = await _login(client, "aicadmin5")

    response = await client.post(
        "/api/v1/ai-configurations",
        json=_payload(provider.id, assessment_id=str(uuid.uuid4())),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_ai_configuration(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicstudent1", role=seed_rbac["student"])
    assessment = await _create_assessment(db_session, code="FORBIDDEN")
    provider = await _create_provider(db_session, code="lexical_heuristic_c6")
    token = await _login(client, "aicstudent1")

    response = await client.post(
        "/api/v1/ai-configurations",
        json=_payload(provider.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_ai_configuration_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin7", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="404")
    token = await _login(client, "aicadmin7")

    response = await client.get(
        f"/api/v1/ai-configurations/{uuid.uuid4()}",
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_ai_configuration_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin8", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="ROUNDTRIP")
    provider = await _create_provider(db_session, code="lexical_heuristic_c8")
    token = await _login(client, "aicadmin8")
    headers = _institution_headers(token, assessment.institution_id)

    create_response = await client.post(
        "/api/v1/ai-configurations", json=_payload(provider.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(f"/api/v1/ai-configurations/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["provider_config"] == {"model": "lexical-v1"}

    update_response = await client.patch(
        f"/api/v1/ai-configurations/{entity_id}",
        json={"provider_config": {"model": "lexical-v2"}, "is_active": False},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["provider_config"] == {"model": "lexical-v2"}
    assert updated_body["is_active"] is False
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/ai-configurations/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/ai-configurations/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/ai-configurations/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/ai-configurations/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/ai-configurations/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_ai_configurations_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="aicadmin9", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="LISTENV")
    provider = await _create_provider(db_session, code="lexical_heuristic_c9")
    token = await _login(client, "aicadmin9")
    headers = _institution_headers(token, assessment.institution_id)

    for _ in range(5):
        response = await client.post(
            "/api/v1/ai-configurations", json=_payload(provider.id), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/ai-configurations?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
