"""
Mark scheme expansion (Module 06) — turns a verified list of
`MarkSchemeRange` rows (e.g. "Questions 1-12 = 1 mark",
"Questions 13-17 = 2 marks") into a per-question maximum-marks map.

Every range is data (a `MarkSchemeRange` row), never a hardcoded
application-code constant — this module works for any examination
pattern the ranges describe, per the brief's explicit "never hardcode
any mark ranges... support any examination pattern" requirement.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.exceptions import ValidationAppError
from app.models.mark_scheme_range import MarkSchemeRange

_LEADING_INT_PATTERN = re.compile(r"^\s*(\d+)")


@dataclass(frozen=True)
class MarkSchemeExpansionResult:
    marks_by_question: dict[str, Decimal]
    warnings: list[str] = field(default_factory=list)


def _parse_leading_int(question_number: str) -> int:
    """Extracts the leading integer from a question-number string
    (`"12"` -> `12`, `"12a"` -> `12`). Range expansion in this pass only
    supports plain-integer question numbering within a range's bounds —
    alphanumeric sub-parts (`"12a"`, `"12b"`) are supported as individual
    `ExtractedQuestion.question_number` values elsewhere in Module 06, but
    a *range* like "12a-15b" cannot be iterated numerically and raises
    `ValidationAppError` here rather than guessing."""
    match = _LEADING_INT_PATTERN.match(question_number)
    if not match:
        raise ValidationAppError(
            f"Cannot parse a question number from {question_number!r} — "
            "mark scheme ranges must start with a plain integer."
        )
    return int(match.group(1))


def expand_mark_scheme_ranges(ranges: list[MarkSchemeRange]) -> MarkSchemeExpansionResult:
    """Expands every range into `{question_number_str: marks}` entries.
    Later ranges (by `display_order`) win on overlap, with a warning
    recorded rather than silently dropped — lets a teacher's edit of one
    range supersede an earlier, now-incorrect one without deleting it
    first, while still surfacing the conflict for review."""
    marks_by_question: dict[str, Decimal] = {}
    warnings: list[str] = []

    for scheme_range in sorted(ranges, key=lambda r: r.display_order):
        start = _parse_leading_int(scheme_range.question_range_start)
        end = _parse_leading_int(scheme_range.question_range_end)
        if end < start:
            raise ValidationAppError(
                f"Mark scheme range {scheme_range.question_range_start}-"
                f"{scheme_range.question_range_end} is invalid: end is before start."
            )
        for question_number in range(start, end + 1):
            key = str(question_number)
            if (
                key in marks_by_question
                and marks_by_question[key] != scheme_range.marks_per_question
            ):
                warnings.append(
                    f"Question {key} is covered by more than one range with different "
                    f"marks ({marks_by_question[key]} vs {scheme_range.marks_per_question}); "
                    f"using the later range's value."
                )
            marks_by_question[key] = scheme_range.marks_per_question

    return MarkSchemeExpansionResult(marks_by_question=marks_by_question, warnings=warnings)


def validate_coverage(
    marks_by_question: dict[str, Decimal], detected_question_numbers: list[str]
) -> list[str]:
    """Cross-checks the expanded mark scheme against the question numbers
    actually detected in the paired Question Paper document — e.g. "you
    said Q1-25 but the paper only has 20 questions." Returns human-readable
    warnings; never raises, since a mismatch is something for a teacher to
    resolve during verification, not a hard failure."""
    warnings: list[str] = []
    marked_questions = set(marks_by_question)
    detected = set(detected_question_numbers)

    missing_marks = sorted(detected - marked_questions, key=lambda q: _safe_sort_key(q))
    if missing_marks:
        warnings.append(
            f"Questions detected in the paper but not covered by any mark scheme range: "
            f"{', '.join(missing_marks)}."
        )

    extra_marks = sorted(marked_questions - detected, key=lambda q: _safe_sort_key(q))
    if extra_marks:
        warnings.append(
            f"Mark scheme covers question numbers not found in the question paper: "
            f"{', '.join(extra_marks)}."
        )

    return warnings


def _safe_sort_key(question_number: str) -> tuple[int, str]:
    try:
        return (_parse_leading_int(question_number), question_number)
    except ValidationAppError:
        return (10**9, question_number)
