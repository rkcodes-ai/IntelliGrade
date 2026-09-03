"""Exam schedule API tests: CRUD, tenancy, time-range validation, and room-overlap rule."""

import uuid
from datetime import UTC, date, datetime, timedelta
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
from app.models.room import Room
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


async def _create_exam_and_room(
    db_session: AsyncSession, *, code: str = "ES1"
) -> tuple[Exam, Room]:
    """Builds the full parent chain an `ExamSchedule` needs and returns (exam, room)."""
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

    room = Room(
        institution_id=institution.id,
        campus_id=campus.id,
        name=f"Room-{code}",
        capacity=60,
        room_type="classroom",
    )
    db_session.add(room)
    await db_session.flush()

    await db_session.commit()
    await db_session.refresh(exam)
    await db_session.refresh(room)
    return exam, room


async def _create_second_exam(db_session: AsyncSession, exam: Exam, *, code: str) -> Exam:
    """Sibling `Exam` in the same institution, reusing `assessment_id`/`section_id`
    (no uniqueness constraint on that pair) so tests can PATCH `exam_id` to a
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


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(s: str) -> datetime:
    """
    Parses a response datetime string, treating a naive result as UTC.

    SQLite has no native timezone-aware datetime type, so a value that
    round-trips through the DB via `session.refresh()` (the MissingGreenlet
    fix every `update()` applies) comes back naive even though the column
    is `DateTime(timezone=True)` and PostgreSQL would preserve the offset
    correctly in production. Comparing parsed instants (assuming naive ==
    UTC) instead of raw strings keeps this test meaningful without being
    sensitive to that SQLite-only quirk.
    """
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


_BASE_START = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
_BASE_END = datetime(2026, 8, 10, 11, 0, tzinfo=UTC)


def _payload(
    exam_id: uuid.UUID, room_id: uuid.UUID | None, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "exam_id": str(exam_id),
        "room_id": str(room_id) if room_id else None,
        "start_time": _iso(_BASE_START),
        "end_time": _iso(_BASE_END),
    }
    payload.update(overrides)
    return payload


async def test_create_exam_schedule_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin1", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="CREATE")
    token = await _login(client, "esadmin1")

    response = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(exam.id, room.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["exam_id"] == str(exam.id)
    assert body["room_id"] == str(room.id)
    assert body["is_active"] is True


async def test_create_exam_schedule_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin2", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="NOHEADER")
    token = await _login(client, "esadmin2")

    response = await client.post(
        "/api/v1/exam-schedules", json=_payload(exam.id, room.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_exam_schedule_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin3", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="BADPARENT")
    token = await _login(client, "esadmin3")

    response = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(uuid.uuid4(), room.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 404


async def test_create_exam_schedule_rejects_invalid_time_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin4", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="BADTIME")
    token = await _login(client, "esadmin4")

    response = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(exam.id, room.id, start_time=_iso(_BASE_END), end_time=_iso(_BASE_START)),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 422


async def test_non_privileged_role_cannot_create_exam_schedule(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esstudent1", role=seed_rbac["student"])
    exam, room = await _create_exam_and_room(db_session, code="FORBIDDEN")
    token = await _login(client, "esstudent1")

    response = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(exam.id, room.id),
        headers=_institution_headers(token, exam.institution_id),
    )

    assert response.status_code == 403


async def test_create_exam_schedule_rejects_overlapping_room_booking(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin5", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="OVERLAP")
    token = await _login(client, "esadmin5")
    headers = _institution_headers(token, exam.institution_id)

    first = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(exam.id, room.id, start_time=_iso(_BASE_START), end_time=_iso(_BASE_END)),
        headers=headers,
    )
    assert first.status_code == 201

    overlapping_start = _BASE_START + timedelta(minutes=30)
    overlapping_end = _BASE_END + timedelta(minutes=30)
    overlapping = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(
            exam.id, room.id, start_time=_iso(overlapping_start), end_time=_iso(overlapping_end)
        ),
        headers=headers,
    )
    assert overlapping.status_code == 409

    non_overlapping_start = _BASE_END
    non_overlapping_end = _BASE_END + timedelta(hours=1)
    non_overlapping = await client.post(
        "/api/v1/exam-schedules",
        json=_payload(
            exam.id,
            room.id,
            start_time=_iso(non_overlapping_start),
            end_time=_iso(non_overlapping_end),
        ),
        headers=headers,
    )
    assert non_overlapping.status_code == 201


async def test_exam_schedule_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin6", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="ROUNDTRIP")
    token = await _login(client, "esadmin6")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-schedules", json=_payload(exam.id, room.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    original_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/exam-schedules/{entity_id}", headers=headers)
    assert get_response.status_code == 200

    new_start = _BASE_END + timedelta(hours=2)
    new_end = _BASE_END + timedelta(hours=3)
    update_response = await client.patch(
        f"/api/v1/exam-schedules/{entity_id}",
        json={"start_time": _iso(new_start), "end_time": _iso(new_end)},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert _parse_iso(updated_body["start_time"]) == new_start
    # SQLite's func.now() has only whole-second resolution, so a fast
    # create-then-update in the same test can legitimately land in the same
    # second — assert non-decreasing, not strict inequality, to avoid
    # flakiness while still catching a regression (missing/stale field).
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/exam-schedules/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/exam-schedules/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/exam-schedules/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/exam-schedules/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/exam-schedules/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_exam_schedule_get_nonexistent_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin7", role=seed_rbac["super_admin"])
    exam, _room = await _create_exam_and_room(db_session, code="404")
    token = await _login(client, "esadmin7")

    response = await client.get(
        f"/api/v1/exam-schedules/{uuid.uuid4()}",
        headers=_institution_headers(token, exam.institution_id),
    )
    assert response.status_code == 404


async def test_list_exam_schedules_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin8", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="PAGE")
    token = await _login(client, "esadmin8")
    headers = _institution_headers(token, exam.institution_id)

    for i in range(5):
        start = _BASE_START + timedelta(hours=3 * i)
        end = _BASE_END + timedelta(hours=3 * i)
        response = await client.post(
            "/api/v1/exam-schedules",
            json=_payload(exam.id, room.id, start_time=_iso(start), end_time=_iso(end)),
            headers=headers,
        )
        assert response.status_code == 201, f"failed at index {i}"

    response = await client.get("/api/v1/exam-schedules?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_bulk_create_exam_schedules_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esbulk1", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="BULK")
    token = await _login(client, "esbulk1")
    headers = _institution_headers(token, exam.institution_id)

    second_start = _BASE_END + timedelta(hours=1)
    second_end = _BASE_END + timedelta(hours=2)
    response = await client.post(
        "/api/v1/exam-schedules/bulk",
        json=[
            _payload(exam.id, room.id, start_time=_iso(_BASE_START), end_time=_iso(_BASE_END)),
            _payload(exam.id, room.id, start_time=_iso(second_start), end_time=_iso(second_end)),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_exam_schedules_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esbulk2", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="BULKERR")
    token = await _login(client, "esbulk2")
    headers = _institution_headers(token, exam.institution_id)
    bad_exam_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/exam-schedules/bulk",
        json=[
            _payload(exam.id, room.id, start_time=_iso(_BASE_START), end_time=_iso(_BASE_END)),
            _payload(bad_exam_id, room.id, start_time=_iso(_BASE_START), end_time=_iso(_BASE_END)),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["exam_id"] == str(bad_exam_id)


async def test_export_exam_schedules_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "esexport1")

    response = await client.get("/api/v1/exam-schedules/export", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_exam_schedules_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "esimport1")

    response = await client.post("/api/v1/exam-schedules/import", headers=auth_headers(token))

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_exam_schedule_accepts_new_exam_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin9", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="UPDFK")
    other_exam = await _create_second_exam(db_session, exam, code="UPDFK2")
    token = await _login(client, "esadmin9")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-schedules", json=_payload(exam.id, room.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-schedules/{entity_id}",
        json={"exam_id": str(other_exam.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["exam_id"] == str(other_exam.id)


async def test_update_exam_schedule_rejects_nonexistent_exam(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin10", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="UPDBAD")
    token = await _login(client, "esadmin10")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-schedules", json=_payload(exam.id, room.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-schedules/{entity_id}",
        json={"exam_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_exam_schedule_rejects_invalid_time_range(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="esadmin11", role=seed_rbac["super_admin"])
    exam, room = await _create_exam_and_room(db_session, code="UPDBADTIME")
    token = await _login(client, "esadmin11")
    headers = _institution_headers(token, exam.institution_id)

    created = await client.post(
        "/api/v1/exam-schedules", json=_payload(exam.id, room.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/exam-schedules/{entity_id}",
        json={"start_time": _iso(_BASE_END), "end_time": _iso(_BASE_START)},
        headers=headers,
    )

    assert update_response.status_code == 422
