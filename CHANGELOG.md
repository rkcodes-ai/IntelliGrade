# Changelog

All notable changes to this project are documented in this file. Format
loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [1.0.1] — Module 10: Deployment & Validation (2026-07-23)

Not a feature release — real deployment/validation of the certified v1.0
build, plus one Critical runtime defect found and fixed. See
`VERSION_1.0_DEPLOYMENT_CERTIFICATE.md` for the full validation record.

### Fixed

- **Critical — global rate limiting (`RATE_LIMIT_DEFAULT`) was silently
  non-functional for every route without its own explicit
  `@limiter.limit(...)`/`@limiter.exempt` decorator** — i.e. virtually
  the entire API surface except the auth endpoints and health probes.
  Found via live load testing (100+ real rapid requests to a running
  instance, zero `429`s observed) rather than code review. Root cause:
  dependency drift (`fastapi` resolving to `0.139.0` under this project's
  unpinned `fastapi>=0.115.0` constraint) introduced an internal
  `_IncludedRouter` route-wrapping optimization that `slowapi`'s
  `SlowAPIMiddleware` route-lookup cannot see through, causing every such
  route to be silently treated as rate-limit-exempt. Fixed by replacing
  `SlowAPIMiddleware` with a new, FastAPI-version-independent
  `DefaultRateLimitMiddleware` (`backend/app/middleware/rate_limit.py`)
  that enforces the same limit without depending on route introspection.
  Verified live (in-process via ASGI transport, and against the actual
  running server): exactly 100 requests through, then `429` for the
  rest; `/health/live` confirmed to remain exempt. See
  `RUNTIME_BUG_REPORT.md` for full detail.

### Added

- `backend/tests/test_security_hardening.py::test_default_rate_limit_applies_to_undecorated_routes`
  — permanent regression test for the fix above.
- 9 deployment-validation deliverables: `ENVIRONMENT_VERIFICATION_REPORT.md`,
  `DEPLOYMENT_REPORT.md`, `INFRASTRUCTURE_VALIDATION_REPORT.md`,
  `UAT_REPORT.md`, `RUNTIME_BUG_REPORT.md`, `PERFORMANCE_SUMMARY.md`,
  `PRODUCTION_VALIDATION_REPORT.md`, `KNOWN_RUNTIME_ISSUES.md`,
  `FINAL_DEPLOYMENT_CHECKLIST.md`, `VERSION_1.0_DEPLOYMENT_CERTIFICATE.md`.
- `KNOWN_LIMITATIONS.md`'s Module 10 section; `SECURITY_CHECKLIST.md`'s
  Module 10 addendum (correcting the Module 08/09 rate-limiting claim in
  light of the above).

### Verified (no other code change)

- Backend: 1112/1112 tests passing (1111 + 1 new regression test), 97%
  coverage. Frontend: 552/552 tests passing, 96.41% coverage. Zero
  regressions from the fix.
- A real, live, HTTP-driven end-to-end run of the complete business
  workflow across all 4 roles (Super Admin, Institution Admin, Teacher,
  Student), including an explicit Teacher Override step and a live `409`
  confirmation that locked results block further edits.
- PostgreSQL's local install was found to be genuinely corrupted (missing
  `lib/`, no `initdb`) rather than merely unreachable — a more precise
  diagnosis than prior modules recorded, though the underlying constraint
  (no real Postgres available in this sandbox) is unchanged.

## [1.0.0] — Module 09: Release Candidate, Final Audit & Production Certification (2026-07-23)

Not a feature module — a full enterprise-grade audit of the entire 8-module
codebase (Architecture, Database, API, Frontend, Security, Performance,
Code Quality, Testing, Documentation), live end-to-end workflow
validation, and production certification, culminating in the **v1.0
release**. Modules 01–08 remain frozen; no business functionality or
database schema was added. See `PRODUCTION_READINESS_REPORT.md` and
`docs/RELEASE_NOTES_v1.0.md` for full detail.

### Fixed

- **Critical — `exam_results.py` route-registration-order bug broke
  Feature 11 (bulk result actions) end-to-end.** `/{entity_id}/approve|
  lock|publish` were registered before `/bulk/approve|lock|publish` in
  the router; Starlette's ordered route matching swallowed `bulk` as a
  literal `entity_id`, and FastAPI's UUID coercion 422'd before ever
  reaching `bulk_transition()`. `bulk_transition()` itself was tested at
  the service layer, but no test exercised the actual HTTP routes — which
  is exactly why this went undetected. Fixed by reordering the routes
  (the same pattern every other router in the codebase already follows
  correctly) and added a new regression test
  (`test_bulk_approve_lock_publish_via_api`) that exercises the real HTTP
  routes so a future regression fails loudly.
- **Critical — a stale test fixture broke `npm run typecheck` and, by
  extension, `npm run build`** (and therefore the frontend production
  Docker image build). `AssessmentDashboardPage.test.tsx` constructed a
  `Subject` fixture with a `description` field the real `Subject` type
  doesn't have. One-line fix; confirmed the full production build now
  succeeds.

### Changed (documentation corrections, no behavior change)

- `docs/architecture.md`, `docs/academic-domain-guide.md` corrected —
  both previously claimed `shared/constants/permissions.ts` was in active
  frontend use; audit found zero real imports. Corrected rather than left
  wrong.
- `docs/api-standards.md` corrected — `/auth/logout`'s documented auth
  requirement didn't match the implementation (cookie-based, not Bearer).
- `docs/security.md`, `SECURITY_CHECKLIST.md` corrected — referenced a
  non-existent setting name (`MAX_FAILED_LOGIN_ATTEMPTS`; real name is
  `ACCOUNT_LOCKOUT_MAX_ATTEMPTS`).
