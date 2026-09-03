"""
Language-Aware OCR Router (Step 4.2 milestone, Sections 30-31, 26).

Chooses ELIGIBLE providers from `language_capability_registry`; the
EXISTING `app.services.ocr.ensemble.run_ensemble()` still executes
whichever subset comes out — this module never re-implements ensemble
execution, only provider *selection* (Section 31's explicit instruction).

Also implements the bounded, single-retry decision (Section 26): given
a `LanguageContext` resolved AFTER an initial OCR pass, decide whether
the initial provider routing was inappropriate enough to justify one
(and only one) corrected re-run. `RoutingDecision.retry_recommended`
is a plain bool a caller checks once — there is no loop, no recursive
call, nothing in this module can retry more than once by construction
(the caller decides to re-invoke `route_providers` a second time or
not; this module has no memory of "how many times have I already
retried").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.document_intelligence.script_detection import ScriptName
from app.services.ocr.language_capability_registry import providers_supporting_script

# Below this confidence, a language-driven OCR retry is not worth the
# extra compute (Section 27: weak predictions must not trigger expensive
# retries) -- the current, possibly-Latin-only routing is kept.
_RETRY_CONFIDENCE_THRESHOLD = 0.75


@dataclass(frozen=True)
class RoutingDecision:
    selected_providers: list[str]
    skipped_providers: list[str]
    skip_reasons: dict[str, str] = field(default_factory=dict)
    script_hint: ScriptName | None = None
    language_hint: str | None = None
    provenance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_providers": self.selected_providers,
            "skipped_providers": self.skipped_providers,
            "skip_reasons": self.skip_reasons,
            "script_hint": self.script_hint,
            "language_hint": self.language_hint,
            "provenance": self.provenance,
        }


def route_providers(
    *,
    available_provider_codes: list[str],
    script: ScriptName | None,
) -> RoutingDecision:
    """Section 30: input is the page's script hint + the set of
    providers this institution/job has enabled; output is which of
    those are eligible to run. When `script` is `None`/`"UNKNOWN"`
    (Section 23 pre-OCR stage, nothing detected yet), every configured
    provider is kept eligible — this is the exact pre-Step-4.2 behavior,
    preserving English/unrouted jobs unchanged (Section 11)."""
    if script is None or script == "UNKNOWN":
        return RoutingDecision(
            selected_providers=list(available_provider_codes),
            skipped_providers=[],
            script_hint=script,
            provenance="no_script_evidence_yet_all_providers_eligible",
        )

    eligible = set(providers_supporting_script(script))
    selected = [code for code in available_provider_codes if code in eligible]
    skipped = [code for code in available_provider_codes if code not in eligible]

    if not selected:
        # Section 31: "1 compatible -> one provider + reduced coverage
        # status" -- but if genuinely ZERO configured providers support
        # this script, degrade to running everything rather than
        # producing no OCR at all (a wrong-script guess must never mean
        # "skip OCR entirely").
        return RoutingDecision(
            selected_providers=list(available_provider_codes),
            skipped_providers=[],
            skip_reasons=dict.fromkeys(
                available_provider_codes,
                f"no registered provider supports script={script}; "
                "falling back to all configured providers rather than skipping OCR",
            ),
            script_hint=script,
            provenance="zero_eligible_providers_fallback_to_all",
        )

    return RoutingDecision(
        selected_providers=selected,
        skipped_providers=skipped,
        skip_reasons=dict.fromkeys(skipped, f"does not support script={script}"),
        script_hint=script,
        provenance="script_capability_filtered",
    )


def should_retry_with_corrected_routing(
    *,
    initial_script_hint: ScriptName | None,
    detected_script: ScriptName,
    detected_language_confidence: float,
) -> bool:
    """Section 26: exactly one controlled retry, only when post-OCR
    evidence is BOTH high-confidence AND genuinely contradicts the
    initial routing (a different script than what was assumed/available
    at OCR time). The caller is responsible for actually enforcing "at
    most once" (this function has no state); it exists purely as the
    single, centralized, testable decision point rather than scattering
    this condition across `ocr_tasks.py`."""
    if detected_language_confidence < _RETRY_CONFIDENCE_THRESHOLD:
        return False
    if initial_script_hint is None or initial_script_hint == "UNKNOWN":
        return False
    return detected_script != initial_script_hint
