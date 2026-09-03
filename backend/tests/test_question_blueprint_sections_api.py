"""QuestionBlueprintSection API tests: CRUD, tenancy, lookup validation, soft-delete/restore."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
from app.models.campus import Campus
from app.models.course import Course
from app.models.department import Department
from app.models.difficulty_level import DifficultyLevel
from app.models.institution import Institution
from app.models.program import Program
from app.models.question_blueprint import QuestionBlueprint
from app.models.question_category import QuestionCategory
from app.models.question_type import QuestionType
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


async def _create_blueprint(db_session: AsyncSession, *, code: str) -> QuestionBlueprint:
    """Builds the full Module 03 parent chain plus a `QuestionBlueprint`."""
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

    blueprint = QuestionBlueprint(
        institution_id=institution.id,
        subject_id=subject.id,
        name=f"Blueprint {code}",
        total_marks=Decimal("100.00"),
        total_questions=20,
    )
    db_session.add(blueprint)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(blueprint)
    return blueprint


async def _create_lookup_rows(
    db_session: AsyncSession, institution_id: uuid.UUID, *, code: str
) -> dict[str, uuid.UUID]:
    """Seeds one row in each Module 04 lookup table a section may reference."""
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


async def _create_second_blueprint(
    db_session: AsyncSession, blueprint: QuestionBlueprint, *, code: str
) -> QuestionBlueprint:
    """A second `QuestionBlueprint` in the same institution (reusing
    `subject_id`), so update tests can PATCH `blueprint_id` to a
    different-but-still-valid parent within the same tenant."""
    second = QuestionBlueprint(
        institution_id=blueprint.institution_id,
        subject_id=blueprint.subject_id,
        name=f"Blueprint {code}",
        total_marks=Decimal("100.00"),
        total_questions=20,
    )
    db_session.add(second)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(second)
    return second


def _payload(blueprint_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "blueprint_id": str(blueprint_id),
        "number_of_questions": 10,
        "marks_per_question": "1.00",
        "display_order": 1,
    }
    payload.update(overrides)
    return payload


async def test_create_question_blueprint_section_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin1", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="CREATE")
    lookups = await _create_lookup_rows(db_session, blueprint.institution_id, code="CREATE")
    token = await _login(client, "bsadmin1")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(
            blueprint.id,
            question_category_id=str(lookups["question_category_id"]),
            difficulty_level_id=str(lookups["difficulty_level_id"]),
        ),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["blueprint_id"] == str(blueprint.id)
    assert body["question_category_id"] == str(lookups["question_category_id"])
    assert body["difficulty_level_id"] == str(lookups["difficulty_level_id"])
    assert body["bloom_level_id"] is None
    assert body["question_type_id"] is None
    assert body["number_of_questions"] == 10
    assert float(body["marks_per_question"]) == 1.0


async def test_create_question_blueprint_section_requires_institution_header(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin2", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="NOHEADER")
    token = await _login(client, "bsadmin2")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_question_blueprint_section_rejects_nonexistent_blueprint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin3", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BADPARENT")
    token = await _login(client, "bsadmin3")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(uuid.uuid4()),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_blueprint_section_rejects_nonexistent_category(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin4", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BADCATEGORY")
    token = await _login(client, "bsadmin4")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id, question_category_id=str(uuid.uuid4())),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_blueprint_section_rejects_nonexistent_difficulty_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin5", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BADDIFFICULTY")
    token = await _login(client, "bsadmin5")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id, difficulty_level_id=str(uuid.uuid4())),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_blueprint_section_rejects_nonexistent_bloom_level(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin6", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BADBLOOM")
    token = await _login(client, "bsadmin6")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id, bloom_level_id=str(uuid.uuid4())),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_blueprint_section_rejects_nonexistent_question_type(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin7", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BADTYPE")
    token = await _login(client, "bsadmin7")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id, question_type_id=str(uuid.uuid4())),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 404


async def test_create_question_blueprint_section_allows_all_lookups_omitted(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """A section may constrain by none of the four lookup dimensions (meaning "any")."""
    await create_test_user(db_session, username="bsadmin8", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="ANYLOOKUP")
    token = await _login(client, "bsadmin8")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["question_category_id"] is None
    assert body["difficulty_level_id"] is None
    assert body["bloom_level_id"] is None
    assert body["question_type_id"] is None


async def test_non_privileged_role_cannot_create_question_blueprint_section(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsstudent1", role=seed_rbac["student"])
    blueprint = await _create_blueprint(db_session, code="FORBIDDEN")
    token = await _login(client, "bsstudent1")

    response = await client.post(
        "/api/v1/question-blueprint-sections",
        json=_payload(blueprint.id),
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 403


async def test_get_nonexistent_question_blueprint_section_returns_404(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin9", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="GETMISSING")
    token = await _login(client, "bsadmin9")

    response = await client.get(
        f"/api/v1/question-blueprint-sections/{uuid.uuid4()}",
        headers=_institution_headers(token, blueprint.institution_id),
    )

    assert response.status_code == 404


async def test_question_blueprint_section_get_update_soft_delete_restore_round_trip(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin10", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="ROUNDTRIP")
    token = await _login(client, "bsadmin10")
    headers = _institution_headers(token, blueprint.institution_id)

    created = await client.post(
        "/api/v1/question-blueprint-sections", json=_payload(blueprint.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    created_updated_at = created.json()["updated_at"]

    get_response = await client.get(
        f"/api/v1/question-blueprint-sections/{entity_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["number_of_questions"] == 10

    update_response = await client.patch(
        f"/api/v1/question-blueprint-sections/{entity_id}",
        json={"number_of_questions": 15},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["number_of_questions"] == 15
    # SQLite's func.now() is whole-second resolution -- use >=, not !=.
    assert update_response.json()["updated_at"] >= created_updated_at

    delete_response = await client.delete(
        f"/api/v1/question-blueprint-sections/{entity_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/api/v1/question-blueprint-sections/{entity_id}", headers=headers
    )
    assert get_after_delete.status_code == 404

    deleted_list = await client.get("/api/v1/question-blueprint-sections/deleted", headers=headers)
    assert deleted_list.status_code == 200
    assert any(item["id"] == entity_id for item in deleted_list.json()["items"])

    restore_response = await client.post(
        f"/api/v1/question-blueprint-sections/{entity_id}/restore", headers=headers
    )
    assert restore_response.status_code == 200

    get_after_restore = await client.get(
        f"/api/v1/question-blueprint-sections/{entity_id}", headers=headers
    )
    assert get_after_restore.status_code == 200


async def test_list_question_blueprint_sections_pagination_and_envelope(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin11", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="LIST")
    token = await _login(client, "bsadmin11")
    headers = _institution_headers(token, blueprint.institution_id)

    for i in range(5):
        response = await client.post(
            "/api/v1/question-blueprint-sections",
            json=_payload(blueprint.id, display_order=i),
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get(
        "/api/v1/question-blueprint-sections?page=1&page_size=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


async def test_bulk_create_question_blueprint_sections_succeeds(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsbulk1", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BULK")
    token = await _login(client, "bsbulk1")
    headers = _institution_headers(token, blueprint.institution_id)

    response = await client.post(
        "/api/v1/question-blueprint-sections/bulk",
        json=[
            _payload(blueprint.id, display_order=1),
            _payload(blueprint.id, display_order=2),
        ],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 2
    assert body["errors"] == []


async def test_bulk_create_question_blueprint_sections_collects_per_item_errors(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsbulk2", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="BULKERR")
    token = await _login(client, "bsbulk2")
    headers = _institution_headers(token, blueprint.institution_id)

    response = await client.post(
        "/api/v1/question-blueprint-sections/bulk",
        json=[_payload(blueprint.id), _payload(uuid.uuid4())],
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert "error" in body["errors"][0]


async def test_export_question_blueprint_sections_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsexport1", role=seed_rbac["super_admin"])
    token = await _login(client, "bsexport1")

    response = await client.get(
        "/api/v1/question-blueprint-sections/export", headers=auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"


async def test_import_question_blueprint_sections_returns_skeleton_response(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsimport1", role=seed_rbac["super_admin"])
    token = await _login(client, "bsimport1")

    response = await client.post(
        "/api/v1/question-blueprint-sections/import", headers=auth_headers(token)
    )

    assert response.status_code == 202


async def test_update_question_blueprint_section_accepts_new_blueprint_in_same_institution(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin9", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="UPDFK")
    other_blueprint = await _create_second_blueprint(db_session, blueprint, code="UPDFK2")
    token = await _login(client, "bsadmin9")
    headers = _institution_headers(token, blueprint.institution_id)

    created = await client.post(
        "/api/v1/question-blueprint-sections", json=_payload(blueprint.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-blueprint-sections/{entity_id}",
        json={"blueprint_id": str(other_blueprint.id)},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["blueprint_id"] == str(other_blueprint.id)


async def test_update_question_blueprint_section_rejects_nonexistent_blueprint(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="bsadmin10", role=seed_rbac["super_admin"])
    blueprint = await _create_blueprint(db_session, code="UPDBAD")
    token = await _login(client, "bsadmin10")
    headers = _institution_headers(token, blueprint.institution_id)

    created = await client.post(
        "/api/v1/question-blueprint-sections", json=_payload(blueprint.id), headers=headers
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]

    update_response = await client.patch(
        f"/api/v1/question-blueprint-sections/{entity_id}",
        json={"blueprint_id": str(uuid.uuid4())},
        headers=headers,
    )

    assert update_response.status_code == 404
