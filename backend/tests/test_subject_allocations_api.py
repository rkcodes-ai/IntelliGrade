"""SubjectAllocation API tests: CRUD, tenancy, and multi-parent-FK/uniqueness business rules.

`Section`/`Semester`/`Batch` are owned by a parallel sibling agent in the
same wave as `SubjectAllocation`; by the time this file runs, their model
files exist on disk (confirmed via `app/repositories/section_repository.py`
and `app/repositories/semester_repository.py`), so the full FK chain is
built with real ORM rows here rather than mocked out.
"""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic_year import AcademicYear
from app.models.batch import Batch
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.room import Room
from app.models.section import Section
from app.models.semester import Semester
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


class Fixture:
    def __init__(
        self,
        institution: Institution,
        subject: Subject,
        section: Section,
        semester: Semester,
        academic_year: AcademicYear,
        teacher: User,
        room: Room,
    ) -> None:
        self.institution = institution
        self.subject = subject
        self.section = section
        self.semester = semester
        self.academic_year = academic_year
        self.teacher = teacher
        self.room = room


async def _build_fixture(db_session: AsyncSession, *, code: str = "ALLOC1") -> Fixture:
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
        credits=4,
        semester_number=1,
    )
    db_session.add(subject)
    await db_session.flush()

    academic_year = AcademicYear(
        institution_id=institution.id,
        year_label=f"2025-2026-{code}",
        start_date=date(2025, 6, 1),
        end_date=date(2026, 5, 31),
    )
    db_session.add(academic_year)
    await db_session.flush()

    semester = Semester(
        institution_id=institution.id,
        academic_year_id=academic_year.id,
        name=f"Semester 1 {code}",
        semester_number=1,
        term_type="odd",
        start_date=date(2025, 6, 1),
        end_date=date(2025, 11, 30),
    )
    db_session.add(semester)
    await db_session.flush()

    batch = Batch(
        institution_id=institution.id,
        course_id=course.id,
        name=f"Batch {code}",
        start_year=2025,
        end_year=2029,
    )
    db_session.add(batch)
    await db_session.flush()

    section = Section(
        institution_id=institution.id, batch_id=batch.id, name=f"A-{code}", max_capacity=60
    )
    db_session.add(section)
    await db_session.flush()

    room = Room(
        institution_id=institution.id,
        campus_id=campus.id,
        name=f"Room {code}",
        capacity=60,
        room_type="classroom",
    )
    db_session.add(room)
    await db_session.flush()

    await db_session.commit()

    teacher = await create_test_user(db_session, username=f"teacher_{code.lower()}")

    await db_session.refresh(subject)
    await db_session.refresh(section)
    await db_session.refresh(semester)
    await db_session.refresh(academic_year)
    await db_session.refresh(room)

    return Fixture(institution, subject, section, semester, academic_year, teacher, room)


def _institution_headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    headers = auth_headers(token)
    headers["X-Institution-Id"] = str(institution_id)
    return headers


def _payload(fixture: Fixture, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_id": str(fixture.subject.id),
        "section_id": str(fixture.section.id),
        "semester_id": str(fixture.semester.id),
        "academic_year_id": str(fixture.academic_year.id),
        "teacher_user_id": str(fixture.teacher.id),
        "room_id": str(fixture.room.id),
    }
    payload.update(overrides)
    return payload


async def test_create_subject_allocation_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin1", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="CREATE")
    token = await _login(client, "allocadmin1")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subject_id"] == str(fixture.subject.id)
    assert body["section_id"] == str(fixture.section.id)
    assert body["semester_id"] == str(fixture.semester.id)
    assert body["academic_year_id"] == str(fixture.academic_year.id)
    assert body["teacher_user_id"] == str(fixture.teacher.id)
    assert body["room_id"] == str(fixture.room.id)
    assert body["is_active"] is True


async def test_create_subject_allocation_without_room_is_allowed(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin2", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="NOROOM")
    token = await _login(client, "allocadmin2")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, room_id=None),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 201
    assert response.json()["room_id"] is None


async def test_create_subject_allocation_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin3", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="NOHEADER")
    token = await _login(client, "allocadmin3")

    response = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_subject_allocation_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin4", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADSUBJ")
    token = await _login(client, "allocadmin4")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, subject_id=str(uuid.uuid4())),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_subject_allocation_rejects_nonexistent_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin5", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADSECTION")
    token = await _login(client, "allocadmin5")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, section_id=str(uuid.uuid4())),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_subject_allocation_rejects_nonexistent_semester(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin6", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADSEM")
    token = await _login(client, "allocadmin6")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, semester_id=str(uuid.uuid4())),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_subject_allocation_rejects_nonexistent_academic_year(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin7", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADYEAR")
    token = await _login(client, "allocadmin7")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, academic_year_id=str(uuid.uuid4())),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_subject_allocation_rejects_nonexistent_teacher(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin8", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADTEACHER")
    token = await _login(client, "allocadmin8")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, teacher_user_id=str(uuid.uuid4())),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_subject_allocation_rejects_nonexistent_room(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin9", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BADROOM")
    token = await _login(client, "allocadmin9")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture, room_id=str(uuid.uuid4())),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 404


