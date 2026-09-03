# AI Evaluation Guide (Module 06)

Once a teacher has verified a Question Paper's extracted questions, a
Model Answer's extracted answers, and a Mark Scheme's expanded per-
question maximums (see
[official-document-guide.md](official-document-guide.md)), Module 06 can
evaluate a student's OCR'd answer script (Module 05, unmodified) against
that verified reference — never against raw, unverified extraction.

This module explicitly does not replace teacher judgment: every
suggestion is confidence-tiered, and anything below the highest tier
requires a teacher action before it counts as a final mark (ADR-040).

## The 7-signal pipeline (ADR-039)

For one (student answer × extracted question) pair,
`AnswerEvaluationService.evaluate_question()`:

1. Locates the student's answer text for that question by reading
   Module 05's `AnswerScript.structured_content` (read-only — see
   [Reading the student's answer](#reading-the-students-answer) below).
2. Looks up the matching verified `ExtractedModelAnswer` — scoped to the
   *same `Exam`* as the question being evaluated (via
   `ExamSession.exam_id == OfficialExamDocument.exam_id`, the document the
   question's own `ExtractedQuestion.document_id` belongs to), then
   matched by `question_number` within that exam's `document_type=
   "model_answer"` document only. This scoping closed a real correctness
   gap: an earlier version matched `question_number` across the whole
   institution with no exam scoping, which could attach the wrong exam's
   model answer whenever two exams happened to number a question the
   same way. Evaluation still runs without a model answer at all — just
   with a weaker reference — if the exam has none uploaded yet.
3. Resolves the question's maximum marks (`ExtractedQuestion.final_marks`,
   set once a teacher has applied the expanded mark scheme).
4. Calls the configured `AIProviderAdapter.evaluate()`, producing:

| Signal | What it measures |
|---|---|
| `semantic_similarity_score` | Cosine similarity (TF-IDF) between student answer and model answer |
| `keyword_match_score` | Coverage of the model answer's top significant terms in the student answer |
| `concept_match_score` | Coverage of the model answer's top bigrams (a lexical proxy for "concepts") |
| `reasoning_score` | Presence of causal/logical connector language, scaled *relative to how much the model answer itself uses* |
| `completeness_score` | Blend of length-adequacy and keyword coverage |
| `relevance_score` | Similarity to the question + model answer combined (flags off-topic answers) |
| `confidence_score` | Weighted mean of the six signals, penalized by their disagreement (stdev) — rewards *consistency*, not just a high average |

Every score is its own column on `AnswerEvaluation`, never collapsed into
one number — a teacher reviewing a low-confidence suggestion can see
*which* signal disagreed (e.g. high keyword overlap but low relevance
suggests a memorized-but-misapplied answer).

**The uploaded official model answer is always the primary reference** —
every signal is computed against it (or the question, for relevance),
never substituted with a generic "does this sound right" judgment. This
is a direct requirement from the brief, not an implementation detail.

## The real provider: a local, lexical/statistical heuristic

Per ADR-041 (mirroring Module 05's OCR-provider precedent exactly), only
one AI provider is a real, working implementation:
`LexicalHeuristicProvider` — TF-IDF cosine similarity + keyword/bigram
overlap + rule-based connector-word detection, using `scikit-learn`. No
hosted LLM, no API key, no network call — genuinely runnable in this
sandbox, the same reasoning that made Tesseract Module 05's real
provider. `OpenAIProvider`/`AnthropicProvider` are registered,
interface-conformant stubs (raise `AIProviderNotImplementedError`),
ready for a real implementation without touching
`AnswerEvaluationService` or any endpoint.

**This is an honest lexical/statistical proxy for the seven signals, not
a claim of deep semantic understanding.** Concretely:

- Cosine similarity over TF-IDF vectors rewards shared vocabulary, not
  necessarily shared meaning — a well-paraphrased correct answer using
  different words than the model answer will score lower than a correct
  answer that happens to reuse the model answer's phrasing.
- "Concept matching" via bigram overlap is a lexical adjacency proxy, not
  real concept extraction.
- "Reasoning analysis" checks for the *presence* of causal/logical
  connector words/phrases — it cannot verify the reasoning is actually
  correct, only that the answer's language pattern resembles reasoned
  argument.

These limitations are why every score stays individually visible and why
the confidence-tiering (below) exists — the system is designed to route
uncertain cases to a human, not to disguise a heuristic as certainty.

### Calibration notes (bugs found and fixed during this module's build)

Two real miscalibrations were caught via direct testing before this
provider shipped:

- **Concept-match bigram mismatch.** Bigrams were built by skipping
  stopwords, then checked via literal substring search against
  *unfiltered* text — so a bigram like `"photosynthesis process"` (built
  by skipping "is the" between the two words) never matched the original
  sentence, even for a verbatim answer. Fixed by comparing against the
  target text's own stopword-filtered bigram set, not a raw substring
  search.
- **Reasoning score as a permanent confidence-dragging outlier.** An
  absolute connector-count scale meant reasoning almost always read low
  (most answers don't pack four+ causal connectors), which the
  confidence formula's "penalize disagreement" logic then punished
  severely — even a word-for-word-identical answer to the model answer
  scored only ~60% confidence. Fixed by scaling reasoning *relative to
  the model answer's own connector count* — matching or exceeding it
  scores 100, rather than measuring against an arbitrary absolute bar.

After both fixes, a verbatim match scores ~97% confidence and full
marks; a good paraphrase scores medium confidence with partial marks; a
poor or off-topic answer scores low confidence, correctly forcing
mandatory review even when one signal is fooled (see
`tests/test_ai_providers.py` for the exact assertions).

## Reading the student's answer

`app/services/answer_extraction_service.py` (new) reads
`AnswerScript.structured_content` (Module 05, read-only, never modified)
and reconstructs each page's line-broken text from
`blocks[].lines[].text` — deliberately **not** using
`structured_content["pages"][*]["detected_questions"]`'s `char_offset`
values, which index into a `normalized_text` string that Module 05's own
`build_page_structure()` computes but never persists (so post-hoc
slicing against it would be indexing into a string that no longer exists
in that exact form). Instead, this module re-applies
`official_document_extraction_service.extract_answers_from_text()` — the
same, already-tested boundary-detection function used for model answers
— to the student's reconstructed text, reused rather than duplicated.

## Confidence-tiered Teacher Review (ADR-040)

| Confidence | Tier | `review_status` | Behavior |
|---|---|---|---|
| ≥ 90% | `high` | `auto_suggested` | Marks suggested and auto-populated into `final_marks` — still overridable, never locked |
| 70–89% | `medium` | `pending_confirmation` | One-click "Confirm" required before `final_marks` is set |
| < 70% | `low` | `pending_review` | Mandatory full teacher review — `final_marks` stays null until a teacher confirms or overrides |

`POST /answer-evaluations/{id}/confirm` sets `final_marks =
suggested_marks`. `POST /answer-evaluations/{id}/override` accepts a
teacher-chosen `final_marks` (validated `<= max_marks`) and optional
notes. Both write an append-only `EvaluationHistory` row (see below).

## `AnswerEvaluation` vs. `EvaluationHistory` (ADR-038)

Module 04's `EvaluationHistory` is **retained exactly as built, never
modified** — and given its first real use in this module: every AI
evaluation run and every teacher confirm/override writes one new
`EvaluationHistory` row (`evaluator_type="ai"` or `"human"`), giving this
previously-unused, forward-looking table (ADR-024) a genuine audit-trail
purpose. `AnswerEvaluation` (new) holds the **current** state — one row
per (student answer × question), updated in place — since an append-only
table is the wrong shape for "what does this question's mark currently
stand at." Same current-state/history-log split as
`AnswerScript.status` vs. Module 05's `ProcessingHistory`.

## RBAC

6 new permission codes (of Module 06's 26):
`ai_providers` (read/update — update is super_admin-only, a platform
toggle), `ai_configurations` (full CRUD), plus `answer_evaluations`
(read/create/confirm/override) from the ingestion guide's list. Students
get zero default access, same reasoning as the ingestion side.

## Testing

Real (not mocked) evaluation runs via `LexicalHeuristicProvider` —
`tests/test_ai_providers.py` (provider-level calibration assertions) and
`tests/test_answer_evaluations_api.py` (full API-level runs, including a
genuinely low-confidence/off-topic case verified to force
`pending_review`, and an override validated against `max_marks`).

## Related documents

- [official-document-guide.md](official-document-guide.md) — the
  ingestion/verification pipeline this module reads its inputs from.
- [ocr-pipeline-guide.md](ocr-pipeline-guide.md) — the Module 05
  `AnswerScript.structured_content` this module reads (read-only).
