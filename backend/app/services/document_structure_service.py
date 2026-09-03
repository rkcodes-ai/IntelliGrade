"""
Stage 6/8 — Document Structure Extraction + Structured Output Generation.

Builds the `AnswerScript.structured_content` JSON tree (see ADR-031) from
the already-persisted `OCRResult`/`OCRBlock` rows for every page of one
script. Pure data assembly + regex heuristics — explicitly NOT answer
evaluation: `detected_questions` marks where a question boundary
*appears* to start (a "Q1"/"Question 2:"/"1)"-style marker in the
normalized text), nothing here reads meaning from, scores, or grades the
content that follows it.
"""

import re
from dataclasses import dataclass

#: Matches common exam-question numbering styles: "Q1", "Q.1", "Question 2:",
#: "3)", "4.". Deliberately permissive (best-effort detection, not a strict
#: grammar) — false positives are acceptable since Module 06 will still need
#: to confirm boundaries against the actual `Question` bank content.
_QUESTION_MARKER_PATTERN = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*(\d{1,3})\b|(\d{1,3})[.)]\s)", re.IGNORECASE | re.MULTILINE
)

STRUCTURED_CONTENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DetectedQuestionMarker:
    marker_text: str
    question_number: str
    page_number: int
    char_offset: int


def detect_question_markers(
    normalized_text: str, *, page_number: int
) -> list[DetectedQuestionMarker]:
    markers: list[DetectedQuestionMarker] = []
    for match in _QUESTION_MARKER_PATTERN.finditer(normalized_text):
        number = match.group(1) or match.group(2)
        markers.append(
            DetectedQuestionMarker(
                marker_text=match.group(0).strip(),
                question_number=number,
                page_number=page_number,
                char_offset=match.start(),
            )
        )
    return markers


def build_page_structure(
    *, page_number: int, normalized_text: str, blocks: list[dict[str, object]]
) -> dict[str, object]:
    """`blocks` is the already-serialized block/line/word tree (see
    `OCRResultService.get_hierarchy()`) for this page's `OCRResult`."""
    markers = detect_question_markers(normalized_text, page_number=page_number)
    return {
        "page_number": page_number,
        "detected_questions": [
            {
                "marker_text": m.marker_text,
                "question_number": m.question_number,
                "char_offset": m.char_offset,
            }
            for m in markers
        ],
        "blocks": blocks,
    }


def build_structured_content(pages: list[dict[str, object]]) -> dict[str, object]:
    """`pages` is a list of `build_page_structure(...)` results, one per
    `AnswerScriptPage`, in page order."""
    return {
        "schema_version": STRUCTURED_CONTENT_SCHEMA_VERSION,
        "page_count": len(pages),
        "pages": pages,
    }
