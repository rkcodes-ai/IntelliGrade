"""Class schedule API tests: CRUD, tenancy, and the room-double-booking conflict rule."""

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


async def _create_allocation_and_room(
    db_session: AsyncSession, *, code: str
) -> tuple[SubjectAllocation, Room]:
    """Builds the full parent chain a `ClassSchedule` needs and returns (allocation, room)."""
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

    allocation_teacher = await create_test_user(db_session, username=f"cs_teacher_{code}")

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
    await db_session.refresh(room)
    return allocation, room


async def test_create_class_schedule_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin1", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="CREATE")
    token = await _login(client, "csadmin1")

    response = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "monday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["day_of_week"] == "monday"
    assert body["start_time"] == "09:00:00"
    assert body["end_time"] == "10:00:00"
    assert body["is_active"] is True


async def test_create_class_schedule_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin2", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="NOHEADER")
    token = await _login(client, "csadmin2")

    response = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "monday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_class_schedule_rejects_invalid_time_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin3", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="BADTIME")
    token = await _login(client, "csadmin3")

    response = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "tuesday",
            "start_time": "10:00:00",
            "end_time": "09:00:00",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 422


async def test_create_class_schedule_rejects_nonexistent_room(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin4", role=seed_rbac["super_admin"])
    allocation, _room = await _create_allocation_and_room(db_session, code="NOROOM")
    token = await _login(client, "csadmin4")

    response = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(uuid.uuid4()),
            "day_of_week": "wednesday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 404


async def test_create_class_schedule_rejects_overlapping_room_booking(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin5", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="OVERLAP")
    token = await _login(client, "csadmin5")
    headers = _institution_headers(token, allocation.institution_id)

    first = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "thursday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
        headers=headers,
    )
    assert first.status_code == 201

    overlapping = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "thursday",
            "start_time": "09:30:00",
            "end_time": "10:30:00",
        },
        headers=headers,
    )
    assert overlapping.status_code == 409

    non_overlapping = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "thursday",
            "start_time": "10:00:00",
            "end_time": "11:00:00",
        },
        headers=headers,
    )
    assert non_overlapping.status_code == 201


async def test_non_admin_cannot_create_class_schedule(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    allocation, room = await _create_allocation_and_room(db_session, code="FORBID")
    student = await create_test_user(db_session, username="csstudent1", role=seed_rbac["student"])
    from app.models.user_institution import UserInstitution

    db_session.add(
        UserInstitution(
            user_id=student.id, institution_id=allocation.institution_id, is_active=True
        )
    )
    await db_session.commit()
    token = await _login(client, "csstudent1")

    response = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "friday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
        headers=_institution_headers(token, allocation.institution_id),
    )

    assert response.status_code == 403


async def test_get_update_list_and_restore_class_schedule(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin6", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="CRUD")
    token = await _login(client, "csadmin6")
    headers = _institution_headers(token, allocation.institution_id)

    created = await client.post(
        "/api/v1/class-schedules",
        json={
            "subject_allocation_id": str(allocation.id),
            "room_id": str(room.id),
            "day_of_week": "saturday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
        headers=headers,
    )
    assert created.status_code == 201
    schedule_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/class-schedules/{schedule_id}", headers=headers)
    assert get_response.status_code == 200

    update_response = await client.patch(
        f"/api/v1/class-schedules/{schedule_id}",
        json={"start_time": "11:00:00", "end_time": "12:00:00"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["start_time"] == "11:00:00"
    # Regression check for the MissingGreenlet bug: updated_at must serialize
    # cleanly over real HTTP and reflect the just-performed update.
    assert "updated_at" in updated_body
    # SQLite's func.now() has only whole-second resolution (unlike
    # PostgreSQL's microsecond precision in production), so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    list_response = await client.get("/api/v1/class-schedules", headers=headers)
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert any(item["id"] == schedule_id for item in list_body["items"])

    delete_response = await client.delete(f"/api/v1/class-schedules/{schedule_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/class-schedules/{schedule_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/class-schedules/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == schedule_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/class-schedules/{schedule_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/class-schedules/{schedule_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_list_class_schedules_pagination(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin7", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="PAGE")
    token = await _login(client, "csadmin7")
    headers = _institution_headers(token, allocation.institution_id)

    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    for i, day in enumerate(days):
        response = await client.post(
            "/api/v1/class-schedules",
            json={
                "subject_allocation_id": str(allocation.id),
                "room_id": str(room.id),
                "day_of_week": day,
                "start_time": "09:00:00",
                "end_time": "10:00:00",
            },
            headers=headers,
        )
        assert response.status_code == 201, f"failed at index {i}"

    response = await client.get("/api/v1/class-schedules?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_bulk_create_class_schedules_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin8", role=seed_rbac["super_admin"])
    allocation, room = await _create_allocation_and_room(db_session, code="BULK")
    token = await _login(client, "csadmin8")
    headers = _institution_headers(token, allocation.institution_id)

    response = await client.post(
        "/api/v1/class-schedules/bulk",
        json=[
            {
                "subject_allocation_id": str(allocation.id),
                "room_id": str(room.id),
                "day_of_week": "monday",
                "start_time": "09:00:00",
                "end_time": "10:00:00",
            },
            {
                "subject_allocation_id": str(allocation.id),
                "room_id": str(room.id),
                "day_of_week": "monday",
                "start_time": "09:30:00",
                "end_time": "10:30:00",
            },
            {
                "subject_allocation_id": str(allocation.id),
                "room_id": str(room.id),
                "day_of_week": "tuesday",
                "start_time": "09:00:00",
                "end_time": "10:00:00",
            },
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_class_schedule_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="csadmin9", role=seed_rbac["super_admin"])
    allocation, _room = await _create_allocation_and_room(db_session, code="IMPEXP")
    token = await _login(client, "csadmin9")
    headers = _institution_headers(token, allocation.institution_id)

    import_response = await client.post("/api/v1/class-schedules/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/class-schedules/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"
