"""
Reference Evidence Bundle assembly (Step 5 milestone — AI Reference
Answer Builder extension, Sections 12-21).

This is an ADDITIVE extension of the already-shipped AI Reference
Answer Builder (`app/services/ai_reference_answer_service.py`) — it does
NOT replace `ReferenceGenerationInput`/`ReferenceContentSchema`/
`AIReferenceAnswer`. It adds a deterministic, evidence-first assembly
step that gathers Step 4/4.2's already-computed Math/Diagram/Table/
Language evidence for a model answer's page(s) *before* any AI call, so
a provider can consume structured evidence instead of re-deriving it
(Section 56/57: "do NOT rerun OCR/math/diagram/table/language detection
-- consume existing evidence").

**Association is page-level, not exact question-span** (an honest,
documented limitation carried over from the Document Intelligence
milestone): `DocumentRegion` links to a page (`official_exam_document_
page_id`), not to a specific `ExtractedQuestion`/`ExtractedModelAnswer`
row. This module resolves evidence via `ExtractedModelAnswer.document_id`
+ `page_number` -> the matching `OfficialExamDocumentPage` -> every
`DocumentRegion` on that page whose `region_type` is `DIAGRAM`/
`EQUATION`/`TABLE`. When a model answer's page has multiple questions'
diagrams/equations, this MAY include evidence belonging to a
neighboring question -- documented honestly via `page_level_association`
in the bundle's provenance rather than silently claimed as
question-exact.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_region import DocumentRegion
from app.models.extracted_model_answer import ExtractedModelAnswer
from app.models.extracted_question import ExtractedQuestion
from app.models.official_exam_document_page import OfficialExamDocumentPage
from app.models.rubric import Rubric
from app.models.rubric_criterion import RubricCriterion

_EVIDENCE_REGION_TYPES = ("DIAGRAM", "EQUATION", "TABLE")


@dataclass(frozen=True)
class RegionEvidenceRef:
    """One `DocumentRegion`'s already-computed evidence, referenced by
    ID (never copied/mutated) — provenance is the region's own id/bbox/
    detector, exactly as Step 4 persisted it."""

    region_id: str
    region_type: str
    bbox: tuple[int, int, int, int]
    confidence: float
    source_detector: str
    extra_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "region_type": self.region_type,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_detector": self.source_detector,
            "extra_metadata": self.extra_metadata,
        }


@dataclass(frozen=True)
class RubricEvidence:
    rubric_id: str
    name: str
    total_marks: float
    criteria: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rubric_id": self.rubric_id,
            "name": self.name,
            "total_marks": self.total_marks,
            "criteria": self.criteria,
        }


@dataclass(frozen=True)
class ReferenceEvidenceBundle:
    """The deterministic, pre-AI evidence bundle (Section 13) — an AI
    provider consumes this, never a giant concatenated OCR-string blob."""

    question_text: str
    model_answer_text: str
    maximum_marks: float
    rubric_evidence: RubricEvidence | None = None
    math_evidence: list[RegionEvidenceRef] = field(default_factory=list)
    diagram_evidence: list[RegionEvidenceRef] = field(default_factory=list)
    table_evidence: list[RegionEvidenceRef] = field(default_factory=list)
    page_level_association: bool = True
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_text": self.question_text,
            "model_answer_text": self.model_answer_text,
            "maximum_marks": self.maximum_marks,
            "rubric_evidence": self.rubric_evidence.to_dict() if self.rubric_evidence else None,
            "math_evidence": [r.to_dict() for r in self.math_evidence],
            "diagram_evidence": [r.to_dict() for r in self.diagram_evidence],
            "table_evidence": [r.to_dict() for r in self.table_evidence],
            "page_level_association": self.page_level_association,
            "provenance": self.provenance,
        }

    def has_multimodal_evidence(self) -> bool:
        return bool(self.math_evidence or self.diagram_evidence or self.table_evidence)


def _to_region_ref(region: DocumentRegion) -> RegionEvidenceRef:
    return RegionEvidenceRef(
        region_id=str(region.id),
        region_type=region.region_type,
        bbox=(region.bbox_left, region.bbox_top, region.bbox_width, region.bbox_height),
        confidence=float(region.confidence),
        source_detector=region.source_detector,
        extra_metadata=region.extra_metadata or {},
    )


async def _fetch_page_region_evidence(
    session: AsyncSession, *, institution_id: uuid.UUID, document_id: uuid.UUID, page_number: int
) -> list[DocumentRegion]:
    page_query = select(OfficialExamDocumentPage).where(
        OfficialExamDocumentPage.institution_id == institution_id,
        OfficialExamDocumentPage.document_id == document_id,
        OfficialExamDocumentPage.page_number == page_number,
        OfficialExamDocumentPage.deleted_at.is_(None),
    )
    page = (await session.execute(page_query)).scalars().first()
    if page is None:
        return []

    region_query = select(DocumentRegion).where(
        DocumentRegion.institution_id == institution_id,
        DocumentRegion.official_exam_document_page_id == page.id,
        DocumentRegion.region_type.in_(_EVIDENCE_REGION_TYPES),
        DocumentRegion.deleted_at.is_(None),
    )
    return list((await session.execute(region_query)).scalars().all())


async def _fetch_rubric_evidence(
    session: AsyncSession, *, institution_id: uuid.UUID, question_id: uuid.UUID
) -> RubricEvidence | None:
    rubric_query = select(Rubric).where(
        Rubric.institution_id == institution_id,
        Rubric.question_id == question_id,
        Rubric.deleted_at.is_(None),
    )
    rubric = (await session.execute(rubric_query)).scalars().first()
    if rubric is None:
        return None

    criteria_query = (
        select(RubricCriterion)
        .where(
            RubricCriterion.institution_id == institution_id,
            RubricCriterion.rubric_id == rubric.id,
            RubricCriterion.deleted_at.is_(None),
        )
        .order_by(RubricCriterion.display_order)
    )
    criteria = (await session.execute(criteria_query)).scalars().all()
    return RubricEvidence(
        rubric_id=str(rubric.id),
        name=rubric.name,
        total_marks=float(rubric.total_marks),
        criteria=[
            {
                "criterion_id": str(c.id),
                "name": c.name,
                "max_marks": float(c.max_marks),
                "is_mandatory": c.is_mandatory,
                "is_language_criterion": c.is_language_criterion,
            }
            for c in criteria
        ],
    )


async def assemble_evidence_bundle(
    session: AsyncSession,
    *,
    institution_id: uuid.UUID,
    question: ExtractedQuestion,
    model_answer: ExtractedModelAnswer,
    maximum_marks: float,
) -> ReferenceEvidenceBundle:
    """Real, deterministic evidence gathering — never invokes an AI
    model, never re-runs OCR/math/diagram/table analysis (Section 57).
    Failure to find optional evidence (no page number recorded, no
    regions detected, no rubric) is NOT an error — it degrades to empty
    lists, exactly like Step 4's own "unknown stays unknown" discipline."""
    math_evidence: list[RegionEvidenceRef] = []
    diagram_evidence: list[RegionEvidenceRef] = []
    table_evidence: list[RegionEvidenceRef] = []

    if model_answer.page_number is not None:
        regions = await _fetch_page_region_evidence(
            session,
            institution_id=institution_id,
            document_id=model_answer.document_id,
            page_number=model_answer.page_number,
        )
        for region in regions:
            ref = _to_region_ref(region)
            if region.region_type == "EQUATION":
                math_evidence.append(ref)
            elif region.region_type == "DIAGRAM":
                diagram_evidence.append(ref)
            elif region.region_type == "TABLE":
                table_evidence.append(ref)

    rubric_evidence: RubricEvidence | None = None
    if question.linked_question_id is not None:
        rubric_evidence = await _fetch_rubric_evidence(
            session, institution_id=institution_id, question_id=question.linked_question_id
        )

    return ReferenceEvidenceBundle(
        question_text=question.question_text,
        model_answer_text=model_answer.answer_text,
        maximum_marks=maximum_marks,
        rubric_evidence=rubric_evidence,
        math_evidence=math_evidence,
        diagram_evidence=diagram_evidence,
        table_evidence=table_evidence,
        page_level_association=True,
        provenance={
            "extracted_question_id": str(question.id),
            "extracted_model_answer_id": str(model_answer.id),
            "model_answer_page_number": model_answer.page_number,
        },
    )
