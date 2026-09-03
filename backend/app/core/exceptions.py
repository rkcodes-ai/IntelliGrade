"""
Application exception hierarchy + FastAPI exception handlers.

Domain code should raise `AppError` subclasses instead of `HTTPException`
directly — this keeps business logic free of HTTP concerns (per the layered
architecture) while still producing consistent HTTP responses at the edge.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all domain/application exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "validation_error"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class RateLimitExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"


class AccountLockedError(AppError):
    """Raised on login when `User.is_locked` — too many recent failed attempts."""

    status_code = status.HTTP_423_LOCKED
    error_code = "account_locked"


class OCRProviderNotImplementedError(AppError):
    """Raised by an `OCRProviderAdapter.extract()` stub (Module 05) whose
    engine has a catalog entry but no real implementation yet — see ADR-032."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "ocr_provider_not_implemented"


class AIProviderNotImplementedError(AppError):
    """Raised by an `AIProviderAdapter.evaluate()` stub (Module 06) whose
    engine has a catalog entry but no real implementation yet — see ADR-041,
    the AI-evaluation sibling of `OCRProviderNotImplementedError`."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "ai_provider_not_implemented"


def _error_response(
    status_code: int, error_code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {},
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire all exception handlers onto the FastAPI app instance."""

    @app.exception_handler(AppError)
    async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_exception",
            path=request.url.path,
            error_code=exc.error_code,
            message=exc.message,
        )
        return _error_response(exc.status_code, exc.error_code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic error dicts can contain non-JSON-serializable values (e.g. a
        # raw exception in `ctx` from a custom validator) — jsonable_encoder
        # normalizes them. Passing exc.errors() straight to JSONResponse would
        # raise TypeError on those cases instead of returning a clean 422.
        errors = jsonable_encoder(exc.errors())
        logger.info("request_validation_error", path=request.url.path, errors=errors)
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "Request validation failed.",
            {"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
        )
