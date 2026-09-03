# Project Status

**Project:** IntelliGrade — AI Answer Script Evaluation System
**Last updated:** 2026-07-23
**Current phase:** **Version 1.0 — certified.** Module 09 (Release Candidate, Final Audit & Production Certification) complete; awaiting Module 10 direction.
**Overall health:** 🟢 Green — see `PRODUCTION_READINESS_REPORT.md` for the full certification verdict.

## Snapshot

| Area | Status | Notes |
|---|---|---|
| Backend (FastAPI) | 🟢 Green | Boots cleanly, 1110/1110 tests passing, 97% coverage — unchanged pass count/coverage after Module 08's infra changes (pool recycle, slow-query logging, bounded connect timeouts, rate-limit middleware, `/metrics`) |
| Frontend (React 19 + Vite) | 🟢 Green | 552/552 tests passing, 96.41% coverage — untouched by Module 08 (no frontend file was modified this module) |
| Database (PostgreSQL + Alembic) | 🟢 Green | 13 migrations, unchanged — Module 08 made no schema changes (mandate: only if "absolutely required," and it wasn't) |
| Authentication & RBAC | 🟢 Green | Unchanged — 304 permission codes, no auth-flow code touched |
| Multi-tenancy | 🟢 Green | Unchanged from Module 07 |
| Object storage | 🟢 Green | Unchanged `StorageService`; now has real backup/restore scripts (`scripts/backup/backup-minio.sh`/`restore-minio.sh`) |
| Background jobs | 🟢 Green | **Fixed this module**: `celery_app.py`'s `include` list was missing all 3 task modules — worked in the API process (which imports task modules directly) but would have silently failed task discovery in a real standalone worker. Now includes `ocr_tasks`/`official_document_tasks`/`report_tasks`, verified via `celery_app.tasks.keys()`. Broker dispatch itself remains unverifiable in this sandbox (Redis-version gap, see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)) |
| AI evaluation | 🟢 Green | Unchanged from Module 07 |
| Result finalization | 🟢 Green | Unchanged from Module 07 |
| Analytics & Reports | 🟢 Green | Unchanged from Module 07 |
| Docker / Compose | 🟢 Green | **Rewritten this module**: multi-stage non-root images (backend/worker/frontend), `docker-compose.prod.yml` (7 services, network-segmented), `docker-compose.monitoring.yml` (Prometheus+Grafana) — not build/run-validated by an actual Docker engine (none exists in this sandbox), YAML-syntax-validated instead |
| Reverse proxy / TLS | 🟢 Green | New `nginx/` — TLS termination, security headers, per-route rate limiting, `/metrics` blocked at the edge |
| CI/CD (GitHub Actions) | 🟢 Green | lint/test/build/docker unchanged; new `security.yml` (secret/dependency/container scanning), `deploy.yml` (GHCR publish), `dependabot.yml` |
| Monitoring / Observability | 🟢 Green | New — real `/metrics` (verified live), Prometheus scrape, auto-provisioned Grafana dashboard (7 panels) |
| Security foundation | 🟢 Green | Module 02 posture unchanged and re-confirmed; Module 08 adds infra-level hardening (TLS, non-root containers, network segmentation, automated scanning, global rate-limit enforcement) — full OWASP Top 10 walkthrough in [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) |
| Documentation | 🟢 Green | 8 new operational docs (production-checklist, runbook, monitoring-guide, incident-response, upgrade, rollback, disaster-recovery, backup-guide) + updated deployment-guide/environment-guide/security.md |

## What works today

- Everything from Module 01 and Module 02 (health endpoints, infra wiring,
  full IAM/auth/RBAC/session/audit flow) — unchanged and re-verified
  against the larger test suite.
- **Academic Domain**: full CRUD, soft-delete/restore, server-side
  search/sort/pagination, and Import/Export skeletons for all 20 academic
  entities, scoped to the caller's current institution and gated by
  permission codes — see [docs/academic-domain-guide.md](docs/academic-domain-guide.md).
- **Multi-tenancy**: `Institution` as the tenant root; every other
  academic table carries its own `institution_id`; a new
  `UserInstitution` membership table (not a change to Module 02's `users`
  table) resolves which institutions a user belongs to; `super_admin`
  bypasses membership checks, every other role is enforced closed (403
  without an active membership).
- **Business-rule validation**: duplicate institution/campus/department/
  program/course/subject codes, academic-year and semester date-overlap
  checks, teacher-assignment and room-double-booking conflict checks,
  student-enrollment uniqueness, parent-FK existence validation on every
  create/update.
- **RBAC extension**: 80 new permission codes (20 entities × CRUD),
  default grants for all four seeded roles, all purely additive —
  zero diffs to Module 02's `rbac.py`/`deps.py`/`users` table.
- **Audit logging**: every academic create/update/delete/restore/
  assignment/enrollment/status-change action logged through the
  unmodified Module 02 `AuditService`.
- **Frontend**: 11 management screens (Institution, Campus, Department,
  Program, Course, Semester, Academic Year, Section, Subject, Teacher
  Assignment, Student Enrollment) — searchable/paginated tables, create/
  edit dialogs, soft-delete confirmation, permission-gated actions, an
  institution switcher in the topbar, dark-mode-aware shared UI
  primitives (Dialog built on Radix, Table, Select, Textarea).

## Module 04 — Assessment Domain

The academic assessment engine Modules 05/06 (OCR, AI Evaluation, Teacher
Review, Reports, Analytics) build on:

- **37 new entities**: Assessment/Exam/Exam Schedule family (10),
  Question Bank (Question + 6 lookups + 3 workflow/history tables),
  Question Paper (8 entities including Blueprint and Randomization
  Strategy), Answer Key/Rubric (10 entities), plus append-only
  `EvaluationHistory` — all reusing Module 03's tenancy/repository/service
  base classes **unmodified**.
- **Approval workflow**: `Question` and `QuestionPaper` get a real
  draft→pending_review→approved/rejected→archived editorial lifecycle
  (`ApprovalWorkflowMixin`, new), with an append-only decision-audit table
  (`QuestionApproval`) separate from the peer-feedback `QuestionReview`
  table.
- **Versioning**: every entity gets a cheap `current_version` counter
  (`VersionCounterMixin`, new); `Question`/`QuestionPaper` additionally get
  a full append-only snapshot history, written on demand via a dedicated
  `/versions` endpoint rather than automatically on every edit.
- **RBAC extension**: 148 new permission codes (243 total). Deliberately
  **not** a blanket "everyone read-only" default like Module 03 —
  students get zero default access to Question/AnswerKey/Rubric/
  QuestionPaper content, since leaking exam content to students by
  default would be a real security bug.
- **AI-preparation, not AI**: typed placeholder columns
  (`confidence_threshold`, `ai_config`, `ai_notes`) and an append-only
  `EvaluationHistory` table exist and are migrated, but nothing reads or
  writes them yet — Module 05/06 will be the first code to use them.
- **Frontend**: 12 management screens (Assessment Dashboard, Exam
  Management, Exam Schedule, Question Bank Dashboard, Question Editor,
  Question Viewer, Question Review Screen, Question Approval Screen,
  Blueprint Builder, Question Paper Builder, Rubric Builder, Answer Key
  Builder) — zero new shared frontend infrastructure needed; every Module
  03 hook/component was reused unchanged, including three screens with
  two-level parent→child→grandchild nested CRUD (Question Paper Builder,
  Rubric Builder) that extend, rather than replace, Module 03's
  single-level nesting pattern.

## Module 05 — Answer Script OCR Pipeline

Converts an uploaded answer script into structured, machine-readable data
for Module 06 to consume — **no evaluation, scoring, or grading of any
kind happens in this module**:

- **11 new entities**: `AnswerScript` (root) → `AnswerScriptPage`,
  `UploadJob`, `ProcessingHistory` (siblings) → `OCRJob` → `OCRResult` →
  `OCRBlock` → `OCRLine` → `OCRWord` (the four-level OCR result
  hierarchy), plus `OCRProvider` (global catalog) and `OCRConfiguration`
  (tenant-scoped engine choice) — all reusing Module 03's tenancy/
  repository/service base classes, except `OCRProvider`, which uses a new
  `GlobalRepository`/`GlobalService` pair (the first genuinely
  non-tenant-scoped entity since Module 02's `Role`/`Permission`).
- **Real infrastructure, not more scaffolding**: MinIO object storage
  (`StorageService`) and Celery background jobs (`ocr.process_answer_script`)
  both go from provisioned-but-unused to real, working code for the first
  time in this codebase.
- **Full pipeline**: upload (single/multiple/bulk, checksum duplicate
  detection, virus-scan extension point) → validation → storage → image
  preprocessing (11-step configurable pipeline: deskew, denoise, contrast,
  brightness, crop, margin-trim, resolution/orientation normalization,
  page-split, blank-page detection) → OCR extraction (real Tesseract + 5
  registered stub providers for EasyOCR/PaddleOCR/Azure/Google Vision/AWS
  Textract) → text normalization (raw AND normalized text both kept) →
  structured per-page block/line/word JSON output.
- **RBAC extension**: 20 new permission codes (263 total). Same
  restrictive-default philosophy as Module 04 — students get **zero**
  default access to any Answer Script or OCR data.
- **Frontend**: 10 screens (Upload Dashboard, Upload Queue, OCR Status
  Dashboard, Answer Script/Page/OCR Text viewers, Processing History, OCR
  Job Details, OCR Provider Management, OCR Configuration) — zero new
  shared frontend infrastructure needed; every Module 03/04 hook/component
  was reused unchanged.

## Module 06 — Official Exam Content Ingestion & AI Evaluation

A scope correction from the original brief: IntelliGrade does not author
examinations — it begins from official Question Paper/Model Answer/Mark
Scheme PDFs the Exam Cell/Faculty already prepared. Approved via a
dedicated Architecture Impact Report (ADR-035 through ADR-041) before any
code was written; Modules 01–05 remain frozen:

- **8 new entities**: `OfficialExamDocument` (root, exam-scoped not
  session-scoped) → `OfficialExamDocumentPage`, `ExtractedQuestion`,
  `ExtractedModelAnswer`, `MarkSchemeRange` (children) — plus `AIProvider`
  (second global catalog, after `OCRProvider`) and `AIConfiguration`
  (tenant-scoped), and `AnswerEvaluation` (new current-evaluation-state
  table, distinct from Module 04's `EvaluationHistory`, which is retained
  unmodified and given its first real use).
- **Reuse, not duplication**: a new, parallel Celery task calls Module
  05's exact OCR engine functions (`PreprocessingPipeline`,
  `OCRProviderAdapter`, PDF extraction, text normalization) — zero OCR
  logic written twice, zero Module 05 files touched.
- **Teacher verification, never auto-trusted**: extracted
  questions/answers/mark-ranges are all teacher-editable and require
  explicit verification before evaluation treats them as authoritative.
  Question Bank promotion is optional and never a precondition of
  evaluation, per an explicit approved decision — the Question Bank stays
  a reusable academic repository, official exam documents stay temporary
  evaluation assets.
- **Data-driven mark scheme**: "Questions 1-12 = 1 mark" style ranges
  expand into per-question maximums via a pure function — no range is
  ever hardcoded in application code, any examination pattern is
  supported.
- **AI evaluation, 7 signals, never one number**: semantic similarity,
  keyword match, concept match, reasoning analysis, completeness
  analysis, answer relevance, and confidence are each individually
  persisted. A new AI-provider abstraction mirrors Module 05's OCR
  provider pattern exactly — one real, local lexical/statistical
  implementation (`scikit-learn`, no network/API-key dependency, same
  "genuinely runnable in this sandbox" reasoning as Module 05's
  Tesseract choice) plus two registered stub providers.
- **Confidence-tiered Teacher Review**: ≥90% auto-suggests marks, 70–89%
  requires one-click confirmation, <70% is mandatory full review —
  implemented exactly as specified, with every suggestion still
  overridable regardless of tier.
- **Frontend**: 8 screens (Official Document Upload Dashboard, Question/
  Model Answer/Mark Scheme Verification, Evaluation Review Dashboard,
  Answer Evaluation Detail, AI Provider Management, AI Configuration) —
  zero new shared frontend infrastructure needed.

Two real bugs were found and fixed during this module's build (both
documented in the new guides): a Module 05 image-preprocessing
false-positive (`orientation` flipping clean printed text 180 degrees,
worked around via existing configuration, no Module 05 file changed),
and two AI-provider calibration errors (a bigram-matching mismatch and a
reasoning-score scale that made even a verbatim match read as low
confidence) — both caught and fixed before the provider shipped.