async def test_create_subject_allocation_rejects_duplicate(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin10", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="DUPE")
    token = await _login(client, "allocadmin10")
    headers = _institution_headers(token, fixture.institution.id)

    first = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=headers
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=headers
    )
    assert duplicate.status_code == 409


async def test_non_privileged_role_cannot_create_subject_allocation(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocstudent1", role=seed_rbac["student"])
    fixture = await _build_fixture(db_session, code="FORBIDDEN")
    token = await _login(client, "allocstudent1")

    response = await client.post(
        "/api/v1/subject-allocations",
        json=_payload(fixture),
        headers=_institution_headers(token, fixture.institution.id),
    )

    assert response.status_code == 403


async def test_subject_allocation_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin11", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="ROUNDTRIP")
    token = await _login(client, "allocadmin11")
    headers = _institution_headers(token, fixture.institution.id)

    create_response = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/subject-allocations/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["subject_id"] == str(fixture.subject.id)

    update_response = await client.patch(
        f"/api/v1/subject-allocations/{entity_id}", json={"is_active": False}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False
    assert update_response.json()["updated_at"] is not None

    delete_response = await client.delete(
        f"/api/v1/subject-allocations/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/subject-allocations/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/subject-allocations/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/subject-allocations/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/subject-allocations/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_list_subject_allocations_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin12", role=seed_rbac["super_admin"])
    token = await _login(client, "allocadmin12")

    fixture = await _build_fixture(db_session, code="LIST")
    headers = _institution_headers(token, fixture.institution.id)

    # The uniqueness constraint is scoped to (subject_id, section_id,
    # semester_id), so distinct rows within the same institution/subject/
    # section need distinct semesters — create four extra semesters in the
    # same academic year (plus the fixture's own semester) for 5 total
    # allocations.
    for i in range(4):
        extra_semester = Semester(
            institution_id=fixture.institution.id,
            academic_year_id=fixture.academic_year.id,
            name=f"Extra Semester {i}",
            semester_number=i + 2,
            term_type="even",
            start_date=date(2025, 12, 1),
            end_date=date(2026, 4, 30),
        )
        db_session.add(extra_semester)
        await db_session.flush()
        await db_session.commit()
        await db_session.refresh(extra_semester)

        create_response = await client.post(
            "/api/v1/subject-allocations",
            json=_payload(fixture, semester_id=str(extra_semester.id)),
            headers=headers,
        )
        assert create_response.status_code == 201

    # Plus the original (subject, section, fixture semester) triple = 5 total.
    original = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=headers
    )
    assert original.status_code == 201

    response = await client.get("/api/v1/subject-allocations?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_subject_allocations_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin13", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="BULK")
    token = await _login(client, "allocadmin13")
    headers = _institution_headers(token, fixture.institution.id)

    response = await client.post(
        "/api/v1/subject-allocations/bulk",
        json=[_payload(fixture), _payload(fixture)],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


async def test_subject_allocation_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin14", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="IMPEXP")
    token = await _login(client, "allocadmin14")
    headers = _institution_headers(token, fixture.institution.id)

    import_response = await client.post("/api/v1/subject-allocations/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/subject-allocations/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"


async def test_update_subject_allocation_rejects_each_missing_related_entity(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin15", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="UPDMISSING")
    token = await _login(client, "allocadmin15")
    headers = _institution_headers(token, fixture.institution.id)

    create_response = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    for field in (
        "subject_id",
        "section_id",
        "semester_id",
        "academic_year_id",
        "teacher_user_id",
        "room_id",
    ):
        response = await client.patch(
            f"/api/v1/subject-allocations/{entity_id}",
            json={field: str(uuid.uuid4())},
            headers=headers,
        )
        assert response.status_code == 404, f"field={field}"


async def test_update_subject_allocation_rechecks_duplicate_conflict(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="allocadmin16", role=seed_rbac["super_admin"])
    fixture = await _build_fixture(db_session, code="UPDCONFLICT")
    token = await _login(client, "allocadmin16")
    headers = _institution_headers(token, fixture.institution.id)

    second_subject = await client.post(
        "/api/v1/subjects",
        json={
            "course_id": str(fixture.subject.course_id),
            "subject_category_id": str(fixture.subject.subject_category_id),
            "code": "SUB-UPDCONFLICT-2",
            "name": "Second Subject",
            "credits": 4,
            "semester_number": 1,
        },
        headers=headers,
    )
    assert second_subject.status_code == 201
    second_subject_id = second_subject.json()["id"]

    first_allocation = await client.post(
        "/api/v1/subject-allocations", json=_payload(fixture), headers=headers
    )
    assert first_allocation.status_code == 201

    second_allocation = await client.post(
        "/api/v1/subject-allocations",
        json={**_payload(fixture), "subject_id": second_subject_id},
        headers=headers,
    )
    assert second_allocation.status_code == 201
    second_allocation_id = second_allocation.json()["id"]

    conflict_response = await client.patch(
        f"/api/v1/subject-allocations/{second_allocation_id}",
        json={"subject_id": str(fixture.subject.id)},
        headers=headers,
    )
    assert conflict_response.status_code == 409
