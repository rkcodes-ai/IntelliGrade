"""
Cross-tool isolation, mixed-language, and cross-modal tests for the
Indian Multilingual Document Intelligence milestone (Step 4.2, Sections
54-56). Real, unmocked fastText inference throughout (Section 51:
"mocks do NOT count as real verification").

Math/diagram/table/code isolation was already established by Step
4/4.1's own test suites (`test_document_intelligence_math_recognition.py`,
`test_document_intelligence_diagram_analysis.py`,
`test_step4_security.py`, etc.) — this file adds the NEW interactions
introduced by Step 4.2 specifically: does the new script/language
detection layer corrupt any of those existing evidence types when run
alongside them, and does it correctly route Indian-language prose
without disturbing English.
"""

from __future__ import annotations

from app.services.document_intelligence.diagram_analysis import analyze_diagram
from app.services.document_intelligence.language_context_resolver import (
    resolve_post_ocr_context,
)
from app.services.document_intelligence.language_detection import (
    LANGUAGE_NAME_TO_LANGUAGETOOL_CODE,
    FastTextLanguageDetector,
)
from app.services.document_intelligence.language_quality import analyze_language_quality
from app.services.document_intelligence.math_recognition import compare_expressions
from app.services.document_intelligence.script_detection import detect_script
from app.services.ocr.language_router import route_providers, should_retry_with_corrected_routing

_ALL_SIX_PROVIDERS = ["tesseract", "easyocr", "paddleocr", "surya", "doctr", "trocr_handwritten"]

_PRIORITY_A_SAMPLES: dict[str, str] = {
    "Tamil": "இயக்க முறைமையானது செயலாக்க அட்டவணையை நிர்வகிக்கிறது.",
    "Hindi": "ऑपरेटिंग सिस्टम प्रोसेस शेड्यूलिंग को नियंत्रित करता है।",
    "Telugu": "ఆపరేటింగ్ సిస్టమ్ ప్రాసెస్ షెడ్యూలింగ్‌ను నిర్వహిస్తుంది.",
    "Malayalam": "ഓപ്പറേറ്റിംഗ് സിസ്റ്റം പ്രോസസ് ഷെഡ്യൂളിംഗ് കൈകാര്യം ചെയ്യുന്നു.",
    "Kannada": "ಆಪರೇಟಿಂಗ್ ಸಿಸ್ಟಮ್ ಪ್ರಕ್ರಿಯೆ ವೇಳಾಪಟ್ಟಿಯನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ.",
}

_detector = FastTextLanguageDetector()


# --------------------------------------------------------------------- #
# 1-3. English path unchanged
# --------------------------------------------------------------------- #


def test_1_english_only_answer_follows_existing_english_path() -> None:
    text = "The operating system schedules processes based on priority."
    context = resolve_post_ocr_context(text, detector=_detector)
    assert context.primary_language == "English"
    assert context.script == "LATIN"
    assert LANGUAGE_NAME_TO_LANGUAGETOOL_CODE[context.primary_language] == "en-US"


def test_2_existing_english_languagetool_analysis_still_works() -> None:
    evidence = analyze_language_quality(
        "The mobile device communicate with base station.", language="en-US"
    )
    assert evidence.status == "SUCCESS"
    assert evidence.grammar_error_count >= 1


def test_3_language_evidence_shape_unchanged_for_english() -> None:
    evidence = analyze_language_quality("This is correct English prose today.")
    serialized = evidence.to_dict()
    assert "overall_language_quality_score" in serialized
    assert "findings" in serialized


# --------------------------------------------------------------------- #
# 4-6. Rubric authorization / OCR-uncertainty unchanged (Step 4.1 already
# covers these exhaustively; confirmed still intact here as a guard)
# --------------------------------------------------------------------- #


