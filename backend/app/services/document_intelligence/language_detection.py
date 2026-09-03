"""
Language identification (Step 4.2 milestone — Indian Multilingual
Document Intelligence, Sections 18-21).

**Engine**: fastText's official `lid.176` model, invoked through the
exact same file-based isolated-runtime bridge already used for
Surya/docTR/TrOCR/pix2tex (see `app.services.ocr.isolated_runtime` and
`isolated_runners/fasttext_runner.py`) — no new subprocess mechanism.

**License verification (Section 15-17)**:
- `fasttext-wheel` (the installable package providing fastText's Python
  bindings) is **MIT licensed** — verified directly against the real
  `LICENSE` file in Facebook's `fastText` repository.
- The `lid.176.ftz` model itself is **CC-BY-SA-3.0** (Creative Commons
  Attribution-ShareAlike), trained on Wikipedia/Tatoeba/SETimes data
  released under that license. This project uses the model unmodified,
  for local inference only — never redistributes a derivative of the
  model itself — so the ShareAlike clause's obligations (attribution,
  same-license-on-derivatives) don't extend to IntelliGrade's own code;
  attribution to Facebook AI Research / fastText is recorded here and in
  this milestone's final report.
- Rejected: `language_tool_python`-style "just pip install it in the
  main venv" — `fasttext-wheel` has **no prebuilt Windows wheel for
  Python 3.13** (this project's main-venv/other-isolated-venv version;
  confirmed via PyPI's file listing — the highest available is cp312),
  so installing it there would force a from-source MSVC compile, a real
  Windows destabilization risk this project avoids by using a dedicated
  `.venv-langid` pinned to Python 3.12 instead (same "isolated runtime,
  don't touch the stable main venv" principle already established for
  Surya/docTR/TrOCR/pix2tex/LanguageTool).

**Responsibility boundary (Section 19)**: this module does language
IDENTIFICATION only. It is never OCR, never grammar/spelling, never
translation, never math/diagram recognition, never grading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.services.ocr.exceptions import OCRIsolatedRuntimeInferenceError
from app.services.ocr.isolated_runtime import (
    RUNNERS_DIR,
    default_isolated_python,
    invoke_isolated_runtime,
)

settings = get_settings()

_RUNNER_SCRIPT = RUNNERS_DIR / "fasttext_runner.py"

# fastText's own ISO-639-ish label -> this project's human-readable
# language name, for the 22 Scheduled Languages of India + English.
# Built from `lid.176`'s REAL 176-label set (enumerated via
# `model.get_labels()` during this milestone's own verification) --
# five Scheduled Languages have NO fastText label at all
# (Bodo/Dogri/Kashmiri/Manipuri-Meitei/Santali); "gom" (Goan Konkani) is
# the closest real label to Konkani, documented honestly as an
# approximation, not a perfect match.
FASTTEXT_LABEL_TO_LANGUAGE: dict[str, str] = {
    "en": "English",
    "as": "Assamese",
    "bn": "Bengali",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "gom": "Konkani",  # approximation: fastText's label is specifically "Goan Konkani"
    "mai": "Maithili",
    "ml": "Malayalam",
    "mr": "Marathi",
    "ne": "Nepali",
    "or": "Odia",
    "pa": "Punjabi",
    "sa": "Sanskrit",
    "sd": "Sindhi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
}

# Human-readable language name -> this project's pre-existing 3-letter
# `OCRResult.language` convention (Tesseract-style codes, matching
# `_DEFAULT_LANGUAGE = "eng"` in `ocr_tasks.py`). "English" intentionally
# maps to the exact pre-existing literal so resolved-English pages
# persist an identical value to before this milestone (Section 11).
LANGUAGE_NAME_TO_OCR_CODE: dict[str, str] = {
    "English": "eng",
    "Assamese": "asm",
    "Bengali": "ben",
    "Gujarati": "guj",
    "Hindi": "hin",
    "Kannada": "kan",
    "Konkani": "kok",
    "Maithili": "mai",
    "Malayalam": "mal",
    "Marathi": "mar",
    "Nepali": "nep",
    "Odia": "ori",
    "Punjabi": "pan",
    "Sanskrit": "san",
    "Sindhi": "snd",
    "Tamil": "tam",
    "Telugu": "tel",
    "Urdu": "urd",
}

# Human-readable language name -> LanguageTool's own code (Step 4.1's
# `SUPPORTED_LANGUAGES`) -- only populated where LanguageTool genuinely
# has a matching code; everything else correctly falls through to
# `analyze_language_quality()`'s existing `UNSUPPORTED_LANGUAGE` status
# (Section 13), never fabricated.
LANGUAGE_NAME_TO_LANGUAGETOOL_CODE: dict[str, str] = {
    "English": "en-US",
    "Tamil": "ta-IN",
}

# Scheduled Languages fastText's lid.176 genuinely cannot identify at
# all (real, confirmed absence from the model's 176-label set) --
# script detection is the only signal available for these; never
# silently claim fastText coverage here.
LANGUAGES_WITHOUT_FASTTEXT_SUPPORT: frozenset[str] = frozenset(
    {"Bodo", "Dogri", "Kashmiri", "Manipuri/Meitei", "Santali"}
)

_LOW_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class LanguageCandidate:
    language: str  # human-readable (e.g. "Tamil"), never fastText's raw label alone
    raw_label: str  # fastText's own label (e.g. "ta"), preserved for audit
    confidence: float


@dataclass(frozen=True)
class LanguageIdentificationResult:
    primary_language: str | None
    confidence: float
    candidate_languages: list[LanguageCandidate] = field(default_factory=list)
    detector: str = "fasttext_lid176"
    detector_version: str = "lid.176.ftz"
    status: str = "SUCCESS"  # SUCCESS | FAILED | LOW_CONFIDENCE | EMPTY_TEXT
    processing_time_ms: int = 0
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_language": self.primary_language,
            "confidence": self.confidence,
            "candidate_languages": [
                {"language": c.language, "raw_label": c.raw_label, "confidence": c.confidence}
                for c in self.candidate_languages
            ],
            "detector": self.detector,
            "detector_version": self.detector_version,
            "status": self.status,
            "processing_time_ms": self.processing_time_ms,
            "detail": self.detail,
        }


class LanguageDetector(Protocol):
    """Abstraction boundary (Section 21) — business logic depends on
    this Protocol, never directly on fastText, so a future detector can
    replace `FastTextLanguageDetector` without touching callers."""

    def detect(self, text: str, *, top_k: int = 3) -> LanguageIdentificationResult: ...


class FastTextLanguageDetector:
    provider_name = "fasttext_lid176"

    def __init__(self, *, python_exe: str | None = None) -> None:
        configured = python_exe or settings.LANGID_PYTHON
        self._python_exe_path = (
            Path(configured) if configured else default_isolated_python(".venv-langid")
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
                result.get("error", "unknown fastText runner error")
            )
        return result

    def detect(self, text: str, *, top_k: int = 3) -> LanguageIdentificationResult:
        """Real, local fastText inference. Never raises: a missing
        runtime/model, timeout, or crash degrades to `status="FAILED"`
        (Section 46's "one language detector failure does not destroy
        OCR evidence")."""
        stripped = text.strip()
        if not stripped:
            return LanguageIdentificationResult(
                primary_language=None, confidence=0.0, status="EMPTY_TEXT"
            )

        try:
            payload = self._invoke({"text": stripped, "top_k": top_k, "mode": "predict"})
        except Exception as exc:  # noqa: BLE001 - isolated-runtime failure must degrade, not crash the caller
            return LanguageIdentificationResult(
                primary_language=None,
                confidence=0.0,
                status="FAILED",
                detail=f"{type(exc).__name__}: {exc}",
            )

        raw_predictions = payload.get("predictions", [])
        candidates = [
            LanguageCandidate(
                language=FASTTEXT_LABEL_TO_LANGUAGE.get(p["language"], p["language"]),
                raw_label=p["language"],
                confidence=float(p["confidence"]),
            )
            for p in raw_predictions
        ]
        if not candidates:
            return LanguageIdentificationResult(
                primary_language=None,
                confidence=0.0,
                status="FAILED",
                detail="fastText returned no predictions",
                processing_time_ms=int(payload.get("processing_time_ms", 0)),
            )

        top = candidates[0]
        status = "SUCCESS" if top.confidence >= _LOW_CONFIDENCE_THRESHOLD else "LOW_CONFIDENCE"
        return LanguageIdentificationResult(
            primary_language=top.language,
            confidence=top.confidence,
            candidate_languages=candidates,
            status=status,
            processing_time_ms=int(payload.get("processing_time_ms", 0)),
        )

    def health_check(self) -> dict[str, Any]:
        if not self._python_exe_path.exists():
            return {
                "installed": False,
                "ready": False,
                "detail": (
                    f"Isolated runtime interpreter not found at {self._python_exe_path}. "
                    "Create the .venv-langid venv (Python 3.12) and install "
                    "fasttext-wheel + numpy<2 to activate language identification."
                ),
            }
        try:
            payload = self._invoke({"mode": "health"})
        except Exception as exc:  # noqa: BLE001 - health check must never raise, only report
            return {"installed": False, "ready": False, "detail": f"health check failed: {exc}"}
        return {
            "installed": bool(payload.get("installed", False)),
            "ready": bool(payload.get("installed", False)),
            "model_path": payload.get("model_path"),
            "detail": None,
        }
