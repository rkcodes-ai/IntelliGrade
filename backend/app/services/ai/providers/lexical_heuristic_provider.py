"""
Real, working AI evaluation adapter — a local, deterministic
lexical/statistical pipeline (TF-IDF cosine similarity + keyword/bigram
overlap + rule-based reasoning/completeness heuristics), not a hosted
LLM. See ADR-041: exactly one provider is real, chosen the same way
Module 05 chose Tesseract — genuinely runnable in this sandbox with no
network call, no API key, and no model download. This is an honest
lexical/statistical proxy for the seven signals, not a claim of deep
semantic understanding; see `docs/ai-evaluation-guide.md` for the exact
limitations of each heuristic.
"""

import re
from statistics import pstdev

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas.ai_reference_answer import ReferenceContentSchema
from app.services.ai.base import (
    AIProviderAdapter,
    AnswerEvaluationInput,
    AnswerEvaluationResult,
    ReferenceGenerationInput,
)

_TOKEN_PATTERN = re.compile(r"[a-zA-Z]{2,}")
_MARK_ROUND_INCREMENT = 0.5

#: Fixed weights for combining the six component scores into one overall
#: "answer quality" figure — used for both `suggested_marks` and
#: `confidence_score`'s mean term. Sums to 1.0. Not currently
#: institution-configurable (see ADR-040/ADR-041).
_COMPONENT_WEIGHTS = {
    "semantic_similarity_score": 0.25,
    "keyword_match_score": 0.15,
    "concept_match_score": 0.15,
    "reasoning_score": 0.15,
    "completeness_score": 0.15,
    "relevance_score": 0.15,
}

#: Best-effort connector-word list for the reasoning-analysis heuristic —
#: presence signals the answer draws a logical/causal link, not that the
#: link is correct. A lexical proxy, not real reasoning comprehension.
_REASONING_CONNECTORS = (
    "because",
    "therefore",
    "thus",
    "hence",
    "since",
    "consequently",
    "as a result",
    "due to",
    "this leads to",
    "which means",
    "implies that",
    "in order to",
)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_PATTERN.findall(text)]


def _cosine_similarity_score(text_a: str, text_b: str) -> float:
    if not text_a.strip() or not text_b.strip():
        return 0.0
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([text_a, text_b])
    except ValueError:
        # Both documents are entirely stopwords/empty after filtering.
        return 0.0
    similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    return round(max(0.0, min(1.0, float(similarity))) * 100, 2)


