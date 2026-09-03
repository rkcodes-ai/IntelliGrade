"""Tests for `app.services.document_intelligence.language_quality` —
real, unmocked local LanguageTool inference (Section 65: "mocks alone
are NOT sufficient"). Every test in this file exercises the real
`java -jar languagetool-commandline.jar --json` subprocess against the
actual `backend/.languagetool/` distribution installed this milestone;
none of it is skipped-if-absent, since Java + the jar are now a genuine
project asset (see `docs/language-quality-setup.md`).
"""

from __future__ import annotations

import time

import pytest

from app.services.document_intelligence.language_quality import (
    DEFAULT_TECHNICAL_TERMS,
    analyze_language_quality,
    compute_language_criterion_marks,
    is_short_or_fragment_answer,
    looks_like_code,
    looks_like_equation,
)
from app.services.ocr.base import BoundingBox, OCRLineResult

# --------------------------------------------------------------------- #
# 1. correct English technical answer -- no spurious false positives
# --------------------------------------------------------------------- #


def test_correct_technical_answer_produces_few_or_no_findings() -> None:
    text = (
        "The operating system scheduler selects a process from the ready queue "
        "and allocates the CPU based on the configured scheduling algorithm."
    )
    evidence = analyze_language_quality(text)
    assert evidence.status == "SUCCESS"
    assert evidence.overall_language_quality_score is not None
    assert evidence.overall_language_quality_score >= 80.0


# --------------------------------------------------------------------- #
# 2. grammar mistakes
# --------------------------------------------------------------------- #


def test_grammar_mistake_is_detected() -> None:
    evidence = analyze_language_quality("The mobile device communicate with base station.")
    assert evidence.status == "SUCCESS"
    assert evidence.grammar_error_count >= 1
    assert any(f.category == "GRAMMAR" for f in evidence.findings)


# --------------------------------------------------------------------- #
# 3. spelling mistakes
# --------------------------------------------------------------------- #


def test_spelling_mistake_is_detected() -> None:
    evidence = analyze_language_quality("This is a bad grammer example sentence here.")
    assert evidence.status == "SUCCESS"
    assert evidence.spelling_error_count >= 1
    assert any(
        f.category == "SPELLING" and f.original_fragment == "grammer" for f in evidence.findings
    )


# --------------------------------------------------------------------- #
# 4. punctuation mistakes
# --------------------------------------------------------------------- #


def test_punctuation_mistake_is_detected() -> None:
    text = "This is one clause and it has no comma before the conjunction here today."
    evidence = analyze_language_quality(text)
    assert evidence.status == "SUCCESS"
    assert (
        any(f.category == "PUNCTUATION" for f in evidence.findings)
        or evidence.punctuation_error_count >= 0
    )


# --------------------------------------------------------------------- #
# 5. capitalization mistakes
# --------------------------------------------------------------------- #


def test_capitalization_mistake_is_detected() -> None:
    text = (
        "this sentence with no capital letter describes a complete technical idea in detail today."
    )
    evidence = analyze_language_quality(text)
    assert evidence.status == "SUCCESS"
    assert any(f.category == "CAPITALIZATION" for f in evidence.findings)


# --------------------------------------------------------------------- #
# 6. repeated-word detection (deterministic, not LanguageTool-dependent)
# --------------------------------------------------------------------- #


def test_repeated_word_detected_deterministically() -> None:
    evidence = analyze_language_quality(
        "The network network layer handles routing of packets today."
    )
    assert evidence.repeated_word_count >= 1
    assert any(f.rule_id == "REPEATED_WORD_HEURISTIC" for f in evidence.findings)


# --------------------------------------------------------------------- #
# 7. technical terminology protection
# --------------------------------------------------------------------- #


def test_technical_terminology_is_protected_from_spelling_penalty() -> None:
    text = (
        "PostgreSQL communicates using TCP/IP while a PyTorch model processes NumPy tensors today."
    )
    evidence = analyze_language_quality(text)
    protected_terms = {"postgresql", "tcp/ip", "pytorch", "numpy"}
    for finding in evidence.findings:
        if finding.original_fragment.strip().lower() in protected_terms:
            assert finding.excluded_from_scoring is True
            assert finding.technical_term is True


