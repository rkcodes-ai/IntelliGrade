# Architecture Overview

## Style: Modular Monolith + DDD-flavored layering

IntelliGrade ships as a **single deployable backend** and a **single
deployable frontend**, but internally both are organized as if they were
already split into services. Each future domain (Auth, Institutions,
Answer Scripts, OCR, Evaluation, Analytics, Notifications) will live as a
self-contained module that only talks to other modules through well-defined
interfaces (service classes, events — not direct DB access across domains).

This buys two things:
1. Fast iteration now (one deploy, one DB, one repo).
2. A credible extraction path later — a module that never reached into
   another module's tables can become its own service by moving a folder
   and standing up its own database.

## Backend layering (`backend/app/`)

```
Request
  → API layer          (app/api)          — HTTP concerns only: routing, request/response
      → Service layer   (app/services)      — business logic, transaction boundaries
          → Repository layer (app/repositories) — persistence access, query building
              → Model layer (app/models)         — SQLAlchemy ORM definitions
```

Rules:
- **API layer** never talks to the database directly — it calls a service.
- **Service layer** never builds SQL — it calls one or more repositories.
- **Repository layer** never contains business rules — it's CRUD + queries.
- Cross-cutting concerns (config, logging, security, exceptions, RBAC) live
  in `app/core/` and are imported by any layer.
- `app/schemas/` (Pydantic) defines the wire contract and is deliberately
  separate from `app/models/` (ORM) — the API shape and the storage shape
  are allowed to diverge.

See `backend/app/repositories/base.py` and `backend/app/services/base.py`
for the generic base classes every domain module builds on.

## Frontend layering (`frontend/src/`)

```
pages/        — route-level composition, minimal logic
  ↓ uses
components/   — ui/ (primitives), layout/ (shell), common/ (cross-cutting)
  ↓ uses
hooks/        — data-fetching (TanStack Query) and stateful logic
  ↓ uses
api/          — Axios client + one module per backend resource
store/        — Redux Toolkit for cross-page client state (theme, sidebar, ...)
```

Server state (anything that comes from the API) is owned by **TanStack
Query**, not Redux. Redux is reserved for genuinely client-only, cross-page
state (theme, UI chrome, feature flags). This avoids the classic
"duplicated cache" problem of syncing server data into a global store.

## Infrastructure

| Concern            | Technology                          |
|---------------------|---------------------------------------|
| Relational data       | PostgreSQL (async, via `asyncpg`)       |
| Cache / broker / rate limit storage | Redis                     |
| Background jobs         | Celery (skeleton — no tasks yet)      |
| Object storage             | MinIO (S3-compatible)               |
| API framework                 | FastAPI                          |
| Migrations                       | Alembic                       |

## Request lifecycle (today)

1. Request hits `CORSMiddleware` → `SecurityHeadersMiddleware` →
   `AccessLogMiddleware` → `RequestIDMiddleware` (see `app/main.py` for the
   registration order — Starlette executes middleware in reverse
   registration order).
2. Routed via `app/api/health.py` (unversioned infra probes) or
   `app/api/v1/router.py` (versioned business API — empty until the next
   module).
3. Unhandled errors are caught by handlers in `app/core/exceptions.py` and
   turned into a consistent `{ "error": { code, message, details } }` JSON
   shape.

## Identity & Access Management (Module 02)

Module 02 adds the first real domain module — Authentication, Authorization
(RBAC), Identity, Session, and Audit management — following the layering
rules above exactly:

```
app/api/v1/endpoints/{auth,users,roles,permissions,sessions}.py
  → app/services/{auth,user,rbac,session,token,password,audit}_service.py
      → app/repositories/{user,role,permission,role_permission,user_role,
                           refresh_token,session,audit_log,password_history,
                           password_reset_token}_repository.py
          → app/models/{user,role,permission,role_permission,user_role,
                         refresh_token,session,audit_log,password_history,
                         password_reset_token}.py
```

Cross-cutting authorization lives in `app/core/rbac.py`
(`CurrentUser`, `require_roles`, `require_permissions`) and is consumed by
every protected endpoint via FastAPI's dependency system — see
[authentication-guide.md](authentication-guide.md) and [rbac.md](rbac.md)
for the full design rationale (token rotation, reuse detection, the
commit-before-raise audit pattern, permission resolution).