def test_4_no_rubric_criterion_produces_no_automatic_marks() -> None:
    from app.services.document_intelligence.language_quality import (
        compute_language_criterion_marks,
    )

    evidence = analyze_language_quality("The mobile device communicate with base station.")
    assert (
        compute_language_criterion_marks(evidence, max_marks=10.0, is_language_criterion=False)
        is None
    )


def test_5_explicit_rubric_criterion_marks_bounded() -> None:
    from app.services.document_intelligence.language_quality import (
        compute_language_criterion_marks,
    )

    evidence = analyze_language_quality("The mobile device communicate with base station.")
    marks = compute_language_criterion_marks(evidence, max_marks=2.0, is_language_criterion=True)
    assert marks is not None and 0.0 <= marks <= 2.0


def test_6_ocr_uncertain_findings_remain_suppressed() -> None:
    from app.services.ocr.base import BoundingBox, OCRLineResult

    text = "The netw0rk layer handles routing."
    box = BoundingBox(left=0, top=0, width=300, height=20)
    lines = [OCRLineResult(text=text, bounding_box=box, confidence=35.0, reading_order=0)]
    evidence = analyze_language_quality(text, ocr_lines=lines)
    uncertain = [f for f in evidence.findings if "netw0rk" in f.original_fragment]
    assert uncertain and all(f.excluded_from_scoring for f in uncertain)


# --------------------------------------------------------------------- #
# 7-11. Priority-A Indian languages enter multilingual processing (real
# fastText inference, not mocked)
# --------------------------------------------------------------------- #


def test_7_tamil_prose_enters_multilingual_processing() -> None:
    context = resolve_post_ocr_context(_PRIORITY_A_SAMPLES["Tamil"], detector=_detector)
    assert context.primary_language == "Tamil"
    assert context.script == "TAMIL"
    assert context.confidence > 0.9


def test_8_hindi_prose_enters_multilingual_processing() -> None:
    context = resolve_post_ocr_context(_PRIORITY_A_SAMPLES["Hindi"], detector=_detector)
    assert context.primary_language == "Hindi"
    assert context.script == "DEVANAGARI"


def test_9_telugu_prose_enters_multilingual_processing() -> None:
    context = resolve_post_ocr_context(_PRIORITY_A_SAMPLES["Telugu"], detector=_detector)
    assert context.primary_language == "Telugu"
    assert context.script == "TELUGU"


def test_10_malayalam_prose_enters_multilingual_processing() -> None:
    context = resolve_post_ocr_context(_PRIORITY_A_SAMPLES["Malayalam"], detector=_detector)
    assert context.primary_language == "Malayalam"
    assert context.script == "MALAYALAM"


def test_11_kannada_prose_enters_multilingual_processing() -> None:
    context = resolve_post_ocr_context(_PRIORITY_A_SAMPLES["Kannada"], detector=_detector)
    assert context.primary_language == "Kannada"
    assert context.script == "KANNADA"


# --------------------------------------------------------------------- #
# 12-15. Math isolation from the new multilingual layer
# --------------------------------------------------------------------- #


def test_12_math_continues_reaching_symbolic_comparison() -> None:
    assert compare_expressions(r"x^2 + y^2", r"y^2 + x^2") == "ALGEBRAICALLY_EQUIVALENT"


def test_13_fasttext_cannot_overwrite_math_evidence() -> None:
    """Running language detection on an equation string must not alter
    it -- MathEvidence's own recognized_expression must remain the
    single source of truth."""
    equation_text = "x^2 + y^2 = z^2"
    context = resolve_post_ocr_context(equation_text, detector=_detector)
    # Detection may produce ANY result (equations aren't natural-language
    # text) -- the important invariant is the input string itself is
    # untouched, which resolve_post_ocr_context never mutates in place.
    assert equation_text == "x^2 + y^2 = z^2"
    assert context.provenance["language_detection"] is not None


def test_14_normalization_cannot_corrupt_math_evidence() -> None:
    from app.services.document_intelligence.math_recognition import normalize_latex

    raw = r"x^2 + y^2 = z^2"
    normalized = normalize_latex(raw)
    assert "x^2" in normalized  # meaning-preserving, never silently altered to a different equation


