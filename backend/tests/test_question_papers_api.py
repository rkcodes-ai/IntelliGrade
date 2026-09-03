"""QuestionPaper API tests: CRUD, tenancy, versioning, approval workflow, soft-delete/restore."""

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
from app.models.question_blueprint import QuestionBlueprint
from app.models.question_paper_template import QuestionPaperTemplate
from app.models.subject import Subject
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


async def _create_assessment(db_session: AsyncSession, *, code: str = "ASM1") -> Assessment:
    """
    Builds the full Institution->Campus->Department->Program->Course->
    SubjectCategory->Subject->AssessmentType/AssessmentStatus->Assessment
    parent chain via direct ORM inserts, mirroring
    `tests/test_assessment_configurations_api.py`'s `_create_assessment` helper.
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


async def _create_blueprint_for(
    db_session: AsyncSession, assessment: Assessment, *, code: str
) -> QuestionBlueprint:
    blueprint = QuestionBlueprint(
        institution_id=assessment.institution_id,
        subject_id=assessment.subject_id,
        name=f"Blueprint {code}",
        total_marks=Decimal("100.00"),
        total_questions=20,
    )
    db_session.add(blueprint)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(blueprint)
    return blueprint


async def _create_template_for(
    db_session: AsyncSession, assessment: Assessment, *, code: str
) -> QuestionPaperTemplate:
    template = QuestionPaperTemplate(
        institution_id=assessment.institution_id, name=f"Template {code}"
    )
    db_session.add(template)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(template)
    return template


async def _create_second_assessment(
    db_session: AsyncSession, assessment: Assessment, *, code: str
) -> Assessment:
    """A second `Assessment` in the same institution (reusing `subject_id`/
    `assessment_type_id`/`assessment_status_id`), so update tests can PATCH
    `assessment_id` to a different-but-still-valid parent within the same
    tenant."""
    second = Assessment(
        institution_id=assessment.institution_id,
        subject_id=assessment.subject_id,
        assessment_type_id=assessment.assessment_type_id,
        assessment_status_id=assessment.assessment_status_id,
        name=f"Assessment {code}",
    )
    db_session.add(second)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(second)
    return second


def _payload(assessment_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assessment_id": str(assessment_id),
        "name": "Midterm Question Paper",
        "total_marks": "100.00",
    }
    payload.update(overrides)
    return payload


async def test_create_question_paper_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin1", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="CREATE")
    token = await _login(client, "qpadmin1")

    response = await client.post(
        "/api/v1/question-papers",
        json=_payload(assessment.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["assessment_id"] == str(assessment.id)
    assert body["name"] == "Midterm Question Paper"
    assert float(body["total_marks"]) == 100.0
    assert body["blueprint_id"] is None
    assert body["template_id"] is None
    assert body["is_active"] is True
    assert body["current_version"] == 1
    assert body["approval_status"] == "draft"
    assert body["approved_by"] is None
    assert body["approved_at"] is None
    assert body["rejection_reason"] is None


async def test_create_question_paper_with_blueprint_and_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin2", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="WITHREFS")
    blueprint = await _create_blueprint_for(db_session, assessment, code="WITHREFS")
    template = await _create_template_for(db_session, assessment, code="WITHREFS")
    token = await _login(client, "qpadmin2")

    response = await client.post(
        "/api/v1/question-papers",
        json=_payload(assessment.id, blueprint_id=str(blueprint.id), template_id=str(template.id)),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["blueprint_id"] == str(blueprint.id)
    assert body["template_id"] == str(template.id)


async def test_create_question_paper_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin3", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="NOHEADER")
    token = await _login(client, "qpadmin3")

    response = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=auth_headers(token)
    )

    assert response.status_code == 422


async def test_create_question_paper_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin4", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADPARENT")
    token = await _login(client, "qpadmin4")

    response = await client.post(
        "/api/v1/question-papers",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_paper_rejects_nonexistent_blueprint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin5", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADBLUEPRINT")
    token = await _login(client, "qpadmin5")

    response = await client.post(
        "/api/v1/question-papers",
        json=_payload(assessment.id, blueprint_id=str(uuid.uuid4())),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_paper_rejects_nonexistent_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin6", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BADTEMPLATE")
    token = await _login(client, "qpadmin6")

    response = await client.post(
        "/api/v1/question-papers",
        json=_payload(assessment.id, template_id=str(uuid.uuid4())),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_non_privileged_role_cannot_create_question_paper(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpstudent1", role=seed_rbac["student"])
    assessment = await _create_assessment(db_session, code="FORBIDDEN")
    token = await _login(client, "qpstudent1")

    response = await client.post(
        "/api/v1/question-papers",
        json=_payload(assessment.id),
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_paper_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin7", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="GETMISSING")
    token = await _login(client, "qpadmin7")

    response = await client.get(
        f"/api/v1/question-papers/{uuid.uuid4()}",
        headers=_institution_headers(token, assessment.institution_id),
    )

    assert response.status_code == 404


async def test_question_paper_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin8", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="ROUNDTRIP")
    token = await _login(client, "qpadmin8")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(f"/api/v1/question-papers/{entity_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Midterm Question Paper"

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(f"/api/v1/question-papers/{entity_id}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/api/v1/question-papers/{entity_id}", headers=headers)
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/question-papers/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(f"/api/v1/question-papers/{entity_id}", headers=headers)
    assert get_after_restore.status_code == 200


async def test_update_question_paper_increments_version_on_name_or_marks_change(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin9", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="VERSION")
    token = await _login(client, "qpadmin9")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    assert created.json()["current_version"] == 1

    # A cosmetic field change alone (is_active) must NOT bump the version counter.
    cosmetic_update = await client.patch(
        f"/api/v1/question-papers/{entity_id}", json={"is_active": False}, headers=headers
    )
    assert cosmetic_update.status_code == 200
    assert cosmetic_update.json()["current_version"] == 1

    # Changing `total_marks` (graded content) must bump it.
    marks_update = await client.patch(
        f"/api/v1/question-papers/{entity_id}", json={"total_marks": "150.00"}, headers=headers
    )
    assert marks_update.status_code == 200
    assert marks_update.json()["current_version"] == 2
    assert float(marks_update.json()["total_marks"]) == 150.0


async def test_list_question_papers_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin10", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="LIST")
    token = await _login(client, "qpadmin10")
    headers = _institution_headers(token, assessment.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/question-papers",
            json=_payload(assessment.id, name=f"Paper {i}"),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/v1/question-papers?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_question_paper_submit_for_review_then_approve_flow(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qpadmin11", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="APPROVE")
    token = await _login(client, "qpadmin11")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    entity_id = created.json()["id"]

    # Approving a draft (not yet submitted) must 409.
    premature_approve = await client.post(
        f"/api/v1/question-papers/{entity_id}/approve", headers=headers
    )
    assert premature_approve.status_code == 409

    submit_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/submit-for-review", headers=headers
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["approval_status"] == "pending_review"

    approve_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/approve", headers=headers
    )
    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["approval_status"] == "approved"
    assert body["approved_by"] == str(admin.id)
    assert body["approved_at"] is not None

    # Approving again (now "approved", not "pending_review") must 409.
    second_approve = await client.post(
        f"/api/v1/question-papers/{entity_id}/approve", headers=headers
    )
    assert second_approve.status_code == 409


async def test_question_paper_submit_for_review_then_reject_flow(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin12", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="REJECT")
    token = await _login(client, "qpadmin12")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    entity_id = created.json()["id"]

    # Rejecting a draft (not yet submitted) must 409.
    premature_reject = await client.post(
        f"/api/v1/question-papers/{entity_id}/reject",
        json={"reason": "too early"},
        headers=headers,
    )
    assert premature_reject.status_code == 409

    submit_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/submit-for-review", headers=headers
    )
    assert submit_response.status_code == 200

    reject_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/reject",
        json={"reason": "Marks distribution is unbalanced."},
        headers=headers,
    )
    assert reject_response.status_code == 200
    body = reject_response.json()
    assert body["approval_status"] == "rejected"
    assert body["rejection_reason"] == "Marks distribution is unbalanced."

    # A rejected paper may be resubmitted for review.
    resubmit_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/submit-for-review", headers=headers
    )
    assert resubmit_response.status_code == 200
    assert resubmit_response.json()["approval_status"] == "pending_review"


async def test_non_privileged_role_cannot_approve_or_reject_question_paper(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin13", role=seed_rbac["super_admin"])
    await create_test_user(db_session, username="qpstudent2", role=seed_rbac["student"])
    assessment = await _create_assessment(db_session, code="NOPRIV")
    admin_token = await _login(client, "qpadmin13")
    student_token = await _login(client, "qpstudent2")
    admin_headers = _institution_headers(admin_token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=admin_headers
    )
    entity_id = created.json()["id"]
    await client.post(
        f"/api/v1/question-papers/{entity_id}/submit-for-review", headers=admin_headers
    )

    student_headers = _institution_headers(student_token, assessment.institution_id)
    approve_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/approve", headers=student_headers
    )
    assert approve_response.status_code == 403

    reject_response = await client.post(
        f"/api/v1/question-papers/{entity_id}/reject",
        json={"reason": "not allowed"},
        headers=student_headers,
    )
    assert reject_response.status_code == 403


async def test_bulk_create_question_papers_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin14", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BULKOK")
    token = await _login(client, "qpadmin14")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.post(
        "/api/v1/question-papers/bulk",
        json=[
            _payload(assessment.id, name="Bulk Paper One"),
            _payload(assessment.id, name="Bulk Paper Two"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_question_papers_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin15", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="BULKERR")
    token = await _login(client, "qpadmin15")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.post(
        "/api/v1/question-papers/bulk",
        json=[
            _payload(assessment.id, name="Valid Paper"),
            _payload(uuid.uuid4(), name="Missing Assessment Paper"),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


async def test_export_question_papers_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin16", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="EXPORT")
    token = await _login(client, "qpadmin16")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.get("/api/v1/question-papers/export", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_papers_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin17", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="IMPORT")
    token = await _login(client, "qpadmin17")
    headers = _institution_headers(token, assessment.institution_id)

    response = await client.post("/api/v1/question-papers/import", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "not_implemented"


async def test_update_question_paper_accepts_new_assessment_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin18", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UPDFK")
    other_assessment = await _create_second_assessment(db_session, assessment, code="UPDFK2")
    token = await _login(client, "qpadmin18")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"assessment_id": str(other_assessment.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["assessment_id"] == str(other_assessment.id)


async def test_update_question_paper_rejects_nonexistent_assessment(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin19", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UPDBADA")
    token = await _login(client, "qpadmin19")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"assessment_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_paper_accepts_new_blueprint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin20", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UPDBP")
    blueprint = await _create_blueprint_for(db_session, assessment, code="UPDBP1")
    token = await _login(client, "qpadmin20")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"blueprint_id": str(blueprint.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["blueprint_id"] == str(blueprint.id)


async def test_update_question_paper_rejects_nonexistent_blueprint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin21", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UPDBADBP")
    token = await _login(client, "qpadmin21")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"blueprint_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_update_question_paper_accepts_new_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin22", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UPDTPL")
    template = await _create_template_for(db_session, assessment, code="UPDTPL1")
    token = await _login(client, "qpadmin22")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"template_id": str(template.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["template_id"] == str(template.id)


async def test_update_question_paper_rejects_nonexistent_template(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin23", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="UPDBADTPL")
    token = await _login(client, "qpadmin23")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-papers/{entity_id}",
        json={"template_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404


async def test_question_paper_submit_for_review_rejects_when_already_pending(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qpadmin24", role=seed_rbac["super_admin"])
    assessment = await _create_assessment(db_session, code="RESUBMIT")
    token = await _login(client, "qpadmin24")
    headers = _institution_headers(token, assessment.institution_id)

    created = await client.post(
        "/api/v1/question-papers", json=_payload(assessment.id), headers=headers
    )
    entity_id = created.json()["id"]

    first_submit = await client.post(
        f"/api/v1/question-papers/{entity_id}/submit-for-review", headers=headers
    )
    assert first_submit.status_code == 200

    second_submit = await client.post(
        f"/api/v1/question-papers/{entity_id}/submit-for-review", headers=headers
    )
    assert second_submit.status_code == 409