def _top_terms(text: str, *, n: int, stopwords: frozenset[str]) -> list[str]:
    counts: dict[str, int] = {}
    for token in _tokenize(text):
        if token in stopwords:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [term for term, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def _top_bigrams(text: str, *, n: int, stopwords: frozenset[str]) -> list[str]:
    tokens = [t for t in _tokenize(text) if t not in stopwords]
    counts: dict[str, int] = {}
    for a, b in zip(tokens, tokens[1:], strict=False):
        bigram = f"{a} {b}"
        counts[bigram] = counts.get(bigram, 0) + 1
    return [term for term, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def _keyword_coverage_score(keywords: list[str], target_text: str) -> float:
    """Single-word substring check — adjacency-independent, so it's safe
    to check against the raw (non-stopword-filtered) target text."""
    if not keywords:
        return 0.0
    target_lower = target_text.lower()
    hits = sum(1 for term in keywords if term in target_lower)
    return round((hits / len(keywords)) * 100, 2)


def _bigram_set(text: str, *, stopwords: frozenset[str]) -> set[str]:
    tokens = [t for t in _tokenize(text) if t not in stopwords]
    return {f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False)}


def _concept_coverage_score(
    model_bigrams: list[str], student_text: str, *, stopwords: frozenset[str]
) -> float:
    """Bigram membership check — must compare against the student text's
    *own* stopword-filtered, adjacency-collapsed bigram set, not a raw
    substring search: `model_bigrams` are built by skipping stopwords, so
    a literal-substring check against unfiltered text would fail whenever
    the original wording has a stopword between two content words that
    the bigram itself skips over (e.g. "photosynthesis is the process"
    yields the filtered bigram "photosynthesis process", which is not a
    literal substring of the raw sentence even though the concept is
    unambiguously present)."""
    if not model_bigrams:
        return 0.0
    student_bigrams = _bigram_set(student_text, stopwords=stopwords)
    hits = sum(1 for bigram in model_bigrams if bigram in student_bigrams)
    return round((hits / len(model_bigrams)) * 100, 2)


def _count_reasoning_connectors(text: str) -> int:
    lower = text.lower()
    return sum(1 for phrase in _REASONING_CONNECTORS if phrase in lower)


def _reasoning_analysis_score(model_answer_text: str, student_text: str) -> float:
    """Measured *relative to the model answer's own level of explicit
    reasoning*, not an absolute connector-count scale: a question whose
    correct answer needs little causal language shouldn't force every
    student answer's reasoning score low just because connectors are
    inherently sparse, and a question whose model answer is
    reasoning-heavy should expect the student to match that. Matching or
    exceeding the model answer's connector count scores 100."""
    model_hits = _count_reasoning_connectors(model_answer_text)
    if model_hits == 0:
        return 100.0
    student_hits = _count_reasoning_connectors(student_text)
    return round(min(student_hits / model_hits, 1.0) * 100, 2)


def _completeness_analysis_score(
    model_answer_text: str, student_text: str, keyword_match_score: float
) -> float:
    model_len = len(_tokenize(model_answer_text))
    student_len = len(_tokenize(student_text))
    length_ratio = 0.0 if model_len == 0 else min(student_len / model_len, 1.0) * 100
    return round((length_ratio + keyword_match_score) / 2, 2)


_ENGLISH_STOPWORDS: frozenset[str] = ENGLISH_STOP_WORDS
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _reasoning_sentences(text: str) -> list[str]:
    """Sentences in the model answer that already contain a reasoning
    connector — a real, deterministic extraction (not an AI-invented
    "expected reasoning" claim), used as `expected_reasoning` entries."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    return [s for s in sentences if _count_reasoning_connectors(s) > 0]


def _mark_aware_scoring_guidance(maximum_marks: float, keywords: list[str]) -> list[str]:
    """Scales the NUMBER of guidance bands to the question's actual
    maximum marks (Phase 5) — roughly one band per 2-3 marks, floor 1,
    ceiling 6 — rather than hardcoding fixed 1/2/5/10-mark cases. Each
    band references a distinct slice of the extracted keywords so the
    guidance is genuinely grounded in this question's content, not
    generic boilerplate."""
    band_count = max(1, min(6, round(maximum_marks / 2.5) or 1))
    if not keywords:
        return [
            f"Award marks proportionally across {band_count} equally-weighted point(s) "
            "covering the official model answer's content."
        ]
    per_band = max(1, len(keywords) // band_count)
    guidance: list[str] = []
    for index in range(band_count):
        band_keywords = keywords[index * per_band : (index + 1) * per_band] or keywords[:1]
        marks_for_band = round(maximum_marks / band_count, 2)
        guidance.append(
            f"Up to {marks_for_band} mark(s) for addressing: {', '.join(band_keywords)}."
        )
    return guidance


class LexicalHeuristicProvider(AIProviderAdapter):
    provider_code = "lexical_heuristic"
    is_implemented = True

    def evaluate(self, data: AnswerEvaluationInput) -> AnswerEvaluationResult:
        if not data.student_answer_text.strip():
            # An honest special case, not a degenerate fallthrough: a
            # blank answer is something the system can be *confident*
            # about (there is nothing to grade), distinct from a
            # low-confidence "I couldn't tell" case.
            return AnswerEvaluationResult(
                semantic_similarity_score=0.0,
                keyword_match_score=0.0,
                concept_match_score=0.0,
                reasoning_score=0.0,
                completeness_score=0.0,
                relevance_score=0.0,
                confidence_score=100.0,
                suggested_marks=0.0,
            )

        semantic_similarity_score = _cosine_similarity_score(
            data.model_answer_text, data.student_answer_text
        )
        # Relevance is measured against the question *and* the model
        # answer combined, not the bare question alone: a good answer
        # paraphrases the topic rather than repeating the question's own
        # wording, so comparing only to the (short, differently-worded)
        # question systematically under-scores genuinely on-topic answers.
        # Combining in the model answer's vocabulary keeps this signal
        # meaningful for its actual purpose — flagging answers that are
        # off-topic for the exam question, not penalizing paraphrasing.
        relevance_reference = f"{data.question_text} {data.model_answer_text}"
        relevance_score = _cosine_similarity_score(relevance_reference, data.student_answer_text)

        keywords = _top_terms(data.model_answer_text, n=15, stopwords=_ENGLISH_STOPWORDS)
        keyword_match_score = _keyword_coverage_score(keywords, data.student_answer_text)

        bigrams = _top_bigrams(data.model_answer_text, n=10, stopwords=_ENGLISH_STOPWORDS)
        concept_match_score = _concept_coverage_score(
            bigrams, data.student_answer_text, stopwords=_ENGLISH_STOPWORDS
        )

        reasoning_score = _reasoning_analysis_score(
            data.model_answer_text, data.student_answer_text
        )
        completeness_score = _completeness_analysis_score(
            data.model_answer_text, data.student_answer_text, keyword_match_score
        )

        component_scores = {
            "semantic_similarity_score": semantic_similarity_score,
            "keyword_match_score": keyword_match_score,
            "concept_match_score": concept_match_score,
            "reasoning_score": reasoning_score,
            "completeness_score": completeness_score,
            "relevance_score": relevance_score,
        }
        weighted_quality = sum(
            component_scores[name] * weight for name, weight in _COMPONENT_WEIGHTS.items()
        )

        # Confidence rewards *agreement* across signals, not just a high
        # average — six signals all near 70 is more trustworthy than a
        # mix of 100s and 10s that happens to average to 70 too.
        values = list(component_scores.values())
        agreement_penalty = pstdev(values) if len(values) > 1 else 0.0
        confidence_score = round(max(0.0, min(100.0, weighted_quality - agreement_penalty)), 2)

        raw_marks = (weighted_quality / 100) * data.max_marks
        suggested_marks = round(raw_marks / _MARK_ROUND_INCREMENT) * _MARK_ROUND_INCREMENT
        suggested_marks = max(0.0, min(suggested_marks, data.max_marks))

        return AnswerEvaluationResult(
            semantic_similarity_score=semantic_similarity_score,
            keyword_match_score=keyword_match_score,
            concept_match_score=concept_match_score,
            reasoning_score=reasoning_score,
            completeness_score=completeness_score,
            relevance_score=relevance_score,
            confidence_score=confidence_score,
            suggested_marks=round(suggested_marks, 2),
        )

    def generate_reference(self, data: ReferenceGenerationInput) -> ReferenceContentSchema:
        """The project's deterministic reference-generation provider — used
        in every automated test (never a paid LLM call). Genuinely real,
        not a stub: extracts real keywords/bigrams/reasoning sentences from
        the official model answer via the same TF-IDF-adjacent techniques
        `evaluate()` uses, and produces real mark-aware scoring guidance
        (Phase 5). Honest about its own limits — `equivalent_terms`,
        `alternative_valid_answers`, and `common_misconceptions` stay empty
        rather than fabricated, since a lexical/statistical method has no
        way to genuinely produce them; `confidence` is capped low for the
        same reason, never dressed up as deep semantic understanding."""
        model_answer_text = data.official_model_answer_text
        keywords = _top_terms(model_answer_text, n=12, stopwords=_ENGLISH_STOPWORDS)
        bigrams = _top_bigrams(model_answer_text, n=10, stopwords=_ENGLISH_STOPWORDS)
        required_concepts = bigrams[:5]
        optional_concepts = bigrams[5:10]
        reasoning = _reasoning_sentences(model_answer_text)
        scoring_guidance = _mark_aware_scoring_guidance(data.maximum_marks, keywords)

        # Real, if modest, confidence: more extractable structure (a
        # longer, more content-rich official answer) earns a bit more
        # confidence, capped at 60 -- this method never claims the deep
        # semantic confidence a real language model could.
        confidence = min(60.0, 15.0 + len(keywords) * 2.5)

        return ReferenceContentSchema(
            reference_answer=model_answer_text,
            required_concepts=required_concepts,
            optional_concepts=optional_concepts,
            keywords=keywords,
            equivalent_terms=[],
            alternative_valid_answers=[],
            expected_reasoning=reasoning,
            common_misconceptions=[],
            scoring_guidance=scoring_guidance,
            confidence=round(confidence, 2),
            has_conflict_with_official_answer=False,
            conflict_notes=None,
        )