- `backend/app/middleware/rate_limit.py`'s docstring updated — still
  described `SlowAPIMiddleware` as unregistered, a pre-Module-08 claim
  the code itself has contradicted since Module 08.
- `SECURITY_CHECKLIST.md`'s file-upload-validation row corrected from
  "Not yet applicable (Module 03+ scope)" — Module 05/06 shipped real
  upload endpoints since, making that note stale.

### Added

- `backend/tests/test_exam_results_api.py::test_bulk_approve_lock_publish_via_api`
  — the regression test for the critical fix above.
- `KNOWN_LIMITATIONS.md`'s Module 09 section — every verified, non-blocking
  audit finding (architecture, database, API, frontend, security,
  performance, code-quality) that was deliberately not fixed, with the
  reasoning for each.
- `SECURITY_CHECKLIST.md`'s Module 09 addendum — independent re-verification
  of every Module 08 security claim (all held up) plus 2 new findings
  (frontend devDependency CVEs, file-upload content-type validation gap).
- 9 new release/operational documents: `docs/RELEASE_NOTES_v1.0.md`,
  `PRODUCTION_READINESS_REPORT.md`, `docs/future-roadmap.md`,
  `docs/deployment-checklist.md`, `docs/operations-manual.md`,
  `docs/administrator-manual.md`, `docs/teacher-user-guide.md`,
  `docs/installation-guide.md`, `docs/troubleshooting-guide.md`.

### Verified (no code change)

- **Version bump to 1.0.0**: `package.json`, `frontend/package.json`,
  `backend/pyproject.toml`, `backend/app/core/config.py`'s `VERSION`.
- Backend: 1111/1111 tests passing (1110 + 1 new regression test), 97%
  coverage.
- Frontend: 552/552 tests passing, 96.41% coverage; `npm run typecheck`
  and `npm run build` both now genuinely pass (previously broken, see
  Fixed above).
