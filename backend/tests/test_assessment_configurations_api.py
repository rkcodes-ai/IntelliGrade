"""AssessmentConfiguration API tests: CRUD, tenancy, and 1:1/marks business rules."""

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


async def _create_assessment(db_session: AsyncSession, *, code: str = "ASM1") -> Assessment:
    """
    Builds the full Institution->Campus->Department->Program->Course->
    SubjectCategory->Subject->AssessmentType/AssessmentStatus->Assessment
    parent chain via direct ORM inserts, mirroring `tests/test_subjects_api.py`'s
    `_create_course_and_category` helper. `Assessment` is a sibling-wave
    model (`app/models/assessment.py`) — this helper uses its exact required
    fields (`subject_id`, `assessment_type_id`, `assessment_status_id`, `name`).
    """
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


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


def _payload(assessment_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assessment_id": str(assessment_id),
        "maximum_marks": "100.00",
        "passing_marks": "40.00",
        "negative_marks": "0.25",
        "grace_marks": "1.00",
        "time_limit_minutes": 60,
        "attempt_rules": {"max_attempts": 1, "allow_retake": False},
    }
    payload.update(overrides)
    return payload


async def test_create_assessment_configuration_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin1", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="CREATE")
    token = await _login(client, "acadmin1")

    response = await client.post(
        "/api/v1/assessment-configurations",
        json=_payload(assessment.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["assessment_id"] == str(assessment.id)
    assert body["maximum_marks"] == "100.00"
    assert body["passing_marks"] == "40.00"
    assert body["is_active"] is True
    assert body["attempt_rules"] == {"max_attempts": 1, "allow_retake": False}


async def test_create_assessment_configuration_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin2", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="NOHEADER")
    token = await _login(client, "acadmin2")

    response = await client.post(
        "/api/v1/assessment-configurations",
        json=_payload(assessment.id),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_assessment_configuration_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin3", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADPARENT")
    token = await _login(client, "acadmin3")

    response = await client.post(
        "/api/v1/assessment-configurations",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_create_assessment_configuration_rejects_passing_marks_above_maximum(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin4", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADMARKS")
    token = await _login(client, "acadmin4")

    response = await client.post(
        "/api/v1/assessment-configurations",
        json=_payload(assessment.id, maximum_marks="50.00", passing_marks="60.00"),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 422


async def test_create_assessment_configuration_rejects_duplicate_for_same_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin5", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="DUPE")
    token = await _login(client, "acadmin5")
    headers = _institution_headers(token, assessment.institution_id)

    first = await client.post(
        "/api/v1/assessment-configurations", json=_payload(assessment.id), headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/assessment-configurations", json=_payload(assessment.id), headers=headers
    )
    assert second.status_code == 409


async def test_non_privileged_role_cannot_create_assessment_configuration(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acstudent1", role=seed_rbac["student"])
    assessment = await _create_assessment(db_session, code="FORBIDDEN")
    token = await _login(client, "acstudent1")

    response = await client.post(
        "/api/v1/assessment-configurations",
        json=_payload(assessment.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 403


async def test_assessment_configuration_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin6", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="ROUNDTRIP")
    token = await _login(client, "acadmin6")
    headers = _institution_headers(token, assessment.institution_id)

    create_response = await client.post(
        "/api/v1/assessment-configurations", json=_payload(assessment.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    get_response = await client.get(
        f"/api/v1/assessment-configurations/{entity_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["maximum_marks"] == "100.00"

    update_response = await client.patch(
        f"/api/v1/assessment-configurations/{entity_id}",
        json={"maximum_marks": "150.00", "passing_marks": "50.00"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["maximum_marks"] == "150.00"
    assert updated_body["passing_marks"] == "50.00"
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    invalid_update = await client.patch(
        f"/api/v1/assessment-configurations/{entity_id}",
        json={"passing_marks": "999.00"},
        headers=headers,
    )
    assert invalid_update.status_code == 422

    delete_response = await client.delete(
        f"/api/v1/assessment-configurations/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/assessment-configurations/{entity_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/assessment-configurations/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/assessment-configurations/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/assessment-configurations/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_assessment_configuration_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin7", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="404")
    token = await _login(client, "acadmin7")

    response = await client.get(
        f"/api/v1/assessment-configurations/{uuid.uuid4()}",
        headers=_institution_headers(token, assessment.institution_id),
    )
    assert response.status_code == 404


async def test_list_assessment_configurations_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin8", role=seed_rbac["super_admin"])
    token = await _login(client, "acadmin8")

    entity_ids: list[str] = []
    for i in range(5):
        assessment = await _create_assessment(db_session, code=f"LIST{i}")
        headers = _institution_headers(token, assessment.institution_id)
        response = await client.post(
            "/api/v1/assessment-configurations", json=_payload(assessment.id), headers=headers
        )
        assert response.status_code == 201
        entity_ids.append(response.json()["id"])

    # All 5 assessments were created under distinct institutions, so list
    # from the last one's institution and expect exactly 1 item there,
    # then verify the pagination envelope shape directly.
    last_headers = _institution_headers(token, assessment.institution_id)
    response = await client.get(
        "/api/v1/assessment-configurations?page=1&page_size=2", headers=last_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 2


async def test_bulk_create_assessment_configurations_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="acadmin9", role=seed_rbac["super_admin"])
    assessment_a = await _create_assessment(db_session, code="BULKA")
    token = await _login(client, "acadmin9")
    headers = _institution_headers(token, assessment_a.institution_id)

    # A second assessment under the SAME institution for the "created" case;
    # the duplicate case re-uses assessment_a's id.
    institution_id = assessment_a.institution_id
    assessment_b = Assessment(
        institution_id=institution_id,
        subject_id=assessment_a.subject_id,
        assessment_type_id=assessment_a.assessment_type_id,
        assessment_status_id=assessment_a.assessment_status_id,
        name="Second Assessment BULKA",
    )
    db_session.add(assessment_b)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(assessment_b)

    response = await client.post(
        "/api/v1/assessment-configurations/bulk",
        json=[
            _payload(assessment_a.id),
            _payload(assessment_a.id),  # duplicate for the same assessment -> 409
            _payload(assessment_b.id),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1
