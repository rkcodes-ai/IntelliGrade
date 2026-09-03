"""Unit tests for the pure mark-scheme range-expansion/validation logic."""

import uuid
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationAppError
from app.models.mark_scheme_range import MarkSchemeRange
from app.services.mark_scheme_service import expand_mark_scheme_ranges, validate_coverage


def _range(start: str, end: str, marks: str, order: int = 0) -> MarkSchemeRange:
    return MarkSchemeRange(
        institution_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        question_range_start=start,
        question_range_end=end,
        marks_per_question=Decimal(marks),
        display_order=order,
    )


def test_expand_mark_scheme_ranges_matches_brief_example() -> None:
    ranges = [_range("1", "12", "1", 0), _range("13", "17", "2", 1), _range("18", "25", "14", 2)]

    result = expand_mark_scheme_ranges(ranges)

    assert len(result.marks_by_question) == 25
    assert result.marks_by_question["1"] == Decimal("1")
    assert result.marks_by_question["12"] == Decimal("1")
    assert result.marks_by_question["13"] == Decimal("2")
    assert result.marks_by_question["17"] == Decimal("2")
    assert result.marks_by_question["18"] == Decimal("14")
    assert result.marks_by_question["25"] == Decimal("14")
    assert result.warnings == []


def test_expand_mark_scheme_ranges_handles_single_question_range() -> None:
    result = expand_mark_scheme_ranges([_range("5", "5", "3")])
    assert result.marks_by_question == {"5": Decimal("3")}


def test_expand_mark_scheme_ranges_rejects_end_before_start() -> None:
    with pytest.raises(ValidationAppError):
        expand_mark_scheme_ranges([_range("10", "5", "1")])


def test_expand_mark_scheme_ranges_rejects_non_integer_question_number() -> None:
    with pytest.raises(ValidationAppError):
        expand_mark_scheme_ranges([_range("abc", "5", "1")])


def test_expand_mark_scheme_ranges_later_range_wins_on_overlap_with_warning() -> None:
    ranges = [_range("1", "10", "1", order=0), _range("5", "8", "2", order=1)]

    result = expand_mark_scheme_ranges(ranges)

    assert result.marks_by_question["5"] == Decimal("2")
    assert result.marks_by_question["1"] == Decimal("1")
    assert len(result.warnings) > 0


def test_validate_coverage_returns_no_warnings_for_exact_match() -> None:
    marks_by_question = {str(i): Decimal("1") for i in range(1, 26)}
    warnings = validate_coverage(marks_by_question, [str(i) for i in range(1, 26)])
    assert warnings == []


def test_validate_coverage_flags_questions_missing_marks() -> None:
    marks_by_question = {str(i): Decimal("1") for i in range(1, 20)}
    warnings = validate_coverage(marks_by_question, [str(i) for i in range(1, 26)])
    assert len(warnings) == 1
    assert "20" in warnings[0]


def test_validate_coverage_flags_marks_for_nonexistent_questions() -> None:
    marks_by_question = {str(i): Decimal("1") for i in range(1, 26)}
    warnings = validate_coverage(marks_by_question, [str(i) for i in range(1, 21)])
    assert len(warnings) == 1
    assert "21" in warnings[0]