## Module 07 — Teacher Review, Result Finalization & Analytics (this repository state)

Begins where Module 06 ends — after AI evaluation has produced a
confidence-tiered `AnswerEvaluation` per question — and turns those
suggestions into officially finalized, published results, plus the
analytics/reports/search/notifications built on top. Purely additive
(ADR-042 through ADR-048); Modules 01–06 remain frozen:

- **3 new entities**: `ExamResult` (root, one per `ExamSession`, created
  lazily by the first finalize action) drives the validated
  `draft → under_review → approved → locked → published` state machine,
  plus an explicit `unlock` transition withheld from the default teacher
  grant. `ReportJob` and `NotificationEvent` are the other two — same
  "system-managed job record"/"storage-only framework" shapes as prior
  modules' equivalents.
- **Teacher Review completed**: `reject()`/`rerun()` join Module 06's
  `confirm()`/`override()` — no new table, one new `review_status` value
  (`teacher_rejected`). A plain re-trigger of an already-reviewed
  evaluation no longer silently overwrites the teacher's decision; only
  the explicit `rerun()` action force-recomputes, always snapshotting
  the pre-rerun state to `EvaluationHistory` first.
- **Result Finalization/Locking**: per-student/per-exam/per-batch
  finalize, bulk approve/lock/publish, and a locked/published result now
  genuinely blocks further `AnswerEvaluation` edits with a 409 — enforced
  once, centrally, in `AnswerEvaluationService`.
