"""
Official-document question/answer extraction heuristics (Module 06).

A deliberately NEW module, not an addition to Module 05's frozen
`app.services.document_structure_service` (ADR-036 — no Module 05 file is
modified). It mirrors that module's regex-heuristic *style* (best-effort,
not evaluative, matching `Q1`/`Question 2:`/`3)`-style numbering) but
targets a different extraction goal: the full text of each numbered
question/answer, plus a best-effort *printed* marks annotation, not just
where a boundary starts.

Like Module 05's `detect_question_markers`, this is explicitly boundary
*detection and text segmentation*, never answer scoring or evaluation —
that stays entirely in `app.services.ai`.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_QUESTION_MARKER_PATTERN = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*(\d{1,3}[a-zA-Z]?)[.):]?\s*|(\d{1,3}[a-zA-Z]?)[.)]\s+)",
    re.IGNORECASE | re.MULTILINE,
)

#: Matches a trailing printed-marks annotation near a question boundary,
#: e.g. "[2]", "(4 marks)", "(5M)", "- 3 marks". Deliberately permissive
#: (best-effort detection) — a missed or misdetected annotation is
#: expected to be caught and corrected during teacher verification, not a
#: reason to fail extraction outright.
_MARKS_ANNOTATION_PATTERN = re.compile(
    r"[\[(]\s*(\d{1,3})\s*(?:marks?|m)?\s*[\])]|[-—]\s*(\d{1,3})\s*(?:marks?|m)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedQuestionCandidate:
    question_number: str
    question_text: str
    detected_marks: Decimal | None
    char_offset: int


@dataclass(frozen=True)
class ExtractedAnswerCandidate:
    question_number: str
    answer_text: str
    char_offset: int


@dataclass(frozen=True)
class ExtractedMarkRangeCandidate:
    question_range_start: str
    question_range_end: str
    marks_per_question: Decimal
    char_offset: int


#: Matches mark-scheme lines like "Questions 1-12 = 1 mark each",
#: "Q13-17: 2 marks", "Question 5 = 3 marks" (single-question range, start
#: == end). Deliberately permissive, same "best-effort, corrected during
#: teacher verification" philosophy as every other pattern in this module
#: — never treated as authoritative without a teacher confirming it.
_MARK_RANGE_PATTERN = re.compile(
    r"questions?\s*(\d{1,3})(?:\s*(?:-|–|to)\s*(\d{1,3}))?\s*[:=]?\s*"
    r"(?:is|are|carr(?:y|ies))?\s*(\d{1,3}(?:\.\d+)?)\s*marks?",
    re.IGNORECASE,
)


def _segments(raw_text: str) -> list[tuple[str, str, int]]:
    """Shared boundary-splitting logic: returns
    `(question_number, segment_text, char_offset)` tuples."""
    matches = list(_QUESTION_MARKER_PATTERN.finditer(raw_text))
    segments: list[tuple[str, str, int]] = []
    for index, match in enumerate(matches):
        number = match.group(1) or match.group(2)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        segments.append((number, raw_text[start:end].strip(), match.start()))
    return segments


def _detect_printed_marks(segment: str) -> Decimal | None:
    match = _MARKS_ANNOTATION_PATTERN.search(segment)
    if not match:
        return None
    raw_value = match.group(1) or match.group(2)
    try:
        return Decimal(raw_value)
    except InvalidOperation:  # pragma: no cover - raw_value is regex-guaranteed digits
        return None


def extract_questions_from_text(raw_text: str) -> list[ExtractedQuestionCandidate]:
    """Splits a question-paper document's raw OCR text into per-question
    candidates, each with a best-effort detected printed-marks value."""
    return [
        ExtractedQuestionCandidate(
            question_number=number,
            question_text=segment,
            detected_marks=_detect_printed_marks(segment),
            char_offset=offset,
        )
        for number, segment, offset in _segments(raw_text)
    ]


def extract_answers_from_text(raw_text: str) -> list[ExtractedAnswerCandidate]:
    """Splits a model-answer document's raw OCR text into per-answer
    candidates, keyed by the same question-number convention as
    `extract_questions_from_text` so the two can be matched at the
    service layer by `question_number`."""
    return [
        ExtractedAnswerCandidate(question_number=number, answer_text=segment, char_offset=offset)
        for number, segment, offset in _segments(raw_text)
    ]


def extract_mark_ranges_from_text(raw_text: str) -> list[ExtractedMarkRangeCandidate]:
    """Best-effort parse of a mark scheme document's raw OCR text into
    range candidates (e.g. "Questions 1-12 = 1 mark" ->
    `question_range_start="1", question_range_end="12", marks_per_question=1`).
    Every candidate is `verification_status="pending"` once persisted —
    never treated as authoritative before a teacher confirms it, per the
    brief's "never hardcode any mark ranges" requirement applying equally
    to *extracted* ranges as to application code."""
    candidates = []
    for match in _MARK_RANGE_PATTERN.finditer(raw_text):
        start, end, marks = match.group(1), match.group(2), match.group(3)
        candidates.append(
            ExtractedMarkRangeCandidate(
                question_range_start=start,
                question_range_end=end or start,
                marks_per_question=Decimal(marks),
                char_offset=match.start(),
            )
        )
    return candidates