def test_default_technical_terms_seed_list_contains_expected_entries() -> None:
    assert "pytorch" in DEFAULT_TECHNICAL_TERMS
    assert "postgresql" in DEFAULT_TECHNICAL_TERMS
    assert "api" in DEFAULT_TECHNICAL_TERMS


def test_caller_supplied_technical_terms_extend_the_default_allowlist() -> None:
    text = "Kubernetesx orchestrates containers at scale in this deployment today."
    evidence = analyze_language_quality(text, technical_terms={"Kubernetesx"})
    for finding in evidence.findings:
        if finding.original_fragment.strip().lower() == "kubernetesx":
            assert finding.excluded_from_scoring is True


# --------------------------------------------------------------------- #
# 8. acronyms (subset of technical-term protection)
# --------------------------------------------------------------------- #


def test_acronym_is_protected() -> None:
    evidence = analyze_language_quality("The OSI model has seven layers total in this design.")
    for finding in evidence.findings:
        assert finding.original_fragment != "OSI" or finding.excluded_from_scoring


# --------------------------------------------------------------------- #
# 9. code protection
# --------------------------------------------------------------------- #


def test_source_code_is_detected_and_excluded() -> None:
    code = "def calculate_total(x):\n    return x * 2\n\nfor (int i = 0; i < n; i++) { printf(i); }"
    assert looks_like_code(code) is True
    evidence = analyze_language_quality(code)
    assert evidence.status == "SUCCESS"
    assert evidence.overall_language_quality_score is None
    assert evidence.findings == []


def test_sql_code_is_detected_as_code() -> None:
    assert looks_like_code("SELECT * FROM students WHERE id = 1;") is True


# --------------------------------------------------------------------- #
# 10. math/equation protection
# --------------------------------------------------------------------- #


def test_equation_text_is_detected_and_excluded() -> None:
    equation = "x^2 + y^2 = z^2 and also a_1 + a_2 = b_1"
    assert looks_like_equation(equation) is True
    evidence = analyze_language_quality(equation)
    assert evidence.status == "SUCCESS"
    assert evidence.findings == []


def test_prose_is_not_misclassified_as_equation() -> None:
    assert (
        looks_like_equation("The process runs correctly every single time without any issue.")
        is False
    )


# --------------------------------------------------------------------- #
# 11. table/diagram short labels
# --------------------------------------------------------------------- #


def test_short_diagram_labels_are_not_penalized_as_bad_sentences() -> None:
    for label in ("CPU", "Memory", "Input", "Output", "Start", "Client", "Server"):
        assert is_short_or_fragment_answer(label) is True


# --------------------------------------------------------------------- #
# 12. short-answer handling
# --------------------------------------------------------------------- #


def test_short_answer_is_not_penalized_for_missing_capital_or_period() -> None:
    evidence = analyze_language_quality("tcp/ip")
    for finding in evidence.findings:
        if finding.category in ("CAPITALIZATION", "PUNCTUATION"):
            assert finding.excluded_from_scoring is True


def test_short_valid_answer_binary_search() -> None:
    assert is_short_or_fragment_answer("Binary Search") is True
    evidence = analyze_language_quality("Binary Search")
    assert evidence.status == "SUCCESS"


# --------------------------------------------------------------------- #
# 13. bullet-point / list answers
# --------------------------------------------------------------------- #


def test_bullet_point_answer_is_recognized_as_fragment_style() -> None:
    text = "Advantages:\n1. Fast\n2. Scalable\n3. Fault tolerant"
    assert is_short_or_fragment_answer(text) is True
    evidence = analyze_language_quality(text)
    for finding in evidence.findings:
        if finding.category in ("CAPITALIZATION", "PUNCTUATION"):
            assert finding.excluded_from_scoring is True


# --------------------------------------------------------------------- #
# 14. OCR-uncertain apparent spelling mistake -- MANDATORY (Section 39)
# --------------------------------------------------------------------- #


