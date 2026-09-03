"""Tests for `app.services.reference_answer_evidence_service` (Step 5
milestone) — real DB-backed evidence bundle assembly, reusing Step 4's
already-persisted `DocumentRegion` rows (Math/Diagram/Table evidence)
without re-running any analysis.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_region import DocumentRegion
from app.models.official_exam_document_page import OfficialExamDocumentPage
from app.models.rubric import Rubric
from app.models.rubric_criterion import RubricCriterion
from app.services.reference_answer_evidence_service import assemble_evidence_bundle
from tests.test_answer_evaluation_model_answer_scoping import (
    _create_exam_under,
    _create_institution,
    _seed_question_and_model_answer,
)


async def _create_uploader(db_session: AsyncSession):
    from tests.conftest import create_test_user

    return await create_test_user(db_session, username="evidence_bundle_uploader")


async def test_evidence_bundle_includes_no_multimodal_evidence_when_none_exists(
    db_session: AsyncSession,
) -> None:
    institution = await _create_institution(db_session, code="EVB1")
    exam = await _create_exam_under(db_session, institution, code="EVB1")
    uploader = await _create_uploader(db_session)
    question, model_answer, _doc = await _seed_question_and_model_answer(
        db_session, exam=exam, uploader=uploader, model_answer_text="Plain text answer only."
    )

    bundle = await assemble_evidence_bundle(
        db_session,
        institution_id=institution.id,
        question=question,
        model_answer=model_answer,
        maximum_marks=10.0,
    )

    assert bundle.question_text == question.question_text
    assert bundle.model_answer_text == "Plain text answer only."
    assert bundle.has_multimodal_evidence() is False
    assert bundle.rubric_evidence is None


async def test_evidence_bundle_links_real_math_diagram_table_regions(
    db_session: AsyncSession,
) -> None:
    institution = await _create_institution(db_session, code="EVB2")
    exam = await _create_exam_under(db_session, institution, code="EVB2")
    uploader = await _create_uploader(db_session)
    question, model_answer, ma_document = await _seed_question_and_model_answer(
        db_session,
        exam=exam,
        uploader=uploader,
        model_answer_text="Answer with a diagram and formula.",
    )
    model_answer.page_number = 1
    await db_session.flush()

    page = OfficialExamDocumentPage(
        institution_id=institution.id,
        document_id=ma_document.id,
        page_number=1,
        storage_key="pages/ma-page-1.png",
    )
    db_session.add(page)
    await db_session.flush()

    math_region = DocumentRegion(
        institution_id=institution.id,
        official_exam_document_page_id=page.id,
        region_type="EQUATION",
        source_label="Equation",
        source_detector="surya_layout",
        reading_order=0,
        bbox_left=10,
        bbox_top=10,
        bbox_width=100,
        bbox_height=30,
        confidence=Decimal("90.00"),
        extra_metadata={"recognized_expression": "E = mc^2", "status": "SUCCESS"},
    )
    diagram_region = DocumentRegion(
        institution_id=institution.id,
        official_exam_document_page_id=page.id,
        region_type="DIAGRAM",
        source_label="Figure",
        source_detector="classical_vision",
        reading_order=1,
        bbox_left=10,
        bbox_top=50,
        bbox_width=200,
        bbox_height=150,
        confidence=Decimal("85.00"),
        extra_metadata={"diagram_type": "flowchart", "status": "SUCCESS"},
    )
    table_region = DocumentRegion(
        institution_id=institution.id,
        official_exam_document_page_id=page.id,
        region_type="TABLE",
        source_label="Table",
        source_detector="hough_line_grid",
        reading_order=2,
        bbox_left=10,
        bbox_top=210,
        bbox_width=200,
        bbox_height=100,
        confidence=Decimal("80.00"),
        extra_metadata={"row_count": 2, "col_count": 2},
    )
    # A PRINTED_TEXT region must never leak into math/diagram/table buckets.
    text_region = DocumentRegion(
        institution_id=institution.id,
        official_exam_document_page_id=page.id,
        region_type="PRINTED_TEXT",
        source_label="Text",
        source_detector="surya_layout",
        reading_order=3,
        bbox_left=10,
        bbox_top=320,
        bbox_width=200,
        bbox_height=30,
        confidence=Decimal("95.00"),
    )
    db_session.add_all([math_region, diagram_region, table_region, text_region])
    await db_session.flush()

    bundle = await assemble_evidence_bundle(
        db_session,
        institution_id=institution.id,
        question=question,
        model_answer=model_answer,
        maximum_marks=10.0,
    )

    assert bundle.has_multimodal_evidence() is True
    assert len(bundle.math_evidence) == 1
    assert bundle.math_evidence[0].extra_metadata["recognized_expression"] == "E = mc^2"
    assert len(bundle.diagram_evidence) == 1
    assert bundle.diagram_evidence[0].extra_metadata["diagram_type"] == "flowchart"
    assert len(bundle.table_evidence) == 1
    assert bundle.table_evidence[0].extra_metadata["row_count"] == 2
    assert bundle.page_level_association is True


async def test_evidence_bundle_includes_rubric_when_linked(db_session: AsyncSession) -> None:
    from app.models.assessment import Assessment
    from app.models.bloom_taxonomy_level import BloomTaxonomyLevel
    from app.models.difficulty_level import DifficultyLevel
    from app.models.question import Question
    from app.models.question_category import QuestionCategory
    from app.models.question_type import QuestionType

    institution = await _create_institution(db_session, code="EVB3")
    exam = await _create_exam_under(db_session, institution, code="EVB3")
    uploader = await _create_uploader(db_session)
    question, model_answer, _doc = await _seed_question_and_model_answer(
        db_session, exam=exam, uploader=uploader, model_answer_text="Some answer."
    )

    assessment = await db_session.get(Assessment, exam.assessment_id)
    assert assessment is not None
    subject_id = assessment.subject_id

    question_type = QuestionType(institution_id=institution.id, name="Descriptive", code="DESC")
    question_category = QuestionCategory(
        institution_id=institution.id, name="Theory", code="THEORY"
    )
    difficulty_level = DifficultyLevel(
        institution_id=institution.id, name="Medium", code="MED", level_order=2
    )
    bloom_level = BloomTaxonomyLevel(
        institution_id=institution.id, name="Understand", code="UNDERSTAND", level_order=2
    )
    db_session.add_all([question_type, question_category, difficulty_level, bloom_level])
    await db_session.flush()

    bank_question = Question(
        institution_id=institution.id,
        subject_id=subject_id,
        question_category_id=question_category.id,
        question_type_id=question_type.id,
        difficulty_level_id=difficulty_level.id,
        bloom_level_id=bloom_level.id,
        question_text="Bank question text",
        marks=Decimal("10.00"),
        created_by=uploader.id,
    )
    db_session.add(bank_question)
    await db_session.flush()
    question.linked_question_id = bank_question.id
    await db_session.flush()

    rubric = Rubric(
        institution_id=institution.id,
        question_id=bank_question.id,
        name="Rubric",
        total_marks=Decimal("10.00"),
    )
    db_session.add(rubric)
    await db_session.flush()
    criterion = RubricCriterion(
        institution_id=institution.id,
        rubric_id=rubric.id,
        name="Definition",
        max_marks=Decimal("2.00"),
        display_order=0,
    )
    db_session.add(criterion)
    await db_session.flush()

    bundle = await assemble_evidence_bundle(
        db_session,
        institution_id=institution.id,
        question=question,
        model_answer=model_answer,
        maximum_marks=10.0,
    )

    assert bundle.rubric_evidence is not None
    assert bundle.rubric_evidence.name == "Rubric"
    assert len(bundle.rubric_evidence.criteria) == 1
    assert bundle.rubric_evidence.criteria[0]["name"] == "Definition"


async def test_evidence_bundle_provenance_records_source_ids(db_session: AsyncSession) -> None:
    institution = await _create_institution(db_session, code="EVB4")
    exam = await _create_exam_under(db_session, institution, code="EVB4")
    uploader = await _create_uploader(db_session)
    question, model_answer, _doc = await _seed_question_and_model_answer(
        db_session, exam=exam, uploader=uploader, model_answer_text="Answer text."
    )

    bundle = await assemble_evidence_bundle(
        db_session,
        institution_id=institution.id,
        question=question,
        model_answer=model_answer,
        maximum_marks=10.0,
    )

    assert bundle.provenance["extracted_question_id"] == str(question.id)
    assert bundle.provenance["extracted_model_answer_id"] == str(model_answer.id)


def test_bundle_to_dict_is_json_serializable() -> None:
    import json

    from app.services.reference_answer_evidence_service import ReferenceEvidenceBundle

    bundle = ReferenceEvidenceBundle(question_text="Q", model_answer_text="A", maximum_marks=5.0)
    serialized = json.dumps(bundle.to_dict())
    assert "question_text" in serialized