- **Analytics computed on demand**: marks stats, pass/fail % (via
  `AssessmentConfiguration.passing_marks`), confidence distribution,
  teacher-override %, average AI-vs-teacher difference, and
  question-wise/most-difficult-question ranking — no new cache table,
  joined through the existing Module 03/04 hierarchy.
- **Reports, for real**: background PDF (`reportlab`)/Excel
  (`openpyxl`)/CSV generation for all 7 report types via a new Celery
  task, verified with real magic-byte checks (not mocked file bytes),
  stored through Module 05's unmodified `StorageService`.
- **Global Search & Notifications**: `ILIKE` search across students/
  teachers/subjects/questions/evaluations; a storage-only notification
  framework with no delivery channel yet — `ExamResultService.publish()`
  is its first real writer.
- **Frontend**: 6 screens (Teacher Review Dashboard, Result Finalization
  & Locking, Analytics Dashboard, Reports, Global Search, Notifications)
  plus reject/rerun added to the existing Answer Evaluation Detail
  screen — zero new shared frontend infrastructure needed.

## Module 08 — Production Readiness, DevOps & Enterprise Hardening

Infrastructure/operations only, per an explicit mandate — Modules 01–07
remain frozen, no business logic or database schema changed:

- **2 real bugs fixed as prerequisites**: the production backend image
  was missing `tesseract-ocr` (would have broken OCR/official-document
  ingestion in a real deployment despite passing every test, since tests
  run against this sandbox's local Tesseract install, not the container);
  `celery_app.py`'s `include` list was missing all 3 task modules —
  worked in the API process (imports task modules directly to call
  `.delay()`) but would silently fail task discovery in an actual
  standalone worker process.
- **Docker**: multi-stage, non-root images for backend/worker/frontend; a
  lean `runtime-base` (no compiler toolchain shipped in production/worker
  images).
- **Production stack**: `docker-compose.prod.yml` (7 services, `edge`/
  `internal` network segmentation, resource limits) + an `nginx` reverse
  proxy (TLS termination, security headers, per-route rate limiting,
  `/metrics` blocked at the public edge) + `docker-compose.monitoring.yml`
  (Prometheus + auto-provisioned Grafana, against a new, live-verified
  `/metrics` endpoint).
- **Security/observability hardening on existing code**: global rate
  limiting now actually enforced (`SlowAPIMiddleware`, closing a gap
  ADR-005 left open since Module 02); DB connection pooling/recycling,
  slow-query logging, and bounded DB/Redis connect timeouts (the last
  discovered and fixed via a real load test that found `/health/ready`
  taking ~4.1s unbounded — now ~3.1s, bounded).
- **CI/CD**: `security.yml` (gitleaks/pip-audit/npm-audit/Trivy),
  `deploy.yml` (GHCR publish by commit SHA), `dependabot.yml`.
- **Backup/restore, load testing, and 8 new operational docs** — see
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md) for the full deliverable table.
- **Full regression re-verified**: 1110/1110 backend tests (97%
  coverage), 552/552 frontend tests (96.41% coverage) — both unchanged,
  confirming zero regressions from the infra changes. Quality gate clean
  (`black`/`isort`/`ruff`; `mypy app` at the same 26 pre-existing Module
  02 errors, 0 new).

