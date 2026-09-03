# Module Progress

Tracks delivery status for each numbered module of the IntelliGrade build-out.
Each module has a stated scope boundary ("STOP after Module N") — see
[ROADMAP.md](ROADMAP.md) for what's planned beyond what's listed here.

## Module 01 — Foundation

**Status:** ✅ Complete, audited, and hardened (Quality Gate passed 2026-07-15)

| Deliverable | Status |
|---|---|
| Modular-monolith folder structure | ✅ |
| FastAPI app factory, config, logging, exception handling | ✅ |
| Health / readiness / liveness / version endpoints | ✅ Verified live |
| Async SQLAlchemy + Redis + Celery wiring | ✅ |
| Alembic baseline migration (no business tables) | ✅ |
| Repository / service layer base classes | ✅ |
| Security primitives (password hashing, JWT) | ✅ Fixed & tested (was broken — see [CHANGELOG.md](CHANGELOG.md)) |
| RBAC skeleton | ✅ (unwired by design — no auth endpoints yet) |
| React 19 + Vite frontend shell | ✅ |
| Routing, layouts, theming, Redux store, TanStack Query | ✅ |
| Docker Compose stack (Postgres, Redis, MinIO, backend, frontend) | ✅ Fixed & verified (frontend build context was broken — see [CHANGELOG.md](CHANGELOG.md)) |
| CI workflows (lint, test, build, docker) | ✅ |
| Documentation set (architecture, standards, guides) | ✅ |
| Governance docs (this file and siblings) | ✅ Added during Quality Gate pass |

**Explicitly out of scope for Module 01** (confirmed still absent):
authentication, business logic, OCR, AI evaluation.

## Module 02 — Identity and Access Management

**Status:** ✅ Complete (2026-07-16)

| Deliverable | Status |
|---|---|
| Authentication (login, logout, refresh, JWT, token rotation + reuse detection) | ✅ |
| Password security (policy, hashing, history/reuse prevention, forgot/reset) | ✅ |
| Account lockout (failed-attempt counter, time-boxed lock) | ✅ |
| User management (create/update/activate/deactivate/soft-delete, profile) | ✅ |
| RBAC (4 seeded roles, 15 permissions, DB-driven, `require_roles`/`require_permissions` on every endpoint) | ✅ |
| Session management (list/revoke, current-session detection) | ✅ |
| Audit logging (append-only, 9 tracked action types, IP/UA/request-id) | ✅ |
| 10 IAM tables via 2 migrations (schema + RBAC seed), UUID PKs, portable `Uuid` type | ✅ |
| REST API: `/auth/*`, `/users/*`, `/roles`, `/permissions`, `/sessions/*` | ✅ |
| Frontend: login/forgot/reset/profile/sessions/unauthorized pages, route/role/permission guards, Redux auth slice, Axios refresh interceptor | ✅ |
| Backend tests: 87 passed, 95% coverage | ✅ |
| Frontend tests: 79 passed, ~97% coverage | ✅ |
| Documentation (this file, architecture, api-standards, database-standards, security, authentication-guide, rbac, ADRs, CHANGELOG) | ✅ |

**Explicitly out of scope for Module 02** (confirmed absent): Institutions,
answer scripts, OCR, AI evaluation, email delivery (reset-token issuance is
implemented; sending the email is deferred).

## Module 03 — Academic Domain

**Status:** ✅ Complete (2026-07-16)

