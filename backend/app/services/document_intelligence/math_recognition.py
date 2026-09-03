"""
Mathematical expression recognition (Step 4 milestone — Free Local Visual +
Diagram + Mathematical Understanding).

Recognition (image -> LaTeX) is done by `pix2tex` (LaTeX-OCR,
`lukas-blecher/LaTeX-OCR`, PyPI package `pix2tex`) in its own isolated
`.venv-math` venv, invoked through the exact same file-based
isolated-runtime bridge already used for Surya/docTR/TrOCR (see
`app.services.ocr.isolated_runtime` and
`isolated_runners/pix2tex_runner.py`) — no new subprocess mechanism.

**License verification (Section 3)**: `pix2tex` is MIT licensed (verified
against the project's own `LICENSE` file) — a clean, unrestricted choice,
in deliberate contrast to Surya's model weights (see this milestone's
final report: Surya's *code* is Apache 2.0 but its *model weights* carry a
modified Open RAIL-M license with a $5M revenue/funding threshold and a
no-compete clause). pix2tex's own checkpoint license was checked at the
same time and found to be released under the same MIT terms as the
repository (no separate, more restrictive model license file exists).

Symbolic validation/comparison (normalization, parseability, structural
and algebraic equivalence) is done with `sympy` (BSD licensed, already a
transitive dependency of `torch` in the main venv) plus `lark` (MIT
licensed, ~113KB, zero transitive dependencies — added specifically to
activate `sympy.parsing.latex.parse_latex_lark`, a pure-Python LaTeX
parser; `sympy`'s other LaTeX backend, `parse_latex`, requires
`antlr4-python3-runtime` pinned to an exact version matching sympy's
bundled grammar, which is a heavier and more fragile dependency for the
same job). This validation work runs in the MAIN venv — unlike
recognition, it is lightweight, pure-Python, and does not touch torch —
consistent with Section 26's mandate to prefer an existing safe library
over hand-rolling parsing, and Section 23's absolute rule that recognized
math is NEVER executed as code: `sympy.parsing.latex.parse_latex_lark`
only builds a symbolic expression tree, and comparison uses
`sympy.simplify`/`sympy.equals()` — never Python's built-in dynamic
code-evaluation on untrusted input.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import (
    RUNNERS_DIR,
    default_isolated_python,
    invoke_isolated_runtime,
)

settings = get_settings()

_RUNNER_SCRIPT = RUNNERS_DIR / "pix2tex_runner.py"

RecognitionStatus = Literal["SUCCESS", "FAILED", "NOT_IMPLEMENTED"]
PrintedOrHandwritten = Literal["printed", "handwritten", "unknown"]
EquivalenceVerdict = Literal[
    "EXACT_STRUCTURAL_MATCH",
    "ALGEBRAICALLY_EQUIVALENT",
    "NUMERICALLY_EQUIVALENT",
    "PARTIAL_STRUCTURAL_MATCH",
    "NOT_EQUIVALENT",
    "UNPARSABLE",
]

# pix2tex's CLI wrapper exposes no per-call confidence signal at all (see
# `pix2tex_runner.py`'s docstring) — this placeholder is surfaced
# unchanged, never dressed up as a measured probability.
_UNMEASURED_CONFIDENCE_PLACEHOLDER = 50.0


@dataclass(frozen=True)
class MathEvidence:
    recognized_expression: str  # raw pix2tex output, unmodified
    normalized_expression: str  # safe, meaning-preserving normalization (see `normalize_latex`)
    latex: str  # alias of recognized_expression -- pix2tex already emits LaTeX
    confidence: float
    status: RecognitionStatus
    printed_or_handwritten: PrintedOrHandwritten = "unknown"
    recognition_provider: str = "pix2tex"
    processing_time_ms: int = 0
    detail: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialization for `DocumentRegion.extra_metadata` — same
        one-JSON-column convention as `DiagramEvidence.to_dict()`."""
        return {
            "recognized_expression": self.recognized_expression,
            "normalized_expression": self.normalized_expression,
            "latex": self.latex,
            "confidence": self.confidence,
            "status": self.status,
            "printed_or_handwritten": self.printed_or_handwritten,
            "recognition_provider": self.recognition_provider,
            "processing_time_ms": self.processing_time_ms,
            "detail": self.detail,
            "raw_metadata": self.raw_metadata,
        }


@dataclass(frozen=True)
class MathValidation:
    """Deterministic, non-fabricated validation signals (Section 25) —
    never "corrects" the recognized expression, only reports facts about
    it."""

    balanced_delimiters: bool
    parseable: bool
    looks_truncated: bool
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "balanced_delimiters": self.balanced_delimiters,
            "parseable": self.parseable,
            "looks_truncated": self.looks_truncated,
            "detail": self.detail,
        }


