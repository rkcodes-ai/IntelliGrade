"""Exam session API tests: CRUD, tenancy, parent-FK, and duplicate-session business rules."""

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
from app.models.user import User
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_exam(db_session: AsyncSession, *, code: str = "ESN1") -> Exam:
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
    """Sibling `Exam` in the same institution, reusing `assessment_id`/`section_id`
    (no uniqueness constraint on that pair), so tests can PATCH `exam_id` to a
    different-but-still-valid exam within the same tenant."""
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


def _payload(
    exam_id: uuid.UUID, student_user_id: uuid.UUID, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "exam_id": str(exam_id),
        "student_user_id": str(student_user_id),
    }
    payload.update(overrides)
    return payload


async def test_create_exam_session_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin1", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="CREATE")
    student = await create_test_user(db_session, username="essstud1")
    token = await _login(client, "essadmin1")

    response = await client.post(
        "/api/v1/exam-sessions",
        json=_payload(exam.id, student.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["exam_id"] == str(exam.id)
    assert body["student_user_id"] == str(student.id)
    assert body["status"] == "not_started"
    assert body["is_active"] is True


async def test_create_exam_session_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin2", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="NOHEADER")
    student = await create_test_user(db_session, username="essstud2")
    token = await _login(client, "essadmin2")

    response = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_exam_session_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin3", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BADPARENT")
    student = await create_test_user(db_session, username="essstud3")
    token = await _login(client, "essadmin3")

    response = await client.post(
        "/api/v1/exam-sessions",
        json=_payload(uuid.uuid4(), student.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_exam_session(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essstudent1", role=seed_rbac["student"])
    exam = await _create_exam(db_session, code="FORBIDDEN")
    student = await create_test_user(db_session, username="essstud4")
    token = await _login(client, "essstudent1")

    response = await client.post(
        "/api/v1/exam-sessions",
        json=_payload(exam.id, student.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 403


async def test_create_exam_session_rejects_duplicate_for_same_exam_and_student(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin4", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="DUPE")
    student = await create_test_user(db_session, username="essstud5")
    token = await _login(client, "essadmin4")
    headers = _institution_headers(token, exam.institution_id)

    first = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=headers
    )
    assert second.status_code == 409


async def test_exam_session_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin5", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="ROUNDTRIP")
    student = await create_test_user(db_session, username="essstud6")
    token = await _login(client, "essadmin5")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/exam-sessions/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "not_started"

    update_response = await client.patch(
        f"/api/v1/exam-sessions/{entity_id}",
        json={"status": "in_progress", "started_at": "2026-08-10T09:00:00Z"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["status"] == "in_progress"
    assert updated_body["started_at"] is not None
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/exam-sessions/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/exam-sessions/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/exam-sessions/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/exam-sessions/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/exam-sessions/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_exam_session_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin6", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="404")
    token = await _login(client, "essadmin6")

    response = await client.get(
        f"/api/v1/exam-sessions/{uuid.uuid4()}",
        headers=_institution_headers(token, exam.institution_id),
    )
    assert response.status_code == 404


async def test_list_exam_sessions_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin7", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="PAGE")
    token = await _login(client, "essadmin7")
    headers = _institution_headers(token, exam.institution_id)

    students: list[User] = []
    for i in range(5):
        student = await create_test_user(db_session, username=f"essstudpage{i}")
        students.append(student)
        response = await client.post(
            "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=headers
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/exam-sessions?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_bulk_create_exam_sessions_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essbulk1", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BULK")
    student1 = await create_test_user(db_session, username="essbulkstud1")
    student2 = await create_test_user(db_session, username="essbulkstud2")
    token = await _login(client, "essbulk1")
    headers = _institution_headers(token, exam.institution_id)

    response = await client.post(
        "/api/v1/exam-sessions/bulk",
        json=[_payload(exam.id, student1.id), _payload(exam.id, student2.id)],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_exam_sessions_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essbulk2", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="BULKERR")
    student = await create_test_user(db_session, username="essbulkstud3")
    token = await _login(client, "essbulk2")
    headers = _institution_headers(token, exam.institution_id)
    bad_exam_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/exam-sessions/bulk",
        json=[_payload(exam.id, student.id), _payload(bad_exam_id, student.id)],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["exam_id"] == str(bad_exam_id)


async def test_export_exam_sessions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "essexport1")

    response = await client.get("/api/v1/exam-sessions/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_exam_sessions_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "essimport1")

    response = await client.post("/api/v1/exam-sessions/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_exam_session_accepts_new_exam_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin8", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPDFK")
    other_exam = await _create_second_exam(db_session, exam, code="UPDFK2")
    student = await create_test_user(db_session, username="essstudupd1")
    token = await _login(client, "essadmin8")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-sessions/{entity_id}",
        json={"exam_id": str(other_exam.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["exam_id"] == str(other_exam.id)


async def test_update_exam_session_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin9", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPDBAD")
    student = await create_test_user(db_session, username="essstudupd2")
    token = await _login(client, "essadmin9")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-sessions/{entity_id}",
        json={"exam_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_exam_session_rejects_duplicate_after_student_change(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="essadmin10", role=seed_rbac["super_admin"])
    exam = await _create_exam(db_session, code="UPDDUPE")
    student_a = await create_test_user(db_session, username="essstudupd3")
    student_b = await create_test_user(db_session, username="essstudupd4")
    token = await _login(client, "essadmin10")
    headers = _institution_headers(token, exam.institution_id)

    session_a = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student_a.id), headers=headers
    )
    assert session_a.status_code == 201

    session_b = await client.post(
        "/api/v1/exam-sessions", json=_payload(exam.id, student_b.id), headers=headers
    )
    assert session_b.status_code == 201
    entity_id = session_b.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-sessions/{entity_id}",
        json={"student_user_id": str(student_a.id)},
        headers=headers,
    )

    assert update_response.status_code == 409