| Deliverable | Status |
|---|---|
| Multi-tenancy model (`Institution` root, shared-database/shared-schema, `institution_id` denormalized on every table, `UserInstitution` membership) | ✅ |
| Tenant resolution (`X-Institution-Id` header, `CurrentInstitutionDep`, `super_admin` bypass) | ✅ |
| 20 academic entities (Institution, Campus, Department, Program, Course, Academic Year, Semester, Academic Calendar, Section, Subject, Subject Category, Teacher Assignment, Student Enrollment, Batch, Class Schedule, Room, Subject Allocation, Academic Status, Grading Policy, Attendance Policy) | ✅ |
| `TenantScopedRepository`/`TenantScopedService` shared base classes | ✅ |
| Full REST CRUD + soft-delete/restore + search/sort/pagination (`Page[T]`/`PageParams`) + Import/Export skeletons + Bulk create, all under `/api/v1` | ✅ |
| Business-rule validation (duplicate codes, academic-year/semester overlap, teacher/room/enrollment conflicts, parent-FK existence) | ✅ |
| RBAC: 80 new permission codes, purely additive, default grants for all 4 roles | ✅ |
| Audit logging (create/update/delete/restore/assignment/enrollment/status-change) reusing Module 02's `AuditService` | ✅ |
| 2 new migrations: 21 tables (`0004`) + idempotent permission seed (`0005`) | ✅ |
| Frontend: 11 management screens (Institution, Campus, Department, Program, Course, Semester, Academic Year, Section, Subject, Teacher Assignment, Student Enrollment) with tables/forms/dialogs/search/pagination/dark-mode/permission-gated actions | ✅ |
| Frontend shared infrastructure: `DataTable`, `FormDialog`, `ConfirmDialog`, pagination/search-input/select/textarea/dialog primitives, generic CRUD API factory, generic pagination/mutation hooks, institution switcher | ✅ |
| Backend tests: 314 passed, 96.55% coverage | ✅ |
| Frontend tests: 159 passed, ~96.2% coverage | ✅ |
| Documentation (this file, PROJECT_STATUS, CHANGELOG, ROADMAP, TESTING_STATUS, architecture, api-standards, database-standards, folder-structure, new academic-domain-guide, 6 new ADRs) | ✅ |

**Explicitly out of scope for Module 03** (confirmed absent): Answer
Scripts, OCR, AI evaluation. No dedicated frontend screen for Batch,
Subject Category, Subject Allocation, Room, Academic Status, Grading
Policy, or Attendance Policy (backend CRUD exists; only the 11 screens
explicitly requested were built — the others are reachable as read-only
dropdown selections on forms that reference them). Import/Export
endpoints are documented skeletons only (no processing logic, no frontend
UI). See [docs/academic-domain-guide.md](docs/academic-domain-guide.md)
for full detail.

## Module 04 — Assessment Domain

**Status:** ✅ Complete (2026-07-18)

| Deliverable | Status |
|---|---|
| 37 assessment entities (Assessment/Exam/Exam Schedule family, Question Bank, Question Paper, Answer Key/Rubric) reusing Module 03's `TenantScopedRepository`/`TenantScopedService` unmodified | ✅ |
| Two new shared mixins: `VersionCounterMixin` (every entity), `ApprovalWorkflowMixin` (Question, Question Paper only) | ✅ |
| Full REST CRUD + soft-delete/restore + search/sort/pagination + Import/Export skeletons + real Bulk create, all under `/api/v1` | ✅ |
| Question/Question Paper approval workflow (`submit-for-review`/`approve`/`reject`, append-only version + approval history) | ✅ |
| RBAC: 148 new permission codes (243 total), including a deliberate divergence from Module 03's "everyone gets read-only" default — students get zero default access to Question/AnswerKey/Rubric/QuestionPaper content | ✅ |
| Audit logging: 6 new `AuditAction` entries reusing Module 02's `AuditService` | ✅ |
| AI-preparation placeholders for Module 05/06 (confidence thresholds, `ai_config`, `ai_notes`, `EvaluationHistory` table) — typed and migrated, read/written by zero application code | ✅ |
| 2 new migrations: 37 tables (`0006`) + idempotent permission seed (`0007`) | ✅ |
| Frontend: 12 management screens (Assessment Dashboard, Exam Management, Exam Schedule, Question Bank Dashboard, Question Editor, Question Viewer, Question Review Screen, Question Approval Screen, Blueprint Builder, Question Paper Builder, Rubric Builder, Answer Key Builder) reusing all Module 03 shared infrastructure unchanged | ✅ |
| Backend tests: 794 passed, 98.08% coverage | ✅ |
| Frontend tests: 331 passed (49 files), 96.42% coverage | ✅ |
| Documentation (this file, PROJECT_STATUS, CHANGELOG, ROADMAP, TESTING_STATUS, KNOWN_LIMITATIONS, architecture, api-standards, database-standards, folder-structure, new assessment-domain-guide/question-bank-guide/rubric-guide, 6 new ADRs) | ✅ |