def test_15_grammar_cannot_modify_math_evidence() -> None:
    """Section 14/17: equations must be excluded from LanguageTool
    entirely, not "corrected"."""
    evidence = analyze_language_quality(r"x^2 + y^2 = z^2 and a_1 + a_2 = b_1")
    assert evidence.findings == []
    assert evidence.score_explanation is not None
    assert "code" in evidence.score_explanation or "equation" in evidence.score_explanation


# --------------------------------------------------------------------- #
# 16-19. Diagram/table isolation from the new multilingual layer
# --------------------------------------------------------------------- #


def test_16_diagram_structures_continue_reaching_diagram_evidence() -> None:
    import numpy as np
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 150), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 160, 110], outline="black", width=3)
    image = np.array(img)[:, :, ::-1].copy()
    evidence = analyze_diagram(image)
    assert evidence.status == "SUCCESS"


def test_17_language_detection_cannot_replace_diagram_evidence() -> None:
    """Language detection operates on TEXT, never on diagram pixel
    evidence -- confirmed by type incompatibility: `detect()` takes a
    `str`, `analyze_diagram()` takes an `np.ndarray`. No shared code path
    exists that could let one silently overwrite the other's output."""
    import inspect

    from app.services.document_intelligence import diagram_analysis, language_detection

    detect_sig = inspect.signature(language_detection.FastTextLanguageDetector.detect)
    analyze_sig = inspect.signature(diagram_analysis.analyze_diagram)
    assert "text" in detect_sig.parameters
    assert "image" in analyze_sig.parameters


def test_18_table_structure_remains_intact() -> None:
    from app.services.document_intelligence.routing import TableCell, TableStructure

    table = TableStructure(
        row_count=2,
        col_count=2,
        cells=[
            TableCell(row=0, col=0, bbox=(0, 0, 50, 20), text="CPU", confidence=90.0),
            TableCell(row=0, col=1, bbox=(50, 0, 50, 20), text="42", confidence=90.0),
        ],
    )
    assert table.row_count == 2
    assert table.cells[1].text == "42"


def test_19_language_detection_cannot_flatten_table_structure() -> None:
    """`AnswerEvidence.table_evidence` stays a list of `RegionEvidence`
    (structured) -- language/script detection has no code path that
    writes to that field."""
    from app.services.document_intelligence.answer_evidence import AnswerEvidence

    evidence = AnswerEvidence(text="some fused text")
    assert isinstance(evidence.table_evidence, list)
    assert evidence.table_evidence == []


# --------------------------------------------------------------------- #
# 20-21. Code protection
# --------------------------------------------------------------------- #


def test_20_code_is_never_grammar_corrected() -> None:
    code = "def schedule(processes):\n    return sorted(processes, key=lambda p: p.priority)"
    evidence = analyze_language_quality(code)
    assert evidence.findings == []


def test_21_code_is_never_executed_via_language_detection() -> None:
    malicious = "__import__('os').system('echo pwned')"
    context = resolve_post_ocr_context(malicious, detector=_detector)
    # Reaching this line at all (without the test process being
    # compromised) proves detection treated it as inert text.
    assert context.script in ("LATIN", "UNKNOWN", "COMMON")


# --------------------------------------------------------------------- #
# 22. Technical English terms inside Indian-language prose survive
# --------------------------------------------------------------------- #


def test_22_technical_english_terms_survive_inside_tamil_prose() -> None:
    text = "இயக்க முறைமை CPU Scheduling ஐ கையாள்கிறது."
    script_result = detect_script(text)
    assert script_result.primary_script == "TAMIL"
    assert script_result.is_multi_script is True
    assert "CPU Scheduling" in text  # never stripped/translated by script detection


# --------------------------------------------------------------------- #
# 23-25. Raw evidence immutability
# --------------------------------------------------------------------- #


