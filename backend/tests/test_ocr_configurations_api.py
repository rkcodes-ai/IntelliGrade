"""OCRConfiguration API tests: CRUD, tenancy, and provider/assessment validation business rules."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.ocr_provider import OCRProvider
from app.models.program import Program
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
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


async def _create_assessment(db_session: AsyncSession, *, code: str) -> Assessment:
    """Builds the full Module 03/04 parent chain an `Assessment` needs, mirroring
    `tests/test_assessment_configurations_api.py`'s `_create_assessment` helper."""
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
) -> OCRProvider:
    defaults: dict[str, object] = {
        "code": code,
        "name": code.title(),
        "is_enabled": True,
        "is_implemented": True,
        "is_default": False,
    }
    defaults.update(overrides)
    provider = OCRProvider(**defaults)  # type: ignore[arg-type]
    db_session.add(provider)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


def _payload(ocr_provider_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ocr_provider_id": str(ocr_provider_id),
        "language": "eng",
        "confidence_threshold": "75.50",
        "preprocessing_steps": ["deskew", "denoise"],
        "max_retry_attempts": 3,
    }
    payload.update(overrides)
    return payload


async def test_create_ocr_configuration_as_institution_wide_default(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin1", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="CREATE")
    provider = await _create_provider(db_session, code="tesseract_c1")
    token = await _login(client, "ocfadmin1")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(provider.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["assessment_id"] is None
    assert body["ocr_provider_id"] == str(provider.id)
    assert body["language"] == "eng"
    assert body["confidence_threshold"] == "75.50"
    assert body["preprocessing_steps"] == ["deskew", "denoise"]
    assert body["is_active"] is True


async def test_create_ocr_configuration_scoped_to_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin2", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="SCOPED")
    provider = await _create_provider(db_session, code="tesseract_c2")
    token = await _login(client, "ocfadmin2")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(provider.id, assessment_id=str(assessment.id)),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    assert response.json()["assessment_id"] == str(assessment.id)


async def test_create_ocr_configuration_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin3", role=seed_rbac["super_admin"])
    provider = await _create_provider(db_session, code="tesseract_c3")
    token = await _login(client, "ocfadmin3")

    response = await client.post(
        "/api/v1/ocr-configurations", json=_payload(provider.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_ocr_configuration_rejects_nonexistent_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin4", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADPROVIDER")
    token = await _login(client, "ocfadmin4")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_create_ocr_configuration_rejects_disabled_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin5", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="DISABLED")
    provider = await _create_provider(db_session, code="disabled_engine", is_enabled=False)
    token = await _login(client, "ocfadmin5")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(provider.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 422


async def test_create_ocr_configuration_rejects_unimplemented_provider(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin6", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UNIMPL")
    provider = await _create_provider(
        db_session, code="unimplemented_engine", is_enabled=False, is_implemented=False
    )
    token = await _login(client, "ocfadmin6")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(provider.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 422


async def test_create_ocr_configuration_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin7", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADASSESSMENT")
    provider = await _create_provider(db_session, code="tesseract_c7")
    token = await _login(client, "ocfadmin7")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(provider.id, assessment_id=str(uuid.uuid4())),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_ocr_configuration(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfstudent1", role=seed_rbac["student"])
    assessment = await _create_assessment(db_session, code="FORBIDDEN")
    provider = await _create_provider(db_session, code="tesseract_c8")
    token = await _login(client, "ocfstudent1")

    response = await client.post(
        "/api/v1/ocr-configurations",
        json=_payload(provider.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_ocr_configuration_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin8", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="404")
    token = await _login(client, "ocfadmin8")

    response = await client.get(
        f"/api/v1/ocr-configurations/{uuid.uuid4()}",
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_ocr_configuration_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin9", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="ROUNDTRIP")
    provider = await _create_provider(db_session, code="tesseract_c9")
    token = await _login(client, "ocfadmin9")
    headers = _institution_headers(token, assessment.institution_id)

    create_response = await client.post(
        "/api/v1/ocr-configurations", json=_payload(provider.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(f"/api/v1/ocr-configurations/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["language"] == "eng"

    update_response = await client.patch(
        f"/api/v1/ocr-configurations/{entity_id}",
        json={"language": "fra", "max_retry_attempts": 5},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["language"] == "fra"
    assert updated_body["max_retry_attempts"] == 5
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(
        f"/api/v1/ocr-configurations/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/ocr-configurations/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/ocr-configurations/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/ocr-configurations/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/ocr-configurations/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_ocr_configurations_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="ocfadmin10", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="LISTENV")
    provider = await _create_provider(db_session, code="tesseract_c10")
    token = await _login(client, "ocfadmin10")
    headers = _institution_headers(token, assessment.institution_id)

    for _ in range(5):
        response = await client.post(
            "/api/v1/ocr-configurations", json=_payload(provider.id), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/ocr-configurations?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
