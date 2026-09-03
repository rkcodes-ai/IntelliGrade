# Rubric Guide (Module 04)

The Rubric Engine and Answer Key are the two halves of "how a `Question`
will eventually be graded" — see the [Assessment Domain
Guide](assessment-domain-guide.md) for how they fit into the wider schema.
Both are designed so a future AI evaluation module (Module 05/06) can read
them without any schema change (see [AI-preparation
placeholders](assessment-domain-guide.md#ai-preparation-placeholders)) —
this module only *prepares* that architecture; no evaluation logic exists
yet.

## Answer Key

`AnswerKey` is **1:1 with `Question`** (unique `question_id`), composing
`VersionCounterMixin` for the same reason `Question` does — a reference
answer can be revised over time.

| Field | Purpose |
|---|---|
| `reference_answer` | Required. The canonical correct answer. |
| `expected_length`, `expected_structure` (JSON) | Optional shape hints — e.g. "should be 3 paragraphs" — for eventual AI grading; unused by any code today. |
| `evaluation_notes` | Free-text guidance for a human evaluator. |
| `confidence_threshold`, `ai_config` (JSON) | AI-preparation placeholders (ADR-024). |

Child collections, each a flat one-to-many off `AnswerKey`:

- **`ModelAnswer`** — one or more fully-worked example answers
  (`content`, `marks_allocated`, `display_order`) — useful when a single
  `reference_answer` string isn't enough (e.g. multiple valid worked
  solutions to a numerical problem).
- **`AlternativeAnswer`** — other acceptable phrasings/values
  (`content`, `is_exact_match` — distinguishes "must match exactly" like a
  numeric answer from "semantically equivalent is fine" like a paraphrase).
- **`ReferenceNote`** — `note_text` + `note_type` (`teacher_note` today;
  `ai_note` is a reserved category for future AI-generated notes — no code
  writes one yet).
- **`ExpectedKeyword`**, **`ExpectedConcept`** — see [Expected Keywords and
  Concepts](#expected-keywords-and-concepts) below; these two tables are
  **shared** with `RubricCriterion`, not answer-key-exclusive.

## Rubric

`Rubric` is a **separate entity from `AnswerKey`**, with a **nullable**
`question_id` (ADR — see the parent guide) — this is deliberate:

- A `Rubric` tied to one `question_id` is a per-question grading rubric.
- A `Rubric` with `question_id: null` is a **reusable template** (e.g. a
  generic "5-paragraph essay" rubric an institution applies across many
  essay questions) — decoupling rubric authorship from any single
  question was an explicit design goal, not an oversight.

`Rubric` composes `VersionCounterMixin` (rubrics get revised as an
institution's grading standards evolve) but **not**
`ApprovalWorkflowMixin` — only `Question` and `QuestionPaper` have a
formal editorial approval workflow; a rubric's correctness is the
authoring teacher's responsibility, reviewed informally the same way any
other content is, not gated behind a publish step. This can be revisited
if a future module needs rubric-specific governance.

### RubricCriterion

One-to-many off `Rubric`, **self-referential** via `parent_criterion_id`
(nullable) to support sub-criteria (e.g. "Argument Quality" as a top-level
criterion with "Thesis clarity" / "Evidence use" as children) — an
arbitrary-depth tree, not a fixed two-level hierarchy, though in practice
most rubrics will use one or two levels.

| Field | Purpose |
|---|---|
| `name` | e.g. "Argument Quality". |
| `weightage_percent` | Nullable — how much this criterion contributes to the rubric's total, if the rubric uses weighted scoring. |
| `max_marks` | Required. |
| `is_mandatory` | Whether this criterion must be scored (vs. an optional bonus criterion). |
| `teacher_notes` | Free-text guidance for a human grader. |
| `ai_notes` | **AI-preparation placeholder** (ADR-024) — a separate field from `teacher_notes` specifically for future AI-evaluator-facing guidance (e.g. "penalize hallucinated citations"), so a rubric author can eventually write AI-specific instructions without overloading the human-facing notes field. Unused by any code today. |
| `display_order` | UI ordering. |

### MarkDistribution

One-to-many off `RubricCriterion` — the scoring bands within that
criterion's mark range, e.g.:

| `band_name` | `min_score` | `max_score` | `description` |
|---|---|---|---|
| Excellent | 8 | 10 | Thesis is precise, well-supported, no logical gaps. |
| Good | 5 | 7.9 | Clear thesis, minor gaps in support. |
| Needs Improvement | 0 | 4.9 | Thesis unclear or unsupported. |

This is the mechanism by which "partial marks" from the original prompt is
satisfied — a grader (human today, AI later) picks the band the answer
falls into rather than needing a fully continuous scoring function.

### Expected Keywords and Concepts

`ExpectedKeyword` (`keyword`, `weight`, `is_mandatory`) and
`ExpectedConcept` (`concept_name`, `description`, `is_mandatory`) both have
**two nullable parent FKs** — `answer_key_id` and `rubric_criterion_id` —
with an *exactly-one-must-be-set* validation enforced at the service
layer (not a DB `CHECK` constraint, to keep the validation error message
consistent with every other business-rule validation in this codebase,
which is a `ValidationAppError` raised from the service, not a raw DB
constraint violation surfacing as a generic 500). This lets the same two
tables serve **either** "keywords/concepts expected somewhere in the
answer text overall" (attached to `AnswerKey`) **or** "keywords/concepts
specific to grading one particular criterion" (attached to
`RubricCriterion`), without duplicating the table definition.

## Scoring rules today vs. later

This module implements the **data model** for scoring rules (mark
distributions, weightage, mandatory flags) but **no scoring engine** —
there is no code anywhere that reads a `Rubric`/`RubricCriterion`/
`MarkDistribution` and computes a score from an actual student answer.
That computation — whether performed by a human teacher via a future
Teacher Review UI or by an AI evaluator via Module 05/06 — is explicitly
out of scope here; this module only guarantees the schema those future
features will read from is already correct and won't need a breaking
migration.

## Related documents

- [assessment-domain-guide.md](assessment-domain-guide.md) — full domain
  overview, ER diagram, AI-preparation placeholders, RBAC table.
- [question-bank-guide.md](question-bank-guide.md) — the `Question`
  entity this rubric/answer-key machinery attaches to.