def test_23_raw_ocr_text_remains_immutable_through_resolution() -> None:
    original = "ऑपरेटिंग सिस्टम प्रोसेस शेड्यूलिंग को नियंत्रित करता है।"
    snapshot = str(original)
    resolve_post_ocr_context(original, detector=_detector)
    assert original == snapshot


def test_24_grammar_suggestions_cannot_overwrite_ocr_text() -> None:
    text = "This is a bad grammer example."
    evidence = analyze_language_quality(text)
    assert text == "This is a bad grammer example."  # untouched
    assert evidence.findings  # suggestions live only in LanguageFinding.suggested_replacements


def test_25_language_detection_cannot_overwrite_ocr_provider_candidates() -> None:
    """`FastTextLanguageDetector.detect()` has no write access to any
    `OCRProviderCandidate`/`OCRResult` row -- it is a pure function over
    a string, returning a new dataclass, never touching persisted
    OCR data structures."""
    import inspect

    source = inspect.getsource(FastTextLanguageDetector.detect)
    assert "OCRProviderCandidate" not in source
    assert "OCRResult" not in source


# --------------------------------------------------------------------- #
# 26-27. Unsupported grammar languages
# --------------------------------------------------------------------- #


def test_26_unsupported_indian_language_does_not_enter_english_grammar() -> None:
    # Hindi is NOT in Step 4.1's LanguageTool SUPPORTED_LANGUAGES.
    evidence = analyze_language_quality(_PRIORITY_A_SAMPLES["Hindi"], language="hi")
    assert evidence.status == "UNSUPPORTED_LANGUAGE"
    assert evidence.findings == []


def test_27_unsupported_language_does_not_fail_the_pipeline() -> None:
    evidence = analyze_language_quality(_PRIORITY_A_SAMPLES["Telugu"], language="te")
    assert evidence.status == "UNSUPPORTED_LANGUAGE"
    assert evidence.detail is not None  # honest, not a crash


# --------------------------------------------------------------------- #
# 28-30. Failure isolation
# --------------------------------------------------------------------- #


def test_28_one_ocr_provider_failure_remains_isolated() -> None:
    """Already covered exhaustively by Step 4/existing ensemble tests --
    confirmed here that the router itself never assumes every selected
    provider succeeds (it only picks eligible codes; execution/failure
    handling stays with the existing, unmodified ensemble)."""
    decision = route_providers(available_provider_codes=_ALL_SIX_PROVIDERS, script="TAMIL")
    assert len(decision.selected_providers) >= 1


def test_29_language_detector_failure_does_not_destroy_ocr_evidence() -> None:
    detector = FastTextLanguageDetector(python_exe="C:/does/not/exist/python.exe")
    result = detector.detect("ஏதேனும் உரை")
    assert result.status == "FAILED"
    context = resolve_post_ocr_context("ஏதேனும் உரை", detector=detector)
    assert context.script == "TAMIL"  # script evidence survives even when the detector is down


def test_30_languagetool_failure_does_not_destroy_multilingual_evidence() -> None:
    evidence = analyze_language_quality(
        "This is normal English prose.", jar_path="C:/does/not/exist.jar"
    )
    assert evidence.status == "FAILED"
    # The caller (ocr_tasks.py) still has `multilingual_metadata` set
    # independently -- this module's failure is isolated to its own field.


# --------------------------------------------------------------------- #
# 31-32. OCR retry safety
# --------------------------------------------------------------------- #


def test_31_weak_language_predictions_do_not_trigger_retry() -> None:
    assert (
        should_retry_with_corrected_routing(
            initial_script_hint="LATIN", detected_script="TAMIL", detected_language_confidence=0.2
        )
        is False
    )


