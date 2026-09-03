"""Teacher assignment API tests: CRUD, tenancy, and the primary-teacher-conflict rule."""

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
from app.models.subject_allocation import SubjectAllocation
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


async def _create_subject_allocation(db_session: AsyncSession, *, code: str) -> SubjectAllocation:
    """Builds the full parent chain a `SubjectAllocation` needs and returns it, committed."""
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
        institution_id=institution.id, batch_id=batch.id, name=f"Sec-{code}", max_capacity=60
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

    subject_category = SubjectCategory(
        institution_id=institution.id, code=f"SC-{code}", name="Core"
    )
    db_session.add(subject_category)
    await db_session.flush()

    subject = Subject(
        institution_id=institution.id,
        course_id=course.id,
        subject_category_id=subject_category.id,
        code=f"SUB-{code}",
        name=f"Subject {code}",
        credits="4.00",
        semester_number=1,
    )
    db_session.add(subject)
    await db_session.flush()

    room = Room(
        institution_id=institution.id,
        campus_id=campus.id,
        name=f"Room-{code}",
        capacity=60,
        room_type="classroom",
    )
    db_session.add(room)
    await db_session.flush()

    allocation_teacher = await create_test_user(db_session, username=f"alloc_teacher_{code}")

    allocation = SubjectAllocation(
        institution_id=institution.id,
        subject_id=subject.id,
        section_id=section.id,
        semester_id=semester.id,
        academic_year_id=academic_year.id,
        teacher_user_id=allocation_teacher.id,
        room_id=room.id,
    )
    db_session.add(allocation)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(allocation)
    return allocation


async def test_create_teacher_assignment_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin1", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="CREATE")
    teacher = await create_test_user(db_session, username="teacher_create")
    token = await _login(client, "taadmin1")

    response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "primary",
            "assigned_from": "2025-06-01",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["teacher_user_id"] == str(teacher.id)
    assert body["subject_allocation_id"] == str(allocation.id)
    assert body["assignment_role"] == "primary"
    assert body["is_active"] is True


async def test_create_teacher_assignment_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin2", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="NOHEADER")
    teacher = await create_test_user(db_session, username="teacher_noheader")
    token = await _login(client, "taadmin2")

    response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assigned_from": "2025-06-01",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_teacher_assignment_rejects_nonexistent_allocation(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin3", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="BADALLOC")
    teacher = await create_test_user(db_session, username="teacher_badalloc")
    token = await _login(client, "taadmin3")

    response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(uuid.uuid4()),
            "assigned_from": "2025-06-01",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 404


