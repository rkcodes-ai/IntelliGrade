# Assessment Domain Guide (Module 04)

The Assessment Domain is IntelliGrade's academic assessment engine — the
foundation that Modules 05/06 (OCR, AI Evaluation, Teacher Review, Reports,
Analytics) will build on. It sits on top of the frozen Module 01–03 layers,
introduces 37 new entities scoped underneath the existing `Institution`
tenant root, and reuses Module 03's tenancy/repository/service/RBAC/audit
infrastructure completely unmodified (see ADR-020 in
[ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md)).

## Scope in one paragraph

Assessment/Exam/Exam Schedule define *when and under what rules* a test
happens. Question Bank (Question, Question Type, Difficulty, Bloom Level,
Tags, Version, Approval, Review) is the reusable content library. Question
Paper (Blueprint, Sections, Ordering, Randomization, Versions) composes
questions from the bank into a specific paper. Answer Key/Rubric (Model
Answer, Alternative Answers, Expected Keywords/Concepts, Rubric Criteria,
Mark Distribution) define how an answer will eventually be graded — by a
human today, and optionally by AI once Module 05/06 lands, without any
schema changes required at that point (see
[AI-preparation](#ai-preparation-placeholders) below).

## Entity list and hierarchy

```
Institution (tenant root, unchanged from Module 03)
├── AssessmentType, AssessmentStatus              (lookups)
├── Assessment                                     (root: subject × type × status)
│   ├── AssessmentConfiguration                    (1:1 — marks/time-limit/attempt rules)
│   ├── EvaluationConfiguration                     (1:1 — manual/auto/hybrid + AI-prep columns)
│   └── Exam                                        (× section)
│       ├── ExamInstructions
│       ├── ExamSchedule                            (room/time, overlap-checked)
│       └── ExamSession                             (× student, unique per exam+student)
│
├── QuestionCategory, QuestionType, DifficultyLevel, BloomTaxonomyLevel, QuestionTag  (lookups)
├── Question                                        (approval workflow: draft→pending_review→approved/rejected→archived)
│   ├── QuestionTagMap                              (× QuestionTag, junction)
│   ├── QuestionVersion                              (append-only snapshot history)
│   ├── QuestionApproval                             (append-only approve/reject decision log)
│   ├── QuestionReview                               (peer feedback, 1–5 rating)
│   └── AnswerKey                                    (1:1)
│       ├── ModelAnswer, AlternativeAnswer, ReferenceNote
│       └── ExpectedKeyword, ExpectedConcept          (also usable off RubricCriterion instead)
│
├── QuestionBlueprint                                (× subject — the "recipe" for a paper)
│   └── QuestionBlueprintSection                     (nullable category/difficulty/bloom/type = "any")
├── QuestionPaperTemplate                            (header/footer/instructions boilerplate)
├── QuestionPaper                                    (approval workflow, same as Question)
│   ├── QuestionPaperVersion                         (append-only snapshot history)
│   ├── QuestionPaperSection
│   │   └── QuestionPaperQuestionMapping             (× Question, order_index, marks_override)
│   └── RandomizationStrategy                        (nullable to paper OR one of its sections)
│
├── Rubric                                           (nullable question_id — reusable templates allowed)
│   └── RubricCriterion                               (self-referential parent_criterion_id for sub-criteria)
│       ├── MarkDistribution                          (scoring bands, e.g. "Excellent" 8–10)
│       └── ExpectedKeyword, ExpectedConcept          (shared tables with AnswerKey, see above)
│
└── EvaluationHistory                                 (append-only, AI-prep — see below)
```

37 tables total. See [database.md](#database) for the exact list and
[database-standards.md](database-standards.md) for column-level
conventions.

## Design decisions worth calling out (see ADR-020 through ADR-025)

- **Consolidation over one-table-per-noun** (ADR-021). The prompt's list
  named Maximum/Passing/Negative/Grace Marks, Time Limit, and Attempt Rules
  as separate concepts — these became **columns on
  `AssessmentConfiguration`**, not six tables. "Question Metadata" became a
  `question_metadata: JSON` column on `Question` (named that, not
  `metadata`, to avoid colliding with SQLAlchemy's reserved
  `Base.metadata` attribute). "Question Ordering" became an `order_index`
  integer column on `QuestionPaperQuestionMapping`. This keeps the schema
  navigable — thirty-seven real tables is already a lot; forty-plus would
  have added ceremony without adding capability.
- **Two shared mixins, both new** (`app/models/assessment_base.py`, ADR-022,
  ADR-023):
  - `VersionCounterMixin` — a cheap `current_version: int` counter
    (default 1), incremented by service-layer code whenever a
    content-changing update happens. This alone satisfies the blanket
    "every entity needs version support" requirement for entities that
    don't need a full history table.
  - `ApprovalWorkflowMixin` — `approval_status` (`draft` → `pending_review`
    → `approved`/`rejected` → `archived`), `approved_by`, `approved_at`,
    `rejection_reason`. Used by exactly two entities with a real editorial
    workflow: **`Question`** and **`QuestionPaper`**. Both additionally get
    a dedicated append-only history table (`QuestionVersion`/
    `QuestionPaperVersion`) — versioning is a separate history table per
    entity, not a temporal/mixin pattern, because "what did this look like
    at version 3" needs the actual snapshot, not just a counter.
- **Restrictive default RBAC for `student`** (ADR-025) — an explicit
  divergence from Module 03's "every role gets read-only by default"
  pattern. Students get read-only on `Assessment`/`Exam`/`ExamSchedule`/
  `ExamInstructions` only — **zero** default access to `Question`/
  `AnswerKey`/`Rubric`/`QuestionPaper`, since a student reading the answer
  key or the exact question bank before an exam is a real security bug,
  not a missing feature. See the [RBAC](#rbac) table below.

## AI-preparation placeholders

Per the explicit "prepare for Module 05/06, do not implement AI" scope
(ADR-024), the following columns/tables exist, are typed, are migrated,
and are read/written by **zero** application code in this module:

| Where | Columns |
|---|---|
| `EvaluationConfiguration` | `confidence_threshold` (Numeric(4,3)), `ai_config` (JSON) |
| `AnswerKey` | `confidence_threshold`, `ai_config` |
| `RubricCriterion` | `ai_notes` (Text — distinct from `teacher_notes`) |
| `EvaluationHistory` (new table) | `exam_session_id`, `answer_key_id`, `evaluator_type` (`human`/`ai`), `score`, `confidence_score`, `embedding_vector` (plain nullable JSON — **not** pgvector; no vector extension is installed anywhere in this stack) |

This is a deliberate "typed placeholder, not a vector store" choice —
adding a real embedding/vector-search capability is Module 05/06's job,
and doing it now would mean guessing at an embedding dimension and
distance metric with no model to validate against.

## Backend architecture

Every entity follows the exact same four-layer shape established in
Module 03 (`endpoints/{entity}.py` → `services/{entity}_service.py` →
`repositories/{entity}_repository.py` → `models/{entity}.py`), building on
the **unmodified** `TenantScopedRepository`/`TenantScopedService` base
classes — zero changes to any Module 03 tenancy file.

### Question workflow endpoints

Beyond standard CRUD, `app/api/v1/endpoints/questions.py` adds:

- `POST /{id}/submit-for-review` — `draft`/`rejected` → `pending_review`.
- `POST /{id}/approve` — `pending_review` → `approved` (writes a
  `QuestionApproval` row internally; `institution_admin`/`super_admin`
  only, per RBAC).
- `POST /{id}/reject` — `pending_review` → `rejected`, with a required
  `reason`.
- `POST /{id}/tags`, `DELETE /{id}/tags/{tag_id}` — `QuestionTagMap`
  management, folded into the Question router rather than given a
  separate CRUD router (matching Module 03's `UserInstitution`
  lightweight-junction precedent).
- `POST /{id}/versions` — snapshots the current state into a new
  `QuestionVersion` row.

`app/api/v1/endpoints/question_papers.py` has the identical shape
(`submit-for-review`/`approve`/`reject`/`versions`) for `QuestionPaper`.

`QuestionApproval`'s router is deliberately **read-only**
(`GET ""`/`GET "/{id}"` only) — rows are written internally by
`QuestionService.approve()`/`reject()`, never accepted from a client-facing
`POST`, since a client-supplied approval record would be a forgeable audit
trail.

### RBAC

148 new `PermissionCode` members (243 total): 35 entity resource prefixes
× create/read/update/delete, plus `evaluation_history`'s create/read-only
pair (append-only, no update/delete), plus 6 workflow-specific actions
(`questions:approve/reject/archive`, `question_papers:approve/reject/archive`).

| Role | Grant shape |
|---|---|
| `super_admin` | Every permission (automatic, unchanged mechanism from Module 02/03). |
| `institution_admin` | Full CRUD + approve/reject/archive on everything. |
| `teacher` | Full CRUD on content-authoring entities (questions, papers, rubrics, answer keys, tags, blueprints) + read-only on exam-scheduling/admin-only entities. **No** approve/reject rights. |
| `student` | Read-only on `Assessment`/`Exam`/`ExamSchedule`/`ExamInstructions` **only** — see [above](#design-decisions-worth-calling-out-see-adr-020-through-adr-025). |

### Audit logging

6 new `AuditAction` entries (31 total): `QUESTION_APPROVED`,
`QUESTION_REJECTED`, `QUESTION_PAPER_GENERATED` (also reused for
question-paper approval), `ANSWER_KEY_UPDATED`, `RUBRIC_UPDATED`,
`EXAM_SCHEDULE_UPDATED`. Plain question/paper create/update reuse the
existing generic `ACADEMIC_ENTITY_CREATED`/`UPDATED` (already
resource-agnostic).

## Database

37 new tables, created by `0006_create_assessment_domain_tables.py`
(generated via Alembic's own `produce_migrations`/`render_python_code`
autogenerate-diff against an in-memory SQLite baseline of the
pre-Module-04 tables — the same technique used for Module 03's `0004`);
permission/grant seed data added by `0007_seed_assessment_permissions.py`
(idempotent against `0003_seed_rbac_baseline.py`, same reasoning as
Module 03's `0005`). Migration chain: `0001` → `0002` → `0003` → `0004` →
`0005` → `0006` → `0007`. See [database-standards.md](database-standards.md)
for the full table list.

Every table: UUID primary key, `institution_id` (denormalized, indexed),
`created_at`/`updated_at`, soft-delete (`deleted_at`), and — where
applicable — `current_version` and/or `approval_status`. Foreign keys
follow Module 03's `ondelete` convention: `CASCADE` for strict
parent-owns-child (e.g. `QuestionPaper` → `QuestionPaperSection`),
`RESTRICT` where silent orphaning would be wrong (e.g. a `Question`'s
`question_type_id`), `SET NULL` for genuinely optional references (e.g.
`RandomizationStrategy.question_paper_section_id`).

### ER diagram (textual summary)

```
Assessment *───1 AssessmentType, AssessmentStatus, Subject (Module 03)
Assessment 1───0..1 AssessmentConfiguration, EvaluationConfiguration
Assessment 1───* Exam *───1 Section (Module 03)
Exam 1───* ExamInstructions, ExamSchedule, ExamSession

Question *───1 Subject, QuestionCategory, QuestionType, DifficultyLevel, BloomTaxonomyLevel
Question *───* QuestionTag (via QuestionTagMap)
Question 1───* QuestionVersion, QuestionApproval, QuestionReview
Question 1───0..1 AnswerKey 1───* ModelAnswer, AlternativeAnswer, ReferenceNote
AnswerKey / RubricCriterion 1───* ExpectedKeyword, ExpectedConcept   (either parent, exactly one required)

QuestionBlueprint 1───* QuestionBlueprintSection
QuestionPaper *───1 Assessment, QuestionBlueprint (0..1), QuestionPaperTemplate (0..1)
QuestionPaper 1───* QuestionPaperVersion, QuestionPaperSection, RandomizationStrategy
QuestionPaperSection 1───* QuestionPaperQuestionMapping *───1 Question

Rubric 0..1───1 Question (nullable — reusable templates)
Rubric 1───* RubricCriterion (self-referential parent_criterion_id) 1───* MarkDistribution

EvaluationHistory *───1 ExamSession, AnswerKey (0..1)
```

## Frontend

Zero new shared infrastructure was needed — every piece of Module 03's
frontend plumbing (`createCrudApi`, `usePaginatedList`, `useCrudMutations`,
`useSelectOptions`, `DataTable`/`FormDialog`/`ConfirmDialog`/
`PaginationControls`/`SearchInput`/`PageHeader`/`FormField`,
`useAppSelector`-based permission checks) was reused unchanged for all 12
new screens (`frontend/src/pages/assessment/*.tsx`):

| Screen | Notes |
|---|---|
| Assessment Dashboard | Root-entity CRUD grid; 3 select dropdowns (subject/type/status). |
| Exam Management | Exam CRUD + a nested "manage instructions" panel (`ExamInstructions`). |
| Exam Schedule | `ExamSchedule` CRUD; `room_id`/`invigilator_user_id` are plain text inputs (no frontend Room API exists yet — see [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md)). |
| Question Bank Dashboard | Search/filter/browse grid over `Question`; navigates to Editor/Viewer (no inline create/edit). |
| Question Editor | Full-page create/edit form, `/dashboard/questions/new` and `/dashboard/questions/:id/edit`. |
| Question Viewer | Read-only detail + approval-status badge + tag management + version-snapshot + workflow actions. |
| Question Review Screen | Per-question peer review comments/ratings, `/dashboard/questions/:id/reviews`. |
| Question Approval Screen | Standalone "pending approvals inbox" (`/dashboard/question-approvals`) + read-only `QuestionApproval` history table. |
| Blueprint Builder | `QuestionBlueprint` → `QuestionBlueprintSection`, one level of nesting, nullable "Any" FK selects. |
| Question Paper Builder | Three-level nesting: `QuestionPaper` → `QuestionPaperSection` → `QuestionPaperQuestionMapping`, plus workflow actions and a `RandomizationStrategy` mini-dialog. |
| Rubric Builder | Three-level nesting: `Rubric` → `RubricCriterion` (self-referential parent select) → `MarkDistribution`. |
| Answer Key Builder | One `AnswerKey` parent + five sibling child sub-panels (Model Answers, Alternative Answers, Reference Notes, Expected Keywords, Expected Concepts). |

Routes are gated with `PermissionGuard` exactly like Module 03 (nested
under `ProtectedRoute` in `routes/index.tsx`, each on that entity's own
`:read`/`:create`/`:update`/`:approve` code), lazy-loaded/code-split the
same way, and the sidebar (`Sidebar.tsx`) filters its new nav entries by
the current user's permissions — `Question Approvals` only appears for a
user holding `questions:approve` (i.e. not `teacher`, matching ADR-025).

`types/assessment.ts` mirrors every backend Pydantic schema field-for-field
(same `Decimal → string` on Read / `number` on Create-Update convention as
`types/academic.ts`), and 36 new `api/*.ts` modules exist — most via the
existing `createCrudApi` factory, five hand-written where the router shape
isn't uniform CRUD (`questions.ts`, `questionPapers.ts`,
`evaluationHistory.ts`, `questionVersions.ts`, `questionApprovals.ts`).

## Testing

Backend: 794 tests, 98.08% coverage. Frontend: 331 tests (49 files),
96.42% coverage. See [TESTING_STATUS.md](../TESTING_STATUS.md) for the
itemized breakdown.

## Related documents

- [question-bank-guide.md](question-bank-guide.md) — Question Bank
  entity-by-entity detail (types, difficulty/Bloom taxonomy, versioning,
  approval workflow).
- [rubric-guide.md](rubric-guide.md) — Rubric Engine detail (criteria,
  sub-criteria, mark distributions, AI-preparation notes).
- [database-standards.md](database-standards.md) — full table list and
  column conventions.
- [api-standards.md](api-standards.md) — REST conventions, including the
  route-registration-order rule every Module 04 router follows.
