# Database Standards

## Source of truth

The schema lives entirely in **Alembic migrations**
(`backend/alembic/versions/`), generated from SQLAlchemy models in
`backend/app/models/`. Never hand-edit the schema directly against a running
database outside of a migration — environments will drift.

## Module 01 state

`0001_initial_baseline.py` enables the `pgcrypto` PostgreSQL extension and
establishes the migration chain. No business tables.

## Module 02 — IAM tables

`0002_create_iam_tables.py` creates ten tables; `0003_seed_rbac_baseline.py`
is a data-only migration seeding the default roles/permissions/grants.

| Table | Purpose |
|---|---|
| `users` | Identity: email, username, password hash, profile fields, lockout state, soft-delete |
| `roles` | RBAC role definitions (`is_system` flags the four seeded roles as non-deletable) |
| `permissions` | RBAC permission codes |
| `role_permissions` | Role ↔ Permission grants (unique on the pair) |
| `user_roles` | User ↔ Role assignments (unique on the pair) |
| `refresh_tokens` | Hashed refresh tokens, `family_id` for rotation/reuse-detection, `revoked_at` |
| `sessions` | Human-readable session records (device label, IP, last-seen) shown in the Sessions UI |
| `audit_logs` | Append-only security/audit trail (see below) |
| `password_history` | Last N password hashes per user, for reuse prevention |
| `password_reset_token` | Hashed, single-use, time-boxed reset tokens |

