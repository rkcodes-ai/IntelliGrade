"""
Structured logging configuration using `structlog`, integrated with stdlib
`logging` so third-party libraries (uvicorn, sqlalchemy, celery, ...) are
formatted consistently with application logs.

Emits JSON logs in production-like environments (easy to ingest into a log
aggregator) and human-readable colored logs in local development.
"""

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog processors. Call once at startup."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # `default=str` is a safety net: a log call that includes an object json.dumps
    # can't natively serialize (e.g. a raw exception, Decimal, or domain object)
    # falls back to str(obj) instead of crashing the entire logging pipeline.
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer(default=str)
        if settings.LOG_JSON
        else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to `name` (typically `__name__`)."""
    return structlog.get_logger(name)
