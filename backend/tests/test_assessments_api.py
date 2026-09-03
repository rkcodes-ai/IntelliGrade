"""Assessment management API tests: CRUD, tenancy, and parent-FK business rules."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_status import AssessmentStatus
from app.models.assessment_type import AssessmentType
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.program import Program
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from app.models.user_institution import UserInstitution
from tests.conftest import auth_headers, create_test_user


async def _login(client: AsyncClient, username: str, password: str = "CorrectHorse9!") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_dependencies(
    db_session: AsyncSession, *, code: str = "ASM1"
) -> tuple[Subject, AssessmentType, AssessmentStatus]:
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

    category = SubjectCategory(
        institution_id=institution.id, code=f"CAT-{code}", name=f"Category {code}"
    )
    db_session.add(category)
    await db_session.flush()

    subject = Subject(
        institution_id=institution.id,
        course_id=course.id,
        subject_category_id=category.id,
        code=f"SUB-{code}",
        name=f"Subject {code}",
        credits=4,
        semester_number=1,
    )
    db_session.add(subject)
    await db_session.flush()

    assessment_type = AssessmentType(institution_id=institution.id, code=f"AT-{code}", name="Quiz")
    db_session.add(assessment_type)
    await db_session.flush()

    assessment_status = AssessmentStatus(
        institution_id=institution.id, code=f"AS-{code}", name="Draft"
    )
    db_session.add(assessment_status)
    await db_session.flush()

    await db_session.commit()
    await db_session.refresh(subject)
    await db_session.refresh(assessment_type)
    await db_session.refresh(assessment_status)
    return subject, assessment_type, assessment_status


async def _create_second_type_and_status(
    db_session: AsyncSession, institution_id: uuid.UUID, *, code: str
) -> tuple[AssessmentType, AssessmentStatus]:
    """A second `AssessmentType`/`AssessmentStatus` pair in the same
    institution, so update tests can PATCH `assessment_type_id`/
    `assessment_status_id` to a different-but-still-valid lookup within the
    same tenant."""
    assessment_type = AssessmentType(institution_id=institution_id, code=f"AT-{code}", name="Exam")
    db_session.add(assessment_type)
    await db_session.flush()

    assessment_status = AssessmentStatus(
        institution_id=institution_id, code=f"AS-{code}", name="Published"
    )
    db_session.add(assessment_status)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(assessment_type)
    await db_session.refresh(assessment_status)
    return assessment_type, assessment_status


async def _add_membership(
    db_session: AsyncSession, user_id: uuid.UUID, institution_id: uuid.UUID
) -> None:
    db_session.add(UserInstitution(user_id=user_id, institution_id=institution_id, is_active=True))
    await db_session.commit()


def _headers(token: str, institution_id: uuid.UUID) -> dict[str, str]:
    return {**auth_headers(token), "X-Institution-Id": str(institution_id)}


def _payload(
    subject_id: uuid.UUID,
    assessment_type_id: uuid.UUID,
    assessment_status_id: uuid.UUID,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_id": str(subject_id),
        "assessment_type_id": str(assessment_type_id),
        "assessment_status_id": str(assessment_status_id),
        "name": "Midterm Assessment",
        "description": "Covers chapters 1-5",
    }
    payload.update(overrides)
    return payload


async def test_create_assessment_as_super_admin(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin1", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="CREATE")
    token = await _login(client, "assmadmin1")

    response = await client.post(
        "/api/v1/assessments",
        json=_payload(subject.id, atype.id, astatus.id),
        headers=_headers(token, subject.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Midterm Assessment"
    assert body["subject_id"] == str(subject.id)
    assert body["assessment_type_id"] == str(atype.id)
    assert body["assessment_status_id"] == str(astatus.id)
    assert body["is_active"] is True
    assert body["current_version"] == 1


async def test_create_assessment_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin2", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="NOHEADER")
    token = await _login(client, "assmadmin2")

    response = await client.post(
        "/api/v1/assessments",
        json=_payload(subject.id, atype.id, astatus.id),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_assessment_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin3", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="BADSUBJECT")
    token = await _login(client, "assmadmin3")

    response = await client.post(
        "/api/v1/assessments",
        json=_payload(uuid.uuid4(), atype.id, astatus.id),
        headers=_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_create_assessment_rejects_nonexistent_assessment_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin4", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="BADTYPE")
    token = await _login(client, "assmadmin4")

    response = await client.post(
        "/api/v1/assessments",
        json=_payload(subject.id, uuid.uuid4(), astatus.id),
        headers=_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_create_assessment_rejects_nonexistent_assessment_status(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin5", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="BADSTATUS")
    token = await _login(client, "assmadmin5")

    response = await client.post(
        "/api/v1/assessments",
        json=_payload(subject.id, atype.id, uuid.uuid4()),
        headers=_headers(token, subject.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    student = await create_test_user(db_session, username="assmstudent1", role=seed_rbac["student"])
    subject, atype, astatus = await _create_dependencies(db_session, code="FORBIDDEN")
    await _add_membership(db_session, student.id, subject.institution_id)
    token = await _login(client, "assmstudent1")

    response = await client.post(
        "/api/v1/assessments",
        json=_payload(subject.id, atype.id, astatus.id),
        headers=_headers(token, subject.institution_id),
    )

    assert response.status_code == 403


async def test_assessment_is_tenant_scoped(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin6", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="TENANTA")
    _other_subject, _other_type, _other_status = await _create_dependencies(
        db_session, code="TENANTB"
    )
    token = await _login(client, "assmadmin6")

    created = await client.post(
        "/api/v1/assessments",
        json=_payload(subject.id, atype.id, astatus.id),
        headers=_headers(token, subject.institution_id),
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    cross_tenant_get = await client.get(
        f"/api/v1/assessments/{entity_id}",
        headers=_headers(token, _other_subject.institution_id),
    )
    assert cross_tenant_get.status_code == 404


async def test_get_nonexistent_assessment_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin7", role=seed_rbac["super_admin"])
    subject, _atype, _astatus = await _create_dependencies(db_session, code="MISSING")
    token = await _login(client, "assmadmin7")

    response = await client.get(
        f"/api/v1/assessments/{uuid.uuid4()}", headers=_headers(token, subject.institution_id)
    )

    assert response.status_code == 404


async def test_assessment_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin8", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="ROUNDTRIP")
    token = await _login(client, "assmadmin8")
    headers = _headers(token, subject.institution_id)

    create_response = await client.post(
        "/api/v1/assessments", json=_payload(subject.id, atype.id, astatus.id), headers=headers
    )
    assert create_response.status_code == 201
    entity_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]
    assert create_response.json()["current_version"] == 1

    get_response = await client.get(f"/api/v1/assessments/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Midterm Assessment"

    update_response = await client.patch(
        f"/api/v1/assessments/{entity_id}",
        json={"name": "Updated Assessment Name"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()
    assert updated_body["name"] == "Updated Assessment Name"
    # `current_version` (VersionCounterMixin) must be bumped on a
    # content-changing update.
    assert updated_body["current_version"] == 2
    # SQLite's func.now() is whole-second resolution, so a fast
    # create-then-update can legitimately land in the same second — assert
    # non-decreasing, not strict inequality.
    assert updated_body["updated_at"] >= original_updated_at

    delete_response = await client.delete(f"/api/v1/assessments/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/assessments/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/assessments/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/assessments/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/assessments/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_assessment_update_rejects_nonexistent_subject(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin9", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="UPDBADSUBJ")
    token = await _login(client, "assmadmin9")
    headers = _headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/assessments", json=_payload(subject.id, atype.id, astatus.id), headers=headers
    )
    entity_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/assessments/{entity_id}",
        json={"subject_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert response.status_code == 404


async def test_list_assessments_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin10", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="LIST")
    token = await _login(client, "assmadmin10")
    headers = _headers(token, subject.institution_id)

    for i in range(5):
        create_response = await client.post(
            "/api/v1/assessments",
            json=_payload(subject.id, atype.id, astatus.id, name=f"Assessment {i}"),
            headers=headers,
        )
        assert create_response.status_code == 201

    response = await client.get("/api/v1/assessments?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_assessments_collects_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin11", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="BULK")
    token = await _login(client, "assmadmin11")
    headers = _headers(token, subject.institution_id)

    response = await client.post(
        "/api/v1/assessments/bulk",
        json=[
            _payload(subject.id, atype.id, astatus.id, name="Bulk One"),
            _payload(uuid.uuid4(), atype.id, astatus.id, name="Bulk Bad Subject"),
            _payload(subject.id, atype.id, astatus.id, name="Bulk Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


async def test_assessment_import_export_skeleton_endpoints(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin12", role=seed_rbac["super_admin"])
    subject, _atype, _astatus = await _create_dependencies(db_session, code="IMPEXP")
    token = await _login(client, "assmadmin12")
    headers = _headers(token, subject.institution_id)

    import_response = await client.post("/api/v1/assessments/import", headers=headers)
    assert import_response.status_code == 202
    assert import_response.json()["status"] == "not_implemented"

    export_response = await client.get("/api/v1/assessments/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "not_implemented"


async def test_assessment_update_accepts_new_assessment_type_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin13", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="UPDTYPE")
    other_type, _other_status = await _create_second_type_and_status(
        db_session, subject.institution_id, code="UPDTYPE2"
    )
    token = await _login(client, "assmadmin13")
    headers = _headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/assessments", json=_payload(subject.id, atype.id, astatus.id), headers=headers
    )
    entity_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/assessments/{entity_id}",
        json={"assessment_type_id": str(other_type.id)},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["assessment_type_id"] == str(other_type.id)


async def test_assessment_update_rejects_nonexistent_assessment_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin14", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="UPDBADTYPE")
    token = await _login(client, "assmadmin14")
    headers = _headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/assessments", json=_payload(subject.id, atype.id, astatus.id), headers=headers
    )
    entity_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/assessments/{entity_id}",
        json={"assessment_type_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert response.status_code == 404


async def test_assessment_update_accepts_new_assessment_status_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin15", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="UPDSTATUS")
    _other_type, other_status = await _create_second_type_and_status(
        db_session, subject.institution_id, code="UPDSTATUS2"
    )
    token = await _login(client, "assmadmin15")
    headers = _headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/assessments", json=_payload(subject.id, atype.id, astatus.id), headers=headers
    )
    entity_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/assessments/{entity_id}",
        json={"assessment_status_id": str(other_status.id)},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["assessment_status_id"] == str(other_status.id)


async def test_assessment_update_rejects_nonexistent_assessment_status(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="assmadmin16", role=seed_rbac["super_admin"])
    subject, atype, astatus = await _create_dependencies(db_session, code="UPDBADSTATUS")
    token = await _login(client, "assmadmin16")
    headers = _headers(token, subject.institution_id)

    created = await client.post(
        "/api/v1/assessments", json=_payload(subject.id, atype.id, astatus.id), headers=headers
    )
    entity_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/assessments/{entity_id}",
        json={"assessment_status_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert response.status_code == 404
