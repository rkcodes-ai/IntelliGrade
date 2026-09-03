# Question Bank Guide (Module 04)

The Question Bank is the reusable content library underneath the
[Assessment Domain](assessment-domain-guide.md) — every `Question` lives
here independently of any specific exam, and is composed into papers via
`QuestionPaperQuestionMapping` (see that guide's ER diagram).

## Classification model

Every `Question` carries:

| Field | Type | Notes |
|---|---|---|
| `subject_id` | FK → Module 03 `Subject` | Required. |
| `unit`, `chapter`, `topic`, `subtopic`, `learning_outcome` | nullable text | Free-text classification within the subject — no separate lookup tables for these; a controlled-vocabulary Unit/Chapter model would need a real curriculum-structure entity, out of scope for this module. |
| `question_category_id` | FK → `QuestionCategory` | e.g. "Theory", "Numerical", "Application". |
| `question_type_id` | FK → `QuestionType` | See [Question Types](#question-types) below. |
| `difficulty_level_id` | FK → `DifficultyLevel` | Has a required `level_order: int` (1 = easiest) — every seeded row must specify it, this is not inferred from insertion order. |
| `bloom_level_id` | FK → `BloomTaxonomyLevel` | Same `level_order` requirement (1 = Remember, ... 6 = Create, in the standard Bloom's taxonomy ordering — the actual names are institution-configurable, not hardcoded). |
| `estimated_time_minutes`, `marks` | nullable int / required Decimal | |
| `language` | text, default `"en"` | |
| `attachments` | nullable JSON array | File references — no upload pipeline is wired up in this module (storage/`uploads` remains a Module 01 placeholder). |
| `diagram_url` | nullable text | Same caveat. |
| `question_metadata` | nullable JSON | Free-form extension point — named `question_metadata`, not `metadata`, to avoid colliding with SQLAlchemy's reserved `Base.metadata` attribute (see ADR-021). |
| `QuestionTag` (via `QuestionTagMap`) | many-to-many | Free-form tagging, orthogonal to category/type/difficulty/Bloom. |

## Question Types

`QuestionType` is a **lookup table**, not a hardcoded enum — the prompt's
requirement that "future types must be extensible" is satisfied by this
being ordinary tenant-scoped CRUD data, not a Python `Literal`/enum that
would need a code change to extend. Seed data for a real institution would
include at minimum: Essay, Short Answer, Long Answer, One Word, MCQ,
True/False, Fill in the Blank, Matching, Programming, Mathematics,
Diagram Based, Case Study — but nothing in the schema or application code
assumes this exact list. `requires_options: bool` flags types where a
separate options/choices UI would apply (MCQ, Matching, True/False) — no
`QuestionOption` table exists yet in this module; wiring one up is a
natural, additive follow-on once a concrete UI need for structured options
(vs. free-text `question_text` describing the options) arises.

## Versioning

`Question` composes `VersionCounterMixin` (a cheap `current_version: int`
counter, bumped by `QuestionService.update()` **only** when
`question_text` or `marks` changes — a cosmetic edit like retagging or
reclassifying difficulty does not bump the version) plus a full,
append-only `QuestionVersion` history table. A snapshot is written
explicitly via `POST /questions/{id}/versions` (not automatically on every
update) — the version-counter bump and the version-snapshot write are
**independent actions**, so a teacher can accumulate several small edits
before deciding to snapshot a checkpoint, rather than getting a noisy
history entry per keystroke-adjacent PATCH.

## Approval workflow

`Question` composes `ApprovalWorkflowMixin`:

```
draft ──submit-for-review──> pending_review ──approve──> approved
  ^                                │
  └──────────────reject────────────┘                    archived (terminal, reachable from approved)
```

- `POST /questions/{id}/submit-for-review` — only from `draft` or
  `rejected`.
- `POST /questions/{id}/approve` — only from `pending_review`; requires
  `questions:approve` (institution_admin/super_admin only — **not**
  teacher, see the parent guide's RBAC table). Writes a `QuestionApproval`
  row (`decision: "approved"`) as a permanent audit trail.
- `POST /questions/{id}/reject` — only from `pending_review`; requires a
  `reason` and `questions:reject`. Writes a `QuestionApproval` row
  (`decision: "rejected"`).
- `QuestionReview` is a separate, lighter-weight concept — peer feedback
  (free-text `comment` + optional 1–5 `rating`) that any reviewer can leave
  at any point in the lifecycle, **not** a workflow gate. It's a
  discussion/feedback trail, distinct from the formal `QuestionApproval`
  decision log.

## Archiving

`approval_status: "archived"` is the soft-retirement state for a question
that should no longer be selected into new papers but must be preserved
for historical papers that already reference it (deleting the row would
break `QuestionPaperQuestionMapping` FKs on past papers). This is separate
from the entity-level soft-delete (`deleted_at`) that every table gets —
archiving is a *content lifecycle* concept, soft-delete is a *data
retention* concept, and they compose independently.

## Search, filter, sort, pagination

`GET /api/v1/questions` uses the same `Page[T]`/`PageParams` contract as
every Module 03/04 list endpoint (`page`, `page_size`, `search`, `sort_by`,
`sort_order` — see [api-standards.md](api-standards.md)). There is
currently **no server-side filter** by category/type/difficulty/Bloom/
approval-status — the frontend's Question Bank Dashboard applies these as
client-side filters over the current page's results (`page_size: 200`),
which is adequate at this module's scale but would need a real
query-parameter-based filter (and probably a dedicated search index) once
question-bank sizes grow past a few thousand rows per institution — noted
in [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).

## Bulk operations and Import/Export

Every Module 04 entity router (including `questions`) has, in the same
documented-skeleton spirit as Module 03:

- `POST /{prefix}/bulk` — **real**, working bulk-create: accepts a list of
  Create payloads, creates what it can, and returns
  `{"created": N, "errors": [{"index", "error", ...}]}` for the rest,
  rather than aborting the whole batch on the first bad row.
- `GET /{prefix}/export`, `POST /{prefix}/import` — documented skeletons
  only (`{"status": "not_implemented", ...}`), matching Module 03's
  existing skeleton for the same two endpoints. No CSV/Excel library has
  been chosen yet.

## Related documents

- [assessment-domain-guide.md](assessment-domain-guide.md) — full domain
  overview, ER diagram, RBAC table, AI-preparation placeholders.
- [rubric-guide.md](rubric-guide.md) — how a `Question`'s `AnswerKey` and
  an optional `Rubric` fit together for eventual grading.
