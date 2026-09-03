"""
AI-provider-specific exceptions, additive to `app.core.exceptions`'s
existing `AIProviderNotImplementedError` (re-exported here so provider
code has one import site for every AI error it can raise). Mirrors
`app.services.ocr.exceptions` exactly (ADR-041's "same shape as OCR"
convention) — each maps to an HTTP status `AppError` already knows how to
render, no new exception handler wiring needed.
"""

from fastapi import status

from app.core.exceptions import AIProviderNotImplementedError, AppError

__all__ = [
    "AIProviderNotImplementedError",
    "AIDependencyMissingError",
    "AIProviderConfigurationError",
    "AIProviderAuthenticationError",
    "AIProviderConnectivityError",
    "AIProviderTimeoutError",
    "AIProviderRateLimitError",
    "AIProviderInvalidResponseError",
]


class AIDependencyMissingError(AppError):
    """Raised when a provider's `is_implemented = True` but its underlying
    SDK isn't actually installed (distinct from
    `AIProviderNotImplementedError`, which is "no code written yet" —
    this is "code exists, dependency doesn't")."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "ai_dependency_missing"


class AIProviderConfigurationError(AppError):
    """Missing/invalid provider configuration — e.g. no OpenAI API key,
    no Anthropic API key."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "ai_provider_configuration_error"


class AIProviderAuthenticationError(AppError):
    """The provider's credentials were present but rejected by the engine."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "ai_provider_authentication_error"


class AIProviderConnectivityError(AppError):
    """Network/connectivity failure reaching a cloud AI engine."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "ai_provider_connectivity_error"


class AIProviderTimeoutError(AppError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "ai_provider_timeout"


class AIProviderRateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "ai_provider_rate_limited"


class AIProviderInvalidResponseError(AppError):
    """The provider returned a response that could not be parsed into
    `ReferenceContentSchema`/`AnswerEvaluationResult` — malformed AI
    output (Phase 4): must fail the generation/evaluation attempt cleanly,
    never become a half-written or guessed result."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ai_provider_invalid_response"