`password_history` and `password_reset_token` were **not** in the
originally named eight tables — they were added because the prompt's
required behaviors ("prevent password reuse," "Forgot Password / Reset
Password") are not implementable without persisted state for them. Treat
this as the standard for future modules: a named requirement that implies
storage gets a table, even if it wasn't enumerated by name.

Every IAM table uses `app.models.base.UUIDPrimaryKeyMixin` (portable
`sqlalchemy.Uuid`, not `postgresql.UUID`, so the same DDL runs on SQLite
for tests and PostgreSQL in production/CI — see ADR-008),
`TimestampMixin` (`created_at`/`updated_at`), and — where the prompt
required actor/soft-delete tracking — `AuditActorMixin`
(`created_by`/`updated_by`) and `SoftDeleteMixin` (`deleted_at`) from the
same module.

### Audit log shape

Every `audit_logs` row captures: `user_id` (nullable — failed logins before
identity is confirmed still get logged against the attempted identifier),
`action` (see `app.core.constants.AuditAction` — 18 values covering the
prompt's 9 required categories (login, logout, failed login, password
change/reset, profile update, role change, session revocation) plus extra
granularity: `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`, `TOKEN_REFRESH`,
`TOKEN_REUSE_DETECTED`, `PASSWORD_CHANGE`, `PASSWORD_RESET_REQUEST`,
`PASSWORD_RESET_COMPLETE`, `PROFILE_UPDATE`, `USER_CREATED/UPDATED/
ACTIVATED/DEACTIVATED/DELETED`, `ROLE_ASSIGNED`, `ROLE_REVOKED`,
`SESSION_REVOKED`, `ACCOUNT_LOCKED`), `ip_address`,
`user_agent`, `request_id` (correlates with the structured request logs
from Module 01's `RequestIDMiddleware`), and a `metadata` JSON column for
action-specific detail. Writes go through `AuditService`/
`AuditLogRepository` only — never insert into `audit_logs` directly from an
endpoint.

## Module 03 — Academic Domain tables

`0004_create_academic_domain_tables.py` creates 21 tables (20 academic
entities + `user_institutions`); `0005_seed_academic_permissions.py` seeds
the 80 new `PermissionCode` rows and their default role grants.

| Table | Purpose |
|---|---|
| `institutions` | Tenant root — no `institution_id` of its own |
| `user_institutions` | User ↔ Institution membership (`is_primary`, `is_active`) |
| `campuses` | Physical campuses within an institution |
| `departments` | Academic departments within a campus |
| `programs` | Degrees awarded (e.g. "B.Tech") within a department |
| `courses` | Specializations/branches offered under a program (e.g. "CSE") |
| `academic_years` | Institution-wide academic year cycles |
| `semesters` | Semesters within an academic year |
| `academic_calendar_events` | Holidays/exam windows within an academic year |
| `batches` | Intake cohorts within a course (e.g. "2026–2030") |
| `sections` | Fixed subdivisions of a batch |
| `subject_categories` | Subject groupings (Core/Elective/Lab) |
| `subjects` | Subjects offered per course, per semester number |
| `rooms` | Physical rooms within a campus |
| `subject_allocations` | Subject × Section × Semester × AcademicYear × teacher × Room binding |
| `class_schedules` | Recurring timetable slots for a subject allocation |
| `teacher_assignments` | Teacher ↔ subject-allocation role assignments |
| `student_enrollments` | Student ↔ Batch/Section/Course/AcademicYear/Semester/Status enrollment |
| `academic_statuses` | Student status reference (Active, Graduated, ... `is_terminal` flag) |
| `grading_policies` | Grading scale/passing-criteria reference (institution- or program-scoped) |
| `attendance_policies` | Minimum-attendance reference (institution- or program-scoped) |

Every table (except `institutions`, the tenant root) gets `institution_id`
via a new `InstitutionOwnedMixin` (`app/models/academic_base.py`) —
denormalized directly onto the table, not just derivable by walking a
parent chain, so every tenant-isolation query is a single indexed-column
filter regardless of hierarchy depth (see ADR-016). All 21 tables use the
same `UUIDPrimaryKeyMixin`/`TimestampMixin`/`AuditActorMixin`/
`SoftDeleteMixin` combination as the IAM tables. Full entity hierarchy,
validation rules, and RBAC grants in
[academic-domain-guide.md](academic-domain-guide.md).

`0005_seed_academic_permissions.py` is written defensively (checks
existing rows before inserting) because `0003_seed_rbac_baseline.py` seeds
`for perm in PermissionCode` using the *live* enum — on a database whose
`0003` runs after these Module 03 permission codes were added to the
enum, `0003` alone would already seed them, and a naive `0005` would then
collide on the unique `code` constraint. See that migration's own
docstring for the full reasoning.

## Module 04 — Assessment Domain tables

`0006_create_assessment_domain_tables.py` creates 37 tables (generated the
same way as `0004` — Alembic's own autogenerate-diff engine against an
in-memory SQLite baseline of the pre-Module-04 schema);
`0007_seed_assessment_permissions.py` seeds the 148 new `PermissionCode`
rows and their default role grants, using the identical defensive
already-exists-check pattern as `0005` and for the identical reason.

| Table | Purpose |
|---|---|
| `assessment_types`, `assessment_statuses` | Lookups |
| `assessments` | Root entity: subject × type × status |
| `assessment_configurations` | 1:1 — maximum/passing/negative/grace marks, time limit, attempt rules |
| `evaluation_configurations` | 1:1 — evaluation mode + AI-preparation columns |
| `exams` | × section |
| `exam_instructions`, `exam_schedules`, `exam_sessions` | Per-exam detail |
| `question_categories`, `question_types`, `difficulty_levels`, `bloom_taxonomy_levels`, `question_tags` | Lookups |
| `questions` | Approval-workflow content entity |
| `question_tag_maps` | `Question` ↔ `QuestionTag` junction |
| `question_versions` | Append-only snapshot history |
| `question_approvals` | Append-only approve/reject decision log |
| `question_reviews` | Peer feedback (comment + 1–5 rating) |
| `answer_keys` | 1:1 with `questions` |
| `model_answers`, `alternative_answers`, `reference_notes` | Off `answer_keys` |
| `question_blueprints`, `question_blueprint_sections` | Paper "recipe" |
| `question_paper_templates` | Header/footer/instructions boilerplate |
| `question_papers` | Approval-workflow content entity |
| `question_paper_versions` | Append-only snapshot history |
| `question_paper_sections`, `question_paper_question_mappings` | Paper structure |
| `randomization_strategies` | Nullable to a paper OR one of its sections |
| `rubrics` | Nullable `question_id` — reusable templates allowed |
| `rubric_criteria` | Self-referential `parent_criterion_id` |
| `mark_distributions` | Scoring bands per criterion |
| `expected_keywords`, `expected_concepts` | Shared between `answer_keys` and `rubric_criteria` (exactly-one-parent validated in the service layer) |
| `evaluation_history` | Append-only, AI-preparation only — no code writes to it yet |

Every table follows the same `UUIDPrimaryKeyMixin`/`TimestampMixin`/
`AuditActorMixin`/`SoftDeleteMixin`/`InstitutionOwnedMixin` combination as
Module 03, plus two new shared mixins in `app/models/assessment_base.py`:
`VersionCounterMixin` (a plain `current_version: int` counter) and
`ApprovalWorkflowMixin` (`approval_status`/`approved_by`/`approved_at`/
`rejection_reason`, used only by `questions` and `question_papers`). Full
entity hierarchy, design rationale, and RBAC grants in
[assessment-domain-guide.md](assessment-domain-guide.md).

## Module 05 — Answer Script OCR Pipeline tables

`0008_create_ocr_pipeline_tables.py` creates 11 tables (generated the same
way as `0004`/`0006` — Alembic's own autogenerate-diff engine against an
in-memory SQLite baseline of the pre-Module-05 schema);
`0009_seed_ocr_pipeline_permissions.py` seeds the 20 new `PermissionCode`
rows and their default role grants (same defensive already-exists-check
pattern as `0005`/`0007`), **and** the 6 `OCRProvider` catalog rows
(`tesseract` seeded enabled/implemented/default; the other five disabled).

| Table | Purpose |
|---|---|
| `answer_scripts` | Root entity: one uploaded document (PDF or image) for one `ExamSession` |
| `answer_script_pages` | One row per physical page, written internally during Stage 4 (pipeline-only, no client `POST`) |
| `upload_jobs` | Upload-attempt tracking (chunk/byte counters, status) — written internally during upload, read-only via API |
| `processing_histories` | Append-only per-stage transition log for one `answer_scripts` row |
| `ocr_providers` | Global engine catalog (`tesseract`, `easyocr`, `paddleocr`, `azure_ocr`, `google_vision`, `aws_textract`) — **not** institution-owned, see [ocr-pipeline-guide.md](ocr-pipeline-guide.md#design-decisions-worth-calling-out-see-adr-026-through-adr-034) |
| `ocr_configurations` | Institution-wide default OR per-assessment OCR engine/settings choice, references one `ocr_providers` row |
| `ocr_jobs` | One per OCR run against an `answer_scripts` row — provider used, status, timing |
| `ocr_results` | One per page — raw OCR text, normalized text, average confidence, language, rotation |
| `ocr_blocks` | × detected block within an `ocr_results` row — bounding box, confidence, reading order, `block_type` |
| `ocr_lines` | × detected line within an `ocr_blocks` row |
| `ocr_words` | × detected word within an `ocr_lines` row — the leaf of the OCR hierarchy |

Every table except `ocr_providers` uses the same
`UUIDPrimaryKeyMixin`/`TimestampMixin`/`AuditActorMixin`/
`SoftDeleteMixin`/`InstitutionOwnedMixin` combination as Modules 03/04.
`ocr_providers` uses everything except `InstitutionOwnedMixin` — the new
`GlobalRepository`/`GlobalService` base classes
(`app/repositories/global_repository.py`,
`app/services/global_service.py`) serve it instead of
`TenantScopedRepository`/`TenantScopedService`. `answer_scripts.structured_content`
(Stage 8 output) and `ocr_configurations.preprocessing_steps` are the only
new `JSON` columns this module adds — no `postgresql.JSONB` variant, same
plain-`JSON` convention as every prior module's JSON columns (verified
against `app/models/question.py`'s existing usage before writing these).
Full entity hierarchy, design rationale, and RBAC grants in
[ocr-pipeline-guide.md](ocr-pipeline-guide.md).

## Module 06 — Official Exam Content Ingestion & AI Evaluation tables

`0010_create_module06_tables.py` creates 8 tables (generated the same way
as `0004`/`0006`/`0008` — Alembic's own autogenerate-diff engine against
an in-memory SQLite baseline of the pre-Module-06 schema);
`0011_seed_module06_permissions.py` seeds the 26 new `PermissionCode` rows
and their default role grants (same defensive already-exists-check
pattern as `0005`/`0007`/`0009`), **and** the 3 `AIProvider` catalog rows
(`lexical_heuristic` seeded enabled/implemented/default; `openai`/
`anthropic` disabled).

| Table | Purpose |
|---|---|
| `official_exam_documents` | Root entity: one official PDF (Question Paper/Model Answer/Mark Scheme, via `document_type`) for one `Exam` — exam-level, not session-level (ADR-035) |
| `official_exam_document_pages` | One row per physical page, written internally during ingestion (pipeline-only) |
| `extracted_questions` | Teacher-verifiable questions extracted from a `question_paper`-type document |
| `extracted_model_answers` | Teacher-verifiable answers extracted from a `model_answer`-type document |
| `mark_scheme_ranges` | Teacher-verifiable question-range → marks-per-question rows extracted from a `mark_scheme`-type document (e.g. "Q1-12 = 1 mark") |
| `ai_providers` | Global AI evaluation engine catalog (`lexical_heuristic`, `openai`, `anthropic`) — **not** institution-owned, mirrors `ocr_providers` exactly (ADR-041) |
| `ai_configurations` | Institution-wide default OR per-assessment AI provider choice, references one `ai_providers` row |
| `answer_evaluations` | Current AI-evaluation state for one (student answer × extracted question) pair — 7 individually-persisted component scores, confidence tier, suggested/final marks (ADR-038/ADR-039) |

Every table except `ai_providers` uses the same
`UUIDPrimaryKeyMixin`/`TimestampMixin`/`AuditActorMixin`/
`SoftDeleteMixin`/`InstitutionOwnedMixin` combination as Modules 03/04/05.
`ai_providers` uses everything except `InstitutionOwnedMixin` — the
second entity (after `OCRProvider`) to use the `GlobalRepository`/
`GlobalService` base classes instead of
`TenantScopedRepository`/`TenantScopedService`. `official_exam_documents.raw_ocr_text`
is the only new large-text column this module adds outside standard
question/answer text fields; `ai_configurations.provider_config` is the
only new `JSON` column — plain `JSON`, no `postgresql.JSONB` variant,
same convention as every prior module's JSON columns. Full entity
hierarchy, design rationale, and RBAC grants in
[official-document-guide.md](official-document-guide.md) and
[ai-evaluation-guide.md](ai-evaluation-guide.md).

No column was added to, removed from, or altered on any Module 01–05
table — every new FK in this module's tables points *into* an existing
table (`exams.id`, `answer_scripts.id`, `exam_sessions.id`, `questions.id`,
`answer_keys.id`, `assessments.id`), never the reverse.

## Module 07 — Teacher Review, Result Finalization & Analytics tables

`0012_create_module07_tables.py` creates 3 tables (same autogenerate-diff
technique as every prior module's table migration);
`0013_seed_module07_permissions.py` seeds the 15 new `PermissionCode` rows
and their default role grants (same defensive already-exists-check
pattern as `0005`/`0007`/`0009`/`0011` — listed as an explicit tuple
rather than a resource-prefix filter, since 2 of the 15 codes share the
`answer_evaluations` prefix with 4 codes Module 06 already seeded).

| Table | Purpose |
|---|---|
| `exam_results` | Root entity: one finalization/locking record per `ExamSession`, unique on `exam_session_id`, created lazily by the first finalize action — drives the `draft → under_review → approved → locked → published` state machine (ADR-042) |
| `report_jobs` | One requested report export (`report_type` × `format`), tracked `pending → processing → completed`/`failed`, mutated only by `app/tasks/report_tasks.py` (ADR-045) |
| `notification_events` | One notification event for one recipient user — storage-only, no delivery channel (ADR-046) |

All three use the same `UUIDPrimaryKeyMixin`/`TimestampMixin`/
`InstitutionOwnedMixin` combination as every other institution-scoped
table; `exam_results`/`report_jobs` additionally use `AuditActorMixin` +
`SoftDeleteMixin` (full audit/soft-delete story, same as
`OfficialExamDocument`); `notification_events` uses `SoftDeleteMixin` but
not `AuditActorMixin` (it has no `created_by`/`updated_by` concept — it's
system-written, not user-authored). `report_jobs.parameters` and
`notification_events.payload` are the only new `JSON` columns this
module adds — plain `JSON`, same convention as every prior module.

No column was added to, removed from, or altered on any Module 01–06
table — every new FK in this module's tables points *into* an existing
table (`exam_sessions.id`, `users.id`, `institutions.id`), never the
reverse. Full entity design, RBAC grants, and the report-generation/
analytics-aggregation design are in
[teacher-review-guide.md](teacher-review-guide.md).

## Model conventions (for future modules)

- Every model inherits `app.db.base.Base`.
- Every model gets a UUID primary key via
  `app.models.base.UUIDPrimaryKeyMixin` (not auto-incrementing integers —
  UUIDs avoid cross-service ID collisions if a domain is later extracted
  into its own database).
- Every model gets `created_at`/`updated_at` via
  `app.models.base.TimestampMixin`, managed by the database
  (`server_default=func.now()`), not application code.
- Foreign keys are explicit and indexed. Cross-domain references (e.g. an
  `AnswerScript` referencing a `Student`) should go through a service call
  or a nullable reference id, not a hard SQLAlchemy relationship, if the two
  models are likely to live in different services eventually — use
  judgment, don't over-engineer this for every relationship on day one.

## Migrations

- Autogenerate, then **read the diff** before committing:
  ```bash
  alembic revision --autogenerate -m "add users table"
  ```
- One logical schema change per migration. Don't bundle unrelated table
  changes into one revision.
- Every migration must have a working `downgrade()` — don't ship `pass`
  unless the upgrade itself is genuinely irreversible (and say why in a
  comment if so).
- Migrations run automatically in CI (`test.yml`) against a fresh Postgres
  container before the test suite runs — a broken migration fails the build.

## Naming

- Tables: `snake_case`, plural (`users`, `answer_scripts`).
- Columns: `snake_case`.
- Indexes/constraints: let Alembic's naming convention apply consistently
  (configure `metadata.naming_convention` on `Base` when the first
  multi-table module lands, so constraint names are deterministic across
  environments).

## Connection management

Async SQLAlchemy engine (`asyncpg` driver) with `pool_pre_ping=True`. Pool
size/overflow are configurable via `DATABASE_POOL_SIZE` /
`DATABASE_MAX_OVERFLOW` env vars (see `backend/.env.example`). One session
per request via the `DbSession` FastAPI dependency
(`app/api/deps.py`) — never share a session across requests.