_DELIMITER_PAIRS = {"{": "}", "(": ")", "[": "]"}
_CLOSERS = {v: k for k, v in _DELIMITER_PAIRS.items()}

# Superficial-representation normalizations only (Section 24) — every
# substitution below preserves mathematical meaning; nothing here ever
# changes what the student actually wrote, only how equivalent notations
# are spelled.
_NORMALIZATION_RULES: list[tuple[str, str]] = [
    (r"\\left", ""),
    (r"\\right", ""),
    (r"\\cdot", "*"),
    (r"\\times", "*"),
    (r"\\div", "/"),
    (r"\s+", " "),
]


def normalize_latex(latex: str) -> str:
    """Safe, reversible-in-spirit normalization for downstream comparison
    only — the RAW `recognized_expression` is always preserved unchanged
    alongside this (Section 24: preserve raw + normalized, never one or
    the other)."""
    normalized = latex.strip()
    for pattern, replacement in _NORMALIZATION_RULES:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized.strip()


def _balanced_delimiters(latex: str) -> bool:
    stack: list[str] = []
    for char in latex:
        if char in _DELIMITER_PAIRS:
            stack.append(char)
        elif char in _CLOSERS:
            if not stack or stack[-1] != _CLOSERS[char]:
                return False
            stack.pop()
    return not stack


def _looks_truncated(latex: str) -> bool:
    """Heuristic only (Section 25 requires flagging "obvious truncation",
    not perfect detection): a recognized expression ending mid-command
    (trailing backslash) or with a dangling binary operator is a strong,
    cheap signal of a cut-off crop."""
    stripped = latex.strip()
    if not stripped:
        return True
    if stripped.endswith("\\"):
        return True
    return bool(re.search(r"[+\-*/=^_]\s*$", stripped))


def validate_math_expression(latex: str) -> MathValidation:
    """Deterministic checks only — no model, no guessing. `parseable` is
    a real attempt via `sympy.parsing.latex.parse_latex_lark`, not a
    regex guess."""
    balanced = _balanced_delimiters(latex)
    truncated = _looks_truncated(latex)

    parseable = False
    detail: str | None = None
    if balanced and latex.strip():
        try:
            from sympy.parsing.latex import parse_latex_lark

            parse_latex_lark(latex)
            parseable = True
        except Exception as exc:  # noqa: BLE001 - any parse failure is a validation *result*, not a crash
            detail = f"{type(exc).__name__}: {exc}"
    elif not balanced:
        detail = "unbalanced delimiters"

    return MathValidation(
        balanced_delimiters=balanced,
        parseable=parseable,
        looks_truncated=truncated,
        detail=detail,
    )


def compare_expressions(expression_a: str, expression_b: str) -> EquivalenceVerdict:
    """Auditable equation-comparison (Section 27) — evidence only, never
    assigns marks itself. Uses only safe `sympy` APIs (`parse_latex_lark`,
    `simplify`, structural equality) — never dynamic code-evaluation on
    either expression (Section 23/26)."""
    normalized_a = normalize_latex(expression_a)
    normalized_b = normalize_latex(expression_b)
    if normalized_a == normalized_b and normalized_a != "":
        return "EXACT_STRUCTURAL_MATCH"

    try:
        from sympy.parsing.latex import parse_latex_lark

        parsed_a = parse_latex_lark(expression_a)
        parsed_b = parse_latex_lark(expression_b)
    except Exception:  # noqa: BLE001 - either side failing to parse is a real, reportable outcome
        return "UNPARSABLE"

    # NOTE: deliberately no `parsed_a == parsed_b` shortcut here. sympy's
    # `Add`/`Mul` are commutative at the data-model level, so `x + y` and
    # `y + x` parse to the *same* sympy object even though their surface
    # LaTeX differs -- that case is correctly ALGEBRAICALLY_EQUIVALENT
    # (caught by `simplify()` below), not EXACT_STRUCTURAL_MATCH, which
    # this function reserves for identical *normalized surface form*.

    try:
        import sympy as sp

        difference = sp.simplify(parsed_a - parsed_b)
        if difference == 0:
            return "ALGEBRAICALLY_EQUIVALENT"
    except Exception:  # noqa: BLE001 - simplify() can itself raise on exotic expressions -- fall through, don't crash
        pass

    try:
        import sympy as sp

        free_symbols = sorted((parsed_a.free_symbols | parsed_b.free_symbols), key=lambda s: s.name)
        if free_symbols:
            sample_point = {symbol: 1.5 + index * 0.37 for index, symbol in enumerate(free_symbols)}
            value_a = complex(parsed_a.evalf(subs=sample_point))
            value_b = complex(parsed_b.evalf(subs=sample_point))
            if abs(value_a - value_b) < 1e-6:
                return "NUMERICALLY_EQUIVALENT"
        else:
            value_a = complex(parsed_a.evalf())
            value_b = complex(parsed_b.evalf())
            if abs(value_a - value_b) < 1e-6:
                return "NUMERICALLY_EQUIVALENT"
    except Exception:  # noqa: BLE001 - numeric evaluation can fail for symbolic-only expressions -- not fatal
        pass

    # PARTIAL_STRUCTURAL_MATCH requires a genuinely shared symbolic
    # sub-term (e.g. `x^2 + y` vs `x^2 + z` both contain the `x^2` term) --
    # sharing only a free variable name (e.g. `x + 1` vs `x + 2`, which
    # share no sub-term at all once expanded into args) is NOT enough to
    # call it "partial", that's just a different value and honestly
    # belongs in NOT_EQUIVALENT.
    try:
        import sympy as sp

        args_a = set(parsed_a.args) if parsed_a.args else {parsed_a}
        args_b = set(parsed_b.args) if parsed_b.args else {parsed_b}
        shared_symbolic_terms = {term for term in (args_a & args_b) if term.free_symbols}
        if shared_symbolic_terms:
            return "PARTIAL_STRUCTURAL_MATCH"
    except Exception:  # noqa: BLE001 - args introspection failing is not fatal, just falls through
        pass

    return "NOT_EQUIVALENT"


