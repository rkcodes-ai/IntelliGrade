"""
OCR Ensemble Orchestrator (Six-Provider OCR milestone, "OCR Ensemble &
Fusion" phase) — runs a page image through every requested local OCR
provider **sequentially** (never concurrently — Section 17's explicit
GPU-memory-safety rule: this dev machine's RTX 4050 has 6 GB VRAM, not
enough to hold every GPU-capable engine loaded at once), collects each
provider's real or failed candidate, and hands the successful ones to
`app.services.ocr.fusion.fuse_page_candidates`.

One provider's failure never aborts the ensemble — every other provider
still runs, and the failure is recorded in the returned
`EnsembleRunResult.candidates` (as a `status="failed"` entry) rather than
raised. Fusion itself only produces an empty result if *every* requested
provider failed.

`adapter.shutdown()` is called after each provider's `extract()` call,
whether it succeeded or failed — this is what actually keeps GPU/CPU
memory bounded across a sequential multi-provider run (EasyOCR's
`shutdown()` drops its cached `Reader`, for example); providers with no
meaningful teardown (Tesseract, the cloud SDKs) already default this to a
no-op (see `OCRProviderAdapter.shutdown()`).
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field

from app.services.ocr.base import OCRPageResult
from app.services.ocr.fusion import FusionResult, ProviderCandidate, fuse_page_candidates
from app.services.ocr.registry import get_provider_adapter


@dataclass(frozen=True)
class EnsembleCandidateOutcome:
    provider_code: str
    status: str  # "success" | "failed"
    result: OCRPageResult | None
    error_message: str | None
    processing_time_ms: int | None


@dataclass(frozen=True)
class EnsembleRunResult:
    fusion: FusionResult
    candidates: list[EnsembleCandidateOutcome] = field(default_factory=list)


def run_ensemble(
    image_path: str,
    provider_codes: list[str],
    *,
    language: str = "eng",
    weights: dict[str, float] | None = None,
) -> EnsembleRunResult:
    """Run `image_path` through every code in `provider_codes`,
    sequentially, and fuse the successful results. `provider_codes` with
    an unknown/unregistered code is treated as a failed candidate (never
    raises `KeyError` out of this function) so one bad configuration entry
    can't abort the whole ensemble."""
    candidates: list[EnsembleCandidateOutcome] = []

    for provider_code in provider_codes:
        start = time.perf_counter()
        try:
            adapter = get_provider_adapter(provider_code)
        except KeyError:
            candidates.append(
                EnsembleCandidateOutcome(
                    provider_code=provider_code,
                    status="failed",
                    result=None,
                    error_message=f"'{provider_code}' is not a registered OCR provider code.",
                    processing_time_ms=None,
                )
            )
            continue

        try:
            page_result = adapter.extract(image_path, language=language)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            candidates.append(
                EnsembleCandidateOutcome(
                    provider_code=provider_code,
                    status="success",
                    result=page_result,
                    error_message=None,
                    processing_time_ms=elapsed_ms,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one provider's failure must never abort the ensemble
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            candidates.append(
                EnsembleCandidateOutcome(
                    provider_code=provider_code,
                    status="failed",
                    result=None,
                    error_message=str(exc),
                    processing_time_ms=elapsed_ms,
                )
            )
        finally:
            # Release GPU/CPU model memory before the next provider loads
            # (Section 17: never hold every engine in memory at once).
            # Teardown failure must never mask the real outcome above.
            with contextlib.suppress(Exception):
                adapter.shutdown()

    fusion_candidates = [
        ProviderCandidate(
            provider_code=c.provider_code,
            status=c.status,
            result=c.result,
            error_message=c.error_message,
            weight=(weights or {}).get(c.provider_code),
        )
        for c in candidates
    ]
    fusion_result = fuse_page_candidates(fusion_candidates, weights=weights)

    return EnsembleRunResult(fusion=fusion_result, candidates=candidates)
