"""
Isolated OCR Runtime Bridge (Surya / docTR / TrOCR milestone).

Some OCR engines (Surya, docTR, TrOCR) pull in dependency trees (torch,
transformers, tensorflow-adjacent packages) that conflict with this
project's stable main venv (see each provider module's docstring for the
concrete `pip install --dry-run` evidence). Rather than force those
packages into the main venv — or skip the providers outright — each such
engine gets its own isolated venv (`.venv-surya`, `.venv-doctr`,
`.venv-trocr`, sitting next to the pre-existing `.venv-paddleocr`, same
convention) and is invoked from the main backend process as a subprocess.

Protocol (deliberately file-based, not stdout-JSON): the caller writes a
JSON request to a temp file and passes its path as argv[1], plus a second
temp path as argv[2] for the runner to write its JSON response to. This
sidesteps an entire class of bugs the "print JSON to stdout" approach
invites — a stray `print()` in a model's warm-up code, a tqdm progress
bar, or a warnings.warn() call would all corrupt a stdout-based protocol;
none of them can touch a response file the runner writes explicitly at
the end. The subprocess's real stdout/stderr are still captured, but only
for diagnostics (logged, or included verbatim in the raised exception on
failure) — never parsed as data.

Every failure mode is a distinct, caught exception (see
`app.services.ocr.exceptions`) so a provider adapter built on top of this
bridge can always produce a `status="failed"` ensemble candidate instead
of crashing the whole ensemble run — see `app.services.ocr.ensemble`.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app.services.ocr.exceptions import (
    OCRIsolatedRuntimeCrashError,
    OCRIsolatedRuntimeMalformedResponseError,
    OCRIsolatedRuntimeMissingError,
    OCRIsolatedRuntimeTimeoutError,
)

logger = logging.getLogger(__name__)

# `backend/app/services/ocr/isolated_runtime.py` -> parents[3] == `backend/`.
BACKEND_ROOT = Path(__file__).resolve().parents[3]
RUNNERS_DIR = Path(__file__).resolve().parent / "isolated_runners"


def default_isolated_python(venv_name: str) -> Path:
    """The venv's interpreter, following the pre-existing `.venv-paddleocr`
    convention of a dedicated venv directory living directly under `backend/`."""
    return BACKEND_ROOT / venv_name / "Scripts" / "python.exe"


class IsolatedRuntimeResult:
    """Thin wrapper around the runner's parsed JSON response payload."""

    __slots__ = ("payload",)

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload


def invoke_isolated_runtime(
    *,
    python_exe: Path,
    runner_script: Path,
    request: dict[str, Any],
    startup_timeout: float = 60.0,
    inference_timeout: float = 300.0,
) -> IsolatedRuntimeResult:
    """Run `runner_script` under `python_exe` with `request` as its input,
    and return its parsed JSON response.

    Raises one of the `OCRIsolatedRuntime*` exceptions for every distinct
    failure mode a caller needs to tell apart: missing interpreter/script,
    timeout, non-zero exit (crash), or a response file that is missing or
    not valid JSON.
    """
    if not python_exe.exists():
        raise OCRIsolatedRuntimeMissingError(
            f"Isolated runtime interpreter not found at {python_exe}. "
            "The isolated venv for this provider has not been created on this machine."
        )
    if not runner_script.exists():
        raise OCRIsolatedRuntimeMissingError(
            f"Isolated runner script not found at {runner_script}."
        )

    total_timeout = startup_timeout + inference_timeout

    with tempfile.TemporaryDirectory(prefix="ocr-isolated-") as tmp_dir:
        request_path = Path(tmp_dir) / "request.json"
        response_path = Path(tmp_dir) / "response.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")

        started = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S603 - fixed interpreter/script paths, no shell, no untrusted argv
                [str(python_exe), str(runner_script), str(request_path), str(response_path)],
                capture_output=True,
                text=True,
                timeout=total_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OCRIsolatedRuntimeTimeoutError(
                f"Isolated runtime timed out after {total_timeout:.0f}s "
                f"running {runner_script.name}."
            ) from exc
        elapsed = time.perf_counter() - started

        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "")[-4000:]
            raise OCRIsolatedRuntimeCrashError(
                f"Isolated runtime {runner_script.name} exited with code "
                f"{proc.returncode} after {elapsed:.1f}s. stderr (tail): {stderr_tail}"
            )

        if proc.stderr:
            # Diagnostics only, never parsed — real model/library warnings
            # (tqdm, transformers, etc.) land here and are simply logged.
            logger.debug("isolated runtime %s stderr: %s", runner_script.name, proc.stderr[-4000:])

        if not response_path.exists():
            raise OCRIsolatedRuntimeMalformedResponseError(
                f"Isolated runtime {runner_script.name} exited 0 but wrote no response file."
            )

        raw = response_path.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OCRIsolatedRuntimeMalformedResponseError(
                f"Isolated runtime {runner_script.name} wrote a non-JSON response: {raw[:500]!r}"
            ) from exc

        if not isinstance(payload, dict):
            raise OCRIsolatedRuntimeMalformedResponseError(
                f"Isolated runtime {runner_script.name} response JSON was not an object."
            )

        return IsolatedRuntimeResult(payload)
