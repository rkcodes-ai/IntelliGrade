"""Unit tests for extracting a student's per-question answer text out of
`AnswerScript.structured_content` (Module 05, read-only)."""

from app.services.answer_extraction_service import extract_student_answers_by_question


def _page(lines: list[str], page_number: int = 1) -> dict:
    return {
        "page_number": page_number,
        "detected_questions": [],
        "blocks": [
            {
                "block_type": "text",
                "reading_order": 0,
                "lines": [
                    {"text": line, "reading_order": i, "words": []} for i, line in enumerate(lines)
                ],
            }
        ],
    }


def test_extract_student_answers_by_question_splits_single_page() -> None:
    structured_content = {
        "schema_version": 1,
        "page_count": 1,
        "pages": [
            _page(
                [
                    "Q1) Photosynthesis is how plants convert light energy.",
                    "It happens in chloroplasts using chlorophyll.",
                    "Q2) The mitochondria is the powerhouse of the cell.",
                ]
            )
        ],
    }

    result = extract_student_answers_by_question(structured_content)

    assert result["1"] == (
        "Photosynthesis is how plants convert light energy.\n"
        "It happens in chloroplasts using chlorophyll."
    )
    assert result["2"] == "The mitochondria is the powerhouse of the cell."


def test_extract_student_answers_by_question_spans_pages() -> None:
    structured_content = {
        "schema_version": 1,
        "page_count": 2,
        "pages": [
            _page(["Q1) This answer starts on page one"], page_number=1),
            _page(["and continues on page two.", "Q2) Second answer."], page_number=2),
        ],
    }

    result = extract_student_answers_by_question(structured_content)

    assert "This answer starts on page one" in result["1"]
    assert "continues on page two" in result["1"]
    assert result["2"] == "Second answer."


def test_extract_student_answers_by_question_handles_empty_structured_content() -> None:
    assert extract_student_answers_by_question({}) == {}


def test_extract_student_answers_by_question_handles_no_markers() -> None:
    structured_content = {"pages": [_page(["just some prose with no question markers"])]}
    assert extract_student_answers_by_question(structured_content) == {}
