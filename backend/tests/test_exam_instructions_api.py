"""Exam instructions management API tests: CRUD, tenancy, and parent-FK business rules."""

import uuid
from datetime import date
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
from app.models.exam import Exam
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


async def _create_exam(db_session: AsyncSession, *, code: str = "EXI1") -> Exam:
    """
    Builds the full Institution->Campus->Department->Program->Course->
    SubjectCategory->Subject->AssessmentType/AssessmentStatus->Assessment
    (-> Batch->Section) ->Exam parent chain via direct ORM inserts.
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

    exam = Exam(
        institution_id=institution.id,
        assessment_id=assessment.id,
        section_id=section.id,
        name=f"Exam {code}",
        exam_date=date(2026, 8, 10),
    )
    db_session.add(exam)
    await db_session.flush()

    await db_session.commit()
    await db_session.refresh(exam)
    return exam


async def _create_second_exam(db_session: AsyncSession, exam: Exam, *, code: str) -> Exam:
    """
    Builds a sibling `Exam` in the same institution as `exam`, reusing its
    `assessment_id`/`section_id` (no uniqueness constraint on that pair —
    see `Exam`'s docstring), so tests can PATCH `exam_id` to a different-but-
    still-valid exam within the same tenant.
    """
    second_exam = Exam(
        institution_id=exam.institution_id,
        assessment_id=exam.assessment_id,
        section_id=exam.section_id,
        name=f"Exam {code}",
        exam_date=date(2026, 9, 1),
    )
    db_session.add(second_exam)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(second_exam)
    return second_exam


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


def _payload(exam_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "exam_id": str(exam_id),
        "instructions_text": "Bring your ID card.",
        "display_order": 1,
    }
    payload.update(overrides)
    return payload


async def test_create_exam_instructions_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin1", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="CREATE")
    token = await _login(client, "eiadmin1")

    response = await client.post(
        "/api/v1/exam-instructions",
        json=_payload(exam.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["exam_id"] == str(exam.id)
    assert body["instructions_text"] == "Bring your ID card."
    assert body["display_order"] == 1
    assert body["is_active"] is True


async def test_create_exam_instructions_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin2", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="NOHEADER")
    token = await _login(client, "eiadmin2")

    response = await client.post(
        "/api/v1/exam-instructions", json=_payload(exam.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_exam_instructions_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin3", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BADPARENT")
    token = await _login(client, "eiadmin3")

    response = await client.post(
        "/api/v1/exam-instructions",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_exam_instructions(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eistudent1", role=seed_rbac["student"])
    exam = await _create_exam(db_session, code="FORBIDDEN")
    token = await _login(client, "eistudent1")

    response = await client.post(
        "/api/v1/exam-instructions",
        json=_payload(exam.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 403


async def test_exam_instructions_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin4", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="ROUNDTRIP")
    token = await _login(client, "eiadmin4")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-instructions", json=_payload(exam.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/exam-instructions/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["instructions_text"] == "Bring your ID card."

    update_response = await client.patch(
        f"/api/v1/exam-instructions/{entity_id}",
        json={"instructions_text": "No calculators allowed.", "display_order": 2},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["instructions_text"] == "No calculators allowed."
    assert updated_body["display_order"] == 2
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/exam-instructions/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/exam-instructions/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/exam-instructions/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/exam-instructions/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/exam-instructions/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_exam_instructions_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin5", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="404")
    token = await _login(client, "eiadmin5")

    response = await client.get(
        f"/api/v1/exam-instructions/{uuid.uuid4()}",
        headers=_institution_headers(token, exam.institution_id),
    )
    assert response.status_code == 404


async def test_list_exam_instructions_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin6", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="PAGE")
    token = await _login(client, "eiadmin6")
    headers = _institution_headers(token, exam.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/exam-instructions",
            json=_payload(exam.id, instructions_text=f"Instruction {i}", display_order=i),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/exam-instructions?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5
    assert body["total_pages"] >= 3


async def test_bulk_create_exam_instructions_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eibulk1", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BULK")
    token = await _login(client, "eibulk1")
    headers = _institution_headers(token, exam.institution_id)

    response = await client.post(
        "/api/v1/exam-instructions/bulk",
        json=[
            _payload(exam.id, instructions_text="Instruction one", display_order=1),
            _payload(exam.id, instructions_text="Instruction two", display_order=2),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_exam_instructions_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eibulk2", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BULKERR")
    token = await _login(client, "eibulk2")
    headers = _institution_headers(token, exam.institution_id)
    bad_exam_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/exam-instructions/bulk",
        json=[
            _payload(exam.id, instructions_text="Valid instruction"),
            _payload(bad_exam_id, instructions_text="Orphan instruction"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["exam_id"] == str(bad_exam_id)


async def test_export_exam_instructions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "eiexport1")

    response = await client.get("/api/v1/exam-instructions/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_exam_instructions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "eiimport1")

    response = await client.post("/api/v1/exam-instructions/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_exam_instructions_accepts_new_exam_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin7", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPDFK")
    other_exam = await _create_second_exam(db_session, exam, code="UPDFK2")
    token = await _login(client, "eiadmin7")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-instructions", json=_payload(exam.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-instructions/{entity_id}",
        json={"exam_id": str(other_exam.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["exam_id"] == str(other_exam.id)


async def test_update_exam_instructions_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="eiadmin8", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPDBAD")
    token = await _login(client, "eiadmin8")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-instructions", json=_payload(exam.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-instructions/{entity_id}",
        json={"exam_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404