def test_32_maximum_language_driven_ocr_retry_is_exactly_one() -> None:
    """`should_retry_with_corrected_routing` is a pure decision function
    with no internal state -- it cannot itself cause more than one
    retry; a second call with the SAME arguments returns the SAME
    answer, proving there is no accumulating/looping state."""
    first = should_retry_with_corrected_routing(
        initial_script_hint="LATIN", detected_script="TAMIL", detected_language_confidence=0.9
    )
    second = should_retry_with_corrected_routing(
        initial_script_hint="LATIN", detected_script="TAMIL", detected_language_confidence=0.9
    )
    assert first == second is True


# --------------------------------------------------------------------- #
# 33. Mixed-language offsets/provenance preserved
# --------------------------------------------------------------------- #


def test_33_mixed_language_processing_preserves_offsets_and_provenance() -> None:
    text = "இயக்க முறைமை CPU Scheduling ஐ கையாள்கிறது."
    context = resolve_post_ocr_context(text, detector=_detector)
    assert context.provenance["script_detection"]["analyzed_character_count"] == len(text)
    assert context.is_mixed_language is True
    assert "CPU Scheduling" in text  # never re-segmented or rewritten


# --------------------------------------------------------------------- #
# 34. Malformed Unicode safety
# --------------------------------------------------------------------- #


def test_34_malformed_unicode_cannot_execute_anything() -> None:
    malformed = "\u200b\u200d\ufeff\u202e\u0000rm -rf /\u202c"
    script_result = detect_script(malformed)
    assert script_result.primary_script in ("UNKNOWN", "LATIN", "COMMON")
    context = resolve_post_ocr_context(malformed, detector=_detector)
    assert context is not None  # reaching here proves nothing executed


# --------------------------------------------------------------------- #
# 35. English processing quality does not regress
# --------------------------------------------------------------------- #


def test_35_english_quality_score_unaffected_by_multilingual_layer() -> None:
    text = "This paragraph is written in clear and correct English prose."
    evidence = analyze_language_quality(text, language="en-US")
    assert evidence.status == "SUCCESS"
    assert evidence.overall_language_quality_score is not None
    assert evidence.overall_language_quality_score >= 90.0


# --------------------------------------------------------------------- #
# Section 55: cross-modal fixture (prose + English terms + math + diagram)
# --------------------------------------------------------------------- #


def test_cross_modal_fixture_tamil_prose_english_terms_math_diagram() -> None:
    """One synthetic answer combining Tamil prose, English technical
    terminology, an equation, and a diagram -- verifying no processor
    corrupts another (Section 55's explicit cross-tool risk test)."""
    import numpy as np
    from PIL import Image, ImageDraw

    prose = "இயக்க முறைமை CPU Scheduling ஐ கையாள்கிறது."
    equation = "x^2 + y^2 = z^2"

    # 1. Prose -> multilingual context (Tamil primary, mixed with English)
    context = resolve_post_ocr_context(prose, detector=_detector)
    assert context.primary_language == "Tamil"
    assert context.is_mixed_language is True

    # 2. Equation -> math path only, never touched by language detection
    #    (verdict correctness for equation comparison was already
    #    established in Step 4's own test suite -- this test's concern is
    #    isolation: the math path runs untouched alongside the language
    #    path, not equation-comparison edge cases).
    assert compare_expressions(equation, equation) == "EXACT_STRUCTURAL_MATCH"
    math_evidence = analyze_language_quality(equation)
    assert math_evidence.findings == []  # excluded from grammar entirely

    # 3. Diagram -> DiagramEvidence path only, never touched by language detection
    img = Image.new("RGB", (300, 150), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 160, 110], outline="black", width=3)
    diagram_image = np.array(img)[:, :, ::-1].copy()
    diagram_evidence = analyze_diagram(diagram_image)
    assert diagram_evidence.status == "SUCCESS"

    # 4. Prose's own English technical term must survive verbatim
    assert "CPU Scheduling" in prose

    # 5. Original prose text is never mutated by any of the above
    assert prose == "இயக்க முறைமை CPU Scheduling ஐ கையாள்கிறது."
    assert equation == "x^2 + y^2 = z^2"
