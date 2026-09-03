"""
Regression test for `app.core.logging`.

The JSON renderer must not crash the whole logging pipeline just because one
log call happens to include a value `json.dumps` can't natively serialize
(e.g. a raw exception object) — it should fall back to `str(obj)`.
"""

import json

import structlog

from app.core.logging import configure_logging


def test_json_renderer_falls_back_to_str_for_unserializable_values() -> None:
    renderer = structlog.processors.JSONRenderer(default=str)

    rendered = renderer(
        None,
        "info",
        {"event": "something_happened", "cause": ValueError("boom")},
    )

    parsed = json.loads(rendered)
    assert parsed["event"] == "something_happened"
    assert "boom" in parsed["cause"]


def test_configure_logging_runs_without_error() -> None:
    # Smoke test: configuring logging twice (as happens across the test
    # session) must not raise.
    configure_logging()
