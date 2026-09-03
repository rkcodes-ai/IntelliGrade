"""Unit tests for the question/answer/mark-range boundary-detection
heuristics that turn OCR'd official-document text into structured
candidates."""

from decimal import Decimal

from app.services.official_document_extraction_service import (
    extract_answers_from_text,
    extract_mark_ranges_from_text,
    extract_questions_from_text,
)


def test_extract_questions_from_text_handles_q_prefixed_bracketed_marks() -> None:
    text = (
        "Q1) Explain the process of photosynthesis in plants. [2]\n"
        "Q2) What is the powerhouse of the cell? (1 mark)\n"
        "Q3) Describe Newtons three laws of motion. - 5 marks"
    )

    candidates = extract_questions_from_text(text)

    assert [c.question_number for c in candidates] == ["1", "2", "3"]
    assert candidates[0].detected_marks == Decimal("2")
    assert "photosynthesis" in candidates[0].question_text
    assert candidates[1].detected_marks == Decimal("1")
    assert candidates[2].detected_marks == Decimal("5")


def test_extract_questions_from_text_handles_question_colon_style() -> None:
    text = "Question 1: What is X? [3 marks]\nQuestion 2: What is Y?"

    candidates = extract_questions_from_text(text)

    assert candidates[0].question_number == "1"
    assert candidates[0].detected_marks == Decimal("3")
    assert candidates[1].question_number == "2"
    assert candidates[1].detected_marks is None


def test_extract_questions_from_text_handles_plain_numbered_style() -> None:
    text = "1) First question here.\n2) Second question here."
    candidates = extract_questions_from_text(text)
    assert [c.question_number for c in candidates] == ["1", "2"]


def test_extract_questions_from_text_handles_alphanumeric_sub_numbering() -> None:
    text = "12a. Explain Z in detail."
    candidates = extract_questions_from_text(text)
    assert candidates[0].question_number == "12a"


def test_extract_questions_from_text_returns_empty_for_no_markers() -> None:
    assert extract_questions_from_text("just some prose with no question markers") == []


def test_extract_answers_from_text_segments_by_question_number() -> None:
    text = (
        "1) Photosynthesis is how plants convert light into chemical energy.\n"
        "2) The mitochondria is the powerhouse of the cell."
    )

    candidates = extract_answers_from_text(text)

    assert candidates[0].question_number == "1"
    assert "Photosynthesis" in candidates[0].answer_text
    assert candidates[1].question_number == "2"
    assert "mitochondria" in candidates[1].answer_text


def test_extract_mark_ranges_from_text_matches_brief_example() -> None:
    text = (
        "Mark Scheme\n"
        "Questions 1-12 = 1 mark each\n"
        "Questions 13-17: 2 marks\n"
        "Question 18 to 25 carries 14 marks"
    )

    ranges = extract_mark_ranges_from_text(text)

    assert len(ranges) == 3
    assert ranges[0].question_range_start == "1"
    assert ranges[0].question_range_end == "12"
    assert ranges[0].marks_per_question == Decimal("1")
    assert ranges[1].question_range_start == "13"
    assert ranges[1].question_range_end == "17"
    assert ranges[1].marks_per_question == Decimal("2")
    assert ranges[2].question_range_start == "18"
    assert ranges[2].question_range_end == "25"
    assert ranges[2].marks_per_question == Decimal("14")


def test_extract_mark_ranges_from_text_handles_single_question_range() -> None:
    ranges = extract_mark_ranges_from_text("Question 5 = 3 marks")
    assert len(ranges) == 1
    assert ranges[0].question_range_start == "5"
    assert ranges[0].question_range_end == "5"
    assert ranges[0].marks_per_question == Decimal("3")


def test_extract_mark_ranges_from_text_returns_empty_for_no_matches() -> None:
    assert extract_mark_ranges_from_text("no mark scheme content here") == []
