"""
Unit tests for `app.services.ocr.ensemble.run_ensemble` — the sequential,
partial-failure-tolerant, GPU-safety-oriented orchestrator that Surya/
docTR/TrOCR now sit behind alongside Tesseract/EasyOCR/PaddleOCR. These
tests use fake in-memory adapters (never real OCR engines) so they cover
the orchestrator's own control flow — order, failure isolation, shutdown
guarantees — independently of which real providers happen to be
installed on a given machine.
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.ocr.base import BoundingBox, OCRBlockResult, OCRLineResult, OCRPageResult
from app.services.ocr.ensemble import run_ensemble


def _fake_page(text: str, confidence: float = 90.0) -> OCRPageResult:
    line = OCRLineResult(
        text=text,
        bounding_box=BoundingBox(left=0, top=0, width=100, height=20),
        confidence=confidence,
        reading_order=0,
    )
    block = OCRBlockResult(
        bounding_box=BoundingBox(left=0, top=0, width=100, height=20),
        confidence=confidence,
        reading_order=0,
        lines=[line],
    )
    return OCRPageResult(
        raw_text=text,
        average_confidence=confidence,
        language="eng",
        rotation_degrees=0.0,
        blocks=[block],
    )


class _FakeAdapter:
    def __init__(
        self,
        *,
        text: str | None = None,
        raises: Exception | None = None,
        call_log: list[str] | None = None,
        name: str = "",
    ) -> None:
        self._text = text
        self._raises = raises
        self._call_log = call_log
        self._name = name
        self.shutdown_called = False

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        if self._call_log is not None:
            self._call_log.append(f"extract:{self._name}")
        if self._raises is not None:
            raise self._raises
        return _fake_page(self._text or "")

    def shutdown(self) -> None:
        self.shutdown_called = True
        if self._call_log is not None:
            self._call_log.append(f"shutdown:{self._name}")


def test_unknown_provider_code_becomes_failed_candidate_not_a_crash() -> None:
    with patch("app.services.ocr.ensemble.get_provider_adapter", side_effect=KeyError("nope")):
        outcome = run_ensemble("/fake.png", ["not_a_real_provider"])

    assert len(outcome.candidates) == 1
    assert outcome.candidates[0].status == "failed"
    assert "not a registered" in outcome.candidates[0].error_message
    assert outcome.fusion.raw_text == ""


def test_providers_run_sequentially_in_requested_order() -> None:
    call_log: list[str] = []
    adapters = {
        "a": _FakeAdapter(text="first", call_log=call_log, name="a"),
        "b": _FakeAdapter(text="second", call_log=call_log, name="b"),
    }
    with patch(
        "app.services.ocr.ensemble.get_provider_adapter", side_effect=lambda code: adapters[code]
    ):
        run_ensemble("/fake.png", ["a", "b"])

    assert call_log == ["extract:a", "shutdown:a", "extract:b", "shutdown:b"]


def test_shutdown_called_even_when_extract_raises() -> None:
    adapter = _FakeAdapter(raises=RuntimeError("engine crashed"))
    with patch("app.services.ocr.ensemble.get_provider_adapter", return_value=adapter):
        outcome = run_ensemble("/fake.png", ["broken"])

    assert adapter.shutdown_called is True
    assert outcome.candidates[0].status == "failed"
    assert "engine crashed" in outcome.candidates[0].error_message


def test_shutdown_exception_does_not_mask_the_real_outcome() -> None:
    class _AdapterWithBrokenShutdown(_FakeAdapter):
        def shutdown(self) -> None:
            raise RuntimeError("shutdown itself is broken")

    adapter = _AdapterWithBrokenShutdown(text="worked anyway")
    with patch("app.services.ocr.ensemble.get_provider_adapter", return_value=adapter):
        outcome = run_ensemble("/fake.png", ["p"])

    assert outcome.candidates[0].status == "success"
    assert outcome.fusion.raw_text == "worked anyway"


def test_one_provider_failing_does_not_prevent_fusion_from_others() -> None:
    adapters = {
        "good": _FakeAdapter(text="genuinely recognized text"),
        "bad": _FakeAdapter(raises=RuntimeError("dependency missing")),
    }
    with patch(
        "app.services.ocr.ensemble.get_provider_adapter", side_effect=lambda code: adapters[code]
    ):
        outcome = run_ensemble("/fake.png", ["good", "bad"])

    statuses = {c.provider_code: c.status for c in outcome.candidates}
    assert statuses == {"good": "success", "bad": "failed"}
    assert outcome.fusion.raw_text == "genuinely recognized text"
    assert "bad" in outcome.fusion.failed_providers


def test_all_providers_failing_yields_empty_fusion_result() -> None:
    adapters = {
        "a": _FakeAdapter(raises=RuntimeError("x")),
        "b": _FakeAdapter(raises=RuntimeError("y")),
    }
    with patch(
        "app.services.ocr.ensemble.get_provider_adapter", side_effect=lambda code: adapters[code]
    ):
        outcome = run_ensemble("/fake.png", ["a", "b"])

    assert outcome.fusion.raw_text == ""
    assert all(c.status == "failed" for c in outcome.candidates)


def test_explicit_weight_override_reaches_fusion() -> None:
    adapters = {
        "low": _FakeAdapter(text="low weight text"),
        "high": _FakeAdapter(text="high weight text"),
    }
    with patch(
        "app.services.ocr.ensemble.get_provider_adapter", side_effect=lambda code: adapters[code]
    ):
        outcome = run_ensemble("/fake.png", ["low", "high"], weights={"low": 0.1, "high": 0.99})

    # Both lines have the same confidence (90.0, from `_fake_page`'s
    # default) and identical geometry (both boxes are (0,0,100,20) in this
    # fixture, so they align at IoU=1.0) — the higher explicit weight must
    # win the tie-break.
    assert outcome.fusion.raw_text == "high weight text"
