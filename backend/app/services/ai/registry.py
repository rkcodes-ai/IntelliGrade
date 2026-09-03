"""
Provider-code -> adapter-class registry. `AIProvider` (the DB lookup
table, seeded by migration) stores the same codes as data — this module
is the code-side half of ADR-041's "global system catalog" design: the DB
row says a provider *exists and is enabled*; this registry says whether
code actually backs it. Mirrors `app.services.ocr.registry` exactly.
"""

from app.services.ai.base import AIProviderAdapter
from app.services.ai.providers.anthropic_provider import AnthropicProvider
from app.services.ai.providers.lexical_heuristic_provider import LexicalHeuristicProvider
from app.services.ai.providers.local_llm_reference_provider import LocalLLMReferenceProvider
from app.services.ai.providers.openai_provider import OpenAIProvider

_REGISTRY: dict[str, type[AIProviderAdapter]] = {
    LexicalHeuristicProvider.provider_code: LexicalHeuristicProvider,
    OpenAIProvider.provider_code: OpenAIProvider,
    AnthropicProvider.provider_code: AnthropicProvider,
    LocalLLMReferenceProvider.provider_code: LocalLLMReferenceProvider,
}


def get_provider_adapter(code: str) -> AIProviderAdapter:
    """Instantiate the adapter for `code`. Raises `KeyError` for an unknown
    code (should never happen if `code` came from a real `AIProvider` row,
    since both are seeded from the same three names)."""
    return _REGISTRY[code]()


def list_registered_codes() -> list[str]:
    return list(_REGISTRY.keys())
