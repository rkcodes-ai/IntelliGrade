"""Tests for `app.services.document_intelligence.math_recognition`.

Symbolic normalization/validation/comparison tests run unconditionally
(pure Python, `sympy` + `lark`, no isolated runtime). The real pix2tex
recognition test is skipped when `.venv-math` isn't present on this
machine (matches the existing `.venv-surya`/`.venv-doctr`/`.venv-trocr`
skip-if-absent convention used elsewhere in this suite) but is NOT
mocked when it does run — this module's whole value is genuine local
inference.
"""

from pathlib import Path

import pytest

from app.services.document_intelligence.math_recognition import (
    MathRecognitionAdapter,
    compare_expressions,
    normalize_latex,
    validate_math_expression,
)
from app.services.ocr.isolated_runtime import default_isolated_python


def test_normalize_latex_collapses_equivalent_notation() -> None:
    assert normalize_latex(r"\left( x \right)  \cdot  y") == "( x ) * y"
    assert normalize_latex(r"a \times b \div c") == "a * b / c"


def test_normalize_latex_never_changes_meaning_only_spelling() -> None:
    raw = r"x^2 + \frac{1}{2}"
    normalized = normalize_latex(raw)
    assert "frac" in normalized  # \frac itself is untouched -- only cosmetic ops are rewritten


def test_validate_math_expression_detects_balanced_delimiters() -> None:
    result = validate_math_expression(r"x^{2} + (y - 1)")
    assert result.balanced_delimiters is True


def test_validate_math_expression_detects_unbalanced_delimiters() -> None:
    result = validate_math_expression(r"x^{2 + (y - 1")
    assert result.balanced_delimiters is False
    assert result.parseable is False


def test_validate_math_expression_flags_obvious_truncation() -> None:
    assert validate_math_expression(r"x + y =").looks_truncated is True
    assert validate_math_expression(r"x^2 + y^2 = z^2").looks_truncated is False


def test_validate_math_expression_parses_real_expression() -> None:
    result = validate_math_expression(r"x^2 + y^2")
    assert result.parseable is True


def test_compare_expressions_exact_structural_match() -> None:
    assert compare_expressions(r"x^2 + y^2", r"x^2 + y^2") == "EXACT_STRUCTURAL_MATCH"


def test_compare_expressions_algebraically_equivalent_commutative() -> None:
    assert compare_expressions(r"x + y", r"y + x") == "ALGEBRAICALLY_EQUIVALENT"


def test_compare_expressions_algebraically_equivalent_factored() -> None:
    assert compare_expressions(r"x^2 - 1", r"(x-1)(x+1)") == "ALGEBRAICALLY_EQUIVALENT"


def test_compare_expressions_numerically_equivalent_constants() -> None:
    assert compare_expressions(r"\frac{1}{2}", r"0.5") in (
        "ALGEBRAICALLY_EQUIVALENT",
        "NUMERICALLY_EQUIVALENT",
        "EXACT_STRUCTURAL_MATCH",
    )


def test_compare_expressions_partial_structural_match_same_variable_wrong_constant() -> None:
    """Same variable used, wrong constant -- genuinely useful partial
    evidence for a teacher ("right form, wrong number"), not simply
    NOT_EQUIVALENT."""
    assert compare_expressions(r"x + 1", r"x + 2") == "PARTIAL_STRUCTURAL_MATCH"


def test_compare_expressions_partial_structural_match_shared_subterm() -> None:
    assert compare_expressions(r"x^2 + y", r"x^2 + z") == "PARTIAL_STRUCTURAL_MATCH"


def test_compare_expressions_not_equivalent_no_shared_structure() -> None:
    assert compare_expressions(r"x + 1", r"y - 3") == "NOT_EQUIVALENT"


def test_compare_expressions_unparsable_never_raises() -> None:
    assert compare_expressions(r"x^{", r"y^2") == "UNPARSABLE"


def test_compare_expressions_never_executes_code() -> None:
    """Security regression (Section 23/58): a malicious 'expression'
    must never be executed as Python -- it must be treated as inert data
    that safely fails to parse."""
    malicious = "__import__('os').system('echo pwned')"
    verdict = compare_expressions(malicious, "x + 1")
    assert verdict == "UNPARSABLE"


_MATH_VENV_PYTHON = default_isolated_python(".venv-math")


@pytest.mark.skipif(not _MATH_VENV_PYTHON.exists(), reason=".venv-math not present on this machine")
def test_real_pix2tex_recognition_on_synthetic_math_image(tmp_path: Path) -> None:
    """Real, unmocked isolated-runtime inference -- this project's
    established discipline of never mocking the thing a module exists to
    verify."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (300, 80), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, 20), "x + y = z", fill="black", font=font)
    crop_path = tmp_path / "math_crop.png"
    img.save(crop_path)

    adapter = MathRecognitionAdapter()
    evidence = adapter.recognize(str(crop_path))

    assert evidence.status == "SUCCESS"
    assert evidence.recognized_expression != ""
    assert evidence.latex == evidence.recognized_expression
    assert evidence.processing_time_ms >= 0
    assert 0.0 <= evidence.confidence <= 100.0


@pytest.mark.skipif(not _MATH_VENV_PYTHON.exists(), reason=".venv-math not present on this machine")
def test_real_pix2tex_health_check() -> None:
    adapter = MathRecognitionAdapter()
    health = adapter.health_check()
    assert health["installed"] is True
    assert health["ready"] is True


def test_math_recognition_adapter_degrades_gracefully_when_runtime_missing() -> None:
    """Failure isolation (Section 47): a missing isolated runtime must
    produce a FAILED MathEvidence, never an unhandled exception."""
    adapter = MathRecognitionAdapter(python_exe="C:/definitely/does/not/exist/python.exe")
    evidence = adapter.recognize("C:/some/crop.png")
    assert evidence.status == "FAILED"
    assert evidence.detail is not None


def test_math_evidence_to_dict_is_json_serializable() -> None:
    import json

    adapter = MathRecognitionAdapter(python_exe="C:/definitely/does/not/exist/python.exe")
    evidence = adapter.recognize("C:/some/crop.png")
    serialized = json.dumps(evidence.to_dict())
    assert "recognized_expression" in serialized