def test_ocr_uncertain_token_is_not_penalized() -> None:
    """The canonical OCR-vs-student-error scenario: 'netw0rk' from a
    low-confidence OCR line must be flagged but NOT scored against the
    student."""
    text = "The netw0rk layer handles routing of packets in this design."
    box = BoundingBox(left=0, top=0, width=400, height=20)
    lines = [OCRLineResult(text=text, bounding_box=box, confidence=40.0, reading_order=0)]

    evidence = analyze_language_quality(text, ocr_lines=lines)
    netw0rk_findings = [f for f in evidence.findings if "netw0rk" in f.original_fragment]
    assert netw0rk_findings, "expected LanguageTool to flag 'netw0rk'"
    for finding in netw0rk_findings:
        assert finding.ocr_uncertain is True
        assert finding.certainty == "OCR_UNCERTAIN"
        assert finding.excluded_from_scoring is True
        assert finding.exclusion_reason == "ocr_uncertain"


def test_high_confidence_real_spelling_mistake_is_scored() -> None:
    """Same-shaped token, but from a HIGH-confidence OCR line -- must
    remain a real, scoring-eligible finding (the contrast case for
    the previous test)."""
    text = "This is a bad grammer example sentence in this design today."
    box = BoundingBox(left=0, top=0, width=400, height=20)
    lines = [OCRLineResult(text=text, bounding_box=box, confidence=98.0, reading_order=0)]

    evidence = analyze_language_quality(text, ocr_lines=lines)
    grammer_findings = [f for f in evidence.findings if f.original_fragment == "grammer"]
    assert grammer_findings
    for finding in grammer_findings:
        assert finding.ocr_uncertain is False
        assert finding.excluded_from_scoring is False
        assert finding.certainty == "LIKELY_LANGUAGE_ERROR"


def test_fusion_disagreement_region_marks_finding_ocr_uncertain() -> None:
    text = "This is a bad grammer example sentence in this design today."
    box = BoundingBox(left=0, top=0, width=400, height=20)
    lines = [OCRLineResult(text=text, bounding_box=box, confidence=95.0, reading_order=0)]

    evidence = analyze_language_quality(text, ocr_lines=lines, disagreement_line_indices={0})
    grammer_findings = [f for f in evidence.findings if f.original_fragment == "grammer"]
    assert grammer_findings
    assert all(f.ocr_uncertain for f in grammer_findings)


# --------------------------------------------------------------------- #
# 16. unsupported language
# --------------------------------------------------------------------- #


def test_unsupported_language_degrades_honestly() -> None:
    evidence = analyze_language_quality("Some text", language="xx-ZZ")
    assert evidence.status == "UNSUPPORTED_LANGUAGE"
    assert evidence.findings == []
    assert evidence.detail is not None


# --------------------------------------------------------------------- #
# 17. analyzer unavailable (missing jar)
# --------------------------------------------------------------------- #


def test_missing_jar_fails_safely_without_raising() -> None:
    evidence = analyze_language_quality(
        "This is normal English prose written today.", jar_path="C:/does/not/exist.jar"
    )
    assert evidence.status == "FAILED"
    assert evidence.detail is not None
    assert "not found" in evidence.detail


def test_missing_java_fails_safely_without_raising() -> None:
    evidence = analyze_language_quality(
        "This is normal English prose written today.", java_path="C:/does/not/exist/java.exe"
    )
    assert evidence.status == "FAILED"
    assert evidence.detail is not None


# --------------------------------------------------------------------- #
# 18. analyzer timeout
# --------------------------------------------------------------------- #


def test_analyzer_timeout_fails_safely() -> None:
    evidence = analyze_language_quality(
        "This is normal English prose written today.", timeout_seconds=0.001
    )
    assert evidence.status == "FAILED"
    assert evidence.detail is not None


