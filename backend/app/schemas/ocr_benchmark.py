"""OCR benchmark schemas (Module 12) — read-only response shapes for
`POST /ocr-providers/benchmark`. Nothing here is persisted; these mirror
`app.services.ocr_benchmark_service`'s dataclasses via `from_attributes`."""

from app.schemas.base import BaseSchema


class ProviderBenchmarkResultRead(BaseSchema):
    provider_code: str
    success: bool
    error: str | None = None
    provider_version: str | None = None
    processing_time_seconds: float | None = None
    average_confidence: float | None = None
    character_count: int
    word_count: int
    throughput_chars_per_second: float | None = None
    cpu_percent: float | None = None
    memory_delta_mb: float | None = None
    gpu_available: bool | None = None
    word_accuracy: float | None = None
    character_accuracy: float | None = None


class BenchmarkReportRead(BaseSchema):
    language: str
    reference_text_supplied: bool
    results: list[ProviderBenchmarkResultRead]
