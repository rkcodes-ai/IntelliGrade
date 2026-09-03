"""Unit tests for the Stage 7 text-normalization pure functions."""

from app.services.text_normalization_service import (
    collapse_blank_lines,
    normalize_line_endings,
    normalize_text,
    normalize_unicode,
    normalize_whitespace,
    rejoin_hyphenated_words,
    strip_standalone_page_numbers,
)


def test_normalize_whitespace_collapses_and_strips() -> None:
    assert normalize_whitespace("hello   world") == "hello world"
    assert normalize_whitespace("  padded  \nline two  ") == "padded\nline two"


def test_normalize_unicode_composes_lookalikes() -> None:
    # Full-width digit "1" (U+FF11) normalizes to ASCII "1" under NFKC.
    assert normalize_unicode("１２３") == "123"


def test_normalize_line_endings_converts_crlf_and_cr() -> None:
    assert normalize_line_endings("a\r\nb\rc") == "a\nb\nc"


def test_rejoin_hyphenated_words() -> None:
    assert rejoin_hyphenated_words("exam-\nple") == "example"
    assert rejoin_hyphenated_words("no hyphen here") == "no hyphen here"


def test_strip_standalone_page_numbers() -> None:
    text = "Answer text\n3\nMore answer text\nPage 12\nfinal line"
    result = strip_standalone_page_numbers(text)
    assert "\n3\n" not in result
    assert "Page 12" not in result
    assert "Answer text" in result
    assert "final line" in result


def test_collapse_blank_lines() -> None:
    assert collapse_blank_lines("a\n\n\n\n\nb") == "a\n\nb"


def test_normalize_text_full_pipeline() -> None:
    raw = "  Q1) What is exam-\nple?  \n\n\n\nPage 2\n\nAnswer:   photo-\nsynthesis.  "
    result = normalize_text(raw)

    assert "example" in result
    assert "photosynthesis" in result
    assert "Page 2" not in result
    assert result == result.strip()
    assert "\n\n\n" not in result


def test_normalize_text_handles_empty_string() -> None:
    assert normalize_text("") == ""


def test_normalize_text_handles_pure_whitespace() -> None:
    assert normalize_text("   \n\n   ") == ""
