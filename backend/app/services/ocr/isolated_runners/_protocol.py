"""
Shared request/response helpers for isolated OCR runner scripts.

Each runner (`surya_runner.py`, `doctr_runner.py`, `trocr_runner.py`) is
invoked as `<isolated-venv-python> <this-runner>.py <request.json>
<response.json>` by `app.services.ocr.isolated_runtime.invoke_isolated_runtime`
running in the MAIN backend process/venv. This module is copied-by-import
only within the runner's own isolated venv's `sys.path` (it lives next to
the runners, not inside any package the main venv imports) — it has zero
dependency on anything in `app/`, deliberately, since it must run standalone
under whichever isolated Python interpreter invokes it.

Every runner's `main()` follows the same shape: read the request file,
try real inference, always write a response file (never let an exception
escape to a bare traceback on stderr with no response file at all — that
would surface as `OCRIsolatedRuntimeMalformedResponseError` instead of a
clear inference-error message).
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any


def read_request(argv: list[str]) -> tuple[dict[str, Any], Path]:
    if len(argv) != 3:
        raise SystemExit(f"usage: {argv[0]} <request.json> <response.json>")
    request_path, response_path = Path(argv[1]), Path(argv[2])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    return request, response_path


def write_success(response_path: Path, payload: dict[str, Any]) -> None:
    payload["success"] = True
    response_path.write_text(json.dumps(payload), encoding="utf-8")


def write_failure(response_path: Path, error: str) -> None:
    response_path.write_text(json.dumps({"success": False, "error": error}), encoding="utf-8")


def run_main(modes: dict[str, Any]) -> None:
    """`modes` maps a request `"mode"` value (default `"extract"`) to an
    `entrypoint(request: dict) -> dict` callable returning the success
    payload (minus `"success"`, added by `write_success`). Any exception is
    caught here, printed to stderr for diagnostics, and turned into a
    well-formed `success: false` response — the isolated process still
    exits 0 in that case (a caught, well-formed inference error), reserving
    a non-zero exit / crash classification for genuinely unhandled process
    failures (segfault, OOM kill, etc.)."""
    request, response_path = read_request(sys.argv)
    mode = request.get("mode", "extract")
    try:
        entrypoint = modes[mode]
        result = entrypoint(request)
        write_success(response_path, result)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this is the last line of defense before an unhandled traceback
        traceback.print_exc(file=sys.stderr)
        write_failure(response_path, f"{type(exc).__name__}: {exc}")
