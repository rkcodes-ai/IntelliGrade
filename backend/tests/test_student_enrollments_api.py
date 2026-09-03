"""Student enrollment API tests: CRUD, tenancy, and enrollment/roll-number conflict rules."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_status import AcademicStatus
from app.models.academic_year import AcademicYear
from app.models.batch import Batch
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.section import Section
from app.models.semester import Semester
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


class _EnrollmentFixture:
    def __init__(
        self,
        institution: Institution,
        course: Course,
        batch: Batch,
        section: Section,
        academic_year: AcademicYear,
        semester: Semester,
        academic_status: AcademicStatus,
    ) -> None:
        self.institution = institution
        self.course = course
        self.batch = batch
        self.section = section
        self.academic_year = academic_year
        self.semester = semester
        self.academic_status = academic_status


async def _build_fixture(
    db_session: AsyncSession, *, code: str, max_capacity: int = 60
) -> _EnrollmentFixture:
    """Builds the full parent chain a `StudentEnrollment` needs, committed."""
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
        code=f"CR-{code}",
    )
    db_session.add(course)
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
        institution_id=institution.id,
        batch_id=batch.id,
        name=f"Sec-{code}",
        max_capacity=max_capacity,
    )
    db_session.add(section)
    await db_session.flush()

    academic_year = AcademicYear(
        institution_id=institution.id,
        year_label=f"2025-{code}",
        start_date=date(2025, 6, 1),
        end_date=date(2026, 5, 31),
    )
    db_session.add(academic_year)
    await db_session.flush()

    semester = Semester(
        institution_id=institution.id,
        academic_year_id=academic_year.id,
        name=f"Sem 1 {code}",
        semester_number=1,
        term_type="odd",
        start_date=date(2025, 6, 1),
        end_date=date(2025, 11, 30),
    )
    db_session.add(semester)
    await db_session.flush()

    academic_status = AcademicStatus(
        institution_id=institution.id, code=f"ACTIVE-{code}", name="Active"
    )
    db_session.add(academic_status)
    await db_session.flush()
    await db_session.commit()

    for entity in (institution, course, batch, section, academic_year, semester, academic_status):
        await db_session.refresh(entity)

    return _EnrollmentFixture(
        institution, course, batch, section, academic_year, semester, academic_status
    )


def _payload(fixture: _EnrollmentFixture, student_id: uuid.UUID, *, roll_number: str) -> dict:
    return {
        "student_user_id": str(student_id),
        "batch_id": str(fixture.batch.id),
        "section_id": str(fixture.section.id),
        "course_id": str(fixture.course.id),
        "academic_year_id": str(fixture.academic_year.id),
        "semester_id": str(fixture.semester.id),
        "academic_status_id": str(fixture.academic_status.id),
        "roll_number": roll_number,
        "enrollment_date": "2025-06-05",
    }


async def test_create_student_enrollment_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin1", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="CREATE")
    student = await create_test_user(db_session, username="student_create")
    token = await _login(client, "seadmin1")

    response = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["student_user_id"] == str(student.id)
    assert body["roll_number"] == "R001"
    assert body["is_active"] is True


async def test_create_student_enrollment_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin2", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="NOHEADER")
    student = await create_test_user(db_session, username="student_noheader")
    token = await _login(client, "seadmin2")

    response = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_student_enrollment_rejects_nonexistent_batch(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin3", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADPARENT")
    student = await create_test_user(db_session, username="student_badparent")
    token = await _login(client, "seadmin3")

    payload = _payload(fixture, student.id, roll_number="R001")
    payload["batch_id"] = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/student-enrollments",
        json=payload,
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_student_enrollment_rejects_duplicate_enrollment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """ "Student enrollment conflicts": one enrollment per (student, year, semester)."""
    await create_test_user(db_session, username="seadmin4", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="DUPEENROLL")
    student = await create_test_user(db_session, username="student_dupeenroll")
    token = await _login(client, "seadmin4")
    headers = _institution_headers(token, fixture.institution.id)

    first = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R002"),
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_student_enrollment_rejects_duplicate_roll_number(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin5", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="DUPEROLL")
    student1 = await create_test_user(db_session, username="student_dupe_roll_1")
    student2 = await create_test_user(db_session, username="student_dupe_roll_2")
    token = await _login(client, "seadmin5")
    headers = _institution_headers(token, fixture.institution.id)

    first = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student1.id, roll_number="R001"),
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student2.id, roll_number="R001"),
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_student_enrollment_rejects_when_section_at_capacity(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin6", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="CAPACITY", max_capacity=1)
    student1 = await create_test_user(db_session, username="student_capacity_1")
    student2 = await create_test_user(db_session, username="student_capacity_2")
    token = await _login(client, "seadmin6")
    headers = _institution_headers(token, fixture.institution.id)

    first = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student1.id, roll_number="R001"),
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student2.id, roll_number="R002"),
        headers=headers,
    )
    assert second.status_code == 409


async def test_non_privileged_role_cannot_create_student_enrollment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="sestudent1", role=seed_rbac["student"])
    fixture = await _build_fixture(db_session, code="FORBIDDEN")
    student = await create_test_user(db_session, username="student_forbidden")
    token = await _login(client, "sestudent1")

    response = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 403


async def test_student_enrollment_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin7", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="ROUNDTRIP")
    student = await create_test_user(db_session, username="student_roundtrip")
    token = await _login(client, "seadmin7")
    headers = _institution_headers(token, fixture.institution.id)

    create_response = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/student-enrollments/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["roll_number"] == "R001"

    # Real HTTP round-trip through the update endpoint — regression test for
    # the "known bug" (missing `session.refresh()` after an UPDATE flush).
    update_response = await client.patch(
        f"/api/v1/student-enrollments/{entity_id}",
        json={"roll_number": "R001-B"},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["roll_number"] == "R001-B"
    assert "updated_at" in body and body["updated_at"]

    delete_response = await client.delete(
        f"/api/v1/student-enrollments/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/student-enrollments/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/student-enrollments/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/student-enrollments/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/student-enrollments/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_student_enrollment_status_change_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin8", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="STATUSCHANGE")
    student = await create_test_user(db_session, username="student_statuschange")
    token = await _login(client, "seadmin8")
    headers = _institution_headers(token, fixture.institution.id)

    create_response = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    assert create_response.json()["academic_status_id"] == str(fixture.academic_status.id)

    new_status = AcademicStatus(
        institution_id=fixture.institution.id, code="GRADUATED-STATUSCHANGE", name="Graduated"
    )
    db_session.add(new_status)
    await db_session.commit()
    await db_session.refresh(new_status)

    status_response = await client.patch(
        f"/api/v1/student-enrollments/{entity_id}/status",
        json={"new_status_id": str(new_status.id)},
        headers=headers,
    )
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["academic_status_id"] == str(new_status.id)
    assert "updated_at" in body and body["updated_at"]

    bad_status_response = await client.patch(
        f"/api/v1/student-enrollments/{entity_id}/status",
        json={"new_status_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert bad_status_response.status_code == 404


async def test_list_student_enrollments_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin9", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="LIST", max_capacity=10)
    token = await _login(client, "seadmin9")
    headers = _institution_headers(token, fixture.institution.id)

    for i in range(3):
        student = await create_test_user(db_session, username=f"student_list_{i}")
        response = await client.post(
            "/api/v1/student-enrollments",
            json=_payload(fixture, student.id, roll_number=f"R00{i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/student-enrollments?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 3


async def test_bulk_create_student_enrollments_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin10", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BULK")
    student_one = await create_test_user(db_session, username="student_bulk_1")
    student_two = await create_test_user(db_session, username="student_bulk_2")
    token = await _login(client, "seadmin10")
    headers = _institution_headers(token, fixture.institution.id)

    response = await client.post(
        "/api/v1/student-enrollments/bulk",
        json=[
            _payload(fixture, student_one.id, roll_number="R100"),
            _payload(fixture, student_one.id, roll_number="R101"),
            _payload(fixture, student_two.id, roll_number="R102"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_student_enrollment_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin11", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="IMPEXP")
    token = await _login(client, "seadmin11")
    headers = _institution_headers(token, fixture.institution.id)

    import_response = await client.post("/api/v1/student-enrollments/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/student-enrollments/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"


async def test_create_student_enrollment_rejects_each_missing_related_entity(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin12", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="MISSING")
    student = await create_test_user(db_session, username="student_missing")
    token = await _login(client, "seadmin12")
    headers = _institution_headers(token, fixture.institution.id)

    for field in (
        "student_user_id",
        "section_id",
        "course_id",
        "academic_year_id",
        "semester_id",
        "academic_status_id",
    ):
        payload = _payload(fixture, student.id, roll_number=f"R-{field}")
        payload[field] = str(uuid.uuid4())
        response = await client.post("/api/v1/student-enrollments", json=payload, headers=headers)
        assert response.status_code == 404, f"field={field}"


async def test_update_student_enrollment_rejects_each_missing_related_entity(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin13", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="UPDMISSING")
    student = await create_test_user(db_session, username="student_updmissing")
    token = await _login(client, "seadmin13")
    headers = _institution_headers(token, fixture.institution.id)

    create_response = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student.id, roll_number="R001"),
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    for field in (
        "student_user_id",
        "batch_id",
        "section_id",
        "course_id",
        "academic_year_id",
        "semester_id",
        "academic_status_id",
    ):
        response = await client.patch(
            f"/api/v1/student-enrollments/{entity_id}",
            json={field: str(uuid.uuid4())},
            headers=headers,
        )
        assert response.status_code == 404, f"field={field}"


async def test_update_student_enrollment_enforces_conflict_and_capacity_checks(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="seadmin14", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="UPDCONFLICT")
    student_a = await create_test_user(db_session, username="student_updconflict_a")
    student_b = await create_test_user(db_session, username="student_updconflict_b")
    student_c = await create_test_user(db_session, username="student_updconflict_c")
    token = await _login(client, "seadmin14")
    headers = _institution_headers(token, fixture.institution.id)

    enrollment_a = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student_a.id, roll_number="R001"),
        headers=headers,
    )
    assert enrollment_a.status_code == 201

    enrollment_b = await client.post(
        "/api/v1/student-enrollments",
        json=_payload(fixture, student_b.id, roll_number="R002"),
        headers=headers,
    )
    assert enrollment_b.status_code == 201
    enrollment_b_id = enrollment_b.json()["id"]

    # Promoting enrollment B's student to A's student conflicts on
    # (student, academic_year, semester).
    conflict_response = await client.patch(
        f"/api/v1/student-enrollments/{enrollment_b_id}",
        json={"student_user_id": str(student_a.id)},
        headers=headers,
    )
    assert conflict_response.status_code == 409

    # Renaming B's roll number to A's conflicts on (section, roll_number).
    roll_conflict_response = await client.patch(
        f"/api/v1/student-enrollments/{enrollment_b_id}",
        json={"roll_number": "R001"},
        headers=headers,
    )
    assert roll_conflict_response.status_code == 409

    second_section = await client.post(
        "/api/v1/sections",
        json={"batch_id": str(fixture.batch.id), "name": "Overflow", "max_capacity": 1},
        headers=headers,
    )
    assert second_section.status_code == 201
    second_section_id = second_section.json()["id"]

    filler_same_institution = await client.post(
        "/api/v1/student-enrollments",
        json={
            **_payload(fixture, student_c.id, roll_number="F002"),
            "section_id": second_section_id,
        },
        headers=headers,
    )
    assert filler_same_institution.status_code == 201

    capacity_response = await client.patch(
        f"/api/v1/student-enrollments/{enrollment_b_id}",
        json={"section_id": second_section_id},
        headers=headers,
    )
    assert capacity_response.status_code == 409
