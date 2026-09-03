"""
Deterministic Unicode script detection (Step 4.2 milestone, Section 20).

Pure codepoint-range classification — no neural model, no new
dependency (the PyPI `regex` package's `\\p{Script=...}` support was
considered and rejected as unnecessary: plain Unicode block ranges from
the stdlib `unicodedata`-adjacent codepoint tables are sufficient and
exactly as deterministic).

**SCRIPT != LANGUAGE** (Section 20's own explicit warning): Devanagari
covers Hindi/Marathi/Nepali/Sanskrit/Konkani/Maithili/Dogri/Bodo. This
module only narrows candidates; `language_detection.py`'s fastText
adapter plus `language_context_resolver.py` do the actual language
disambiguation. Script detection never fabricates a single-language
answer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

ScriptName = Literal[
    "LATIN",
    "DEVANAGARI",
    "BENGALI",
    "GURMUKHI",
    "GUJARATI",
    "ORIYA",
    "TAMIL",
    "TELUGU",
    "KANNADA",
    "MALAYALAM",
    "SINHALA",
    "ARABIC",
    "MEITEI_MAYEK",
    "OL_CHIKI",
    "COMMON",  # digits, punctuation, whitespace -- script-neutral
    "UNKNOWN",
]

# Real Unicode block ranges (Unicode Standard, Basic Multilingual
# Plane) -- each maps directly to one or more of this milestone's 22
# Scheduled Languages + English via `SCRIPT_TO_CANDIDATE_LANGUAGES`.
_SCRIPT_RANGES: tuple[tuple[int, int, ScriptName], ...] = (
    (0x0041, 0x005A, "LATIN"),
    (0x0061, 0x007A, "LATIN"),
    (0x00C0, 0x024F, "LATIN"),  # Latin-1 Supplement + Extended-A/B
    (0x0600, 0x06FF, "ARABIC"),  # covers Urdu/Kashmiri/Sindhi (Perso-Arabic derived)
    (0x0750, 0x077F, "ARABIC"),  # Arabic Supplement
    (0x08A0, 0x08FF, "ARABIC"),  # Arabic Extended-A
    (0xFB50, 0xFDFF, "ARABIC"),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF, "ARABIC"),  # Arabic Presentation Forms-B
    (0x0900, 0x097F, "DEVANAGARI"),  # Hindi/Marathi/Nepali/Sanskrit/Konkani/Maithili/Dogri/Bodo
    (0x0980, 0x09FF, "BENGALI"),  # Bengali/Assamese
    (0x0A00, 0x0A7F, "GURMUKHI"),  # Punjabi
    (0x0A80, 0x0AFF, "GUJARATI"),
    (0x0B00, 0x0B7F, "ORIYA"),  # Odia
    (0x0B80, 0x0BFF, "TAMIL"),
    (0x0C00, 0x0C7F, "TELUGU"),
    (0x0C80, 0x0CFF, "KANNADA"),
    (0x0D00, 0x0D7F, "MALAYALAM"),
    (0x0D80, 0x0DFF, "SINHALA"),
    (0xABC0, 0xABFF, "MEITEI_MAYEK"),  # Manipuri/Meitei
    (0x1C50, 0x1C7F, "OL_CHIKI"),  # Santali
)

# Script -> Scheduled Languages it's consistent with (never a single
# guaranteed answer -- see module docstring). Order is not meaningful.
SCRIPT_TO_CANDIDATE_LANGUAGES: dict[ScriptName, tuple[str, ...]] = {
    "LATIN": ("English",),
    "DEVANAGARI": (
        "Hindi",
        "Marathi",
        "Nepali",
        "Sanskrit",
        "Konkani",
        "Maithili",
        "Dogri",
        "Bodo",
    ),
    "BENGALI": ("Bengali", "Assamese"),
    "GURMUKHI": ("Punjabi",),
    "GUJARATI": ("Gujarati",),
    "ORIYA": ("Odia",),
    "TAMIL": ("Tamil",),
    "TELUGU": ("Telugu",),
    "KANNADA": ("Kannada",),
    "MALAYALAM": ("Malayalam",),
    "SINHALA": (),  # not a Scheduled Language of India; detected for completeness/non-fabrication
    "ARABIC": ("Urdu", "Kashmiri", "Sindhi"),
    "MEITEI_MAYEK": ("Manipuri/Meitei",),
    "OL_CHIKI": ("Santali",),
    "COMMON": (),
    "UNKNOWN": (),
}


def _classify_codepoint(codepoint: int) -> ScriptName:
    if codepoint < 0x21 or (0x30 <= codepoint <= 0x39) or codepoint in (0x2C, 0x2E, 0x3A, 0x3B):
        return "COMMON"  # whitespace, control, digits, comma/period/colon/semicolon
    for start, end, script in _SCRIPT_RANGES:
        if start <= codepoint <= end:
            return script
    return "UNKNOWN"


@dataclass(frozen=True)
class ScriptDetectionResult:
    primary_script: ScriptName
    script_distribution: dict[ScriptName, float] = field(default_factory=dict)
    candidate_languages: tuple[str, ...] = field(default_factory=tuple)
    is_multi_script: bool = False
    analyzed_character_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_script": self.primary_script,
            "script_distribution": self.script_distribution,
            "candidate_languages": list(self.candidate_languages),
            "is_multi_script": self.is_multi_script,
            "analyzed_character_count": self.analyzed_character_count,
        }


# A script must clear this share of non-COMMON characters to count as
# "present" for multi-script detection -- filters out stray/OCR-noise
# codepoints from being reported as a second script.
_MULTI_SCRIPT_PRESENCE_THRESHOLD = 0.05


def detect_script(text: str) -> ScriptDetectionResult:
    """Real, deterministic, per-codepoint classification — never a
    neural-model guess. Empty/script-neutral-only text returns
    `primary_script="UNKNOWN"` honestly rather than fabricating LATIN as
    a default."""
    if not text:
        return ScriptDetectionResult(primary_script="UNKNOWN", analyzed_character_count=0)

    counts: Counter[ScriptName] = Counter(_classify_codepoint(ord(ch)) for ch in text)
    total = sum(counts.values())
    meaningful = {script: count for script, count in counts.items() if script != "COMMON"}
    meaningful_total = sum(meaningful.values())

    if meaningful_total == 0:
        return ScriptDetectionResult(primary_script="UNKNOWN", analyzed_character_count=total)

    distribution = {script: count / total for script, count in counts.items()}
    primary_script = max(meaningful, key=lambda script: meaningful[script])
    present_scripts = [
        script
        for script, count in meaningful.items()
        if count / meaningful_total >= _MULTI_SCRIPT_PRESENCE_THRESHOLD
    ]
    is_multi_script = len({s for s in present_scripts if s != "UNKNOWN"}) > 1

    return ScriptDetectionResult(
        primary_script=primary_script,
        script_distribution=distribution,
        candidate_languages=SCRIPT_TO_CANDIDATE_LANGUAGES.get(primary_script, ()),
        is_multi_script=is_multi_script,
        analyzed_character_count=total,
    )
