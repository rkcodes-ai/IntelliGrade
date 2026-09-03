"""
Tests for `app.services.ocr.isolated_runtime` — the generic subprocess
bridge Surya/docTR/TrOCR are built on. Every failure mode is exercised
with a trivial fake "runner" script executed by the *current* interpreter
(no need for any of the three heavy isolated venvs to exist) so these
tests run in the normal fast backend suite, not gated behind optional
ML dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services.ocr.exceptions import (
    OCRIsolatedRuntimeCrashError,
    OCRIsolatedRuntimeMalformedResponseError,
    OCRIsolatedRuntimeMissingError,
    OCRIsolatedRuntimeTimeoutError,
)
from app.services.ocr.isolated_runtime import invoke_isolated_runtime

_PYTHON = Path(sys.executable)


def _write_runner(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_runner.py"
    script.write_text(body, encoding="utf-8")
    return script


def test_missing_python_interpreter_raises_missing_error(tmp_path: Path) -> None:
    runner = _write_runner(tmp_path, "")
    with pytest.raises(OCRIsolatedRuntimeMissingError):
        invoke_isolated_runtime(
            python_exe=tmp_path / "does-not-exist" / "python.exe",
            runner_script=runner,
            request={},
        )


def test_missing_runner_script_raises_missing_error(tmp_path: Path) -> None:
    with pytest.raises(OCRIsolatedRuntimeMissingError):
        invoke_isolated_runtime(
            python_exe=_PYTHON,
            runner_script=tmp_path / "does-not-exist.py",
            request={},
        )


def test_successful_round_trip_returns_parsed_payload(tmp_path: Path) -> None:
    runner = _write_runner(
        tmp_path,
        """
import json, sys
request = json.loads(open(sys.argv[1], encoding="utf-8").read())
open(sys.argv[2], "w", encoding="utf-8").write(
    json.dumps({"success": True, "echo": request.get("value")})
)
""",
    )
    result = invoke_isolated_runtime(
        python_exe=_PYTHON, runner_script=runner, request={"value": "hello"}
    )
    assert result.payload == {"success": True, "echo": "hello"}


def test_nonzero_exit_raises_crash_error(tmp_path: Path) -> None:
    runner = _write_runner(tmp_path, "import sys; sys.exit(1)")
    with pytest.raises(OCRIsolatedRuntimeCrashError):
        invoke_isolated_runtime(python_exe=_PYTHON, runner_script=runner, request={})


def test_no_response_file_raises_malformed_response_error(tmp_path: Path) -> None:
    runner = _write_runner(tmp_path, "pass")  # exits 0, writes nothing
    with pytest.raises(OCRIsolatedRuntimeMalformedResponseError):
        invoke_isolated_runtime(python_exe=_PYTHON, runner_script=runner, request={})


def test_non_json_response_raises_malformed_response_error(tmp_path: Path) -> None:
    runner = _write_runner(
        tmp_path, "import sys; open(sys.argv[2], 'w').write('not json at all')"
    )
    with pytest.raises(OCRIsolatedRuntimeMalformedResponseError):
        invoke_isolated_runtime(python_exe=_PYTHON, runner_script=runner, request={})


def test_timeout_raises_timeout_error(tmp_path: Path) -> None:
    runner = _write_runner(tmp_path, "import time; time.sleep(5)")
    with pytest.raises(OCRIsolatedRuntimeTimeoutError):
        invoke_isolated_runtime(
            python_exe=_PYTHON,
            runner_script=runner,
            request={},
            startup_timeout=0.1,
            inference_timeout=0.1,
        )


def test_stray_stdout_noise_does_not_corrupt_protocol(tmp_path: Path) -> None:
    """A model/library that prints warnings/progress bars to stdout must
    never corrupt the response — only the response *file* is parsed."""
    runner = _write_runner(
        tmp_path,
        """
import json, sys
print("noisy warning that is NOT json")
print("another stray line")
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps({"success": True, "ok": True}))
""",
    )
    result = invoke_isolated_runtime(python_exe=_PYTHON, runner_script=runner, request={})
    assert result.payload == {"success": True, "ok": True}
