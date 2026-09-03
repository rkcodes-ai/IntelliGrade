"""
OCRBenchmarkService — runs the same page image through multiple OCR
providers and reports comparable accuracy/confidence/performance metrics
for each (Module 12).

Deliberately a plain, stateless, non-tenant-scoped service (not a
`TenantScopedService`) -- a benchmark run reads/writes no institution data,
it only exercises `OCRProviderAdapter.extract()` for each requested
provider against a caller-supplied image and reports what happened. Never
persisted -- the OCR Administration page's benchmark view calls this
on-demand and renders the response directly (see `docs/ocr-pipeline-
guide.md`'s benchmark section).

CPU/memory sampling is a best-effort, same-process measurement via
`psutil.Process(os.getpid())` -- it captures this worker process's overall
resource use around each provider call, not a perfectly isolated per-call
figure (a cloud SDK call is mostly waiting on network I/O, not CPU, and a
local ML engine like EasyOCR may use background threads) -- reported
honestly as an approximation, not a fabricated precise number. GPU usage is
reported as "available" (from `capabilities()`/`health_check()`), not
"utilized" -- this module doesn't attempt real GPU utilization sampling
(would require `pynvml`/vendor-specific tooling, a real dependency this
project doesn't otherwise need).

Word/character accuracy are only computed when the caller supplies
`reference_text` (a human-verified transcription) -- without one, "accuracy"
would be meaningless, so those fields stay `None` rather than reporting a
fabricated number.
"""

import os
import time
from dataclasses import dataclass

import psutil

from app.services.ocr.base import OCRProviderAdapter
from app.services.ocr.registry import get_provider_adapter, list_registered_codes


@dataclass(frozen=True)
class ProviderBenchmarkResult:
    provider_code: str
    success: bool
    error: str | None
    provider_version: str | None
    processing_time_seconds: float | None
    average_confidence: float | None
    character_count: int
    word_count: int
    throughput_chars_per_second: float | None
    cpu_percent: float | None
    memory_delta_mb: float | None
    gpu_available: bool | None
    word_accuracy: float | None
    character_accuracy: float | None


@dataclass(frozen=True)
class BenchmarkReport:
    language: str
    reference_text_supplied: bool
    results: list[ProviderBenchmarkResult]


class OCRBenchmarkService:
    def run(
        self,
        image_path: str,
        *,
        language: str = "eng",
        provider_codes: list[str] | None = None,
        reference_text: str | None = None,
    ) -> BenchmarkReport:
        codes = provider_codes if provider_codes is not None else list_registered_codes()
        results = [
            self._run_one(code, image_path, language=language, reference_text=reference_text)
            for code in codes
        ]
        return BenchmarkReport(
            language=language,
            reference_text_supplied=reference_text is not None,
            results=results,
        )

    def _run_one(
        self,
        provider_code: str,
        image_path: str,
        *,
        language: str,
        reference_text: str | None,
    ) -> ProviderBenchmarkResult:
        try:
            adapter = get_provider_adapter(provider_code)
        except KeyError:
            return ProviderBenchmarkResult(
                provider_code=provider_code,
                success=False,
                error=f"'{provider_code}' is not a registered OCR provider code.",
                provider_version=None,
                processing_time_seconds=None,
                average_confidence=None,
                character_count=0,
                word_count=0,
                throughput_chars_per_second=None,
                cpu_percent=None,
                memory_delta_mb=None,
                gpu_available=None,
                word_accuracy=None,
                character_accuracy=None,
            )

        process = psutil.Process(os.getpid())
        process.cpu_percent(interval=None)  # first call always returns 0.0 -- primes the sample
        memory_before = process.memory_info().rss

        wall_start = time.perf_counter()
        try:
            page_result = adapter.extract(image_path, language=language)
        except Exception as exc:  # noqa: BLE001 - a benchmark run must never abort on one provider's failure
            return ProviderBenchmarkResult(
                provider_code=provider_code,
                success=False,
                error=str(exc),
                provider_version=_safe_provider_version(adapter),
                processing_time_seconds=None,
                average_confidence=None,
                character_count=0,
                word_count=0,
                throughput_chars_per_second=None,
                cpu_percent=None,
                memory_delta_mb=None,
                gpu_available=_safe_gpu_available(adapter),
                word_accuracy=None,
                character_accuracy=None,
            )
        wall_seconds = time.perf_counter() - wall_start

        cpu_percent = process.cpu_percent(interval=None)
        memory_delta_mb = (process.memory_info().rss - memory_before) / (1024 * 1024)

        processing_time = adapter.processing_time() or wall_seconds
        character_count = len(page_result.raw_text)
        word_count = len(page_result.raw_text.split())
        throughput = (character_count / processing_time) if processing_time > 0 else None

        word_accuracy = character_accuracy = None
        if reference_text is not None:
            character_accuracy = _character_accuracy(page_result.raw_text, reference_text)
            word_accuracy = _word_accuracy(page_result.raw_text, reference_text)

        return ProviderBenchmarkResult(
            provider_code=provider_code,
            success=True,
            error=None,
            provider_version=_safe_provider_version(adapter),
            processing_time_seconds=processing_time,
            average_confidence=page_result.average_confidence,
            character_count=character_count,
            word_count=word_count,
            throughput_chars_per_second=throughput,
            cpu_percent=cpu_percent,
            memory_delta_mb=memory_delta_mb,
            gpu_available=_safe_gpu_available(adapter),
            word_accuracy=word_accuracy,
            character_accuracy=character_accuracy,
        )


def _safe_provider_version(adapter: OCRProviderAdapter) -> str | None:
    try:
        return adapter.provider_version()
    except Exception:  # noqa: BLE001 - version lookup failing must not break the benchmark result
        return None


def _safe_gpu_available(adapter: OCRProviderAdapter) -> bool | None:
    try:
        return adapter.health_check().gpu_available
    except Exception:  # noqa: BLE001 - health_check failing must not break the benchmark result
        return None


def _word_accuracy(hypothesis: str, reference: str) -> float:
    """`1 - WER` (word error rate), clamped to `[0, 1]` -- WER can exceed 1
    when the hypothesis is much longer than the reference (more insertions
    than reference words), which isn't a meaningful "negative accuracy"."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 1.0 if not hyp_words else 0.0
    distance = _edit_distance(ref_words, hyp_words)
    return max(0.0, 1.0 - distance / len(ref_words))


def _character_accuracy(hypothesis: str, reference: str) -> float:
    """`1 - CER` (character error rate), same clamping rationale as `_word_accuracy`."""
    if not reference:
        return 1.0 if not hypothesis else 0.0
    distance = _edit_distance(list(reference), list(hypothesis))
    return max(0.0, 1.0 - distance / len(reference))


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    """Classic Levenshtein distance via dynamic programming -- O(len(reference)
    * len(hypothesis)) time and O(len(hypothesis)) space. Used for both
    word-level (WER) and character-level (CER) accuracy above."""
    previous_row = list(range(len(hypothesis) + 1))
    for i, ref_token in enumerate(reference, start=1):
        current_row = [i] + [0] * len(hypothesis)
        for j, hyp_token in enumerate(hypothesis, start=1):
            insertion = current_row[j - 1] + 1
            deletion = previous_row[j] + 1
            substitution = previous_row[j - 1] + (0 if ref_token == hyp_token else 1)
            current_row[j] = min(insertion, deletion, substitution)
        previous_row = current_row
    return previous_row[-1]