## Module 09 — Release Candidate, Final Audit & Production Certification (this repository state)

**IntelliGrade is certified Version 1.0.** Not a feature module — an
11-phase enterprise audit (Architecture, Database, API, Frontend,
Security, Performance, Code Quality, Testing, Documentation, End-to-End
Validation, Production Certification), run via 6 parallel independent
audit passes plus direct live validation:

- **2 real Critical bugs found and fixed** (only fixes made — no new
  business features, no architecture redesign, per this module's
  mandate): (1) a route-registration-order bug in `exam_results.py` made
  all 3 bulk result-action endpoints unreachable via the API (422 before
  ever reaching the service) — the service method itself was tested, but
  no test exercised the real HTTP routes, which is exactly why it went
  undetected; fixed and a regression test added. (2) A stale test fixture
  broke `npm run typecheck`/`npm run build`, meaning the frontend
  production Docker image currently could not be built — fixed, and the
  full production build re-verified passing.
- **Every prior module's documented claims re-verified against the
  actual code**, not just re-read: JWT/RBAC/rate-limiting/network-
  segmentation/security-headers all confirmed true; 90-table database
  schema audited (FKs, indexes, constraints, tenant isolation, cascades)
  — clean, with 4 missing indexes documented for a future migration;
  494-path-template API surface audited — clean beyond the one critical
  bug; 57-page frontend audited — clean structurally, with a documented
  form-validation gap (`FormDialog` disables native validation and ~50
  CRUD pages never adopted the RHF+Zod pattern the 4 auth pages use).
  2 stale documentation claims were found and corrected (`shared/`
  constants file has zero real frontend consumers despite
  `architecture.md` claiming otherwise; `/auth/logout`'s documented auth
  requirement didn't match the implementation).
- **A new, real, live end-to-end run** chained the entire v1.0 workflow
  in one continuous story for the first time this session: real Tesseract
  OCR on an official question paper, model answer, and a student answer
  script → teacher verification → real AI evaluation
  (`LexicalHeuristicProvider`, not pre-set marks) → teacher confirm →
  finalize → approve → lock (the locked-result edit-block re-verified
  live) → publish → real analytics aggregation → real `reportlab` PDF
  generation → 9 real audit-log entries, all in a single run.
- **Full regression re-verified**: 1111/1111 backend tests (1110 + 1 new
  regression test, 97% coverage), 552/552 frontend tests (96.41%
  coverage, now including a genuinely passing `typecheck`/`build`).
  Quality gate clean.
- **Version bumped to 1.0.0** across `package.json`, `frontend/package.json`,
  `backend/pyproject.toml`, and `Settings.VERSION`.
- Everything found but *not* fixed (architecture convention deviations,
  missing indexes, N+1 queries, the frontend form-validation gap, dead
  code, oversized components, dependency CVEs confined to frontend
  devDependencies) is catalogued with reasoning in
  `KNOWN_LIMITATIONS.md`'s Module 09 section — real, verified debt for a
  future module, not hidden or silently dropped.

See `PRODUCTION_READINESS_REPORT.md` and `docs/RELEASE_NOTES_v1.0.md` for
the full certification record.

## What's intentionally not here yet

No evaluation, scoring, or grading logic touches Module 04's Question
Bank directly unless an institution explicitly promotes extracted
content into it. 2 of 3 AI providers are stubs (only the lexical/
statistical heuristic runs — no hosted LLM integration exists yet). No
per-institution confidence-threshold override (the 90%/70% bands are
fixed constants). No scoring engine that actually computes a grade from
a Module 04 `Rubric` directly (Module 06/07's evaluation/review path is
independent of it). No semantic similarity/embedding search beyond
lexical TF-IDF — the `embedding_vector` column on `EvaluationHistory` is
still plain JSON, not pgvector. No email delivery for password resets
(unchanged from Module 02) and no delivery channel for
`NotificationEvent` either. No analytics caching/rollup table (every
figure computed on demand, ADR-044). No per-report-type dynamic
parameter form (Reports takes a single free-text JSON field). No
student-facing full result-card view beyond the notification payload. No
dedicated frontend screen for Batch/Subject Category/Subject Allocation/
Room/Academic Status/Grading Policy/Attendance Policy (Module 03 gap,
unchanged) — and no frontend Room-picker for `ExamSchedule.room_id`
either. Import/Export endpoints are documented skeletons only. 5 of 6 OCR
providers are stubs (only Tesseract is real). No chunked/resumable
upload endpoint for either answer scripts or official documents. See
[ROADMAP.md](ROADMAP.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Immediate next step

**Version 1.0 is certified and shipped.** Module 10, scope TBD by the
next prompt. Two categories of candidate: (1) the Module 09 audit's own
documented backlog (`KNOWN_LIMITATIONS.md`) — a real, verified priority
list starting with the frontend form-validation gap and the 4 missing
database indexes; (2) new capability (see [ROADMAP.md](ROADMAP.md)): a
fuller Teacher Review UI, a real notification delivery channel,
multi-node cloud deployment/IaC (`infrastructure/terraform`/`k8s` remain
empty placeholders — Module 08 covered single-host Docker Compose only),
or rubric-based scoring. `AnswerEvaluation`/`ExamResult`/
`EvaluationHistory` are ready to feed any of these without a breaking
schema change.

## Related documents

- [MODULE_PROGRESS.md](MODULE_PROGRESS.md) — per-module delivery tracking
- [QUALITY_GATE.md](QUALITY_GATE.md) — Module 01 audit findings and scores
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — deliberate gaps and environment constraints
- [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) — security posture tracking
- [TESTING_STATUS.md](TESTING_STATUS.md) — test coverage detail
- [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) — ADR log
- [CHANGELOG.md](CHANGELOG.md) — full change history
- [docs/academic-domain-guide.md](docs/academic-domain-guide.md) — Module 03 design reference
- [docs/assessment-domain-guide.md](docs/assessment-domain-guide.md) — Module 04 design reference
- [docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md) — Module 05 design reference
- [docs/storage-guide.md](docs/storage-guide.md) — Module 05 object storage reference
- [docs/official-document-guide.md](docs/official-document-guide.md) — Module 06 ingestion design reference
- [docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md) — Module 06 AI evaluation design reference
- [docs/teacher-review-guide.md](docs/teacher-review-guide.md) — Module 07 design reference
