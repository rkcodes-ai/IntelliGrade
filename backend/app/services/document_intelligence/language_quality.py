"""
Language Quality Intelligence (Step 4.1 milestone — Free Local Grammar,
Spelling & Language Quality Intelligence).

**Engine**: the local, open-source LanguageTool standalone distribution
(`languagetool-org/languagetool`), invoked as a subprocess
(`java -jar languagetool-commandline.jar --json`) — never the paid
LanguageTool cloud/API service, never `language_tool_python` (that PyPI
wrapper is GPL-3.0-only; this project links against LanguageTool's own
core, which is LGPL-2.1-or-later — see `COPYING.txt` in
`backend/.languagetool/`, verified directly against the real downloaded
distribution, not assumed from memory). LanguageTool 6.6 (the last
fixed-version "stable" release before the project switched to a
snapshot-based model in March 2025) is pinned by using a specific,
version-controlled `.languagetool/` directory rather than always
fetching "whatever is current" — the same reproducibility discipline
already applied to `surya-ocr==0.13.1`/`transformers==4.46.3` elsewhere
in this codebase.

**Runtime**: LanguageTool is Java, not Python — the first non-Python
isolated runtime in this pipeline (Surya/docTR/TrOCR/pix2tex are all
Python venvs). It is bridged the same way in spirit (a fixed executable
path + a bounded-timeout subprocess call, `shell=False`, real JSON
parsing, never a shell string), just with `java.exe` instead of a venv's
`python.exe` — no new subprocess *framework* was invented, only a new
executable pointed at the existing pattern.

**Core principle (Section 2 of the milestone)**: language analysis
produces EVIDENCE. It never rewrites `OCRResult.raw_text`/
`normalized_text`, never "corrects" a student's answer before semantic
evaluation, and by default never affects marks — see `RUBRIC-AWARE
SCORING` below and `RubricCriterion.is_language_criterion`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.services.ocr.base import OCRLineResult

settings = get_settings()

LanguageQualityStatus = Literal["SUCCESS", "FAILED", "UNSUPPORTED_LANGUAGE", "NOT_IMPLEMENTED"]
FindingCategory = Literal[
    "GRAMMAR", "SPELLING", "PUNCTUATION", "CAPITALIZATION", "REPETITION", "STYLE", "OTHER"
]
FindingCertainty = Literal["LIKELY_LANGUAGE_ERROR", "POSSIBLE_LANGUAGE_ERROR", "OCR_UNCERTAIN"]

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LANGUAGETOOL_DIR = BACKEND_ROOT / ".languagetool"
DEFAULT_LANGUAGETOOL_JAR = DEFAULT_LANGUAGETOOL_DIR / "languagetool-commandline.jar"

# Real Java 21 install location this milestone provisioned via winget
# (`EclipseAdoptium.Temurin.21.JRE`) -- used only when
# `settings.LANGUAGETOOL_JAVA_PATH` is unset and plain `"java"` isn't on
# PATH (a freshly-installed JRE often isn't visible to an already-running
# shell/service until it restarts).
_KNOWN_TEMURIN_PATH = Path("C:/Program Files/Eclipse Adoptium/jre-21.0.11.10-hotspot/bin/java.exe")

# Real, confirmed-supported language codes (from `java -jar
# languagetool-commandline.jar --list` against the actual downloaded
# 6.6 distribution) -- checked BEFORE spawning a JVM, so an unsupported
# language never pays JVM startup cost only to fail.
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {
        "ar",
        "ast-ES",
        "be-BY",
        "br-FR",
        "ca-ES",
        "ca-ES-balear",
        "ca-ES-valencia",
        "crh-UA",
        "da-DK",
        "de",
        "de-AT",
        "de-CH",
        "de-DE",
        "de-DE-x-simple-language",
        "el-GR",
        "en",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-NZ",
        "en-US",
        "en-ZA",
        "eo",
        "es",
        "es-AR",
        "fa",
        "fr",
        "fr-BE",
        "fr-CA",
        "fr-CH",
        "ga-IE",
        "gl-ES",
        "it",
        "ja-JP",
        "km-KH",
        "nl",
        "nl-BE",
        "pl-PL",
        "pt",
        "pt-AO",
        "pt-BR",
        "pt-MZ",
        "pt-PT",
        "ro-RO",
        "ru-RU",
        "sk-SK",
        "sl-SI",
        "sv",
        "ta-IN",
        "tl-PH",
        "uk-UA",
        "zh-CN",
    }
)

# Real LanguageTool `rule.category.id` values (confirmed via real local
# invocation this milestone, not guessed) -> this project's finding
# vocabulary. Anything not listed falls back to "OTHER" -- never crashes
# on an unmapped category.
_CATEGORY_MAP: dict[str, FindingCategory] = {
    "GRAMMAR": "GRAMMAR",
    "COMPOUNDING": "GRAMMAR",
    "CONFUSED_WORDS": "GRAMMAR",
    "TYPOS": "SPELLING",
    "CASING": "CAPITALIZATION",
    "PUNCTUATION": "PUNCTUATION",
    "REDUNDANCY": "REPETITION",
    "REPETITIONS_STYLE": "REPETITION",
    "STYLE": "STYLE",
    "MISC": "STYLE",
    "SEMANTICS": "STYLE",
    "COLLOCATIONS": "STYLE",
    "TYPOGRAPHY": "OTHER",
}

# Weights for the deterministic language-quality score (Section 25) --
# documented, reasonable defaults, NOT measured accuracy figures, same
# framing as `app.services.ocr.fusion.DEFAULT_PROVIDER_WEIGHTS`. Grammar
# and spelling matter more to comprehension than punctuation/
# capitalization; repetition sits in between.
_SCORE_WEIGHTS: dict[FindingCategory, float] = {
    "GRAMMAR": 3.0,
    "SPELLING": 3.0,
    "PUNCTUATION": 1.0,
    "CAPITALIZATION": 1.0,
    "REPETITION": 1.5,
    "STYLE": 0.5,
    "OTHER": 0.5,
}

# A short, generic seed list (Section 14's own examples) -- deliberately
# NOT the only source; `analyze_language_quality`'s `technical_terms`
# parameter lets a caller add question/model-answer/course-scoped terms
# on top of this. Matching is case-insensitive.
DEFAULT_TECHNICAL_TERMS: frozenset[str] = frozenset(
    term.lower()
    for term in (
        "PostgreSQL",
        "MySQL",
        "NumPy",
        "Pandas",
        "PyTorch",
        "TensorFlow",
        "OpenCV",
        "PaddleOCR",
        "Tesseract",
        "Surya",
        "docTR",
        "TrOCR",
        "pix2tex",
        "SymPy",
        "Kubernetes",
        "Docker",
        "Redis",
        "Celery",
        "MinIO",
        "TCP/IP",
        "TCP",
        "UDP",
        "OSI",
        "IPv4",
        "IPv6",
        "DBMS",
        "NoSQL",
        "API",
        "REST",
        "JSON",
        "SQL",
        "HTTP",
        "HTTPS",
        "CNN",
        "RNN",
        "LSTM",
        "Transformer",
        "backpropagation",
        "polymorphism",
        "virtualization",
        "microservices",
        "IntelliGrade",
    )
)

_LOW_OCR_CONFIDENCE_THRESHOLD = 70.0
_SHORT_ANSWER_MAX_WORDS = 6
_CODE_KEYWORD_PATTERN = re.compile(
    r"\b(def|class|import|function|return|console\.log|System\.out|printf|"
    r"SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|public\s+class|void\s+\w+\s*\(|"
    r"#include|for\s*\(|while\s*\(|elif|endif)\b",
    re.IGNORECASE,
)
_CODE_SYMBOL_PATTERN = re.compile(r"[{};]|==|!=|->|=>|::|\+\+")
_EQUATION_PATTERN = re.compile(
    r"(\\[a-zA-Z]+|[∫∑∏√±≤≥≠∞πθαβγΔ]|[a-zA-Z]\s*\^\s*[0-9a-zA-Z]|[a-zA-Z]_\{?[0-9a-zA-Z])"
)
_REPEATED_WORD_PATTERN = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)
_BULLET_LINE_PATTERN = re.compile(r"^\s*([-*•]|\d+[.)]|\([a-zA-Z0-9]+\))\s+")


@dataclass(frozen=True)
class LanguageFinding:
    rule_id: str
    category: FindingCategory
    message: str
    offset: int
    length: int
    original_fragment: str
    suggested_replacements: list[str] = field(default_factory=list)
    severity: str = "info"
    certainty: FindingCertainty = "LIKELY_LANGUAGE_ERROR"
    ocr_confidence: float | None = None
    ocr_uncertain: bool = False
    technical_term: bool = False
    excluded_from_scoring: bool = False
    exclusion_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "message": self.message,
            "offset": self.offset,
            "length": self.length,
            "original_fragment": self.original_fragment,
            "suggested_replacements": self.suggested_replacements,
            "severity": self.severity,
            "certainty": self.certainty,
            "ocr_confidence": self.ocr_confidence,
            "ocr_uncertain": self.ocr_uncertain,
            "technical_term": self.technical_term,
            "excluded_from_scoring": self.excluded_from_scoring,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True)
class LanguageEvidence:
    analyzer_provider: str
    analyzer_version: str
    language: str
    status: LanguageQualityStatus
    original_text_hash: str
    analyzed_character_count: int
    word_count: int
    sentence_count: int
    grammar_error_count: int = 0
    spelling_error_count: int = 0
    punctuation_error_count: int = 0
    capitalization_error_count: int = 0
    repeated_word_count: int = 0
    grammar_errors_per_100_words: float = 0.0
    spelling_errors_per_100_words: float = 0.0
    overall_language_quality_score: float | None = None
    score_explanation: str | None = None
    findings: list[LanguageFinding] = field(default_factory=list)
    processing_time_ms: int = 0
    detail: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzer_provider": self.analyzer_provider,
            "analyzer_version": self.analyzer_version,
            "language": self.language,
            "status": self.status,
            "original_text_hash": self.original_text_hash,
            "analyzed_character_count": self.analyzed_character_count,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "grammar_error_count": self.grammar_error_count,
            "spelling_error_count": self.spelling_error_count,
            "punctuation_error_count": self.punctuation_error_count,
            "capitalization_error_count": self.capitalization_error_count,
            "repeated_word_count": self.repeated_word_count,
            "grammar_errors_per_100_words": self.grammar_errors_per_100_words,
            "spelling_errors_per_100_words": self.spelling_errors_per_100_words,
            "overall_language_quality_score": self.overall_language_quality_score,
            "score_explanation": self.score_explanation,
            "findings": [f.to_dict() for f in self.findings],
            "processing_time_ms": self.processing_time_ms,
            "detail": self.detail,
            "raw_metadata": self.raw_metadata,
        }


def _resolve_java_path(java_path: str | None) -> Path:
    configured = java_path or settings.LANGUAGETOOL_JAVA_PATH
    if configured:
        return Path(configured)
    if _KNOWN_TEMURIN_PATH.exists():
        return _KNOWN_TEMURIN_PATH
    return Path("java")  # fall back to PATH resolution


def _resolve_jar_path(jar_path: str | None) -> Path:
    configured = jar_path or settings.LANGUAGETOOL_JAR_PATH
    return Path(configured) if configured else DEFAULT_LANGUAGETOOL_JAR


def looks_like_code(text: str) -> bool:
    """Heuristic-only (Section 16/41): common code keywords/punctuation
    density. There is no dedicated `CODE` region type in this project's
    layout vocabulary (Surya's own `Code` label collapses into `OTHER`),
    so protecting code from grammar-checking must work from the text
    itself, not a region-type lookup."""
    if not text.strip():
        return False
    keyword_hits = len(_CODE_KEYWORD_PATTERN.findall(text))
    symbol_hits = len(_CODE_SYMBOL_PATTERN.findall(text))
    density = (keyword_hits + symbol_hits) / max(len(text.split()), 1)
    return keyword_hits >= 2 or density > 0.15


def looks_like_equation(text: str) -> bool:
    """Heuristic-only text-level math detection (Section 17/42) -- a
    complement to, not a replacement for, an explicit `MathEvidence`/
    EQUATION-region exclusion a caller may supply via
    `excluded_char_ranges`."""
    if not text.strip():
        return False
    hits = len(_EQUATION_PATTERN.findall(text))
    return hits >= 2 or hits / max(len(text.split()), 1) > 0.3


def is_short_or_fragment_answer(text: str) -> bool:
    """Section 26/27: very short answers ('TCP/IP', 'Yes') and bullet-
    style fragments must not be judged like essays."""
    stripped = text.strip()
    if not stripped:
        return True
    word_count = len(stripped.split())
    if word_count <= _SHORT_ANSWER_MAX_WORDS:
        return True
    lines = [line for line in stripped.splitlines() if line.strip()]
    bullet_lines = sum(1 for line in lines if _BULLET_LINE_PATTERN.match(line))
    return bool(lines) and bullet_lines / len(lines) > 0.5


def _detect_repeated_words(text: str) -> list[LanguageFinding]:
    """Deterministic (Section 31/32) -- not delegated to LanguageTool, a
    plain regex, independently testable, immune to LanguageTool being
    unavailable."""
    findings: list[LanguageFinding] = []
    for match in _REPEATED_WORD_PATTERN.finditer(text):
        findings.append(
            LanguageFinding(
                rule_id="REPEATED_WORD_HEURISTIC",
                category="REPETITION",
                message=f"Repeated word: '{match.group(1)}'.",
                offset=match.start(),
                length=len(match.group(0)),
                original_fragment=match.group(0),
                suggested_replacements=[match.group(1)],
                certainty="LIKELY_LANGUAGE_ERROR",
            )
        )
    return findings


def _build_uncertain_ranges(
    ocr_lines: list[OCRLineResult] | None,
    disagreement_line_indices: set[int] | None,
    *,
    low_confidence_threshold: float,
) -> list[tuple[int, int, float | None]]:
    """Replays the exact `\\n.join(...)` construction
    `app.services.ocr.fusion.fuse_page_candidates` uses to build
    `raw_text`, so a line's character range here lines up exactly with
    `disagreement_regions`' `line_index` -- see this module's own
    docstring on why OCR-uncertainty analysis targets `raw_text`, not
    `normalized_text` (normalization can shift/collapse lines)."""
    if not ocr_lines:
        return []
    ranges: list[tuple[int, int, float | None]] = []
    cursor = 0
    disagreement_line_indices = disagreement_line_indices or set()
    for index, line in enumerate(ocr_lines):
        start = cursor
        end = start + len(line.text)
        is_uncertain = (
            line.confidence < low_confidence_threshold or index in disagreement_line_indices
        )
        if is_uncertain:
            ranges.append((start, end, line.confidence))
        cursor = end + 1  # +1 for the joining "\n"
    return ranges


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _invoke_languagetool(
    text: str, *, language: str, java_path: Path, jar_path: Path, timeout_seconds: float
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(  # noqa: S603 - fixed interpreter/jar paths, no shell, argv list only
            [str(java_path), "-jar", str(jar_path), "--json", "-l", language, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            check=False,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "")[-2000:]
        raise RuntimeError(
            f"LanguageTool exited with code {proc.returncode}. stderr: {stderr_tail}"
        )
    # The CLI prints one or two human-readable status lines ("Expected
    # text language...", "Working on <file>...") to stdout BEFORE the
    # JSON payload -- extract the JSON object, never assume stdout is
    # pure JSON.
    stdout = proc.stdout or ""
    json_start = stdout.find("{")
    if json_start == -1:
        raise RuntimeError(f"LanguageTool produced no JSON output. stdout: {stdout[-2000:]}")
    return dict(json.loads(stdout[json_start:]))


def analyze_language_quality(
    text: str,
    *,
    language: str = "en-US",
    ocr_lines: list[OCRLineResult] | None = None,
    disagreement_line_indices: set[int] | None = None,
    technical_terms: set[str] | None = None,
    excluded_char_ranges: list[tuple[int, int]] | None = None,
    java_path: str | None = None,
    jar_path: str | None = None,
    timeout_seconds: float | None = None,
) -> LanguageEvidence:
    """Real, local LanguageTool analysis with OCR-uncertainty awareness
    and content protection. Never raises: every failure mode (missing
    Java/jar, unsupported language, timeout, malformed output) returns a
    `LanguageEvidence` with an honest `status` instead (Section 48:
    "analyzer failure cannot break grading").

    `excluded_char_ranges` lets a caller that already has region-level
    classification (DIAGRAM/EQUATION/TABLE `DocumentRegion`s, or
    `MathEvidence`) tell this function exactly which character spans of
    `text` are non-prose -- those spans are stripped before submission to
    LanguageTool. When absent, `looks_like_code`/`looks_like_equation`
    heuristics provide best-effort protection from the text alone.
    """
    started = time.perf_counter()
    original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    word_count = len(text.split())
    sentence_count = len([s for s in re.split(r"[.!?]+", text) if s.strip()])

    base_kwargs: dict[str, Any] = {
        "analyzer_provider": "languagetool_local",
        "analyzer_version": "6.6",
        "language": language,
        "original_text_hash": original_hash,
        "analyzed_character_count": len(text),
        "word_count": word_count,
        "sentence_count": sentence_count,
    }

    if not text.strip():
        return LanguageEvidence(
            **base_kwargs,
            status="SUCCESS",
            overall_language_quality_score=None,
            score_explanation="empty text -- no score computed",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )

    if language not in SUPPORTED_LANGUAGES:
        return LanguageEvidence(
            **base_kwargs,
            status="UNSUPPORTED_LANGUAGE",
            detail=f"'{language}' is not in LanguageTool's supported language list.",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )

    if looks_like_code(text) or looks_like_equation(text):
        return LanguageEvidence(
            **base_kwargs,
            status="SUCCESS",
            overall_language_quality_score=None,
            score_explanation="skipped -- content classified as code/equation, not prose",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
            raw_metadata={"skipped_reason": "code_or_equation_content"},
        )

    analysis_text = text
    if excluded_char_ranges:
        chars = list(text)
        for start, end in excluded_char_ranges:
            for i in range(max(start, 0), min(end, len(chars))):
                chars[i] = " "  # blank out, preserving offsets for remaining findings
        analysis_text = "".join(chars)

    resolved_java = _resolve_java_path(java_path)
    resolved_jar = _resolve_jar_path(jar_path)
    resolved_timeout = timeout_seconds or settings.LANGUAGETOOL_TIMEOUT_SECONDS

    if not resolved_jar.exists():
        return LanguageEvidence(
            **base_kwargs,
            status="FAILED",
            detail=f"LanguageTool jar not found at {resolved_jar}.",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )

    try:
        try:
            payload = _invoke_languagetool(
                analysis_text,
                language=language,
                java_path=resolved_java,
                jar_path=resolved_jar,
                timeout_seconds=resolved_timeout,
            )
        except subprocess.TimeoutExpired:
            # Exactly ONE bounded retry (never a loop, Section 9's "retry
            # once, never infinite" precedent from the Step 4 milestone) --
            # JVM startup time is genuinely more sensitive to transient
            # system load (other heavy tests/processes competing for CPU)
            # than a Python venv's interpreter start, so a single retry
            # absorbs real, observed transient contention without masking
            # a persistently broken installation (a second timeout still
            # surfaces as `status="FAILED"`, never silently swallowed).
            payload = _invoke_languagetool(
                analysis_text,
                language=language,
                java_path=resolved_java,
                jar_path=resolved_jar,
                timeout_seconds=resolved_timeout,
            )
    except subprocess.TimeoutExpired:
        return LanguageEvidence(
            **base_kwargs,
            status="FAILED",
            detail=f"LanguageTool timed out after {resolved_timeout:.0f}s (retried once).",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - any analyzer failure degrades, never propagates
        return LanguageEvidence(
            **base_kwargs,
            status="FAILED",
            detail=f"{type(exc).__name__}: {exc}",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )

    fragment_is_fragment_answer = is_short_or_fragment_answer(text)
    technical_allowlist = DEFAULT_TECHNICAL_TERMS | {t.lower() for t in (technical_terms or set())}
    uncertain_ranges = _build_uncertain_ranges(
        ocr_lines, disagreement_line_indices, low_confidence_threshold=_LOW_OCR_CONFIDENCE_THRESHOLD
    )

    findings: list[LanguageFinding] = []
    for match in payload.get("matches", []):
        offset = int(match.get("offset", 0))
        length = int(match.get("length", 0))
        fragment = text[offset : offset + length]
        category_id = match.get("rule", {}).get("category", {}).get("id", "OTHER")
        category = _CATEGORY_MAP.get(category_id, "OTHER")
        replacements = [r.get("value", "") for r in match.get("replacements", [])]

        is_technical_term = fragment.strip().lower() in technical_allowlist
        ocr_confidence: float | None = None
        ocr_uncertain = False
        for start, end, confidence in uncertain_ranges:
            if _overlaps(offset, offset + length, start, end):
                ocr_uncertain = True
                ocr_confidence = confidence
                break

        excluded = False
        reason: str | None = None
        if is_technical_term:
            excluded, reason = True, "technical_term"
        elif ocr_uncertain:
            excluded, reason = True, "ocr_uncertain"
        elif fragment_is_fragment_answer and category in ("CAPITALIZATION", "PUNCTUATION"):
            excluded, reason = True, "short_answer_fragment"

        certainty: FindingCertainty = "LIKELY_LANGUAGE_ERROR"
        if ocr_uncertain:
            certainty = "OCR_UNCERTAIN"
        elif category in ("STYLE", "OTHER"):
            certainty = "POSSIBLE_LANGUAGE_ERROR"

        findings.append(
            LanguageFinding(
                rule_id=match.get("rule", {}).get("id", "UNKNOWN_RULE"),
                category=category,
                message=match.get("message", ""),
                offset=offset,
                length=length,
                original_fragment=fragment,
                suggested_replacements=replacements,
                certainty=certainty,
                ocr_confidence=ocr_confidence,
                ocr_uncertain=ocr_uncertain,
                technical_term=is_technical_term,
                excluded_from_scoring=excluded,
                exclusion_reason=reason,
            )
        )

    findings.extend(_detect_repeated_words(text))

    scoreable = [f for f in findings if not f.excluded_from_scoring]
    grammar_count = sum(1 for f in scoreable if f.category == "GRAMMAR")
    spelling_count = sum(1 for f in scoreable if f.category == "SPELLING")
    punctuation_count = sum(1 for f in scoreable if f.category == "PUNCTUATION")
    capitalization_count = sum(1 for f in scoreable if f.category == "CAPITALIZATION")
    repetition_count = sum(1 for f in scoreable if f.category == "REPETITION")

    words_for_rate = max(word_count, 1)
    grammar_rate = grammar_count / words_for_rate * 100
    spelling_rate = spelling_count / words_for_rate * 100
    punctuation_rate = punctuation_count / words_for_rate * 100
    capitalization_rate = capitalization_count / words_for_rate * 100
    repetition_rate = repetition_count / words_for_rate * 100

    penalty = (
        grammar_rate * _SCORE_WEIGHTS["GRAMMAR"]
        + spelling_rate * _SCORE_WEIGHTS["SPELLING"]
        + punctuation_rate * _SCORE_WEIGHTS["PUNCTUATION"]
        + capitalization_rate * _SCORE_WEIGHTS["CAPITALIZATION"]
        + repetition_rate * _SCORE_WEIGHTS["REPETITION"]
    )
    score = max(0.0, min(100.0, 100.0 - penalty))

    return LanguageEvidence(
        **base_kwargs,
        status="SUCCESS",
        grammar_error_count=grammar_count,
        spelling_error_count=spelling_count,
        punctuation_error_count=punctuation_count,
        capitalization_error_count=capitalization_count,
        repeated_word_count=repetition_count,
        grammar_errors_per_100_words=round(grammar_rate, 2),
        spelling_errors_per_100_words=round(spelling_rate, 2),
        overall_language_quality_score=round(score, 2),
        score_explanation=(
            "100 - (grammar_rate*3.0 + spelling_rate*3.0 + punctuation_rate*1.0 + "
            "capitalization_rate*1.0 + repetition_rate*1.5), rates per 100 words, "
            "clamped to [0, 100]; excludes findings marked excluded_from_scoring "
            "(technical terms, OCR-uncertain spans, short-answer fragment rules)."
        ),
        findings=findings,
        processing_time_ms=int((time.perf_counter() - started) * 1000),
        raw_metadata={"raw_match_count": len(payload.get("matches", []))},
    )


def compute_language_criterion_marks(
    evidence: LanguageEvidence, *, max_marks: float, is_language_criterion: bool
) -> float | None:
    """Rubric-aware scoring policy (Sections 3/4/36/40): returns `None`
    (never a number) unless `is_language_criterion` is explicitly True --
    i.e. unless a `RubricCriterion.is_language_criterion` row exists and
    was passed in as such. When it IS authorized, the contribution is a
    simple linear mapping of `overall_language_quality_score` (0-100)
    onto `[0, max_marks]`, clamped -- it can never exceed `max_marks` and
    can never affect any *other* criterion's marks. This function
    produces EVIDENCE for a human/evaluation-engine decision, never
    calls itself authoritative (Section 36: "must NOT directly become
    marks... the evaluation engine remains responsible for marks")."""
    if not is_language_criterion:
        return None
    if evidence.overall_language_quality_score is None:
        return None
    fraction = evidence.overall_language_quality_score / 100.0
    return round(max(0.0, min(1.0, fraction)) * max_marks, 2)