This module establishes the pattern every future domain module
(Institutions, OCR, Evaluation, ...) should follow: models → repositories →
services → API, with `app/core/rbac.py`'s dependencies reused unchanged for
authorization, not reimplemented per-domain.

## Academic Domain & Multi-Tenancy (Module 03)

Module 03 adds the first multi-tenant business domain — Institution,
Campus, Department, Program, Course, Academic Year, Semester, Section,
Subject, and eleven more entities — on the same layering rules, with
`Institution` as the tenant root:

```
app/api/v1/endpoints/{institutions,campuses,departments,...}.py
  → app/services/{...}_service.py
      → app/repositories/{...}_repository.py
          → app/models/{...}.py
```

Two new shared base classes generalize the tenant-scoping pattern every
entity but `Institution` needs: `TenantScopedRepository`/`TenantScopedService`
(`app/repositories/tenant_repository.py`, `app/services/tenant_service.py`),
extending Module 02's unmodified `BaseRepository`/`BaseService`. Tenant
resolution/authorization is a new dependency, `app/core/tenancy.py`'s
`CurrentInstitutionDep`, built entirely on top of the unmodified
`CurrentUserDep` — per [rbac.md](rbac.md)'s own guidance that per-resource
authorization is "an additional service-layer check," not a change to
`require_permissions`. Full design (multi-tenancy model, entity hierarchy,
validation rules, RBAC grants) in
[academic-domain-guide.md](academic-domain-guide.md).

This is also the first module to introduce a real pagination contract
(`app/schemas/pagination.py`'s `Page[T]`/`PageParams`). A `PermissionCode`
TypeScript mirror was added to `shared/constants/permissions.ts` and a
`@shared/*` path alias was wired up (`tsconfig.app.json`, `vite.config.ts`)
so the frontend could import it — **correction (Module 09 audit,
2026-07-23): no frontend file actually does.** `routes/index.tsx` passes
hardcoded permission-code string literals to every `PermissionGuard`
instead, so the alias/file exist but have zero real consumers — see
`KNOWN_LIMITATIONS.md`'s Module 09 section. This paragraph previously
claimed the wiring was in active use; it wasn't, and the claim is
corrected here rather than left standing.

## Assessment Domain (Module 04)

Module 04 adds the academic assessment engine — Assessment/Exam/Exam
Schedule, Question Bank, Question Paper, Answer Key/Rubric — 37 entities
on the same layering rules, still scoped underneath `Institution`:

```
app/api/v1/endpoints/{assessments,questions,question_papers,rubrics,...}.py
  → app/services/{...}_service.py
      → app/repositories/{...}_repository.py
          → app/models/{...}.py
```

Zero changes to Module 03's `TenantScopedRepository`/`TenantScopedService`,
`app/core/tenancy.py`, or any other tenancy file — this module is
additive-only on top of that infrastructure (ADR-020). Two new shared
mixins in `app/models/assessment_base.py` generalize patterns Module 03
didn't need: `VersionCounterMixin` (a cheap version counter every entity
gets) and `ApprovalWorkflowMixin` (a draft→pending_review→approved/
rejected→archived lifecycle, used only by `Question` and `QuestionPaper`,
the two entities with a real editorial workflow). Full design (entity
hierarchy, RBAC grants, AI-preparation placeholders) in
[assessment-domain-guide.md](assessment-domain-guide.md).

This module also lays groundwork for Module 05/06 (OCR, AI Evaluation)
without implementing either: typed placeholder columns
(`confidence_threshold`, `ai_config`, `ai_notes`) and an append-only
`EvaluationHistory` table exist and are migrated, but are read/written by
zero application code today — see the parent guide's AI-preparation
section for why this is a deliberate "prepare the schema, not the
feature" scope boundary.

## Answer Script OCR Pipeline (Module 05)

Module 05 adds the first Celery background-processing pipeline and the
first real object-storage integration — Answer Script upload, validation,
image preprocessing, OCR extraction, text normalization, and structured
output generation — 11 entities on the same layering rules, still scoped
underneath `Institution` (with one deliberate exception, below):

```
app/api/v1/endpoints/{answer_scripts,ocr_jobs,ocr_results,...}.py
  → app/services/{...}_service.py
      → app/repositories/{...}_repository.py
          → app/models/{...}.py
```

