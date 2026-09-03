"""
Extracts one student's per-question answer text from their OCR'd
`AnswerScript.structured_content` (Module 05, read-only — never modified;
ADR-038). Used by `app.services.answer_evaluation_service` to build the
`student_answer_text` snapshot on `AnswerEvaluation`.

Deliberately does NOT use `structured_content["pages"][*]["detected_questions"]`'s
`char_offset` values — those index into the page's `normalized_text` at
the point `document_structure_service.build_page_structure()` ran
(Module 05), which is discarded and never persisted onto the structure
tree itself, so post-hoc slicing against it would be indexing into a
string that no longer exists in this exact form. Instead, this module
reconstructs each page's line-broken text directly from the already-
persisted `blocks[].lines[].text` values (the same reliable source
`app.tasks.official_document_tasks` reconstructs from) and re-applies
`app.services.official_document_extraction_service`'s already-tested
boundary-detection heuristic — reused, not duplicated.
"""

from typing import Any

from app.services.official_document_extraction_service import extract_answers_from_text


def _reconstruct_page_text(page: dict[str, Any]) -> str:
    lines = [
        line.get("text", "") for block in page.get("blocks", []) for line in block.get("lines", [])
    ]
    return "\n".join(lines)


def extract_student_answers_by_question(structured_content: dict[str, Any]) -> dict[str, str]:
    """Returns `{question_number: answer_text}` for every question boundary
    detected across the whole script (spanning pages, since a student's
    answer to one question may continue onto a later page)."""
    pages = structured_content.get("pages", [])
    combined_text = "\n".join(_reconstruct_page_text(page) for page in pages)
    candidates = extract_answers_from_text(combined_text)
    return {candidate.question_number: candidate.answer_text for candidate in candidates}
