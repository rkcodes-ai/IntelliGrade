"""Security regression tests for the AI Reference Answer Builder's Step
5 extension (Sections 51, 79): official document text is untrusted DATA
passed to a local LLM subprocess -- it must never be interpolated into
a shell command, executed, or allowed to change system behavior.
"""

from __future__ import annotations

import inspect


def test_no_shell_true_in_local_llm_provider() -> None:
    import app.services.ai.providers.local_llm_reference_provider as module

    source = inspect.getsource(module)
    assert "shell=True" not in source


def test_no_eval_or_exec_in_local_llm_provider() -> None:
    import app.services.ai.providers.local_llm_reference_provider as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_no_eval_or_exec_in_grounding_validator() -> None:
    import app.services.ai.grounding_validator as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_no_eval_or_exec_in_evidence_service() -> None:
    import app.services.reference_answer_evidence_service as module

    source = inspect.getsource(module)
    assert "eval(" not in source
    assert "exec(" not in source


def test_isolated_runtime_bridge_reused_not_reinvented() -> None:
    """Confirms the local LLM provider is invoked through the same,
    already-audited `invoke_isolated_runtime` bridge (argv list,
    shell=False, bounded timeout) as every other isolated model in this
    project, not a new, unaudited subprocess mechanism."""
    import app.services.ai.providers.local_llm_reference_provider as module

    source = inspect.getsource(module)
    assert "invoke_isolated_runtime" in source
    assert "shell=True" not in source


def test_json_parsing_never_uses_eval() -> None:
    """The LLM's raw text output is parsed via `json.loads` on a
    regex-extracted substring -- never `eval()`, which would be a
    genuine remote-code-execution risk given the text originates from a
    subprocess whose output could, in principle, be influenced by
    adversarial official-document content."""
    from app.services.ai.providers.local_llm_reference_provider import LocalLLMReferenceProvider

    source = inspect.getsource(LocalLLMReferenceProvider._parse_llm_json)
    assert "json.loads" in source
    assert "eval(" not in source


def test_malformed_json_output_fails_safely_not_via_eval() -> None:
    from app.services.ai.providers.local_llm_reference_provider import LocalLLMReferenceProvider

    provider = LocalLLMReferenceProvider()
    try:
        provider._parse_llm_json("this is not json at all, just prose")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_prompt_template_delimits_evidence_as_untrusted() -> None:
    """Section 52: the prompt must explicitly mark official evidence as
    untrusted data and instruct the model not to follow instructions
    found inside it -- a real, inspectable mitigation, not just a claim."""
    from app.services.ai.providers.local_llm_reference_provider import _PROMPT_TEMPLATE

    lowered = _PROMPT_TEMPLATE.lower()
    assert "untrusted" in lowered
    assert "ignore that content" in lowered or "ignore" in lowered
    assert "begin official exam evidence" in lowered
    assert "end official exam evidence" in lowered


def test_reference_generation_input_is_never_shell_interpolated() -> None:
    """Static guard: nothing in the local LLM provider module builds a
    shell command string from `ReferenceGenerationInput` fields -- the
    provider only ever calls the shared, already-audited
    `invoke_isolated_runtime` bridge, never `subprocess`/`os.system`
    directly."""
    import app.services.ai.providers.local_llm_reference_provider as module

    source = inspect.getsource(module)
    assert "subprocess.run" not in source
    assert "os.system" not in source
