# Known Limitations

Deliberate gaps, deferred work, and environment constraints. Distinct from
bugs — everything listed here is either an intentional scope boundary or a
constraint of the environment this audit ran in, not a defect left unfixed.

## Module 10 — Deployment & Validation findings (2026-07-23)

Real deployment/validation against a live, running instance of the
application (not just re-reading code or re-running the existing test
suite). Two categories of finding: environment constraints re-confirmed
with more precision than before, and one genuine, previously-undetected
runtime defect — found and fixed.

### Environment (re-confirmed, more precisely diagnosed than before)

- **Docker CLI/daemon: still completely absent.** Unchanged since Module 01.
- **PostgreSQL: precisely diagnosed as unrecoverable in this sandbox, not
  just "unreachable."** A Windows service (`postgresql-x64-17`) is
  registered and a real, previously-initialized data directory exists at
  `C:\Program Files\PostgreSQL\17\data` — but the actual install is
  **corrupted**: `C:\Program Files\PostgreSQL\17\` has no `bin\` at all,
  and the separate `C:\PostgreSQL\17\bin\` the service's own registry
  `ImagePath` points at has only `pg_ctl.exe`/`postgres.exe` — no `lib\`,
  `share\`, or `initdb.exe`. Directly confirmed via `postgres.exe`'s own
  error: `FATAL: could not open directory "C:/PostgreSQL/17/lib"`. There
  is no `initdb` anywhere on this machine to rebuild a fresh data
  directory either. This is new, precise information — prior modules
  described this only as "no Postgres reachable" without diagnosing why.
- **MinIO: no standalone binary exists** (`minio.exe`/`mc.exe` not found
  anywhere) — object-storage-dependent validation continues to use the
  application's own fake in-memory storage bucket, as in every prior
  module.
- **Redis: running, but confirmed still the wrong version for real
  Celery dispatch.** `redis-cli ping` → `PONG`, but `redis-server
  --version` reports `3.0.504` (the same old, unofficial Windows port
  documented since Module 05) — directly tested: `redis-py` fails with
  `unknown command 'HELLO'`, and a real `celery -A app.tasks.celery_app
  worker` process starts, correctly registers all 3 real tasks, but
  cannot connect to the broker for the identical reason. Unchanged from
  every prior module's documented constraint — this pass just verified it
  directly again rather than assuming it still held.

### Fixed: global rate limiting was silently non-functional

**Found via live UAT-style load testing, not code review** — hammering a
running instance of the app with 100+ rapid requests to an undecorated
route and observing zero `429` responses, contradicting Module 08's and
Module 09's own (at-the-time-correct) verification that
`SlowAPIMiddleware` enforced `RATE_LIMIT_DEFAULT` globally.

**Root cause**: `slowapi==0.1.10`'s `SlowAPIMiddleware` finds the
matching route by walking `app.routes` and calling `.matches(scope)` on
each (`_find_route_handler`). The installed `fastapi==0.139.0` (resolved
via this project's unpinned `fastapi>=0.115.0` constraint — dependency
drift between sessions, not a deliberate upgrade) wraps every
`include_router()`'d route in an internal `_IncludedRouter` optimization
object that this lookup can't see through, so it always returns
`handler=None`. `slowapi` treats "no handler found" as "exempt," so every
route without its own explicit `@limiter.limit(...)`/`@limiter.exempt`
decorator — i.e. everywhere except the auth endpoints and health
probes — silently stopped being protected by the global default. Directly
confirmed: `_find_route_handler` returns `None` for `/api/v1/institutions`
on this FastAPI version; `Limiter._check_request_limit` correctly
enforces the limit when given any real, stable callable, proving the
`Limiter` itself was never broken — only `SlowAPIMiddleware`'s
FastAPI-version-specific route lookup was.

**Fix**: replaced `SlowAPIMiddleware` with a new, small
`DefaultRateLimitMiddleware` (`app/middleware/rate_limit.py`) that calls
`Limiter._check_request_limit` directly with a fixed, stable marker
function instead of trying to resolve the real route handler — sidesteps
the FastAPI incompatibility entirely rather than depending on a fix or
version-pin timeline outside this project's control. This makes
`RATE_LIMIT_DEFAULT` a genuine global-per-client cap across the whole API
surface combined (not per-route) — a stricter, not weaker, reading of
"enforced globally" than the original per-route-keyed design would have
given anyway. Verified live, twice: once in-process via ASGI transport,
once against the actual running uvicorn server — both show exactly 100
requests through then `429` for the rest; `/health/live` confirmed to
remain exempt across 100+ requests. A permanent regression test
(`test_default_rate_limit_applies_to_undecorated_routes`,
`tests/test_security_hardening.py`) now exercises this directly — no
prior test in the suite ever hit a single route anywhere near
`RATE_LIMIT_DEFAULT` (100) times, which is exactly why this went
undetected until this pass's live load testing.

**Residual recommendation, not fixed here** (would be a broader change
than this defect requires): `backend/pyproject.toml`'s `fastapi>=0.115.0`
constraint has no upper bound, which is what let this drift happen in the
first place. A future module should consider pinning a tested range
(e.g. `fastapi>=0.115.0,<0.140.0`) — not done here since the middleware
fix already resolves the actual defect independent of which FastAPI
version is installed, and a version pin is a separate, broader dependency
-management decision than "fix the one broken thing."

## Module 09 — Release Certification Audit findings (2026-07-23)

A full 6-pass audit (Architecture, Database, API, Frontend, Security,
Performance/Code Quality) was run against the entire codebase ahead of
v1.0 certification. Two genuine, release-blocking bugs were found and
fixed (see `CHANGELOG.md`'s `[0.9.0]` entry); everything below is
real, verified audit findings that were deliberately **not** fixed —
either because they're below the "critical bug" bar this module's mandate
sets, or because fixing them would mean redesigning architecture or
touching frozen business logic, both explicitly out of scope for this
module. Each is a genuine backlog item for a future module, not a hidden
defect.

### Architecture

- **`GET /permissions` bypasses the service layer** — the endpoint calls
  `PermissionRepository` directly with no `PermissionService` in between
  (`backend/app/api/v1/endpoints/permissions.py`), the only such instance
  found across all 82 endpoint files. Functionally correct, just an
  isolated convention deviation.
- **`exam_result_service.py` and `answer_evaluation_service.py` build raw
  SQL against `self.session` instead of going through their repositories**,
  despite both having one. This is the dominant query-access pattern in
  exactly the two services carrying the most business-critical logic
  (result locking/publishing, AI-evaluation scoring). Not a functional
  defect — both work correctly and are fully tested — but it means
  `exam_result_repository.py`/`answer_evaluation_repository.py` are
  effectively vestigial. A real refactor candidate for a future module;
  not attempted here since it would mean restructuring core business
  logic, which this module's mandate explicitly forbids ("do NOT redesign
  architecture").
- **`shared/constants/permissions.ts` has zero real frontend consumers.**
  The `@shared/*` alias is correctly wired (`vite.config.ts`,
  `tsconfig.app.json`), and the constants file exists, but
  `frontend/src/routes/index.tsx` passes hardcoded permission-code string
  literals to every `PermissionGuard` instead of importing from it —
  reintroducing the exact duplication-risk `shared/` was built to
  prevent (the permission string exists, hand-typed, in two unlinked
  places: the backend `PermissionCode` enum and ~36 frontend route
  literals). `docs/architecture.md` should be corrected to not claim this
  is wired up, or a future module should actually wire it.

### Database

- **Two required catalog FKs are missing an index**:
  `AnswerEvaluation.ai_provider_id` and `OCRJob.ocr_provider_id` (their
  sibling `AIConfiguration.ai_provider_id`/`OCRConfiguration.ocr_provider_id`
  columns *are* indexed — this is an inconsistency, not a deliberate
  omission). `OCRJob.status` and `ReportJob.requested_by` are similarly
  unindexed despite being natural query filters (their sibling
  `ReportJob.status` is indexed). Not fixed here — adding an index is a
  schema migration, and this module's mandate is explicit: "do NOT change
  database schema unless a critical production bug is discovered." These
  are real but Medium-severity (will matter at scale, not today) —
  recommended as the first schema migration of whatever module follows.
- **Three semantically-parallel "history" tables have inconsistent
  pluralization**: `password_history`/`evaluation_history` (singular) vs.
  `processing_histories` (plural) — cosmetic, not fixed (schema-touching).
- **`Base.metadata.naming_convention` was never configured**, despite
  `docs/database-standards.md` flagging it as a "do this when the first
  multi-table module lands" item back in Module 02/03. Risk is mitigated
  today (every `UniqueConstraint` has an explicit `name=`, Postgres's
  default FK-naming is deterministic) but the documented intention was
  never followed through.
- **No DB-level `CheckConstraint`s exist anywhere** — status/lifecycle
  columns are validated only at the Pydantic/service layer, by explicit,
  documented design (`assessment_base.py`'s own docstring: "so new
  statuses never require a migration"). A deliberate trade-off, not an
  oversight, but it does mean a raw SQL statement bypassing the service
  layer could write an invalid status value with no DB-level guardrail.

### API

- **`GET /notifications` has no pagination** — the one genuinely unbounded
  list-endpoint response body in the entire 494-path-template API surface.
  Every other Module 07 list endpoint correctly uses `Page[T]`. Not fixed
  here (would require a `PageParams`/`Page[NotificationEventRead]`
  signature change plus a matching frontend update) — recommended as a
  small, contained fix for the next module.
- **`assign_role`/`revoke_role` status-code drift** (`users.py`) —
  `assign_role` returns 200 instead of 201 (inconsistent with the
  analogous `POST /institutions/{id}/members`); `revoke_role` returns 200
  with a body instead of 204, unlike every other revoke/delete in the API.
  Cosmetic, low-risk, not fixed (would be a breaking response-shape
  change for any existing caller).
- **`docs/api-standards.md` documents `POST /auth/logout` as requiring a
  Bearer token**; the actual implementation identifies the session from
  the refresh cookie alone and no-ops if absent. Functionally reasonable,
  doc/code mismatch not yet reconciled.
- Several endpoints return a bare `dict[str, str]` instead of a typed
  `response_model` (`download_answer_script`, `download_report`,
  `get_unread_notification_count`) — minor OpenAPI-schema polish, not a
  functional gap.

### Frontend

- **~50 of ~54 data-entry forms have no client-side validation.**
  `FormDialog` sets `noValidate` on its `<form>` (disabling native HTML5
  validation), and only the 4 auth-related pages (Login, Forgot/Reset
  Password, Profile) use the React Hook Form + Zod stack the app
  otherwise standardizes on. Every CRUD page (Academic/Assessment/OCR/
  Module 06/07) relies entirely on the backend's 422 response surfaced as
  a generic toast, with no inline per-field error. This is a real, if
  non-critical, UX/consistency gap — not fixed here (correcting all ~50
  forms is a substantial, multi-page undertaking well beyond a "fix only
  critical issues" mandate) but flagged as the top frontend priority for
  a future module. Two concrete, confirmed consequences of this gap:
  - `ProfilePage.tsx`'s change-password form only checks `min(8)`, missing
    the upper/lower/digit/special-character checks `ResetPasswordPage.tsx`
    correctly mirrors from the backend policy — an in-app inconsistency,
    not just a frontend/backend one.
  - The Institution form's `code` field has no client-side length/pattern
    check matching the backend's `^[A-Z0-9_-]+$` constraint.
- **`DashboardHomePage` (the post-login landing page) is a literal
  placeholder** ("Nothing to show yet") despite 50+ fully-built feature
  screens existing elsewhere in the app. A product/UX decision for a
  future module, not a defect.
- **`RoleGuard.tsx` is fully implemented but never used** in the actual
  route tree (only `PermissionGuard` is) — referenced only from its own
  test file. Dead code; either remove it or find its intended use case.
- Only 11 of 57 page files use any responsive Tailwind breakpoint class;
  several multi-column form grids (`QuestionEditorPage`, `ProfilePage`)
  have no mobile/`sm:` fallback and will feel cramped on narrow viewports.
- No shared `Badge`/status-pill component exists — at least 10 pages
  independently reimplement one with duplicated Tailwind classes. A
  low-risk cleanup candidate.
- Frontend production build now emits one Rollup "chunk larger than
  500 kB" warning (`index-*.js`, 554 kB / 170 kB gzipped) — a real
  bundle-size observation, not an error; code-splitting is a reasonable
  future optimization, not required for v1.0.

### Security

- **`npm audit` reports 7 real CVEs (2 critical, 2 high, 3 moderate)** in
  frontend **devDependencies** — the `vite`/`vitest`/`esbuild`/`fast-uri`
  toolchain. None are shipped in the production frontend bundle (dev/test
  tooling only); `pip-audit` reports zero backend vulnerabilities.
  `.github/workflows/security.yml`'s `npm audit` job is
  `continue-on-error: true`, so these do not currently block CI. Genuine,
  currently-unremediated gap — real remediation requires a `vite`/`vitest`
  major-version bump, which risks destabilizing the test toolchain and was
  judged too risky to force through under this module's "fix only
  critical issues" mandate (the underlying CVEs have no production-bundle
  impact). Recommended as the first dependency-upgrade task for whoever
  owns the next module.
- **File-upload content-type validation trusts the client-supplied
  `Content-Type` header rather than sniffing actual file bytes**
  (`AnswerScriptService.validate_candidate`, also used by
  `OfficialExamDocumentService`). `SECURITY_CHECKLIST.md` previously
  marked this "Not yet applicable (Module 03+ scope)" — that note was
  **stale** (Module 05/06 shipped real upload endpoints since) and has
  been corrected. Size validation is real and enforced; content-type
  sniffing (e.g. via `python-magic`) is not. Not fixed here — adding a new
  dependency and touching Module 05/06's upload validation path is exactly
  the kind of change this module's mandate reserves for "critical
  production bug" status, and no exploit was demonstrated, only a
  defense-in-depth gap.

### Performance

- **N+1 query** in `AnalyticsService.get_question_wise()` — loops issuing
  one `session.get()` per unique question instead of a single
  `WHERE id IN (...)` fetch.
- **`UPLOAD_MAX_PAGE_COUNT` (config value, default 60) is defined but
  never enforced anywhere in the codebase.** `extract_pages_as_images()`
  rasterizes every page of an uploaded PDF into a 300 DPI in-memory array
  before OCR begins, bounded only by `UPLOAD_MAX_FILE_SIZE_BYTES` (50 MB)
  — a highly-compressible many-page PDF could stay under the size limit
  while producing a large number of full-resolution rasters in memory.
  Real gap between documented intent and actual enforcement; not fixed
  here (adding the check touches Module 05's upload validation path) but
  flagged as a real resource-exhaustion hardening item.
- **Celery task retries are not idempotent.** If `ocr_tasks.py`'s or
  `official_document_tasks.py`'s pipeline fails partway through and
  Celery retries, the retried run re-inserts child rows (pages, extracted
  questions) from the top rather than resuming or upserting — a retry
  after partial failure can produce duplicate rows. Not fixed here
  (needs a real idempotency-guard design across two task pipelines,
  which is a Module 05/06 business-logic change) but worth a dedicated
  fix before real production retry traffic is expected.
- **Bulk exam-result transitions run synchronously and serially** —
  `bulk_transition()` loops over every session in an exam with a DB round
  trip per item, all inside the request path (no Celery offload). Fine at
  small institution scale; a real latency/timeout risk for large cohorts.
- 5 sequential `COUNT` queries in `TeacherReviewDashboardService`'s
  summary could collapse into one aggregate query — a minor efficiency
  win, not a correctness issue.

### Code Quality

- 4 small dead-code items confirmed unreferenced anywhere:
  `RateLimitExceededError` (superseded by `slowapi`'s own exception
  class), `UserPublic`, `ErrorResponse` (both unused Pydantic schemas),
  `InstitutionType` (unused enum — `Institution.institution_type` is a
  plain string column).
- `AnswerEvaluationService.evaluate_question()` is a ~150-line method — a
  reasonable candidate for extraction, not urgent.
- 4 frontend page components exceed 500 lines (`AnswerKeyBuilderPage.tsx`
  1157, `QuestionPaperBuilderPage.tsx` 973, `RubricBuilderPage.tsx` 739,
  `BlueprintBuilderPage.tsx` 547) — genuinely complex multi-step builder
  UIs, not markup bloat, but real maintainability risk at that size.

### Testing

- The 1 pre-existing frontend `tsc` failure and its accompanying build
  breakage documented in Module 08's entry below is **now fixed** (see
  `CHANGELOG.md`'s `[0.9.0]` entry) — left in place below for history,
  since it was genuinely true as of Module 08's certification.
- The 110-file Prettier formatting drift documented in Module 08's entry
  below remains **unfixed** — still out of scope for the same reason
  (mass-reformatting 110 files across Modules 03–07 is exactly the kind
  of scope creep a "no new business features, no architecture redesign"
  mandate exists to prevent). Recommended as a dedicated, diff-only
  formatting pass in a future module.

## Deliberate scope boundaries (by design, not oversight)

- **No Answer Scripts, OCR, or AI evaluation logic as of Module 03.**
  Module 03 (Academic Domain) added `institutions` and 20 related academic
  tables on top of Module 02's IAM tables — see
  [docs/academic-domain-guide.md](docs/academic-domain-guide.md). Their
  top-level directories (`ocr/`, `ai/`, `evaluation/`) still exist as
  documented placeholders only — real OCR/AI code lives under
  `backend/app/services/` instead (Modules 05/06). `analytics/` and
  `notification/` are likewise still empty top-level placeholders, but
  Module 07 now delivers real analytics (`AnalyticsService`) and a real
  (storage-only) notification framework (`NotificationEvent`) under
  `backend/app/services/`/`backend/app/models/` — see
  [docs/teacher-review-guide.md](docs/teacher-review-guide.md). A future
  module may still choose to populate the top-level placeholder
  directories themselves if a concrete need for that separation emerges.
- **No email delivery.** Password-reset token issuance and validation are
  fully implemented and tested; actually emailing the token to the user is
  deferred — no SMTP/SES/etc. provider is wired in.
- **Rate limiting's global default is still configured-not-enforced**
  (ADR-005 stands for non-auth routes), but auth endpoints now have
  explicit, enforced per-route limits (`10/minute` login, `5/minute`
  forgot-password) — see [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md).
- **`shared/` now holds one real, actively-imported file**
  (`constants/permissions.ts`, consumed by the frontend via a new
  `@shared/*` path alias — see ADR-004's update in Module 03) but is still
  not a published/versioned npm package; `constants/roles.ts` remains an
  unconsumed reference file for now.
- **No dedicated frontend screen for 7 supporting academic entities**
  (Batch, Subject Category, Subject Allocation, Room, Academic Status,
  Grading Policy, Attendance Policy) — full backend CRUD exists for all of
  them, but only the 11 entities explicitly scoped for Module 03's UI got
  a management screen. The other 7 are reachable as read-only dropdown
  selections on the forms that reference them.
- **Import/Export endpoints are documented skeletons only.** `POST
  /{entity}/import` returns `202` without processing anything; `GET
  /{entity}/export` is a stub. `POST /{entity}/bulk` (bulk create) is
  fully implemented with per-item error collection. No frontend UI is
  wired to the import/export skeletons yet.
- **`require_permissions` is AND-only.** No any-of (OR) variant exists yet
  — a caller needing either/or semantics isn't yet supported by a single
  dependency call. Add if a concrete future need arises (see `docs/rbac.md`).
- **No AI evaluation or scoring engine.** Module 04 (Assessment Domain)
  added 37 assessment tables and prepares the schema for AI evaluation
  (typed `confidence_threshold`/`ai_config`/`ai_notes` columns, an
  append-only `EvaluationHistory` table); Module 05 (Answer Script OCR
  Pipeline) produces the structured, OCR'd data an evaluator would read —
  but nothing in this codebase actually evaluates, scores, or grades any
  answer content yet. See
  [docs/assessment-domain-guide.md](docs/assessment-domain-guide.md#ai-preparation-placeholders)
  and [docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md).
- **5 of 6 OCR providers are interface-conformant stubs, not working
  integrations.** Only `TesseractProvider` actually calls an OCR engine
  (the real, locally-installed Tesseract binary). `EasyOCRProvider`/
  `PaddleOCRProvider`/`AzureOCRProvider`/`GoogleVisionProvider`/
  `AWSTextractProvider` all raise `OCRProviderNotImplementedError` (HTTP
  501) — see ADR-032 and
  [docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md#adding-a-new-ocr-provider)
  for what implementing one actually requires.
- **No chunked/resumable upload endpoint.** `StorageService` has the key
  scheme and promotion helper (`build_temp_chunk_key`,
  `promote_temp_to_permanent`) ready for it, but `POST /answer-scripts` is
  a single-request multipart upload only, bounded by
  `UPLOAD_MAX_FILE_SIZE_BYTES`. Large-file/flaky-connection uploads are
  not yet resumable.
- **Virus scanning is a genuine no-op.** `scan_for_viruses_placeholder()`
  is called on every uploaded file's bytes but performs no actual
  scanning — no ClamAV or equivalent engine is wired in. Treat any file
  accepted by `POST /answer-scripts` as not virus-scanned.
- **No multilingual OCR UI.** `OCRProviderAdapter.extract()` accepts a
  `language` parameter and `OCRConfiguration.language` is a real, typed
  column, but every pipeline run today hardcodes `"eng"`
  (`app/tasks/ocr_tasks.py::_DEFAULT_LANGUAGE`) — no language-detection
  step and no frontend language picker exist yet.
- **`EvaluationHistory.embedding_vector` is plain JSON, not a vector
  type.** No pgvector extension (or any vector-search library) is
  installed anywhere in this stack. Semantic-similarity search is a
  Module 05/06 concern; the column exists purely so that module won't
  need a breaking migration to add it.
- **No `QuestionOption` table.** `QuestionType.requires_options` flags
  MCQ/Matching/True-False question types, but structured options
  currently live inside the free-text `question_text` field rather than
  a normalized options table — see
  [docs/question-bank-guide.md](docs/question-bank-guide.md#question-types).
- **`Rubric`/`RubricCriterion`/`MarkDistribution` are still not wired to
  any scoring computation.** Module 06's AI evaluator (7-signal
  lexical/statistical pipeline, ADR-039) and Module 07's Teacher Review
  workflow (confirm/override/reject, ADR-043) together do compute and
  finalize real marks now — but neither reads a `Rubric`/
  `RubricCriterion`/`MarkDistribution` row to do it. Rubric-based scoring
  (checking specific criteria against a student answer) remains a
  distinct, unbuilt feature — see
  [ROADMAP.md](ROADMAP.md) item "Rubric-Based Marking".
- **No frontend Room picker.** Module 04's `ExamSchedule.room_id` is a
  plain text UUID input on the Exam Schedule screen — no `rooms.ts`
  frontend API module exists yet even though the backend `Room` entity
  (Module 03) has full CRUD. Add a `rooms.ts` module and swap the text
  input for a `useSelectOptions` dropdown once convenient.
- **Question Bank search/filter is client-side only.** The Question Bank
  Dashboard's category/type/difficulty/Bloom/approval-status filters run
  over the current page of results (`page_size: 200`), not real
  server-side query parameters — adequate at this module's scale, but
  will need a real filter API (and likely a search index) once
  per-institution question banks grow past a few thousand rows.
- **No dedicated frontend management screen for `QuestionPaperTemplate`,
  `EvaluationConfiguration`, or `AssessmentConfiguration`** as standalone
  grids — `AssessmentConfiguration`/`EvaluationConfiguration` are 1:1
  with `Assessment` and reachable only via the backend API today (no UI
  panel on the Assessment Dashboard yet); `QuestionPaperTemplate` has
  full backend CRUD but is only selectable, not manageable, from the
  Question Paper Builder screen's template dropdown. Mirrors Module 03's
  precedent of shipping backend CRUD ahead of every entity getting its
  own dedicated screen.
- **No analytics caching/rollup table (Module 07).** `AnalyticsService`
  computes every figure on demand from `ExamResult`/`AnswerEvaluation` at
  request time (ADR-044) — correct-by-construction, but re-scans the
  relevant rows on every call. Fine at this module's scale; revisit once
  per-institution result volumes grow large enough to matter.
- **No per-report-type dynamic parameter form.** The Reports screen takes
  a single free-text JSON field for `parameters` rather than a bespoke
  form per `report_type` (each type needs different keys — `exam_id`,
  `exam_session_id`, `subject_id`, etc.) — a reasonable first pass, not a
  polished data-entry experience.
- **No student-facing full result view.** Module 07's `notifications:read`
  grant lets a student see their own "result published" notification
  (which does carry total/max marks), but there is no dedicated
  student-facing result-card screen — see ADR-048.
- **2 of 3 AI providers are interface-conformant stubs, not working
  integrations.** Only `LexicalHeuristicProvider` actually evaluates
  answers (a local, deterministic TF-IDF/keyword/bigram/rule-based
  heuristic — no network call, no API key, same "one real implementation"
  rationale as Module 05's Tesseract choice). `OpenAIProvider` and
  `AnthropicProvider` both raise `AIProviderNotImplementedError` (HTTP
  501) — see ADR-041 and
  [docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md#adding-a-new-ai-provider)
  for what implementing one actually requires.
- **No per-institution confidence-threshold override for Teacher
  Review.** The 90%/70% tier boundaries (`AnswerEvaluation.review_status`
  high/medium/low — see ADR-040) are fixed application constants, not a
  configurable value on `AIConfiguration` or `Institution`. Every
  institution gets the same thresholds today.
- **Question Bank promotion UI doesn't exist yet.** `ExtractedQuestion`/
  `ExtractedModelAnswer` already carry nullable
  `linked_question_id`/`linked_answer_key_id` FKs into Module 04's
  Question Bank (ADR-037), but no frontend action or backend endpoint
  actually performs that promotion — evaluation works entirely from the
  verified extracted data and never requires it, by design.

## Environment constraints encountered during this audit

- **No Postgres or Docker daemon available in this sandbox** (unchanged
  since Module 01). `docker` / `docker compose` / `psql`/a reachable
  `localhost:5432` are not available here, so:
  - All four table-creating migrations
    (`0004_create_academic_domain_tables.py`,
    `0006_create_assessment_domain_tables.py`,
    `0008_create_ocr_pipeline_tables.py`, and their paired permission-seed
    migrations) were verified structurally — the DDL was generated
    directly from the real ORM metadata via Alembic's own
    `produce_migrations`/`render_python_code` autogenerate engine
    (diffed against an in-memory SQLite baseline of the schema as it
    stood immediately before each), then syntax-checked, linted, and
    exercised indirectly through the full pytest suite (which builds its
    schema via `Base.metadata`, exercising the same model definitions the
    migrations were generated from). Module 05's `0008`/`0009` were
    additionally verified end-to-end via a standalone script running the
    full `0002` → `0009` chain against a real (if temporary/in-memory)
    SQLite database — upgrade and downgrade both confirmed clean (79
    tables → 0 tables) — but **no migration in this project has ever been
    run via a literal `alembic upgrade head` against a real PostgreSQL
    database in any session so far.**
  - The full stack was not booted via `docker compose up`. Module 05's
    `docker-compose.yml` MinIO service was exercised only through
    `StorageService`'s tests (a `MagicMock` client, not a live MinIO
    server) — no test in this session has written to or read from a real
    running MinIO instance. **Action:** run `alembic upgrade head` and
    `docker compose up -d --build` once on a machine with Postgres/
    Docker/MinIO before relying on any of them in a real deployment
    pipeline.
  - **Exception, Module 05: Tesseract is real; Redis is running but not
    actually usable by this app's client stack.** Tesseract-OCR 5.5.0 was
    installed via `winget` specifically for this module (a deliberate,
    user-approved choice — see [MODULE_PROGRESS.md](MODULE_PROGRESS.md)),
    so `TesseractProvider` was verified against the real binary throughout
    (`tests/test_ocr_providers.py`, `tests/test_ocr_tasks.py`), not a
    mocked adapter. A Redis **server process** is genuinely running and
    reachable — `redis-cli ping` returns `PONG` — but live-validation in
    this session discovered it is Redis 3.0.504 (an old, unofficial
    Windows port), which predates the `HELLO` command Redis 6.0+
    introduced for RESP2/RESP3 protocol negotiation. `redis-py` 8.0.1 (this
    project's client) sends `HELLO` on every new connection by default,
    so **every real `redis-py`/Celery/kombu connection to this Redis
    instance fails** with `unknown command 'HELLO'` — including a real
    Celery worker's broker connection and a plain `redis.Redis().ping()`
    call, even though `redis-cli` itself (an older-protocol client)
    connects fine. This means `/health/ready`'s Redis check correctly
    reports unreachable, the rate limiter correctly falls back to its
    in-memory store (see `conftest.py`'s `_disable_rate_limiter`
    docstring), and — the important correction to earlier documentation
    in this file — **no Celery task in this project has ever actually
    been dispatched through a live worker via `.delay()`/a real broker
    round-trip in this sandbox.** `tests/test_ocr_tasks.py` correctly
    works around this by calling the pipeline's `_run_pipeline()`
    function directly, bypassing Celery's broker entirely — that
    exercises real pipeline logic (real Tesseract, real SQLAlchemy async
    session, real image processing) but not real task queuing/delivery.
    **Action:** upgrade the local Windows Redis binary to 6.0+ (or run it
    in Docker once available) before relying on live Celery dispatch in
    this sandbox; production/CI Redis (a normal, current version) is
    unaffected by this.
  - **Module 06 inherits this exact constraint for its own new Celery
    task.** `tests/test_official_document_tasks.py` verifies
    `official_document_tasks.py`'s orchestration the same way Module 05
    does — calling the task function directly against the real Tesseract
    binary and a real (SQLite) async session, not through `.delay()`/a
    live broker round-trip. No new environment issue was introduced;
    it's the same unresolved Redis-version gap, now affecting two tasks
    instead of one.
  - **Module 07's `report_tasks.py` (background report generation) is
    verified the same way.** `tests/test_report_tasks.py` calls
    `_run_report_generation()` directly against the real `reportlab`/
    `openpyxl`/csv libraries and the fake in-memory storage bucket — real
    PDF/Excel/CSV bytes are genuinely produced and verified (magic-byte
    checks), but not through a live Celery broker round-trip. The
    `POST /reports` HTTP tests confirm the best-effort dispatch helper
    correctly leaves a job `pending` when the broker is unreachable
    (exactly this sandbox's situation) rather than 500ing the request —
    same unresolved Redis-version gap, now affecting three tasks.
- **Playwright e2e suite not executed in this pass** (unchanged from prior
  modules) — Vitest unit/integration tests were used as the faster
  equivalent coverage. Recommend running `npm run test:e2e` in CI or
  before the next release.
- **`mypy app` (the same scope CI runs — see `.github/workflows/lint.yml`)
  runs successfully in this session's environment** (superseding an
  earlier note in this file that it could not be executed — that was
  specific to a prior sandbox's Windows Application Control policy, not a
  lasting constraint). It was re-run against the full backend, including
  every Module 05 file, this module; the only errors reported remain the
  same pre-existing, out-of-scope issues in Module 02's
  `user_repository.py`/`role_repository.py`/`refresh_token_repository.py`/
  `schemas/base.py`/`core/logging.py`/`middleware/rate_limit.py`/
  `services/auth_service.py`/`main.py` (unchanged, not touched by Modules
  03–05). `mypy app tests` (a wider scope CI does **not** use) additionally
  reports ~900 pre-existing `no-untyped-def`/`no-any-return` findings
  across nearly every prior module's test file — these are not new, not
  in CI's checked scope, and out of scope for this module to fix.
- **Module 06 re-verified the same `mypy app` result: 26 pre-existing
  Module 02 errors, unchanged count, zero attributable to any Module 06
  file.** All 8 new models, the new `AIProviderAdapter` registry/provider
  set, the new orchestration task, and every new
  repository/service/schema/endpoint pass `mypy app` cleanly. The one
  addition needed was a `[[tool.mypy.overrides]]` block for
  `sklearn`/`sklearn.*` (`ignore_missing_imports = true`, added to
  `backend/pyproject.toml`), mirroring the existing `pytesseract`/`cv2`/
  `celery` overrides — `scikit-learn` ships no bundled type stubs.
- **Module 07 re-verified the same `mypy app` result again: still 26
  pre-existing Module 02 errors, unchanged count, zero attributable to
  any Module 07 file.** All 3 new models, `ExamResultService`'s state
  machine, `AnalyticsService`, `TeacherReviewDashboardService`,
  `SearchService`, `ReportService`/`report_tasks.py`,
  `NotificationService`, and every new repository/schema/endpoint pass
  `mypy app` cleanly. The one addition needed was a
  `[[tool.mypy.overrides]]` block for `reportlab`/`reportlab.*`/
  `openpyxl`/`openpyxl.*` (`ignore_missing_imports = true`), mirroring
  the existing `sklearn`/`pytesseract`/`cv2`/`celery` overrides — neither
  package ships bundled type stubs.

## Module 08 — Production Readiness environment constraints

- **No Docker CLI/daemon and no `nginx` binary exist in this sandbox at
  all** — confirmed via `docker version`, `which docker`, `which nginx`,
  `nginx -v` all failing/not-found. This is the single biggest caveat on
  everything Module 08 built: `backend/Dockerfile`, `frontend/Dockerfile`,
  `docker-compose.prod.yml`, `docker-compose.monitoring.yml`, and every
  file under `nginx/` were constructed carefully by hand against
  well-known, battle-tested patterns (multi-stage builds, non-root base
  images, standard nginx reverse-proxy idioms) and cross-checked for
  internal consistency (stage names, port numbers, network membership,
  env-var names matching `.env.production.example`), but **none of it has
  been built or run by an actual Docker engine, and no nginx config here
  has been syntax-checked by `nginx -t`.** Building and running all of it
  for the first time in a real Docker environment must be the first item
  on `docs/production-checklist.md`, not an afterthought.
- **Real load testing was limited to infrastructure-level endpoints.**
  `backend/loadtests/locustfile.py` was run headlessly (20 users, 45s)
  against the real, live backend in this sandbox — genuine, captured
  results, not fabricated (health/liveness/version/docs/openapi endpoints
  all responded correctly; `/health/ready` correctly reported `503` since
  no real Postgres/Redis exists here; `/openapi.json` genuinely returned
  `429` under load, confirming the new global `SlowAPIMiddleware` rate
  limiting is actually enforced end-to-end). Business endpoints (auth,
  ingestion, teacher review, ...) could not be load-tested since they
  require a real Postgres/Redis/MinIO this sandbox doesn't have — extend
  the locustfile with real business scenarios once a real environment is
  available.
- **A real, previously-undiscovered latency issue was found and fixed via
  that load test.** `/health/ready` was observed taking ~4.1s per call
  with the DB unreachable (no configured connect timeout on either the
  SQLAlchemy/asyncpg engine or the Redis client) — uncomfortably close to
  `docker-compose.prod.yml`'s 5s backend healthcheck timeout. Fixed by
  adding `DATABASE_CONNECT_TIMEOUT_SECONDS`/`REDIS_CONNECT_TIMEOUT_SECONDS`
  (both default 3s, wired into `create_async_engine`'s `connect_args` and
  `aioredis.from_url`'s `socket_connect_timeout`/`socket_timeout`) —
  re-measured afterward at ~3.1s, confirmed bounded.
- **`ruff`/`mypy` hit a transient Windows Application Control block for
  most of this module** (`OSError: [WinError 4551]` for `ruff`,
  `ImportError: DLL load failed while importing ...__mypyc` for `mypy`) —
  the same class of issue previously seen and resolved on retry for
  `scikit-learn` earlier in this project's history. It persisted across
  several retries mid-module (deferred rather than blocking other work),
  then cleared on its own by the final quality-gate pass: `ruff check .`
  reports **all checks passed** across the entire backend, and `mypy app`
  reports **26 errors in 8 files** — the exact same pre-existing Module 02
  baseline (`auth_service.py`/`user_repository.py`/`role_repository.py`/
  `refresh_token_repository.py`/`schemas/base.py`/`middleware/rate_limit.py`/
  `main.py`), zero attributable to any Module 08 file. One real, small fix
  was needed to get there: the new `@limiter.exempt` decorators added to
  `app/api/health.py`'s three endpoints tripped mypy's
  `disallow_untyped_decorators` (strict mode) since `slowapi`'s `exempt`
  ships no type annotations — resolved with a targeted
  `# type: ignore[untyped-decorator]` per line, the same precedent as the
  existing `# type: ignore[method-assign]` already in `main.py`, not a
  project-wide strictness relaxation.
- **No CSRF token was added, by design — not an oversight.** See
  `SECURITY_CHECKLIST.md`'s Module 08 addendum: the existing three-layer
  mitigation (bearer-header access tokens, `SameSite=Lax` + path-scoped
  refresh cookie, origin-allowlisted CORS) remains defensible and adding a
  dedicated CSRF token would mean touching frozen Module 02 auth-flow
  code, which this module's constraints explicitly forbid.
- **No additional caching layer beyond the existing Redis usage
  (rate-limit counters, Celery broker/result backend) was added.** Feature
  11 (Caching) in the Module 08 spec was interpreted as "ensure what
  exists is production-hardened" (connection pooling, `pool_recycle`,
  bounded connect timeouts — all delivered) rather than adding a new
  read-through response/query cache, since introducing one would mean
  deciding cache-invalidation semantics for Teacher Review/Analytics data
  — a business-logic-adjacent design decision explicitly out of scope for
  a module that must not change business logic. Flagged here as a
  deliberate scope interpretation, not a missed requirement.
- **`/health/ready` does not check MinIO.** Only Postgres and Redis are
  checked (unchanged, pre-existing behavior from Module 01/02) — a MinIO
  outage will not flip readiness to `not_ready` even though file-upload/
  report-generation endpoints would fail. Documented in
  `docs/incident-response-guide.md`; not changed here since altering the
  readiness contract touches code outside this module's stated scope.
- **Disaster-recovery RTO is a planning estimate, not a measured result.**
  `docs/disaster-recovery.md` states this explicitly — this sandbox has no
  real multi-GB Postgres/MinIO dataset or second host to run an actual
  timed DR drill against.
- **One pre-existing frontend `tsc -b --noEmit` error was discovered
  (not introduced) while running the full Module 08 regression pass.**
  `frontend/src/tests/unit/AssessmentDashboardPage.test.tsx:75` builds a
  `Subject` test fixture with a `description` field the real `Subject`
  interface (`frontend/src/types/academic.ts:224`) does not have —
  `error TS2353`. This file was not touched by Module 08 (no frontend file
  was — this module is backend/infra-only) and is a Module 04-era test
  fixture bug, not a Module 08 regression. It does not fail the actual
  test suite (`npm run frontend:test`, 552/552 passing) since Vitest
  transforms via esbuild and does not type-check — only the dedicated
  `npm run typecheck` / `npm run build` (`tsc -b`) commands surface it.
  Left unfixed per this module's "do not modify any previous module"
  constraint; flagged here rather than silently ignored.
- **`npm run format:check` (Prettier) reports 110 pre-existing files with
  formatting drift, none of them touched by Module 08.** Discovered the
  same way as the `tsc` finding above — running the full quality gate
  surfaced it, but it predates this module entirely (no frontend file was
  edited in Module 08). Not fixed here for the same reason: reformatting
  110 files across Modules 03–07 is a mass edit to code this module is
  explicitly barred from touching, and doing so under a "production
  readiness only" mandate would be exactly the kind of scope creep that
  mandate exists to prevent. Worth a dedicated formatting-only pass in a
  future module (`npx prettier --write .`, reviewed as a diff-only commit,
  never mixed with a functional change).

## Things worth deciding before they become load-bearing

- **Color-contrast accessibility not visually audited.** The Tailwind
  CSS-variable-based theme tokens are semantically reasonable, but actual
  contrast ratios (WCAG AA) haven't been measured against rendered output
  in a real browser with a color picker — this audit verified structural/
  semantic accessibility (landmarks, accessible names, skip links) but not
  color contrast. Recommend a pass once real brand colors are finalized.
- **Import/Export is a skeleton, not a plan.** No CSV/Excel parsing
  library has been chosen yet, and the shape of bulk-import error
  reporting to the frontend hasn't been designed — worth deciding before
  a future module tries to implement it under time pressure.
- **`structured_content`'s JSON schema has no formal version-migration
  plan.** `STRUCTURED_CONTENT_SCHEMA_VERSION` exists and is written into
  every `AnswerScript.structured_content` payload (currently always `1`),
  but nothing reads or branches on it yet — worth deciding how a future
  schema change (e.g. Module 06 needing a new field) will handle
  already-processed rows before that becomes a real migration problem.
- **`OCRConfiguration.confidence_threshold` is stored but never
  enforced.** Nothing in the pipeline currently compares a page's or
  word's OCR confidence against this configured threshold to flag
  low-confidence results for review — it's a typed column ready for a
  future "flag for manual review" feature, not a working gate today.