**Explicitly out of scope for Module 04** (confirmed absent): OCR, AI
evaluation, any scoring engine that actually computes a grade from a
rubric, semantic similarity/embedding search (the `embedding_vector`
column is plain JSON, not pgvector — no vector extension is installed),
email delivery, a frontend Room-picker (no `rooms.ts` API module exists
yet — Exam Schedule's `room_id` is a plain text field). Import/Export
endpoints are documented skeletons only. See
[docs/assessment-domain-guide.md](docs/assessment-domain-guide.md) for
full detail.

## Module 05 — Answer Script OCR Pipeline

**Status:** ✅ Complete (2026-07-19)

| Deliverable | Status |
|---|---|
| 11 OCR pipeline entities (AnswerScript, AnswerScriptPage, UploadJob, ProcessingHistory, OCRProvider, OCRConfiguration, OCRJob, OCRResult, OCRBlock, OCRLine, OCRWord) reusing Module 03's `TenantScopedRepository`/`TenantScopedService` unmodified, plus a new `GlobalRepository`/`GlobalService` pair for the one global entity (`OCRProvider`) | ✅ |
| Upload management: single/multiple/bulk upload, checksum-based duplicate detection, format/size/page-count validation, virus-scan extension point (no-op today) | ✅ |
| Real MinIO object storage integration (`StorageService`) — the first real (non-config-only) use of the MinIO service provisioned since Module 01 | ✅ |
| 11-step configurable image preprocessing pipeline (deskew, denoise, contrast, brightness, crop, margin-trim, resolution/orientation normalization, page-split, blank-page detection, PDF page extraction) | ✅ |
| OCR provider abstraction: 1 real adapter (Tesseract, via `pytesseract`) + 5 registered, interface-conformant stub adapters (EasyOCR, PaddleOCR, Azure OCR, Google Vision, AWS Textract) | ✅ |
| Text normalization (whitespace/unicode/line-ending/hyphenation cleanup) — raw AND normalized OCR text both persisted | ✅ |
| Structured output generation: per-page block→line→word JSON tree + best-effort question-marker detection, written to `AnswerScript.structured_content` | ✅ |
| Background processing: first real, registered Celery task (`ocr.process_answer_script`), with retry, cancellation, and per-stage `ProcessingHistory` logging | ✅ |
| Full REST CRUD (where applicable) + soft-delete/restore/search/sort/pagination + retry/cancel/download/bulk-upload, all under `/api/v1` | ✅ |
| RBAC: 20 new permission codes (263 total), including a deliberate divergence — students get zero default access to any Answer Script/OCR data | ✅ |
| Audit logging: 7 new `AuditAction` entries (38 total) reusing Module 02's `AuditService`; automatic pipeline-stage transitions logged separately via the new append-only `ProcessingHistory` table | ✅ |
| 2 new migrations: 11 tables (`0008`) + idempotent permission seed + OCR provider catalog seed (`0009`) | ✅ |
| Frontend: 10 screens (Answer Script Upload Dashboard, Upload Queue, OCR Status Dashboard, Answer Script Viewer, Page Viewer, OCR Text Viewer, Processing History, OCR Job Details, OCR Provider Management, OCR Configuration) reusing all Module 03/04 shared infrastructure unchanged, routes/nav wired into `routes/index.tsx`/`Sidebar.tsx` | ✅ |
| Backend tests: 944 passed, 97.54% coverage (target ≥97%) — includes a real, non-mocked Tesseract OCR pass through the full Celery pipeline orchestration function | ✅ |
| Frontend tests: 407 passed (60 files), 96.42% coverage (target ≥96%) | ✅ |
| Documentation (this file, PROJECT_STATUS, CHANGELOG, ROADMAP, TESTING_STATUS, KNOWN_LIMITATIONS, architecture, database-standards, folder-structure, README, new ocr-pipeline-guide/storage-guide, 9 new ADRs) | ✅ |

**Explicitly out of scope for Module 05** (confirmed absent): AI
evaluation, scoring, or grading of any answer content — this module only
produces structured, OCR'd data for a future Module 06 to consume. 5 of 6
OCR providers are stubs (only Tesseract actually runs). Chunked/resumable
upload has storage-layer readiness (`build_temp_chunk_key`,
`promote_temp_to_permanent`) but no endpoint implements it — uploads are
single-request multipart today. No multilingual OCR beyond whatever
language Tesseract is invoked with (`eng` default) — the architecture
supports per-configuration `language`, but no language-detection or UI
picker exists yet. See
[docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md) for full detail.

## Module 06 — Official Exam Content Ingestion & AI Evaluation

**Status:** ✅ Complete (2026-07-19)

A scope correction from the original Module 06 brief: IntelliGrade does
not author examinations — the Question Paper, Model Answer, and Mark
Scheme already exist as official PDFs the Exam Cell/Faculty prepared.
This module begins from those documents. Approved via a dedicated
Architecture Impact Report before implementation (see ADR-035 through
ADR-041); Modules 01–05 remain frozen and unmodified.

| Deliverable | Status |
|---|---|
| 8 new entities (OfficialExamDocument — exam-scoped root, not session-scoped; OfficialExamDocumentPage; ExtractedQuestion; ExtractedModelAnswer; MarkSchemeRange; AIProvider; AIConfiguration; AnswerEvaluation) reusing Module 03's `TenantScopedRepository`/`TenantScopedService` unmodified, plus Module 05's `GlobalRepository`/`GlobalService` for the second global entity (`AIProvider`) | ✅ |
| Official document upload (Question Paper/Model Answer/Mark Scheme), checksum-based duplicate detection, format/size validation | ✅ |
| New, parallel ingestion Celery task reusing Module 05's OCR engine layer (image preprocessing, `OCRProviderAdapter`, PDF extraction, text normalization) exactly — zero OCR logic duplicated, zero Module 05 files modified | ✅ |
| Question/answer/mark-range extraction heuristics (regex-based boundary detection + printed-marks detection), all teacher-verifiable before use — never authoritative pre-verification | ✅ |
| Data-driven mark-scheme range expansion ("Questions 1-12 = 1 mark" → per-question maximums) — no hardcoded ranges anywhere in application code, supports any examination pattern | ✅ |
| Question Bank promotion kept fully optional and outside the evaluation workflow — evaluation never requires it (per explicit approved decision) | ✅ |
| AI evaluation: 7-signal pipeline (semantic similarity, keyword match, concept match, reasoning analysis, completeness analysis, answer relevance, confidence) via a new AI-provider abstraction mirroring Module 05's OCR-provider pattern exactly — 1 real local lexical/statistical implementation (`scikit-learn` TF-IDF + heuristics, no network/API-key dependency) + 2 registered stub providers (OpenAI, Anthropic) | ✅ |
| Confidence-tiered Teacher Review: ≥90% auto-suggested, 70-89% requires confirmation, <70% mandatory review — implemented exactly as specified | ✅ |
| `AnswerEvaluation` (new, current evaluation state) kept distinct from Module 04's `EvaluationHistory` (retained unmodified, given its first real use as the append-only AI/teacher-review action log) | ✅ |
| Full REST CRUD (where applicable) + soft-delete/restore/pagination + retry/cancel/download/verify/expand/confirm/override, all under `/api/v1` | ✅ |
| RBAC: 26 new permission codes (289 total) — students get zero default access to any official document, extraction, or evaluation data (official model answers/mark schemes are more exam-sensitive than Module 05's ungraded scripts) | ✅ |
| Audit logging: 10 new `AuditAction` entries (48 total) reusing Module 02's `AuditService` | ✅ |
| 2 new migrations: 8 tables (`0010`) + idempotent permission seed + AI provider catalog seed (`0011`) | ✅ |
| Frontend: 8 screens (Official Document Upload Dashboard, Question/Model Answer/Mark Scheme Verification, Evaluation Review Dashboard, Answer Evaluation Detail, AI Provider Management, AI Configuration) reusing all Module 03/04/05 shared infrastructure unchanged, routes/nav wired into `routes/index.tsx`/`Sidebar.tsx` | ✅ |
| Backend tests: 1060 passed, 97.12% coverage (target ≥97%) — includes real, non-mocked Tesseract OCR passes for all 3 document types and real (non-mocked) AI evaluation runs, including a genuine low-confidence/off-topic case verified to force mandatory review | ✅ |
| Frontend tests: coverage verified ≥96% (target met) | ✅ |
| Documentation (this file, PROJECT_STATUS, CHANGELOG, ROADMAP, TESTING_STATUS, KNOWN_LIMITATIONS, architecture, database-standards, folder-structure, README, new official-document-guide/ai-evaluation-guide, 7 new ADRs) | ✅ |

Two real bugs were found and fixed during this module's build, both
documented in [docs/official-document-guide.md](docs/official-document-guide.md)
and [docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md): a
Module-05 image-preprocessing false-positive (the `orientation` step
flipping clean printed text 180 degrees, worked around via
`PreprocessingPipeline`'s existing configurable step list — no Module 05
file changed) and two AI-provider calibration errors (a bigram-matching
mismatch, and a reasoning-score scale that made even a verbatim match
score low confidence) — both fixed before the provider shipped.

**Explicitly out of scope for Module 06** (confirmed absent): no
evaluation, scoring, or grading logic anywhere touches Module 04's
Question Bank directly — extracted content stays in its own tables
unless an institution explicitly promotes it. 2 of 3 AI providers are
stubs (only the lexical/statistical heuristic actually runs — no hosted
LLM integration exists). No chunked/resumable upload for official
documents (single-request multipart only, matching Module 05's own gap).
No per-institution confidence-threshold override (the 90%/70% bands are
fixed constants in this pass). See
[docs/official-document-guide.md](docs/official-document-guide.md) and
[docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md) for full
detail.

## Module 07 — Teacher Review, Result Finalization & Analytics

**Status:** ✅ Complete (2026-07-19)

Begins where Module 06 ends — after AI evaluation has produced a
confidence-tiered `AnswerEvaluation` per question — and turns those
suggestions into officially finalized, published results, plus the
analytics/reports/search/notifications built on top. Purely additive
(ADR-042 through ADR-048); Modules 01–06 remain frozen and unmodified.

| Deliverable | Status |
|---|---|
| 3 new entities (`ExamResult` — per-`ExamSession` finalization/locking root; `ReportJob`; `NotificationEvent`) reusing `TenantScopedRepository`/`TenantScopedService` unmodified | ✅ |
| Result Finalization/Locking: validated `draft → under_review → approved → locked → published` state machine + explicit `unlock`, per-student/per-exam/per-batch finalize, bulk approve/lock/publish, `AnswerEvaluationService` refusing further edits once locked/published | ✅ |
| Teacher Review: 2 new actions on `AnswerEvaluation` (`reject`, `rerun`) + 1 new `review_status` value (`teacher_rejected`) — no new table; a plain re-trigger no longer silently overwrites a teacher's prior decision, and `rerun()` snapshots pre-rerun state to `EvaluationHistory` first | ✅ |
| Teacher Review Dashboard: 5 independent bucket counts + a filtered, paginated review queue (exam/subject/course/department/student/confidence/status/teacher) | ✅ |
| Analytics: marks stats, pass/fail % (via `AssessmentConfiguration.passing_marks`), confidence distribution, teacher-override %, average AI-vs-teacher difference, question-wise performance/most-difficult ranking — all computed on demand, no new cache table (ADR-044) | ✅ |
| Reports: background PDF (`reportlab`)/Excel (`openpyxl`)/CSV generation for all 7 report types via a new Celery task + `StorageService` reuse, presigned-URL download | ✅ |
| Global Search: `ILIKE` search across students (name + `StudentEnrollment.roll_number`), teachers, subjects, questions, and evaluations, institution-scoped | ✅ |
| Notifications: storage-only `NotificationEvent` framework, no delivery channel — `ExamResultService.publish()` writes a real event a student can list/mark-read (self-scoped, one narrow default student grant) | ✅ |
| RBAC: 15 new permission codes (304 total) — `exam_results:unlock` deliberately withheld from the default teacher grant (institution_admin/super_admin only); students get zero new grants except self-scoped `notifications:read`/`:update` | ✅ |
| Audit logging: 9 new `AuditAction` entries (57 total) reusing Module 02's `AuditService`, plus continued `EvaluationHistory` writes for reject/rerun | ✅ |
| 2 new migrations: 3 tables (`0012`) + idempotent permission seed (`0013`) | ✅ |
| Frontend: 6 screens (Teacher Review Dashboard, Result Finalization & Locking, Analytics Dashboard, Reports, Global Search, Notifications) plus reject/rerun added to the existing Answer Evaluation Detail screen, all reusing Module 03–06 shared infrastructure unchanged, routes/nav wired into `routes/index.tsx`/`Sidebar.tsx` | ✅ |
| Backend tests: 1110 passed, 97%+ coverage (target ≥97%) — includes real PDF/Excel/CSV generation (magic-byte verified) for all 7 report types, and a genuine locked-result 409 rejecting further evaluation edits | ✅ |
| Frontend tests: 552 passed across 77 files, 96.41% coverage (target ≥96%) | ✅ |
| Documentation (this file, PROJECT_STATUS, CHANGELOG, ROADMAP, TESTING_STATUS, KNOWN_LIMITATIONS, architecture, database-standards, folder-structure, README, new teacher-review-guide, 7 new ADRs) | ✅ |

**Explicitly out of scope for Module 07** (confirmed absent): no
analytics caching/rollup table (every figure computed on demand, ADR-044);
no per-report-type dynamic parameter form (a single free-text JSON field
covers all 7 types); no rubric-based scoring computation (`Rubric`/
`RubricCriterion`/`MarkDistribution` still aren't read by any scoring
path); no student-facing full result-card view beyond the notification
payload; no per-institution override of the 90%/70% confidence-review
thresholds (unchanged Module 06 gap). See
[docs/teacher-review-guide.md](docs/teacher-review-guide.md) for full
detail.

## Module 08 — Production Readiness, DevOps & Enterprise Hardening

**Status:** ✅ Complete (2026-07-23)

Infrastructure/operations only, per explicit mandate — no business logic,
no database schema, no frozen Module 01–07 behavior changed. Two real bugs
were fixed as prerequisites for anything else to be trustworthy (missing
`tesseract-ocr` in the runtime image, an incomplete Celery `include` list
that silently worked in the API process but would fail a real standalone
worker), then infrastructure/observability/security/operational-docs work
built on top.

| Deliverable | Status |
|---|---|
| Docker: multi-stage `backend/Dockerfile` (`runtime-base`/`build-base`/`deps`/`production`/`worker`/`development`, non-root `appuser`, `HEALTHCHECK`) and `frontend/Dockerfile` (`nginxinc/nginx-unprivileged:1.27-alpine`, non-root by design, build-time `VITE_*` args) | ✅ |
| `docker-compose.prod.yml`: 7 services (postgres/redis/minio/backend/worker/frontend/nginx), `edge`/`internal` network segmentation, resource limits, only `nginx` publishes host ports | ✅ |
| `nginx/` reverse proxy: TLS termination (self-signed for this sandbox), HSTS + security headers, per-route rate-limit zones, `/metrics` blocked at the public edge | ✅ |
| `.env.production.example` + `.gitignore` updates (verified via `git check-ignore`/`git add --dry-run`) | ✅ |
| `docker-compose.monitoring.yml`: Prometheus (real `/metrics` scrape, `prometheus-fastapi-instrumentator`) + Grafana (auto-provisioned datasource + 7-panel dashboard, verified against live metric names) | ✅ |
| Global rate limiting actually enforced (`SlowAPIMiddleware` registered — closes the ADR-005 gap), DB pool recycling + slow-query logging + bounded DB/Redis connect timeouts (the last discovered and fixed via a real load test) | ✅ |
| CI/CD: `.github/workflows/security.yml` (gitleaks, pip-audit, npm audit, Trivy container scan), `.github/workflows/deploy.yml` (GHCR image publish by commit SHA), `.github/dependabot.yml` (pip/npm/docker×2/actions) | ✅ |
| Backup/restore: `scripts/backup/{backup,restore}-{postgres,minio}.sh`, integrity-verified, retention-pruning | ✅ |
| Load testing: `backend/loadtests/locustfile.py`, real headless run against the live backend (612 requests, 15.05 req/s) — surfaced and led to fixing the unbounded readiness-probe latency | ✅ |
| Security hardening review: OWASP Top 10 (2021) walkthrough (`SECURITY_CHECKLIST.md` addendum), CORS/CSRF/JWT re-confirmed unchanged and sound | ✅ |
| 8 new operational docs: production-checklist, runbook, monitoring-guide, incident-response-guide, upgrade-guide, rollback-guide, disaster-recovery, backup-guide | ✅ |
| Updated docs: deployment-guide, environment-guide, security.md, SECURITY_CHECKLIST.md, KNOWN_LIMITATIONS.md, docs/README.md index | ✅ |
| Backend regression: 1110/1110 passing, 97% coverage (unchanged from Module 07) | ✅ |
| Frontend regression: 552/552 passing, 96.41% coverage (unchanged — no frontend file touched this module) | ✅ |
| Quality gate: `black`/`isort`/`ruff` clean; `mypy app` — 26 pre-existing Module 02 errors, 0 attributable to Module 08 (one new `untyped-decorator` finding from `@limiter.exempt` fixed with a targeted `# type: ignore`) | ✅ |
| Live verification: `/health`, `/health/live`, `/health/ready`, `/health/version`, `/metrics`, `/openapi.json` (494 paths, `/metrics` correctly excluded) all confirmed live | ✅ |

**Explicitly out of scope for Module 08** (confirmed, by design): no
Docker CLI/daemon or `nginx` binary exists in this sandbox, so no
Dockerfile/compose file/nginx config here was built or syntax-validated by
actually running the tool (YAML-syntax-validated and brace-balance
checked instead — see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)); no
CSRF token added (existing 3-layer mitigation deemed sufficient, changing
it would touch frozen Module 02 auth flow); no new caching layer beyond
hardening the existing Redis usage (deciding cache-invalidation semantics
for Teacher Review/Analytics data is a business-logic-adjacent design
decision out of scope here); `/health/ready` still doesn't check MinIO
(pre-existing, unchanged scope). See
[docs/production-checklist.md](docs/production-checklist.md) for the full
pre-launch checklist.

## Module 09 — Release Candidate, Final Audit & Production Certification

**Status:** ✅ Complete — **IntelliGrade certified Version 1.0** (2026-07-23)

Not a feature module — a full enterprise-grade audit across 11 phases
(Architecture, Database, API, Frontend, Security, Performance, Code
Quality, Testing, Documentation, End-to-End Validation, Production
Certification), run via 6 parallel independent audit passes plus direct
live validation. Modules 01–08 remain frozen; no business functionality
or database schema was added, per this module's explicit mandate. See
`PRODUCTION_READINESS_REPORT.md` and `docs/RELEASE_NOTES_v1.0.md` for the
full certification record.

| Deliverable | Status |
|---|---|
| Architecture Audit — module boundaries, layering, dependency graph, config management (`~100` services/repositories reviewed) | ✅ 2 High findings (documented, not fixed — architecture redesign out of scope) |
| Database Audit — 90 tables, FKs, indexes, constraints, tenant isolation, cascade rules (13 migrations reviewed) | ✅ Clean; 4 missing indexes on sibling-inconsistent columns documented for a future schema migration |
| API Audit — 494 path templates / 677 operations across 83 routers | ✅ 1 **Critical** bug found and fixed (see below); everything else Info/Low |
| Frontend Audit — 57 pages, navigation, accessibility, forms, TypeScript quality | ✅ 1 **Critical** build-blocker found and fixed (see below); form-validation gap documented |
| Security Audit — JWT, RBAC, rate limiting, secrets, Docker/network security, headers, OWASP Top 10 | ✅ Every Module 08 claim re-verified true; 2 new Medium findings documented (frontend devDependency CVEs, upload content-type validation) |
| Performance + Code Quality Audit — N+1 queries, caching, background tasks, OCR/AI perf, dead code, code smells | ✅ 6 Medium findings documented (N+1, unenforced page-count limit, Celery retry idempotency, sync bulk transitions, one long method, 4 large frontend components) |
| **Critical fix**: `exam_results.py` route-registration-order bug made all 3 bulk result actions (`/bulk/approve\|lock\|publish`) unreachable via the API (422, never reaching the service) | ✅ Fixed + regression test added |
| **Critical fix**: stale test fixture broke `npm run typecheck`/`npm run build` (and therefore the frontend production Docker image build) | ✅ Fixed; full production build re-verified passing |
| Testing Audit | ✅ Backend 1111/1111 passing (97% coverage), Frontend 552/552 passing (96.41% coverage), quality gate clean (`black`/`isort`/`ruff` clean, `mypy app` at the same 26 pre-existing baseline errors) |
| Documentation Audit | ✅ 3 stale/false doc claims corrected (`shared/` usage in `architecture.md`/`academic-domain-guide.md`, `/auth/logout` auth requirement in `api-standards.md`, 2 setting-name mismatches) |
| End-to-End Validation | ✅ Real, live, single continuous run: Tesseract OCR (question paper + model answer + student script) → teacher verification → real AI evaluation → confirm → finalize → approve → lock (locked-edit guard re-verified) → publish → analytics → real PDF report → 9 real audit-log entries |
| Production Certification | ✅ Module 08 artifacts (compose files, nginx configs, CI workflows, Grafana dashboard, backup scripts) re-verified valid |
| 9 new release/operational docs (Release Notes, Production Readiness Report, Future Roadmap, Deployment Checklist, Operations Manual, Administrator Manual, Teacher User Guide, Installation Guide, Troubleshooting Guide) | ✅ |
| Version bump to 1.0.0 (`package.json`, `frontend/package.json`, `backend/pyproject.toml`, `Settings.VERSION`) | ✅ |

**Explicitly out of scope for Module 09** (confirmed, by design — this
module's mandate: fix only critical issues, no new business features, no
architecture redesign, no schema changes unless critical): the
Architecture/Performance/Code-Quality audits' Medium/High findings
(`exam_result_service.py`/`answer_evaluation_service.py` bypassing their
repositories, ~50 CRUD forms with no client-side validation, missing
indexes on 4 columns, N+1 in analytics, Celery retry idempotency, 4
oversized frontend components) were all deliberately left as documented
backlog items rather than fixed — see `KNOWN_LIMITATIONS.md`'s Module 09
section for the full list and the reasoning behind each decision.

## Module 10+ — Not yet started

See [ROADMAP.md](ROADMAP.md) for the full anticipated module sequence
post-v1.0 (Reports/Analytics refinements, Notifications delivery channel,
multi-node Cloud Deployment/IaC, Microservice extraction, and the
Module 09 audit's own documented backlog). Order and scope are subject to
change based on direction given in future prompts.
