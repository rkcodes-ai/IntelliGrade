"""
Stage 7 — Text Normalization.

Pure functions, no I/O, no DB access: takes an `OCRResult.raw_text` string
and produces the `normalized_text` stored alongside it. Both are kept
(`raw_text` untouched, `normalized_text` this function's output) so a
later Module 06 step can always fall back to the original if a
normalization heuristic turns out to be lossy for some input.
"""

import re
import unicodedata

_MULTIPLE_WHITESPACE = re.compile(r"[ \t]+")
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")
_STANDALONE_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:page\s*)?\d{1,4}\s*$", re.IGNORECASE | re.MULTILINE
)


def normalize_whitespace(text: str) -> str:
    text = _MULTIPLE_WHITESPACE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines)


def normalize_unicode(text: str) -> str:
    """NFKC: compatibility-composes lookalike characters (e.g. curly vs.
    straight quotes, full-width vs. half-width digits) into one canonical form."""
    return unicodedata.normalize("NFKC", text)


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def rejoin_hyphenated_words(text: str) -> str:
    """A word broken across a line-wrap with a trailing hyphen (`"exam-\\nple"`)
    is rejoined into `"example"` — a common OCR/print artifact, not a real hyphen."""
    return _TRAILING_HYPHEN_LINEBREAK.sub(r"\1\2", text)


def strip_standalone_page_numbers(text: str) -> str:
    """Removes lines that are ONLY a page number (e.g. a footer `"Page 3"` or
    bare `"3"`) — noise for downstream structure extraction, not part of the
    student's actual answer content."""
    return _STANDALONE_PAGE_NUMBER_LINE.sub("", text)


def collapse_blank_lines(text: str) -> str:
    return _MULTIPLE_BLANK_LINES.sub("\n\n", text)


def normalize_text(raw_text: str) -> str:
    """The full Stage 7 pipeline, applied in a fixed order (each step is
    also independently usable/testable above)."""
    text = normalize_unicode(raw_text)
    text = normalize_line_endings(text)
    text = rejoin_hyphenated_words(text)
    text = strip_standalone_page_numbers(text)
    text = normalize_whitespace(text)
    text = collapse_blank_lines(text)
    return text.strip()
