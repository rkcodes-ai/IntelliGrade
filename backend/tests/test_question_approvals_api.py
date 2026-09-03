"""QuestionApproval API tests: browsing (read-only router), service-level create/record.

`QuestionApproval` is a read/audit-trail entity: per its spec, the HTTP
router (`app/api/v1/endpoints/question_approvals.py`) exposes only
`GET /api/v1/question-approvals` (list) and `GET
/api/v1/question-approvals/{entity_id}` (read one) — there is no `POST`
route. Rows are created directly through `QuestionApprovalService`
(`create()`/`record()`), exactly as another service would call it, then
verified as readable through the two GET endpoints. See this repo's final
report for a flagged follow-up: wiring `QuestionService.approve()`/`reject()`
to call `QuestionApprovalService.record()` automatically.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.difficulty_level import DifficultyLevel
from app.models.institution import Institution
from app.models.program import Program
from app.models.question_category import QuestionCategory
from app.models.question_type import QuestionType
from app.models.subject import Subject
from app.models.subject_category import SubjectCategory
from app.schemas.question_approval import QuestionApprovalCreate
from app.services.question_approval_service import QuestionApprovalService
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


async def _create_subject(db_session: AsyncSession, *, code: str) -> Subject:
    """Builds the full Module 03 parent chain a `Question` needs and returns the `Subject`."""
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
    await db_session.commit()
    await db_session.refresh(subject)
    return subject


async def _create_lookup_rows(
    db_session: AsyncSession, institution_id: uuid.UUID, *, code: str
) -> dict[str, uuid.UUID]:
    category = QuestionCategory(
        institution_id=institution_id, code=f"QC-{code}", name=f"Category {code}"
    )
    question_type = QuestionType(
        institution_id=institution_id, code=f"QT-{code}", name=f"Type {code}"
    )
    difficulty = DifficultyLevel(
        institution_id=institution_id, code=f"DL-{code}", name=f"Difficulty {code}", level_order=1
    )
    bloom = BloomTaxonomyLevel(
        institution_id=institution_id, code=f"BL-{code}", name=f"Bloom {code}", level_order=1
    )
    db_session.add_all([category, question_type, difficulty, bloom])
    await db_session.flush()
    await db_session.commit()
    for row in (category, question_type, difficulty, bloom):
        await db_session.refresh(row)
    return {
        "question_category_id": category.id,
        "question_type_id": question_type.id,
        "difficulty_level_id": difficulty.id,
        "bloom_level_id": bloom.id,
    }


def _question_payload(
    subject_id: uuid.UUID, lookups: dict[str, uuid.UUID], **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_id": str(subject_id),
        "question_category_id": str(lookups["question_category_id"]),
        "question_type_id": str(lookups["question_type_id"]),
        "difficulty_level_id": str(lookups["difficulty_level_id"]),
        "bloom_level_id": str(lookups["bloom_level_id"]),
        "question_text": "What is 2 + 2?",
        "marks": 5.0,
    }
    payload.update(overrides)
    return payload


async def _setup(db_session: AsyncSession, *, code: str) -> tuple[Subject, dict[str, uuid.UUID]]:
    subject = await _create_subject(db_session, code=code)
    lookups = await _create_lookup_rows(db_session, subject.institution_id, code=code)
    return subject, lookups


async def _create_question(
    client: AsyncClient, headers: dict[str, str], subject: Subject, lookups: dict[str, uuid.UUID]
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/questions", json=_question_payload(subject.id, lookups), headers=headers
    )
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


async def test_create_question_approval_via_service_is_visible_through_get(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qaadmin1", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APR1")
    token = await _login(client, "qaadmin1")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    service = QuestionApprovalService(db_session)
    approval = await service.create(
        subject.institution_id,
        QuestionApprovalCreate(
            question_id=uuid.UUID(str(question["id"])), decision="approved", comments="Looks good."
        ),
        reviewed_by=admin.id,
    )
    await db_session.commit()

    response = await client.get(f"/api/v1/question-approvals/{approval.id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["question_id"] == question["id"]
    assert body["decision"] == "approved"
    assert body["reviewed_by"] == str(admin.id)
    assert body["comments"] == "Looks good."
    assert body["reviewed_at"] is not None


async def test_record_helper_delegates_to_create(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qaadmin2", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APR2")
    token = await _login(client, "qaadmin2")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    service = QuestionApprovalService(db_session)
    approval = await service.record(
        subject.institution_id,
        uuid.UUID(str(question["id"])),
        "rejected",
        reviewed_by=admin.id,
        comments="Needs rework.",
    )
    await db_session.commit()

    response = await client.get(f"/api/v1/question-approvals/{approval.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["decision"] == "rejected"
    assert response.json()["comments"] == "Needs rework."


async def test_create_question_approval_rejects_nonexistent_question(
    db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qaadmin3", role=seed_rbac["super_admin"])
    institution = Institution(
        name="Institution APR3", code="I-APR3", institution_type="university", is_active=True
    )
    db_session.add(institution)
    await db_session.flush()

    service = QuestionApprovalService(db_session)
    with pytest.raises(NotFoundError):
        await service.record(
            institution.id, uuid.uuid4(), "approved", reviewed_by=None, comments=None
        )


async def test_list_question_approvals_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qaadmin4", role=seed_rbac["super_admin"])
    token = await _login(client, "qaadmin4")

    response = await client.get("/api/v1/question-approvals", headers=auth_headers(token))

    assert response.status_code == 422


async def test_non_privileged_role_cannot_list_question_approvals(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qastudent1", role=seed_rbac["student"])
    subject = await _create_subject(db_session, code="APR5")
    token = await _login(client, "qastudent1")

    response = await client.get(
        "/api/v1/question-approvals", headers=_institution_headers(token, subject.institution_id)
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_approval_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qaadmin6", role=seed_rbac["super_admin"])
    subject = await _create_subject(db_session, code="APR6")
    token = await _login(client, "qaadmin6")
    headers = _institution_headers(token, subject.institution_id)

    response = await client.get(f"/api/v1/question-approvals/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_question_approval_soft_delete_and_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qaadmin7", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APR7")
    token = await _login(client, "qaadmin7")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    service = QuestionApprovalService(db_session)
    approval = await service.record(
        subject.institution_id,
        uuid.UUID(str(question["id"])),
        "approved",
        reviewed_by=admin.id,
        comments=None,
    )
    await db_session.commit()
    created_updated_at = approval.updated_at

    get_response = await client.get(f"/api/v1/question-approvals/{approval.id}", headers=headers)
    assert get_response.status_code == 200

    await service.soft_delete(
        subject.institution_id, approval.id, actor_id=admin.id, action="academic_entity_deleted"
    )
    await db_session.commit()

    get_after_delete = await client.get(
        f"/api/v1/question-approvals/{approval.id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    restored = await service.restore(
        subject.institution_id, approval.id, actor_id=admin.id, action="academic_entity_restored"
    )
    await db_session.commit()
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert restored.updated_at >= created_updated_at

    get_after_restore = await client.get(
        f"/api/v1/question-approvals/{approval.id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_list_question_approvals_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qaadmin8", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APR8")
    token = await _login(client, "qaadmin8")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)

    service = QuestionApprovalService(db_session)
    for _ in range(5):
        await service.record(
            subject.institution_id,
            uuid.UUID(str(question["id"])),
            "approved",
            reviewed_by=admin.id,
            comments=None,
        )
    await db_session.commit()

    response = await client.get("/api/v1/question-approvals?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_create_question_approval_with_valid_question_version_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    admin = await create_test_user(db_session, username="qaadmin9", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APR9")
    token = await _login(client, "qaadmin9")
    headers = _institution_headers(token, subject.institution_id)

    question = await _create_question(client, headers, subject, lookups)
    question_id = uuid.UUID(str(question["id"]))

    from app.models.question_version import QuestionVersion

    version = QuestionVersion(
        institution_id=subject.institution_id,
        question_id=question_id,
        version_number=1,
        question_text="What is 2 + 2?",
        marks=Decimal("5.00"),
        difficulty_level_id=lookups["difficulty_level_id"],
    )
    db_session.add(version)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(version)

    service = QuestionApprovalService(db_session)
    approval = await service.create(
        subject.institution_id,
        QuestionApprovalCreate(
            question_id=question_id,
            question_version_id=version.id,
            decision="approved",
            comments="Version-specific approval.",
        ),
        reviewed_by=admin.id,
    )
    await db_session.commit()

    assert approval.question_version_id == version.id


async def test_create_question_approval_rejects_nonexistent_question_version(
    db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="qaadmin10", role=seed_rbac["super_admin"])
    subject, lookups = await _setup(db_session, code="APR10")

    from app.models.question import Question

    question = Question(
        institution_id=subject.institution_id,
        subject_id=subject.id,
        question_category_id=lookups["question_category_id"],
        question_type_id=lookups["question_type_id"],
        difficulty_level_id=lookups["difficulty_level_id"],
        bloom_level_id=lookups["bloom_level_id"],
        question_text="What is 3 + 3?",
        marks=Decimal("5.00"),
    )
    db_session.add(question)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(question)

    service = QuestionApprovalService(db_session)
    with pytest.raises(NotFoundError):
        await service.create(
            subject.institution_id,
            QuestionApprovalCreate(
                question_id=question.id,
                question_version_id=uuid.uuid4(),
                decision="approved",
                comments=None,
            ),
            reviewed_by=None,
        )