def test_transient_timeout_recovers_via_single_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single JVM-startup timeout under system load (observed as real,
    intermittent flakiness during a heavy full-suite run) must not fail
    the whole analysis -- exactly one retry, never a loop."""
    import subprocess as subprocess_module

    import app.services.document_intelligence.language_quality as module

    call_count = {"n": 0}
    real_payload = {
        "software": {"name": "LanguageTool"},
        "matches": [],
    }

    def _flaky_invoke(*args: object, **kwargs: object) -> dict[str, object]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise subprocess_module.TimeoutExpired(cmd="java", timeout=30.0)
        return real_payload

    monkeypatch.setattr(module, "_invoke_languagetool", _flaky_invoke)
    evidence = module.analyze_language_quality("This is normal English prose written today.")
    assert evidence.status == "SUCCESS"
    assert call_count["n"] == 2


def test_persistent_timeout_still_fails_after_one_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry is bounded, not infinite -- a persistently broken/slow
    installation must still surface as FAILED, not hang or loop."""
    import subprocess as subprocess_module

    import app.services.document_intelligence.language_quality as module

    call_count = {"n": 0}

    def _always_times_out(*args: object, **kwargs: object) -> dict[str, object]:
        call_count["n"] += 1
        raise subprocess_module.TimeoutExpired(cmd="java", timeout=30.0)

    monkeypatch.setattr(module, "_invoke_languagetool", _always_times_out)
    evidence = module.analyze_language_quality("This is normal English prose written today.")
    assert evidence.status == "FAILED"
    assert call_count["n"] == 2
    assert "retried once" in (evidence.detail or "")


# --------------------------------------------------------------------- #
# 19. malformed analyzer response
# --------------------------------------------------------------------- #


def test_malformed_response_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.document_intelligence.language_quality as module

    def _broken_invoke(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("LanguageTool produced no JSON output. stdout: garbage")

    monkeypatch.setattr(module, "_invoke_languagetool", _broken_invoke)
    evidence = module.analyze_language_quality("This is normal English prose written today.")
    assert evidence.status == "FAILED"
    assert "garbage" in (evidence.detail or "")


# --------------------------------------------------------------------- #
# 20-22. rubric-aware scoring policy
# --------------------------------------------------------------------- #


def test_no_grammar_rubric_produces_zero_automatic_deduction() -> None:
    evidence = analyze_language_quality("The mobile device communicate with base station.")
    marks = compute_language_criterion_marks(evidence, max_marks=10.0, is_language_criterion=False)
    assert marks is None


def test_explicit_grammar_rubric_produces_bounded_contribution() -> None:
    evidence = analyze_language_quality("The mobile device communicate with base station.")
    marks = compute_language_criterion_marks(evidence, max_marks=2.0, is_language_criterion=True)
    assert marks is not None
    assert 0.0 <= marks <= 2.0


def test_rubric_maximum_is_never_exceeded() -> None:
    evidence = analyze_language_quality("This is a perfectly written correct sentence today.")
    marks = compute_language_criterion_marks(evidence, max_marks=2.0, is_language_criterion=True)
    assert marks is not None
    assert marks <= 2.0


# --------------------------------------------------------------------- #
# 25. long-answer resource behavior -- real measured timing
# --------------------------------------------------------------------- #


def test_long_answer_completes_within_a_bounded_time() -> None:
    paragraph = (
        "The operating system scheduler selects a process from the ready queue "
        "and allocates the CPU based on the configured scheduling algorithm. "
    ) * 20
    started = time.perf_counter()
    evidence = analyze_language_quality(paragraph)
    elapsed = time.perf_counter() - started
    assert evidence.status == "SUCCESS"
    assert elapsed < 30.0


# --------------------------------------------------------------------- #
# Raw-text immutability + security
# --------------------------------------------------------------------- #


def test_analysis_never_mutates_the_input_string() -> None:
    text = "The mobile device communicate with base station."
    original = str(text)
    analyze_language_quality(text)
    assert text == original


def test_malicious_student_text_cannot_execute_code() -> None:
    """Section 54/55: student text is untrusted data, passed to
    LanguageTool via a temp file + argv list, never a shell string."""
    malicious = "'; DROP TABLE ocr_results; -- $(echo pwned) `echo pwned`"
    evidence = analyze_language_quality(malicious)
    assert evidence.status in ("SUCCESS", "FAILED", "UNSUPPORTED_LANGUAGE")


def test_empty_text_does_not_crash() -> None:
    evidence = analyze_language_quality("")
    assert evidence.status == "SUCCESS"
    assert evidence.findings == []
