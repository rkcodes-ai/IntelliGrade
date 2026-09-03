"""
OCR-provider-specific exceptions, additive to `app.core.exceptions`'s
existing `OCRProviderNotImplementedError` (re-exported here so provider
code has one import site for every OCR error it can raise). Each maps to
an HTTP status the API layer already knows how to render via
`AppError`/`_error_response` in `app.core.exceptions` — no new exception
handler wiring is needed.
"""

from fastapi import status

from app.core.exceptions import AppError, OCRProviderNotImplementedError

__all__ = [
    "OCRProviderNotImplementedError",
    "OCRDependencyMissingError",
    "OCRProviderConfigurationError",
    "OCRProviderAuthenticationError",
    "OCRProviderConnectivityError",
    "OCRProviderTimeoutError",
    "OCRProviderRateLimitError",
    "OCRUnsupportedFormatError",
    "OCRCorruptedDocumentError",
    "OCRIsolatedRuntimeMissingError",
    "OCRIsolatedRuntimeTimeoutError",
    "OCRIsolatedRuntimeCrashError",
    "OCRIsolatedRuntimeMalformedResponseError",
    "OCRIsolatedRuntimeInferenceError",
]


class OCRDependencyMissingError(AppError):
    """Raised when a provider's `is_implemented = True` but its underlying
    SDK/model/executable isn't actually installed on this machine (distinct
    from `OCRProviderNotImplementedError`, which is "no code written yet" —
    this is "code exists, dependency doesn't")."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "ocr_dependency_missing"


class OCRProviderConfigurationError(AppError):
    """Missing/invalid provider configuration — e.g. no Azure endpoint,
    no Google service-account credentials path, no AWS region."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "ocr_provider_configuration_error"


class OCRProviderAuthenticationError(AppError):
    """The provider's credentials were present but rejected by the engine
    (expired key, revoked service account, wrong secret, etc.)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "ocr_provider_authentication_error"


class OCRProviderConnectivityError(AppError):
    """Network/connectivity failure reaching a cloud OCR engine."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "ocr_provider_connectivity_error"


class OCRProviderTimeoutError(AppError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "ocr_provider_timeout"


class OCRProviderRateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "ocr_provider_rate_limited"


class OCRUnsupportedFormatError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    error_code = "ocr_unsupported_format"


class OCRCorruptedDocumentError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "ocr_corrupted_document"


class OCRIsolatedRuntimeMissingError(AppError):
    """The isolated venv (interpreter or runner script) for a bridged
    provider (Surya/docTR/TrOCR) doesn't exist on this machine — distinct
    from `OCRDependencyMissingError` (package not importable in-process),
    since here the whole isolated environment is absent."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "ocr_isolated_runtime_missing"


class OCRIsolatedRuntimeTimeoutError(AppError):
    """The isolated subprocess did not finish within its startup+inference
    budget — likely a genuinely slow/stuck model load, not a transient
    blip, since real inference timeouts here are already generous."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "ocr_isolated_runtime_timeout"


class OCRIsolatedRuntimeCrashError(AppError):
    """The isolated subprocess exited with a non-zero code (uncaught
    exception, CUDA OOM, segfault, etc.)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ocr_isolated_runtime_crash"


class OCRIsolatedRuntimeMalformedResponseError(AppError):
    """The isolated subprocess exited 0 but its response file was missing
    or not valid JSON — a protocol violation, not an inference failure."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ocr_isolated_runtime_malformed_response"


class OCRIsolatedRuntimeInferenceError(AppError):
    """The isolated subprocess ran, wrote a well-formed response, and that
    response itself reports `success: false` (a genuine, caught error
    inside the runner — e.g. a corrupt image) rather than a crash."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "ocr_isolated_runtime_inference_error"