async def test_create_teacher_assignment_rejects_duplicate_teacher_on_allocation(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin4", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="DUPE")
    teacher = await create_test_user(db_session, username="teacher_dupe")
    token = await _login(client, "taadmin4")
    headers = _institution_headers(token, allocation.institution_id)

    first = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "assistant",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "substitute",
            "assigned_from": "2025-07-01",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_teacher_assignment_rejects_second_active_primary(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """
    The dedicated "Teacher assignment conflicts" business rule: a subject
    allocation may have at most one active primary teacher at a time.
    """
    await create_test_user(db_session, username="taadmin5", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="PRIMARY")
    first_teacher = await create_test_user(db_session, username="teacher_primary_1")
    second_teacher = await create_test_user(db_session, username="teacher_primary_2")
    token = await _login(client, "taadmin5")
    headers = _institution_headers(token, allocation.institution_id)

    first = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(first_teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "primary",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(second_teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "primary",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert second.status_code == 409

    # An assistant, however, may be added freely alongside the primary.
    assistant = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(second_teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "assistant",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert assistant.status_code == 201


async def test_non_privileged_role_cannot_create_teacher_assignment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="tastudent1", role=seed_rbac["student"])
    allocation = await _create_subject_allocation(db_session, code="FORBIDDEN")
    teacher = await create_test_user(db_session, username="teacher_forbidden")
    token = await _login(client, "tastudent1")

    response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assigned_from": "2025-06-01",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 403


async def test_teacher_assignment_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin6", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="ROUNDTRIP")
    teacher = await create_test_user(db_session, username="teacher_roundtrip")
    token = await _login(client, "taadmin6")
    headers = _institution_headers(token, allocation.institution_id)

    create_response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "assistant",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/teacher-assignments/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["assignment_role"] == "assistant"

    # This PATCH is the "known bug" regression test — a real HTTP round-trip
    # through the update endpoint, not a service-layer-only check, so it
    # would fail with a 500 (MissingGreenlet) if `session.refresh()` were
    # missing from `TeacherAssignmentService.update()`.
    update_response = await client.patch(
        f"/api/v1/teacher-assignments/{entity_id}",
        json={"assigned_to": "2026-05-31"},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["assigned_to"] == "2026-05-31"
    assert "updated_at" in body and body["updated_at"]

    delete_response = await client.delete(
        f"/api/v1/teacher-assignments/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/teacher-assignments/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/teacher-assignments/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/teacher-assignments/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/teacher-assignments/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_update_teacher_assignment_promoting_to_primary_checks_conflict(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin7", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="PROMOTE")
    primary_teacher = await create_test_user(db_session, username="teacher_promote_primary")
    assistant_teacher = await create_test_user(db_session, username="teacher_promote_assistant")
    token = await _login(client, "taadmin7")
    headers = _institution_headers(token, allocation.institution_id)

    primary_response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(primary_teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "primary",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert primary_response.status_code == 201

    assistant_response = await client.post(
        "/api/v1/teacher-assignments",
        json={
            "teacher_user_id": str(assistant_teacher.id),
            "subject_allocation_id": str(allocation.id),
            "assignment_role": "assistant",
            "assigned_from": "2025-06-01",
        },
        headers=headers,
    )
    assert assistant_response.status_code == 201
    assistant_id = assistant_response.json()["id"]

    promote_response = await client.patch(
        f"/api/v1/teacher-assignments/{assistant_id}",
        json={"assignment_role": "primary"},
        headers=headers,
    )
    assert promote_response.status_code == 409


async def test_list_teacher_assignments_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin8", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="LIST")
    token = await _login(client, "taadmin8")
    headers = _institution_headers(token, allocation.institution_id)

    for i in range(3):
        teacher = await create_test_user(db_session, username=f"teacher_list_{i}")
        response = await client.post(
            "/api/v1/teacher-assignments",
            json={
                "teacher_user_id": str(teacher.id),
                "subject_allocation_id": str(allocation.id),
                "assignment_role": "assistant",
                "assigned_from": "2025-06-01",
            },
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/teacher-assignments?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 3


async def test_bulk_create_teacher_assignments_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin9", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="BULK")
    teacher_one = await create_test_user(db_session, username="teacher_bulk_1")
    teacher_two = await create_test_user(db_session, username="teacher_bulk_2")
    token = await _login(client, "taadmin9")
    headers = _institution_headers(token, allocation.institution_id)

    response = await client.post(
        "/api/v1/teacher-assignments/bulk",
        json=[
            {
                "teacher_user_id": str(teacher_one.id),
                "subject_allocation_id": str(allocation.id),
                "assignment_role": "assistant",
                "assigned_from": "2025-06-01",
            },
            {
                "teacher_user_id": str(teacher_one.id),
                "subject_allocation_id": str(allocation.id),
                "assignment_role": "assistant",
                "assigned_from": "2025-06-01",
            },
            {
                "teacher_user_id": str(teacher_two.id),
                "subject_allocation_id": str(allocation.id),
                "assignment_role": "assistant",
                "assigned_from": "2025-06-01",
            },
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_teacher_assignment_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="taadmin10", role=seed_rbac["super_admin"])
    allocation = await _create_subject_allocation(db_session, code="IMPEXP")
    token = await _login(client, "taadmin10")
    headers = _institution_headers(token, allocation.institution_id)

    import_response = await client.post("/api/v1/teacher-assignments/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/teacher-assignments/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