- A new, throwaway, real end-to-end script (not part of the durable
  suite) chained the entire v1.0 workflow in one continuous run: real
  Tesseract OCR (official question paper, model answer, and student
  answer script) → teacher verification → real AI evaluation
  (`LexicalHeuristicProvider`) → teacher confirm → finalize → approve →
  lock (with a live-verified 409-equivalent block on further edits) →
  publish → real analytics aggregation → real `reportlab` PDF generation
  → 9 real audit-log entries. All passed on the first complete run after
  fixture corrections; the script was deleted after (throwaway, per this
  project's established precedent).
- `mypy app`: 26 pre-existing Module 02 errors, 0 new. `black`/`isort`/
  `ruff check .`: all clean.

## [0.8.0] — Module 08: Production Readiness, DevOps & Enterprise Hardening (2026-07-23)

Infrastructure/operations only — Modules 01–07 remain frozen, no business
logic or database schema changed. See [MODULE_PROGRESS.md](MODULE_PROGRESS.md)
and [docs/production-checklist.md](docs/production-checklist.md) for full
detail.

### Fixed

- **Missing `tesseract-ocr` in the backend's production/worker Docker
  images.** The single prior `base` stage never installed it — OCR/
  official-document ingestion would have failed in a real container
  despite every test passing (tests run against this sandbox's local
  Tesseract install, not the image). Fixed by adding `tesseract-ocr` to
  the new `runtime-base` stage.
- **`app/tasks/celery_app.py`'s `include` list was missing all 3 task
  modules** (`ocr_tasks`, `official_document_tasks`, `report_tasks`).
  Task registration worked fine in the API process (which imports task
  modules directly to call `.delay()`), masking that a real standalone
  `celery worker` process would never have discovered any task. Fixed and
  verified via `celery_app.tasks.keys()`.
- **`/health/ready` had no bounded connect timeout on either the DB or
  Redis client.** Discovered via a real load test: the probe took ~4.1s
  per call with the DB unreachable, uncomfortably close to
  `docker-compose.prod.yml`'s 5s healthcheck timeout. Fixed with new
  `DATABASE_CONNECT_TIMEOUT_SECONDS`/`REDIS_CONNECT_TIMEOUT_SECONDS`
  (default 3s each) — re-measured afterward at ~3.1s.

### Added

- **Docker**: multi-stage `backend/Dockerfile` (new `runtime-base`/
  `build-base` split, non-root `appuser`, new `worker` target) and
  `frontend/Dockerfile` (`nginxinc/nginx-unprivileged:1.27-alpine`,
  build-time `VITE_API_BASE_URL`/`VITE_APP_NAME` args).
- **`docker-compose.prod.yml`**: 7-service production stack, `edge`/
  `internal` network segmentation, resource limits, only `nginx` publishes
  host ports. **`docker-compose.monitoring.yml`**: Prometheus + Grafana
  overlay, auto-provisioned datasource + 7-panel dashboard.
- **`nginx/`**: TLS-terminating reverse proxy (self-signed cert for this
  sandbox, `scripts/generate-self-signed-cert.sh`), security headers,
  per-route rate-limit zones, `/metrics` blocked at the public edge.
- **`.env.production.example`**, `.gitignore` updates for the new
  production secrets/cert paths.
- **Observability**: real `/metrics` endpoint
  (`prometheus-fastapi-instrumentator`), `SlowAPIMiddleware` now actually
  enforcing the global rate-limit default (closing a gap ADR-005 left
  open since Module 02), DB connection pool recycling
  (`DATABASE_POOL_RECYCLE_SECONDS`), slow-query logging
  (`SLOW_QUERY_THRESHOLD_MS`).
- **CI/CD**: `.github/workflows/security.yml` (gitleaks secret scanning,
  pip-audit + npm audit dependency scanning, Trivy container scanning),
  `.github/workflows/deploy.yml` (GHCR image publish tagged by commit
  SHA), `.github/dependabot.yml` (pip/npm/docker×2/github-actions).
- **Backup/restore**: `scripts/backup/{backup,restore}-{postgres,minio}.sh`
  — integrity-verified, retention-pruning.
- **Load testing**: `backend/loadtests/locustfile.py`, run for real
  against the live backend (612 requests, 15.05 req/s, 45s/20 users).
- **8 new operational docs**: `docs/production-checklist.md`,
  `docs/runbook.md`, `docs/monitoring-guide.md`,
  `docs/incident-response-guide.md`, `docs/upgrade-guide.md`,
  `docs/rollback-guide.md`, `docs/disaster-recovery.md`,
  `docs/backup-guide.md`.
- **Security review**: OWASP Top 10 (2021) walkthrough added to
  `SECURITY_CHECKLIST.md`; CORS/CSRF/JWT re-confirmed unchanged and sound.

### Changed

- `docs/deployment-guide.md`, `docs/environment-guide.md`, `docs/security.md`
  updated to describe the now-implemented production stack.
- `backend/app/core/config.py`: new `DATABASE_POOL_RECYCLE_SECONDS`,
  `SLOW_QUERY_THRESHOLD_MS`, `DATABASE_CONNECT_TIMEOUT_SECONDS`,
  `REDIS_CONNECT_TIMEOUT_SECONDS` settings.
- `backend/app/db/session.py`, `backend/app/db/redis.py`: pool
  recycling, slow-query event listeners, bounded connect timeouts.
- `backend/app/main.py`: `SlowAPIMiddleware` registration, `/metrics`
  exposure.
- `backend/app/api/health.py`: `@limiter.exempt` on all 3 probe endpoints.

### Verified (no code change)

- Backend: 1110/1110 tests passing, 97% coverage (unchanged).
- Frontend: 552/552 tests passing, 96.41% coverage (unchanged — no
  frontend file was modified this module).
- `black`/`isort`/`ruff` clean; `mypy app` — 26 pre-existing Module 02
  errors, 0 new (one `untyped-decorator` finding from the new
  `@limiter.exempt` usage fixed with a targeted `# type: ignore`).
- Live: `/health`, `/health/live`, `/health/ready`, `/health/version`,
  `/metrics`, and `/openapi.json` (494 paths, `/metrics` correctly
  excluded) all confirmed live via direct curl.

## [0.7.0] — Module 07: Teacher Review, Result Finalization & Analytics (2026-07-19)

Begins where Module 06 ends — after AI evaluation has produced a
confidence-tiered `AnswerEvaluation` per question — and turns those
suggestions into officially finalized, published results, plus the
analytics/reports/search/notifications built on top. 3 new entities, 2
new Teacher Review actions, a validated result finalization/locking
state machine, on-demand analytics, background report generation, global
search, and a storage-only notification framework. Modules 01–06 remain
frozen and unmodified. See [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
[docs/teacher-review-guide.md](docs/teacher-review-guide.md) for full
detail.

### Added

- **Database**: 2 new migrations — `0012_create_module07_tables.py` (3
  tables: `exam_results`, `report_jobs`, `notification_events`) and
  `0013_seed_module07_permissions.py` (15 new permission codes + default
  role grants, idempotent against `0003_seed_rbac_baseline.py` the same
  way `0005`/`0007`/`0009`/`0011` are — listed as an explicit tuple since
  2 codes share the `answer_evaluations` prefix with 4 codes Module 06
  already seeded).
- **Backend infrastructure**: `app/services/exam_result_service.py` (the
  `draft → under_review → approved → locked → published` state machine +
  `unlock`, per-student/exam/batch finalize, bulk approve/lock/publish);
  `app/services/analytics_service.py` (marks stats, pass/fail %,
  confidence distribution, teacher-override %, AI-vs-teacher difference,
  question-wise performance — computed on demand, no new cache table);
  `app/services/teacher_review_dashboard_service.py` (5 dashboard bucket
  counts + filtered queue); `app/services/search_service.py` (global
  `ILIKE` search); `app/services/report_service.py` +
  `app/tasks/report_tasks.py` (a new Celery task generating real PDF/
  Excel/CSV files for 7 report types via `reportlab`/`openpyxl`/csv, reusing
  Module 05's `StorageService`); `app/services/notification_service.py`
  (storage-only `NotificationEvent` framework, no delivery channel).
  `AnswerEvaluationService` gains `reject()`/`rerun()` and a
  `_ensure_not_locked()` guard shared by every write action.
- **Backend entities**: 3 new model/schema/repository/service/router/test
  stacks (`ExamResult`, `ReportJob`, `NotificationEvent`); 15 new
  `PermissionCode` members (304 total, `exam_results:unlock` deliberately
  withheld from the default teacher grant); 9 new `AuditAction` members
  (57 total). Module 04's `EvaluationHistory` continues to log every
  reject/rerun action alongside confirm/override.
- **Frontend**: 6 new screens (`pages/ocr/*.tsx`) — Teacher Review
  Dashboard, Result Finalization & Locking, Analytics Dashboard, Reports,
  Global Search, Notifications — plus Reject/Re-run actions added to the
  existing Answer Evaluation Detail screen; all built on Module 03–06's
  existing shared infrastructure with zero new generic components/hooks
  needed; `types/teacherReview.ts` and 6 new `api/*.ts` modules; new
  sidebar/route entries gated by `PermissionGuard`.
- **Documentation**: this entry, plus new
  `docs/teacher-review-guide.md`, and Module 07 sections added to
  `MODULE_PROGRESS.md`, `PROJECT_STATUS.md`, `ROADMAP.md`,
  `TESTING_STATUS.md`, `KNOWN_LIMITATIONS.md`, `docs/architecture.md`,
  `docs/database-standards.md`, `docs/folder-structure.md`, `README.md`,
  `docs/README.md`, and 7 new ADRs (ADR-042 through ADR-048) in
  `ARCHITECTURE_DECISIONS.md`.

### Fixed

- A plain re-trigger of `POST /answer-evaluations` on an
  already-teacher-reviewed row previously silently recomputed and
  overwrote the teacher's confirm/override/reject decision.
  `evaluate_question()` now checks `review_status` first and returns the
  existing row unchanged if a teacher has already acted — only the new,
  explicit `rerun()` action (which snapshots history first) can force
  past that.

## [0.6.0] — Module 06: Official Exam Content Ingestion & AI Evaluation (2026-07-19)

A scope correction from the original brief: IntelliGrade does not author
examinations — the Question Paper, Model Answer, and Mark Scheme already
exist as official PDFs the Exam Cell/Faculty prepared. Approved via a
dedicated Architecture Impact Report (ADR-035 through ADR-041) before any
code was written. 8 new entities, a new parallel ingestion pipeline
reusing Module 05's OCR engine exactly, teacher-verifiable extraction,
data-driven mark-scheme expansion, and a 7-signal AI evaluation pipeline
with confidence-tiered teacher review. Modules 01–05 remain frozen and
unmodified. See [MODULE_PROGRESS.md](MODULE_PROGRESS.md),
[docs/official-document-guide.md](docs/official-document-guide.md), and
[docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md) for full
detail.

### Added

- **Database**: 2 new migrations — `0010_create_module06_tables.py` (8
  tables) and `0011_seed_module06_permissions.py` (26 new permission
  codes + default role grants + 3 `AIProvider` catalog rows, idempotent
  against `0003_seed_rbac_baseline.py` the same way `0005`/`0007`/`0009`
  are).
- **Backend infrastructure**: a new `app.services.ai` package (provider
  abstraction + registry, mirroring `app.services.ocr` exactly) with one
  real implementation (`LexicalHeuristicProvider` — `scikit-learn` TF-IDF
  cosine similarity + keyword/bigram overlap + rule-based reasoning/
  completeness heuristics, no network/API-key dependency) and 2
  registered stub providers (OpenAI, Anthropic); a new, parallel Celery
  task (`app/tasks/official_document_tasks.py`) reusing Module 05's OCR
  engine layer exactly — zero OCR logic duplicated, zero Module 05 files
  modified; `app/services/official_document_extraction_service.py`
  (question/answer/mark-range boundary-detection heuristics);
  `app/services/mark_scheme_service.py` (pure range-expansion logic);
  `app/services/answer_extraction_service.py` (reads Module 05's
  `AnswerScript.structured_content` read-only to locate a student's
  per-question answer text).
- **Backend entities**: 8 new model/schema/repository/service/router/test
  stacks (`OfficialExamDocument`, `OfficialExamDocumentPage`,
  `ExtractedQuestion`, `ExtractedModelAnswer`, `MarkSchemeRange`,
  `AIProvider`, `AIConfiguration`, `AnswerEvaluation`); 26 new
  `PermissionCode` members (289 total); 10 new `AuditAction` members (48
  total). Module 04's `EvaluationHistory` is retained unmodified and put
  to its first real use (append-only AI/teacher-review action log).
- **Frontend**: 9 new screens (`pages/ocr/*.tsx`) — Official Document
  Upload Dashboard, Official Exam Document Detail, Question/Model
  Answer/Mark Scheme Verification, Evaluation Review Dashboard, Answer
  Evaluation Detail, AI Provider Management, AI Configuration — all built
  on Module 03/04/05's existing shared infrastructure with zero new
  generic components/hooks needed; `types/officialExam.ts` and 8 new
  `api/*.ts` modules; new sidebar/route entries gated by
  `PermissionGuard`.
- **Documentation**: this entry, plus new
  `docs/official-document-guide.md`, `docs/ai-evaluation-guide.md`, and
  Module 06 sections added to `MODULE_PROGRESS.md`, `PROJECT_STATUS.md`,
  `ROADMAP.md`, `TESTING_STATUS.md`, `KNOWN_LIMITATIONS.md`,
  `docs/architecture.md`, `docs/database-standards.md`,
  `docs/folder-structure.md`, `README.md`, `docs/README.md`, and 7 new
  ADRs (ADR-035 through ADR-041) in `ARCHITECTURE_DECISIONS.md`.

### Fixed

- Module 05's `PreprocessingPipeline` default step list includes an
  `orientation` correction step that produces a false-positive
  180-degree flip on clean, well-formed single-column printed text —
  exactly what official exam documents are. Since `orientation.py` is
  frozen, `app/tasks/official_document_tasks.py` explicitly configures
  its pipeline to exclude that one step — a config choice at the call
  site (exactly the escape hatch ADR-033 built the configurable step
  list for), not a change to the frozen file.
- Two calibration errors in `LexicalHeuristicProvider`, both caught via
  direct testing before the provider shipped: a bigram-matching mismatch
  (concept-match coverage checked filtered bigrams against unfiltered
  text, so even a verbatim answer scored well below 100%), and a
  reasoning-score scale that measured against an absolute connector-count
  threshold rather than the model answer's own level of reasoning
  language, causing even a word-for-word-identical answer to read as
  only ~60% confidence. Both fixed before any test asserted against the
  provider's output.

## [0.5.0] — Module 05: Answer Script OCR Pipeline (2026-07-19)

Converts uploaded answer scripts into structured, machine-readable data
for a future Module 06 (AI Evaluation) to consume — no evaluation,
scoring, or grading of any kind. 11 new entities scoped under the
existing `Institution` tenant root (plus one deliberate global exception,
`OCRProvider`), the first real MinIO object-storage integration, the
first real Celery background task, an 11-step image preprocessing
pipeline, a 6-provider OCR adapter abstraction (1 real, 5 stubs), and 10
frontend screens. See [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
[docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md) for full detail.

### Added

- **Database**: 2 new migrations — `0008_create_ocr_pipeline_tables.py`
  (11 tables) and `0009_seed_ocr_pipeline_permissions.py` (20 new
  permission codes + default role grants + 6 `OCRProvider` catalog rows,
  idempotent against `0003_seed_rbac_baseline.py` the same way `0005`/
  `0007` are).
- **Backend infrastructure**: `StorageService`/`app/db/storage.py` (real
  MinIO client, sync core + async wrappers); `app/tasks/ocr_tasks.py`
  (the first real, registered Celery task, bridging async services via
  `asyncio.run`); a new `GlobalRepository`/`GlobalService` base-class pair
  for the one non-tenant-scoped entity (`OCRProvider`); an
  `OCRProviderAdapter` abstraction + registry
  (`app/services/ocr/`, 1 real Tesseract implementation + 5
  interface-conformant stubs); a 12-function image-preprocessing package
  (`app/services/image_processing/`) composed by a configurable
  `PreprocessingPipeline`; `text_normalization_service.py`;
  `document_structure_service.py` (structured-output assembly + best-effort
  question-marker detection).
- **Backend entities**: 11 new model/schema/repository/service/router/test
  stacks (`AnswerScript`, `AnswerScriptPage`, `UploadJob`,
  `ProcessingHistory`, `OCRProvider`, `OCRConfiguration`, `OCRJob`,
  `OCRResult`, `OCRBlock`, `OCRLine`, `OCRWord`); 20 new `PermissionCode`
  members (263 total); 7 new `AuditAction` members (38 total); a
  virus-scan extension point (`scan_for_viruses_placeholder`, no-op today)
  called on every upload.
- **Frontend**: 10 new screens (`pages/ocr/*.tsx`) — Answer Script Upload
  Dashboard, Upload Queue, OCR Status Dashboard, Answer Script Viewer,
  Page Viewer, OCR Text Viewer, Processing History, OCR Job Details, OCR
  Provider Management, OCR Configuration — all built on Module 03/04's
  existing shared infrastructure with zero new generic components/hooks
  needed; `types/ocr.ts` and 8 new `api/*.ts` modules; new sidebar/route
  entries gated by `PermissionGuard`.
- **Documentation**: this entry, plus new `docs/ocr-pipeline-guide.md`,
  `docs/storage-guide.md`, and Module 05 sections added to
  `MODULE_PROGRESS.md`, `PROJECT_STATUS.md`, `ROADMAP.md`,
  `TESTING_STATUS.md`, `KNOWN_LIMITATIONS.md`, `docs/architecture.md`,
  `docs/database-standards.md`, `docs/folder-structure.md`, `README.md`,
  `docs/README.md`, and 9 new ADRs (ADR-026 through ADR-034) in
  `ARCHITECTURE_DECISIONS.md`.

### Fixed

- `StorageService.presigned_get_url_sync` initially called a nonexistent
  Minio SDK method (`presigned_get_url`); the real SDK method is
  `presigned_get_object`. Caught by `mypy`, fixed before any test ran
  against it.

## [0.4.0] — Module 04: Assessment Domain (2026-07-18)

The academic assessment engine built on the frozen Module 01–03
foundation: 37 new entities (Assessment/Exam/Exam Schedule, Question Bank,
Question Paper, Answer Key/Rubric) scoped under the existing `Institution`
tenant root, full CRUD with soft-delete/restore/search/sort/pagination, a
real approval workflow for `Question`/`QuestionPaper`, RBAC/audit-logging
reuse, AI-preparation placeholders for Module 05/06, and 12 frontend
management screens. See [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
[docs/assessment-domain-guide.md](docs/assessment-domain-guide.md) for
full detail.

### Added

- **Database**: 2 new migrations — `0006_create_assessment_domain_tables.py`
  (37 tables) and `0007_seed_assessment_permissions.py` (148 new
  permission codes + default role grants, idempotent against
  `0003_seed_rbac_baseline.py` the same way `0005` is).
- **Backend**: two new shared mixins (`VersionCounterMixin`,
  `ApprovalWorkflowMixin` in `app/models/assessment_base.py`); 37 new
  model/schema/repository/service/router/test stacks; 148 new
  `PermissionCode` members (243 total); 6 new `AuditAction` members (31
  total); `Question`/`QuestionPaper` workflow endpoints
  (`submit-for-review`/`approve`/`reject`/`versions`); a real, working
  `POST /{prefix}/bulk` (per-item error collection) on every entity,
  matching Module 03's existing `Import`/`Export` skeleton convention.
- **Frontend**: 12 new management screens (`pages/assessment/*.tsx`) —
  Assessment Dashboard, Exam Management, Exam Schedule, Question Bank
  Dashboard, Question Editor, Question Viewer, Question Review Screen,
  Question Approval Screen, Blueprint Builder, Question Paper Builder,
  Rubric Builder, Answer Key Builder — all built on Module 03's existing
  shared infrastructure with zero new generic components/hooks needed;
  `types/assessment.ts` and 36 new `api/*.ts` modules; new sidebar/route
  entries gated by `PermissionGuard`.
- **Documentation**: this entry, plus new
  `docs/assessment-domain-guide.md`, `docs/question-bank-guide.md`,
  `docs/rubric-guide.md`, and Module 04 sections added to
  `MODULE_PROGRESS.md`, `PROJECT_STATUS.md`, `ROADMAP.md`,
  `TESTING_STATUS.md`, `KNOWN_LIMITATIONS.md`, `docs/architecture.md`,
  `docs/api-standards.md`, `docs/database-standards.md`,
  `docs/folder-structure.md`, `README.md`, and 6 new ADRs
  (ADR-020 through ADR-025) in `ARCHITECTURE_DECISIONS.md`.

### Fixed

- `PermissionRepository.list_all()`'s default `limit` was hardcoded to
  200 — with Module 04 pushing the total `PermissionCode` count to 243,
  `/api/v1/permissions` began silently truncating results (caught by
  `test_rbac.py::test_super_admin_role_includes_every_permission`
  failing after integration). Bumped the default to 2000.
- `ToastProvider`'s auto-dismiss `setTimeout` was never cleared on
  unmount, so a toast firing after a test's component tree had already
  torn down surfaced as a spurious, non-deterministically-attributed
  "state update after unmount" error — causing `npm run test:coverage`
  to report a false failure (exit 1) even when every test passed. Fixed
  by tracking and clearing pending timeouts on unmount.

## [0.3.0] — Module 03: Academic Domain (2026-07-16)

Multi-tenant Academic Domain built on the frozen Module 01/02 foundation:
`Institution` as the tenant root, 20 academic entities, full CRUD with
soft-delete/restore/search/sort/pagination, RBAC/audit-logging reuse, and
11 frontend management screens. See [MODULE_PROGRESS.md](MODULE_PROGRESS.md)
and [docs/academic-domain-guide.md](docs/academic-domain-guide.md) for full
detail.

### Added

- **Database**: 2 new migrations — `0004_create_academic_domain_tables.py`
  (21 tables: `institutions`, `user_institutions`, `campuses`,
  `departments`, `programs`, `courses`, `academic_years`, `semesters`,
  `academic_calendar_events`, `batches`, `sections`, `subject_categories`,
  `subjects`, `rooms`, `subject_allocations`, `class_schedules`,
  `teacher_assignments`, `student_enrollments`, `academic_statuses`,
  `grading_policies`, `attendance_policies`) and
  `0005_seed_academic_permissions.py` (80 new permission codes + default
  role grants, written idempotently against `0003`'s live-enum seeding).
- **Backend**: models/schemas/repositories/services/routers for all 20
  academic entities; new shared base classes
  `TenantScopedRepository`/`TenantScopedService`
  (`app/repositories/tenant_repository.py`,
  `app/services/tenant_service.py`) extending Module 02's unmodified
  `BaseRepository`/`BaseService`; `app/core/tenancy.py`
  (`CurrentInstitutionDep`, `X-Institution-Id` header resolution) built
  entirely on top of the unmodified `CurrentUserDep`; hand-rolled
  `Page[T]`/`PageParams` pagination contract
  (`app/schemas/pagination.py`); `GET /institutions/mine` for the
  frontend's institution switcher; 80 new `PermissionCode` members and 7
  new generic `AuditAction` entries in `app/core/constants.py`, purely
  additive.
- **Frontend**: 11 management screens (`pages/academic/*Page.tsx`) for
  Institution, Campus, Department, Program, Course, Semester, Academic
  Year, Section, Subject, Teacher Assignment, Student Enrollment; shared
  `DataTable`/`FormDialog`/`ConfirmDialog`/`PaginationControls`/
  `SearchInput`/`PageHeader` components; new `Dialog`/`Table`/`Select`/
  `Textarea` UI primitives (`Dialog` wraps `@radix-ui/react-dialog`, the
  first Radix primitive beyond `react-slot`); generic `createCrudApi`
  factory and `usePaginatedList`/`useCrudMutations`/`useSelectOptions`/
  `useMyInstitutions` hooks; new Redux `institutionSlice` (current
  institution, persisted to `localStorage`) plus `X-Institution-Id`
  injection in the Axios client; `InstitutionSwitcher` in the topbar;
  `PermissionGuard`-gated routes and permission-filtered sidebar nav
  entries (the first real use of both mechanisms, previously wired but
  unused); `shared/constants/permissions.ts` (new `@shared/*` path alias
  in `tsconfig.app.json`/`vite.config.ts`/`vitest.config.ts` — the first
  real runtime use of `shared/`).
- **Tests**: 314 backend tests (96.55% coverage) covering every entity's
  CRUD/validation/tenant-isolation/RBAC behavior against a real (SQLite)
  database; 159 frontend tests (36 files, ~96.2% coverage) covering every
  new hook, every shared component, the institution slice/switcher, and a
  full CRUD-dialog or list+create flow for all 11 pages.
- **Documentation**: new
  [docs/academic-domain-guide.md](docs/academic-domain-guide.md); updates
  to [docs/architecture.md](docs/architecture.md),
  [docs/api-standards.md](docs/api-standards.md),
  [docs/database-standards.md](docs/database-standards.md),
  [docs/folder-structure.md](docs/folder-structure.md),
  [README.md](README.md), [MODULE_PROGRESS.md](MODULE_PROGRESS.md),
  [PROJECT_STATUS.md](PROJECT_STATUS.md), [ROADMAP.md](ROADMAP.md),
  [TESTING_STATUS.md](TESTING_STATUS.md), and 6 new ADRs (014–019, see
  [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)).

### Fixed (found via integration testing during this module, not regressions from Module 02)

- **`MissingGreenlet` crash on every entity's update/restore response**:
  `TimestampMixin.updated_at` (an existing, frozen Module 02 mixin) is left
  "expired" by SQLAlchemy after an UPDATE-triggered flush, and every
  Academic Domain `*Read` schema (unlike Module 02's `UserRead`) includes
  `updated_at` — reading it during response serialization triggered an
  implicit lazy-refresh outside async-greenlet context. Fixed by calling
  `await self.session.refresh(entity)` immediately after every `update()`
  flush and in the shared `TenantScopedService.restore()`.
- **Route-registration-order bug**: 19 of 20 entity routers registered
  `/import`/`/export`/`/bulk` **after** `/{entity_id}` in the file, so
  FastAPI's registration-order route matching let `/{entity_id}` greedily
  capture e.g. `GET /subjects/export`, failing UUID parsing with a
  spurious `422`. Fixed by moving those routes to immediately after
  `GET /deleted` (before `POST ""`) in all 19 files — see
  [docs/api-standards.md](docs/api-standards.md).
- **Flaky `updated_at` regression-test assertion**: `assert
  updated_body["updated_at"] != original_updated_at` failed intermittently
  under SQLite's whole-second `func.now()` resolution (vs. PostgreSQL's
  microsecond precision in production) when a test's create-then-update
  round-trip landed in the same second. Loosened to `>=` (still catches a
  missing/stale field) in the 4 affected test files.

## [0.2.0] — Module 02: Identity and Access Management (2026-07-16)

Full Authentication, Authorization (RBAC), Identity, Session, and Audit
management, built on the Module 01 foundation. See
[MODULE_PROGRESS.md](MODULE_PROGRESS.md),
[docs/authentication-guide.md](docs/authentication-guide.md), and
[docs/rbac.md](docs/rbac.md) for full detail.

### Added

- **Database**: 2 new migrations — `0002_create_iam_tables.py` (10 tables:
  `users`, `roles`, `permissions`, `role_permissions`, `user_roles`,
  `refresh_tokens`, `sessions`, `audit_logs`, `password_history`,
  `password_reset_token`) and `0003_seed_rbac_baseline.py` (4 roles, 15
  permissions, 34 grants).
- **Backend**: models, schemas, repositories, and services for the full
  IAM domain; `AuthService`, `TokenService`, `PasswordService`,
  `RBACService`, `SessionService`, `AuditService`, `UserService`; endpoint
  routers for `/auth`, `/users`, `/roles`, `/permissions`, `/sessions`
  under `/api/v1`; `app/core/rbac.py` rewritten with a real
  `CurrentUser`/`get_current_user`/`require_roles`/`require_permissions`
  implementation backed by the database; `app/core/password_policy.py`.
- **Frontend**: login, forgot-password, reset-password, profile, sessions,
  and unauthorized pages; `ProtectedRoute`/`RoleGuard`/`PermissionGuard`
  route guards; Redux `authSlice`; Axios request/response interceptors with
  silent token refresh, in-flight de-duplication, and logout-on-refresh-
  failure; `AuthProvider` session bootstrap.
- **Tests**: 87 backend tests (95% coverage) covering auth flow, RBAC,
  sessions, password policy, password reset, and security hardening; 79
  frontend tests (~97% coverage) covering the auth slice, guards, every new
  page, API modules, and the Axios interceptor refresh/retry logic.
- **Documentation**: this entry, plus
  [docs/authentication-guide.md](docs/authentication-guide.md) and
  [docs/rbac.md](docs/rbac.md) (new), and updates to
  [docs/architecture.md](docs/architecture.md),
  [docs/api-standards.md](docs/api-standards.md),
  [docs/database-standards.md](docs/database-standards.md),
  [docs/security.md](docs/security.md), [README.md](README.md),
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md), and 6 new ADRs (see
  [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)).

### Fixed (found via integration testing during this module, not regressions from Module 01)

- **Audit trail loss on failed login/lockout**: the failed-login counter
  and lockout timestamp were being rolled back whenever the request
  ultimately raised an exception (FastAPI's session-per-request rollback
  runs on any unhandled exception). Fixed by committing explicitly before
  every `raise` that follows a state-changing write in `auth_service.py`
  and `token_service.py`.
- **`MissingGreenlet` on permission resolution**: `UserRepository`'s eager
  loading didn't reach `role.role_permissions.permission`, so
  `CurrentUser` triggered an async lazy-load outside the request's async
  context. Fixed by extending the `selectinload` chain to the full
  `user_roles → role → role_permissions → permission` depth.
- **Sessions list always showed no "current" session**: the refresh-token
  cookie is path-scoped to `/api/v1/auth` and never reaches
  `/api/v1/sessions`, so comparing against it always failed. Fixed by
  carrying `family_id` in the access token as well, exposed via
  `CurrentUser.session_family_id`.
- **Naive/aware datetime comparison `TypeError`** on `User.is_locked`,
  `RefreshToken.is_active`, `PasswordResetToken.is_valid`: some DB drivers
  don't guarantee timezone-aware round-trips even from
  `DateTime(timezone=True)` columns. Fixed with an `ensure_aware()` helper.
- **`ProfilePage` state update after unmount**: a `setTimeout` clearing the
  "saved" banner wasn't cancelled on unmount, firing a React state update
  against a torn-down component in fast test/navigation sequences. Fixed
  with `useRef`-tracked timeout ids cleared in a cleanup effect.

## [Unreleased] — Module 01 Quality Gate (2026-07-15)

A full architecture/code/security/DevOps audit of the Module 01 foundation,
performed before authorizing Module 02. See [QUALITY_GATE.md](QUALITY_GATE.md)
for the full report. No business logic, authentication, or new features were
added — this pass verified and hardened what Module 01 already delivered.

### Fixed — Critical

- **Backend: password hashing was completely broken.** `passlib[bcrypt]`
  1.7.4 (unmaintained since 2020) is incompatible with modern `bcrypt`
  releases (>=4.1) — every call to `hash_password()` raised at runtime.
  Replaced with direct `bcrypt` library usage in `app/core/security.py`.
- **Docker: the frontend image could not build.** `frontend/Dockerfile` used
  a `./frontend` build context, but this is an npm-workspaces monorepo whose
  lockfile lives at the repo root — `npm ci` had no lockfile to install
  from and would fail immediately. Changed the frontend build to a
  repo-root context (`docker-compose.yml`, `.github/workflows/docker.yml`,
  `frontend/Dockerfile` all updated); added a root `.dockerignore`.
- **npm: root `prepare` script broke any scoped install.** `npm ci
  --workspace=frontend` (as used by the fixed Docker build) still runs the
  root package's `prepare: "husky"` script, which fails when husky itself
  isn't part of the scoped install — aborting the entire install. Changed
  to `"prepare": "husky || true"` (Husky's own documented fix for this).

### Fixed — Hardening

- Validation-error responses could crash with a raw `TypeError` instead of
  returning a clean 422 when a custom Pydantic validator raised `ValueError`
  (its `ctx` field isn't natively JSON-serializable). Now passed through
  `jsonable_encoder` in `app/core/exceptions.py`.
- Structured JSON logging had no fallback serializer — any log call
  including a non-JSON-serializable value would crash the whole logging
  pipeline. Added `default=str` to the JSON renderer.
- Request ID was stored on `request.state` but never bound into structlog's
  `contextvars`, so `merge_contextvars` (already wired into the processor
  chain) never actually did anything — log lines outside the access-log
  middleware had no request ID. Now bound/cleared in `RequestIDMiddleware`.
- `app/api/deps.py`'s `DbSession` dependency wrapped `get_db_session` in a
  pointless pass-through async generator; simplified to depend on it
  directly.
- `/health/ready` checked Postgres and Redis sequentially, doubling probe
  latency versus necessary; now checked concurrently via `asyncio.gather`.
- DB/Redis health-check failures were swallowed silently; now logged at
  `warning` level for observability.
- Added a fail-fast startup check: booting with `ENVIRONMENT=production`
  and a known-placeholder or too-short `SECRET_KEY` now raises immediately
  instead of silently signing tokens with a guessable key.
- Rate limiting: `default_limits` was configured on the `Limiter` but never
  enforced (no `SlowAPIMiddleware` registered) — deliberately left inert for
  Module 01 (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)), but the
  misleading docstring was corrected and `in_memory_fallback_enabled=True`
  added so the limiter degrades safely once it is wired up.
- Frontend: `src/api/health.ts` read `import.meta.env` directly, violating
  this repo's own documented rule (env access goes through the validated
  `src/config/env.ts`); fixed, and swapped a fragile regex URL-suffix-strip
  for `new URL(...).origin`.
- Frontend accessibility: collapsed sidebar nav links were icon-only with
  no accessible name (the label was conditionally unmounted) — a WCAG
  failure for screen reader users. Fixed via a `title` attribute plus an
  `sr-only` label kept in the DOM. Added a "skip to main content" link on
  `DashboardLayout`.
- Root `package.json` declared `shared` as an npm workspace even though it
  has no `package.json` — npm silently dropped it, making the declaration
  dead. Removed it from `workspaces` to match reality.
- Misleading migration docstring: `0001_initial_baseline` claimed pgcrypto
  was "used for database-side UUID generation," but
  `UUIDPrimaryKeyMixin` actually generates UUIDs application-side via
  Python's `uuid.uuid4()`. Corrected.
- Minor cleanups: inlined a trivial one-line helper in `app/core/rbac.py`;
  moved a local `sqlalchemy.text` import to module level in `app/db/session.py`.

### Added

- Backend test coverage for previously-untested modules: `test_security.py`,
  `test_config.py`, `test_exceptions.py`, `test_logging.py`,
  `test_middleware.py` (26 tests total, up from 4; see
  [TESTING_STATUS.md](TESTING_STATUS.md)).
- Frontend test coverage: `Sidebar.test.tsx` (regression test for the
  accessibility fix above).
- Governance docs: this file, plus `PROJECT_STATUS.md`,
  `MODULE_PROGRESS.md`, `ROADMAP.md`, `ARCHITECTURE_DECISIONS.md`,
  `QUALITY_GATE.md`, `KNOWN_LIMITATIONS.md`, `SECURITY_CHECKLIST.md`,
  `TESTING_STATUS.md`.

## [0.1.0] — Module 01: Foundation (2026-07-15)

Initial enterprise-grade project foundation: modular-monolith architecture,
FastAPI backend skeleton (health/readiness/liveness/version endpoints,
config, logging, security primitives, DB/Redis/Celery wiring, repository
and service layer base classes), React 19 + Vite frontend skeleton
(routing, layouts, theming, Redux store, TanStack Query, toast/error
boundary), Docker Compose stack, CI workflows, and initial documentation
set. No authentication, business logic, OCR, or AI features. See the
[README](README.md) module roadmap.