class MathRecognitionAdapter:
    """Adapter over the isolated `.venv-math` pix2tex runtime — same
    bridge shape as `TrOCRHandwrittenAdapter`. Never a page-level OCR
    replacement: callers pass one already-cropped equation region."""

    def __init__(self, *, python_exe: str | None = None) -> None:
        configured = python_exe or settings.MATH_PYTHON
        self._python_exe_path = (
            Path(configured) if configured else default_isolated_python(".venv-math")
        )

    def _invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        result = invoke_isolated_runtime(
            python_exe=self._python_exe_path,
            runner_script=_RUNNER_SCRIPT,
            request=request,
            startup_timeout=settings.OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS,
            inference_timeout=settings.OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS,
        ).payload
        if not result.get("success", True):
            raise OCRIsolatedRuntimeInferenceError(
                result.get("error", "unknown pix2tex runner error")
            )
        return result

    def recognize(
        self, crop_path: str, *, printed_or_handwritten: PrintedOrHandwritten = "unknown"
    ) -> MathEvidence:
        """Real isolated-runtime inference. Never raises for a structurally
        valid crop — a failed recognition returns `status="FAILED"` with
        the original crop path preserved in `raw_metadata` (Section 22:
        preserve the image regardless of recognition success) rather than
        propagating an exception that would abort the whole page."""
        started = time.perf_counter()
        try:
            payload = self._invoke({"crop": crop_path, "mode": "extract"})
        except Exception as exc:  # noqa: BLE001 - isolated-runtime failure must degrade, not crash the caller
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return MathEvidence(
                recognized_expression="",
                normalized_expression="",
                latex="",
                confidence=0.0,
                status="FAILED",
                printed_or_handwritten=printed_or_handwritten,
                processing_time_ms=elapsed_ms,
                detail=f"{type(exc).__name__}: {exc}",
                raw_metadata={"crop_path": crop_path},
            )

        raw_latex = str(payload.get("latex", ""))
        return MathEvidence(
            recognized_expression=raw_latex,
            normalized_expression=normalize_latex(raw_latex),
            latex=raw_latex,
            confidence=float(payload.get("confidence", _UNMEASURED_CONFIDENCE_PLACEHOLDER)),
            status="SUCCESS",
            printed_or_handwritten=printed_or_handwritten,
            processing_time_ms=int(payload.get("processing_time_ms", 0)),
            raw_metadata={
                "crop_path": crop_path,
                "provider_version": payload.get("provider_version", "unknown"),
            },
        )

    def health_check(self) -> dict[str, Any]:
        if not self._python_exe_path.exists():
            return {
                "installed": False,
                "ready": False,
                "detail": (
                    f"Isolated runtime interpreter not found at {self._python_exe_path}. "
                    "Create the .venv-math venv and install pix2tex + torch to activate "
                    "math recognition."
                ),
            }
        try:
            payload = self._invoke({"mode": "health"})
        except Exception as exc:  # noqa: BLE001 - health check must never raise, only report
            return {"installed": False, "ready": False, "detail": f"health check failed: {exc}"}
        return {
            "installed": bool(payload.get("installed", False)),
            "ready": bool(payload.get("installed", False)),
            "version": payload.get("version"),
            "gpu_available": payload.get("gpu_available"),
            "detail": None,
        }