Zero changes to Module 03's `TenantScopedRepository`/`TenantScopedService`
or `app/core/tenancy.py` — this module is additive-only on top of that
infrastructure, same as Module 04 (ADR-026). One new pair of base classes,
`GlobalRepository`/`GlobalService` (`app/repositories/global_repository.py`,
`app/services/global_service.py`), mirrors the tenant-scoped pair minus the
`institution_id` filter — needed because `OCRProvider` (the OCR engine
catalog) is genuinely global system data, not per-tenant content, the
first entity since Module 02's `Role`/`Permission` with that shape.

This module also introduces two genuinely new pieces of cross-cutting
infrastructure that Modules 01–04 only stubbed:

- **Object storage** (`app/db/storage.py`, `app/services/storage_service.py`)
  — MinIO has been provisioned in `docker-compose.yml` since Module 01 but
  had no client or read/write code path until now. See
  [storage-guide.md](storage-guide.md).
- **Background jobs** (`app/tasks/ocr_tasks.py`) — the first real,
  registered Celery task (`celery_app.py`'s `include=[]` predates this
  module). A synchronous Celery task body bridges into the codebase's
  async service layer via `asyncio.run(...)`.

Two new self-contained backend packages hold the pipeline's processing
logic, each independently swappable per their own ADR:
`app/services/ocr/` (a provider-adapter abstraction — one real Tesseract
implementation, five interface-conformant stubs, see ADR-032) and
`app/services/image_processing/` (a 12-step, composable preprocessing
pipeline, see ADR-033). Full design (entity hierarchy, pipeline stages,
RBAC grants, structured-output schema) in
[ocr-pipeline-guide.md](ocr-pipeline-guide.md).

This module explicitly does **not** evaluate, score, or grade any answer
content — it only produces `AnswerScript.structured_content` for a future
Module 06 to consume.

## Official Exam Content Ingestion & AI Evaluation (Module 06)

Module 06's premise is a correction to earlier scope framing: IntelliGrade
does **not** author examinations. The Question Paper, Model Answer, and
Mark Scheme already exist as official PDFs the Exam Cell/Faculty prepared
outside this system; Module 06 begins from those documents. This is an
**additive-only extension** — Modules 01–05 are frozen and unmodified; see
ADR-035 through ADR-041 for the full design record.

```
app/api/v1/endpoints/{official_exam_documents,extracted_questions,answer_evaluations,...}.py
  → app/services/{...}_service.py
      → app/repositories/{...}_repository.py
          → app/models/{...}.py
```

Two entity groups, both new, neither touching any Module 04/05 table:

- **Ingestion**: `OfficialExamDocument` (root, FK'd to `Exam` — not
  `ExamSession`, since a question paper belongs to the exam as a whole,
  not one student's sitting of it), `OfficialExamDocumentPage`,
  `ExtractedQuestion`, `ExtractedModelAnswer`, `MarkSchemeRange`. OCR
  reuses Module 05's engine layer (`image_processing/`, `services/ocr/`,
  `StorageService`) **exactly as implemented**, through a new,
  parallel orchestration task (`app/tasks/official_document_tasks.py`) —
  `app/tasks/ocr_tasks.py` is not modified or imported from (ADR-036).
  Extracted content is never promoted into Module 04's `Question` bank
  as a precondition of evaluation — promotion is optional, nullable-FK,
  outside the evaluation workflow entirely (ADR-037).
