"""Regression tests for cross-cutting middleware behavior."""

import logging

from httpx import AsyncClient

from app.core.constants import REQUEST_ID_HEADER


async def test_response_carries_a_request_id_header(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) > 0


async def test_client_supplied_request_id_is_echoed_back(client: AsyncClient) -> None:
    response = await client.get("/health", headers={REQUEST_ID_HEADER: "test-trace-id-123"})
    assert response.headers[REQUEST_ID_HEADER] == "test-trace-id-123"


async def test_request_id_is_bound_into_structlog_context_during_the_request(
    client: AsyncClient,
) -> None:
    # Attaches a plain stdlib logging.Handler directly to the root logger
    # (reusing the already-configured formatter) rather than relying on
    # structlog's `capture_logs()` or pytest's stdout capture fixtures: both
    # proved unreliable here since our handler is bound to `sys.stdout` at
    # app-import time, before either capture mechanism attaches per-test.
    # This exercises the exact same formatter production log lines go through.
    root_logger = logging.getLogger()
    existing_handler = root_logger.handlers[0]
    records: list[str] = []

    class _CollectingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(existing_handler.formatter.format(record))  # type: ignore[union-attr]

    collector = _CollectingHandler()
    root_logger.addHandler(collector)
    try:
        response = await client.get("/health", headers={REQUEST_ID_HEADER: "trace-abc"})
    finally:
        root_logger.removeHandler(collector)

    assert response.status_code == 200
    access_log_lines = [line for line in records if "http_request" in line and "trace-abc" in line]
    assert (
        access_log_lines
    ), f"expected an http_request log line containing the request id, got:\n{records}"


async def test_response_has_security_headers(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
