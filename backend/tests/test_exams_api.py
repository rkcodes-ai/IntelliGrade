"""Exam management API tests: CRUD, tenancy, and parent-FK business rules."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.batch import Batch
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.section import Section
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_assessment_and_section(
    db_session: AsyncSession, *, code: str = "EXM1"
) -> tuple[Assessment, Section]:
    """
    Builds the full Institution->Campus->Department->Program->Course->
    SubjectCategory->Subject->AssessmentType/AssessmentStatus->Assessment
    parent chain (mirroring `tests/test_assessment_configurations_api.py`'s
    `_create_assessment()` helper), plus a `Batch`->`Section` under the same
    `Course` (mirroring `tests/test_sections_api.py`'s `_create_batch()`
    helper), so `Exam` has both parents it needs.
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

    batch = Batch(
        institution_id=institution.id,
        course_id=course.id,
        name=f"Batch {code}",
        start_year=2024,
        end_year=2028,
    )
    db_session.add(batch)
    await db_session.flush()

    section = Section(
        institution_id=institution.id, batch_id=batch.id, name=f"Sec-{code}", max_capacity=60
    )
    db_session.add(section)
    await db_session.flush()

    await db_session.commit()
    await db_session.refresh(assessment)
    await db_session.refresh(section)
    return assessment, section


async def _create_second_assessment_and_section(
    db_session: AsyncSession, assessment: Assessment, section: Section, *, code: str
) -> tuple[Assessment, Section]:
    """Sibling `Assessment`/`Section` in the same institution, reusing the
    first pair's parent FKs, so tests can PATCH `assessment_id`/`section_id`
    to a different-but-still-valid parent within the same tenant."""
    second_assessment = Assessment(
        institution_id=assessment.institution_id,
        subject_id=assessment.subject_id,
        assessment_type_id=assessment.assessment_type_id,
        assessment_status_id=assessment.assessment_status_id,
        name=f"Assessment {code}",
    )
    db_session.add(second_assessment)
    await db_session.flush()

    second_section = Section(
        institution_id=section.institution_id,
        batch_id=section.batch_id,
        name=f"Sec-{code}",
        max_capacity=60,
    )
    db_session.add(second_section)
    await db_session.flush()

    await db_session.commit()
    await db_session.refresh(second_assessment)
    await db_session.refresh(second_section)
    return second_assessment, second_section


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


def _payload(
    assessment_id: uuid.UUID, section_id: uuid.UUID, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "assessment_id": str(assessment_id),
        "section_id": str(section_id),
        "name": "Midterm Exam",
        "exam_date": "2026-08-10",
    }
    payload.update(overrides)
    return payload


async def test_create_exam_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin1", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="CREATE")
    token = await _login(client, "examadmin1")

    response = await client.post(
        "/api/v1/exams",
        json=_payload(assessment.id, section.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Midterm Exam"
    assert body["exam_date"] == "2026-08-10"
    assert body["assessment_id"] == str(assessment.id)
    assert body["section_id"] == str(section.id)
    assert body["is_active"] is True
    assert body["current_version"] == 1


async def test_create_exam_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin2", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="NOHEADER")
    token = await _login(client, "examadmin2")

    response = await client.post(
        "/api/v1/exams", json=_payload(assessment.id, section.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_exam_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin3", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="BADASSESS")
    token = await _login(client, "examadmin3")

    response = await client.post(
        "/api/v1/exams",
        json=_payload(uuid.uuid4(), section.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_create_exam_rejects_nonexistent_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin4", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="BADSECTION")
    token = await _login(client, "examadmin4")

    response = await client.post(
        "/api/v1/exams",
        json=_payload(assessment.id, uuid.uuid4()),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examstudent1", role=seed_rbac["student"])
    assessment, section = await _create_assessment_and_section(db_session, code="FORBIDDEN")
    token = await _login(client, "examstudent1")

    response = await client.post(
        "/api/v1/exams",
        json=_payload(assessment.id, section.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 403


async def test_exam_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin5", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="ROUNDTRIP")
    token = await _login(client, "examadmin5")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/exams", json=_payload(assessment.id, section.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/exams/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Midterm Exam"

    update_response = await client.patch(
        f"/api/v1/exams/{entity_id}",
        json={"name": "Re-exam", "exam_date": "2026-09-01"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["name"] == "Re-exam"
    assert updated_body["exam_date"] == "2026-09-01"
    assert updated_body["current_version"] == 2
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/exams/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/exams/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/exams/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(f"/api/v1/exams/{entity_id}/restore", headers=headers)
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/exams/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_exam_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin6", role=seed_rbac["super_admin"])
    assessment, _section = await _create_assessment_and_section(db_session, code="404")
    token = await _login(client, "examadmin6")

    response = await client.get(
        f"/api/v1/exams/{uuid.uuid4()}",
        headers=_institution_headers(token, assessment.institution_id),
    )
    assert response.status_code == 404


async def test_list_exams_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin7", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="PAGE")
    token = await _login(client, "examadmin7")
    headers = _institution_headers(token, assessment.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/exams",
            json=_payload(assessment.id, section.id, name=f"Exam {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/exams?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5
    assert body["total_pages"] >= 3


async def test_bulk_create_exams_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="exambulk1", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="BULK")
    token = await _login(client, "exambulk1")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.post(
        "/api/v1/exams/bulk",
        json=[
            _payload(assessment.id, section.id, name="Exam One"),
            _payload(assessment.id, section.id, name="Exam Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_exams_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="exambulk2", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="BULKERR")
    token = await _login(client, "exambulk2")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.post(
        "/api/v1/exams/bulk",
        json=[
            _payload(assessment.id, section.id, name="Valid Exam"),
            _payload(assessment.id, uuid.uuid4(), name="Orphan Exam"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["name"] == "Orphan Exam"


async def test_export_exams_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "examexport1")

    response = await client.get("/api/v1/exams/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_exams_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "examimport1")

    response = await client.post("/api/v1/exams/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_exam_accepts_new_assessment_and_section_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin8", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="UPDFK")
    other_assessment, other_section = await _create_second_assessment_and_section(
        db_session, assessment, section, code="UPDFK2"
    )
    token = await _login(client, "examadmin8")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/exams", json=_payload(assessment.id, section.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exams/{entity_id}",
        json={"assessment_id": str(other_assessment.id), "section_id": str(other_section.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["assessment_id"] == str(other_assessment.id)
    assert body["section_id"] == str(other_section.id)


async def test_update_exam_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin9", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="UPDBADA")
    token = await _login(client, "examadmin9")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/exams", json=_payload(assessment.id, section.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exams/{entity_id}",
        json={"assessment_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_exam_rejects_nonexistent_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="examadmin10", role=seed_rbac["super_admin"])
    assessment, section = await _create_assessment_and_section(db_session, code="UPDBADS")
    token = await _login(client, "examadmin10")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/exams", json=_payload(assessment.id, section.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exams/{entity_id}",
        json={"section_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404