- **Evaluation**: `AnswerEvaluation` (new — current evaluation state, 7
  individually-persisted component scores per question, ADR-039) plus
  `AIProvider`/`AIConfiguration` (new — a provider abstraction mirroring
  Module 05's `OCRProvider`/`OCRConfiguration` exactly, ADR-041). Module
  04's `EvaluationHistory` is **retained unmodified** and put to its
  first real use as the append-only log of every AI-evaluation and
  teacher-review action (ADR-038) — the same current-state/history-log
  split as `AnswerScript.status` vs. Module 05's `ProcessingHistory`.

Confidence-tiered review (ADR-040): ≥90% confidence auto-suggests marks,
70–89% requires a one-click teacher confirmation, <70% is a mandatory
full review — `AnswerEvaluation.review_status` encodes where each row
sits in that lifecycle.

## Teacher Review, Result Finalization & Analytics (Module 07)

Module 07 begins where Module 06 ends — after AI evaluation has produced
a `AnswerEvaluation` row per question — and turns those suggestions into
officially finalized, published results. Purely additive: no Module
01–06 table or file is modified; see ADR-042 through ADR-048 for the
full design record.

```
app/api/v1/endpoints/{teacher_review_dashboard,exam_results,analytics,reports,search,notifications}.py
  → app/services/{exam_result,analytics,teacher_review_dashboard,report,search,notification}_service.py
      → app/repositories/{exam_result,report_job,notification_event}_repository.py
          → app/models/{exam_result,report_job,notification_event}.py
```

Three new tables, all institution-scoped:

- **`ExamResult`** (root, FK'd to `ExamSession` — one row per student's
  sitting, unique on `exam_session_id`, created lazily by the first
  finalization action, ADR-042) drives the one validated lifecycle
  Feature 4/5 needs: `draft → under_review → approved → locked →
  published`, plus an explicit `unlock` transition back to `draft`
  gated on its own permission (`exam_results:unlock`, withheld from the
  default teacher grant — an institution_admin/super_admin-only
  backward transition). Once `locked`/`published`,
  `AnswerEvaluationService` refuses further per-question edits for that
  session until unlocked (enforced centrally in
  `_ensure_not_locked()`).
- **`ReportJob`** (background report-generation tracking, ADR-045) —
  same "system-managed job record" shape as Module 05's `OCRJob`/Module
  06's `OfficialExamDocument` orchestration: `POST /reports` persists a
  `pending` row and best-effort-dispatches
  `app/tasks/report_tasks.py`'s Celery task, which resolves the
  requested report type into a generic list of row-dicts (via
  `AnalyticsService`/`TeacherReviewDashboardService`) and renders it with
  `reportlab` (PDF), `openpyxl` (Excel), or the stdlib `csv` module —
  one renderer per format, reused across all 7 report types — then
  stores the file through Module 05's unmodified `StorageService`.
- **`NotificationEvent`** (storage-only framework, ADR-046) — no
  delivery channel exists yet; services just write an event row at the
  point something notification-worthy happens (e.g.
  `ExamResultService.publish()` writes one `result_published` event per
  student). Every notification endpoint self-scopes to
  `current_user.id` as recipient, which is why students get this one
  narrow default grant (`notifications:read`/`:update`) despite ADR-048's
  otherwise-restrictive default.

Two more services add read-only aggregation with no new tables (ADR-044:
computed on demand, deferred caching until a real scale need appears):
`AnalyticsService` (marks stats, pass/fail — via `AssessmentConfiguration.
passing_marks`, confidence distribution, override %, AI-vs-teacher
difference, question-wise performance) and
`TeacherReviewDashboardService` (the 5 dashboard bucket counts plus a
filtered review queue), both joining through the existing Module 03/04
hierarchy (`Exam → Assessment → Subject → Course → Program →
Department`). `SearchService` (Feature 9) is the same shape — read-only
`ILIKE` queries across students (name/`StudentEnrollment.roll_number`),
teachers, subjects, questions, and evaluations, no new index.

Teacher Review itself (Feature 2/3) added exactly two new
`AnswerEvaluationService` actions (`reject()`/`rerun()`, ADR-043) and one
new `review_status` value (`"teacher_rejected"`) — no new table. A plain
re-trigger of an already-reviewed evaluation now returns the existing row
unchanged rather than silently overwriting a teacher's decision; only the
explicit `rerun()` action force-recomputes, always after snapshotting the
pre-rerun state to `EvaluationHistory` first.

## What's intentionally NOT here yet

No email delivery (password-reset tokens are issued and validated;
sending the email is deferred) — Module 07's `NotificationEvent`
framework is the same "lay the groundwork, defer the integration"
pattern, still with no delivery channel. No frontend UI for the
Import/Export skeleton endpoints (backend-only stubs for now). No
scoring engine that actually computes a grade from a `Rubric` directly —
Module 04's rubric/mark-distribution model remains available for
optional per-question context, but is not required by Module 06's
evaluation path. Five of Module 05's six OCR provider adapters remain
interface-conformant stubs (only Tesseract is real) — Module 06's
AI-provider registry follows the identical one-real/rest-stubbed pattern.
No analytics caching/rollup table (Module 07 computes every figure on
demand — ADR-044) and no per-institution override of the 90%/70%
confidence-review thresholds. See the root [README.md](../README.md) for
the module roadmap.
