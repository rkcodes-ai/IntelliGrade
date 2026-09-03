# Roadmap

High-level, subject to reprioritization by whoever issues the next module
prompt. This is a planning aid, not a commitment — see
[MODULE_PROGRESS.md](MODULE_PROGRESS.md) for what's actually been built.

## Completed

- **Module 01 — Foundation.** Modular-monolith architecture, tooling,
  CI/CD, Docker, health checks, documentation. Audited and hardened via a
  dedicated Quality Gate pass (see [QUALITY_GATE.md](QUALITY_GATE.md)).
- **Module 02 — Identity & Access Management.** Authentication (login,
  logout, refresh with rotation + reuse detection, password reset/change,
  lockout), RBAC (4 roles, 15 permissions), session management, and audit
  logging. Email delivery for password resets was deferred (token
  issuance/validation only) — see [MODULE_PROGRESS.md](MODULE_PROGRESS.md).
- **Module 03 — Academic Domain.** Shared-database multi-tenancy
  (`Institution` root, `X-Institution-Id` header resolution), 20 academic
  entities (Campus, Department, Program, Course, Academic Year, Semester,
  Section, Subject, Teacher Assignment, Student Enrollment, and 10 more),
  full CRUD/soft-delete/restore/search/sort/pagination, 80 new RBAC
  permission codes, audit logging reuse, and 11 frontend management
  screens — see [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
  [docs/academic-domain-guide.md](docs/academic-domain-guide.md).
- **Module 04 — Assessment Domain.** The academic assessment engine: 37
  entities (Assessment/Exam/Exam Schedule, Question Bank, Question Paper,
  Answer Key/Rubric), a real approval workflow for Question/Question
  Paper, versioning, 148 new RBAC permission codes (a deliberately
  restrictive student default — no default access to exam
  content/answers), AI-preparation placeholders for Modules 05/06
  (unused by any code yet), and 12 frontend management screens — see
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
  [docs/assessment-domain-guide.md](docs/assessment-domain-guide.md).
- **Module 05 — Answer Script OCR Pipeline.** Upload/validation/storage,
  an 11-step image preprocessing pipeline, OCR extraction (real Tesseract
  plus 5 registered stub providers), text normalization, and structured
  per-page block/line/word output — 11 entities, the first real MinIO and
  Celery integrations, 20 new RBAC permission codes (students get zero
  default access, same restrictive philosophy as Module 04), and 10
  frontend screens. Does **not** evaluate or score any answer content —
  see [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
  [docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md).
- **Module 06 — Official Exam Content Ingestion & AI Evaluation.** Begins
  from official Question Paper/Model Answer/Mark Scheme PDFs the Exam
  Cell/Faculty already prepared (a scope correction from the original
  brief, approved via a dedicated Architecture Impact Report). 8 entities,
  a new parallel ingestion pipeline reusing Module 05's OCR engine
  exactly, teacher-verifiable extraction (never auto-trusted, Question
  Bank promotion optional), data-driven mark-scheme expansion, a 7-signal
  AI evaluation pipeline (one real local lexical/statistical provider, 2
  registered stubs) with confidence-tiered teacher review, 26 new RBAC
  permission codes, and 9 frontend screens — see
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md),
  [docs/official-document-guide.md](docs/official-document-guide.md),
  and [docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md).
- **Module 07 — Teacher Review, Result Finalization & Analytics.** Turns
  Module 06's confidence-tiered AI suggestions into officially finalized,
  published results. 3 entities (`ExamResult`'s validated
  `draft→under_review→approved→locked→published` state machine,
  `ReportJob`, `NotificationEvent`), 2 completed Teacher Review actions
  (reject/rerun), a locked result genuinely blocking further evaluation
  edits, on-demand analytics (pass/fail, confidence distribution,
  question-wise performance), background PDF/Excel/CSV report generation
  for 7 report types, global search, a storage-only notification
  framework, 15 new RBAC permission codes, and 6 frontend screens — see
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
  [docs/teacher-review-guide.md](docs/teacher-review-guide.md).
- **Module 08 — Production Readiness, DevOps & Enterprise Hardening.**
  Infrastructure/operations only — no business logic changed, Modules
  01–07 remain frozen. Multi-stage, non-root Docker images (backend/
  worker/frontend) with a lean runtime base; a production Docker Compose
  stack (`docker-compose.prod.yml`) with network segmentation (`edge`/
  `internal`) and an `nginx` TLS-terminating reverse proxy; a Prometheus +
  Grafana monitoring overlay (`docker-compose.monitoring.yml`) against a
  new, verified-real `/metrics` endpoint; global rate limiting actually
  enforced (`SlowAPIMiddleware`, closing a gap ADR-005 left open since
  Module 02); DB connection pooling/recycling, slow-query logging, and
  bounded DB/Redis connect timeouts (the last discovered and fixed via a
  real load test); CI/CD additions (`security.yml` secret/dependency/
  container scanning, `deploy.yml` GHCR image publishing, Dependabot);
  Postgres/MinIO backup+restore scripts; and 8 new operational docs
  (production checklist, runbook, monitoring, incident response, upgrade,
  rollback, disaster recovery, backup) — see
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md) and
  [docs/production-checklist.md](docs/production-checklist.md).
- **Module 09 — Release Candidate, Final Audit & Production Certification.**
  **IntelliGrade Version 1.0.** An 11-phase enterprise audit (Architecture,
  Database, API, Frontend, Security, Performance, Code Quality, Testing,
  Documentation, End-to-End Validation, Production Certification) run
  against the full 8-module codebase, plus a real live end-to-end
  workflow run (Tesseract OCR → AI evaluation → teacher review →
  finalize/approve/lock/publish → analytics → PDF report → audit log, all
  in one continuous script). Found and fixed 2 real Critical bugs (an
  unreachable bulk-actions API route, a broken frontend production
  build); corrected 2 stale documentation claims; catalogued everything
  else found but not fixed (by mandate — no architecture redesign, no new
  features) in `KNOWN_LIMITATIONS.md` — see
  [MODULE_PROGRESS.md](MODULE_PROGRESS.md),
  `PRODUCTION_READINESS_REPORT.md`, and
  [docs/RELEASE_NOTES_v1.0.md](docs/RELEASE_NOTES_v1.0.md).

## Module 09 audit backlog (real, verified findings, priority order)

See `KNOWN_LIMITATIONS.md`'s Module 09 section for full detail and the
reasoning behind leaving each unfixed (mandate: no architecture redesign,
no new features, no schema changes unless critical):

1. **Frontend form validation** — ~50 of ~54 CRUD forms have no
   client-side validation (`FormDialog` disables native HTML5 validation
   and only the 4 auth pages adopted RHF+Zod). The single highest-value
   frontend fix identified.
2. **4 missing database indexes** — `AnswerEvaluation.ai_provider_id`,
   `OCRJob.ocr_provider_id`, `OCRJob.status`, `ReportJob.requested_by` —
   a small, contained schema migration.
3. **`exam_result_service.py`/`answer_evaluation_service.py` repository
   bypass** — a real architectural refactor to route their raw
   `self.session` queries through their (currently vestigial)
   repositories.
4. **N+1 query fix** in `AnalyticsService.get_question_wise()`.
5. **`UPLOAD_MAX_PAGE_COUNT` enforcement** — the config value exists but
   is never checked before OCR rasterizes an entire PDF into memory.
6. **Celery task retry idempotency** — retried OCR/document-ingestion
   tasks can currently create duplicate child rows.
7. **Frontend devDependency CVE remediation** — `vite`/`vitest` major
   version bump (2 critical, 2 high CVEs, dev/test-tooling only, zero
   production-bundle impact).

## Anticipated next modules (order not yet finalized)

1. **Email delivery** — wire an actual provider (SMTP/SES/etc.) to the
   already-implemented password-reset token flow.
2. **Notification delivery channel** — Module 07's `NotificationEvent`
   framework stores events (e.g. "result published") but has no email/
   in-app-push/SMS consumer yet; build one against the existing table
   rather than a schema change. Populates the `notification/` placeholder.
3. **Rubric-Based Marking** — `Rubric`/`RubricCriterion`/
   `MarkDistribution` (Module 04) still aren't read by any scoring path;
   Module 06's AI evaluator and Module 07's Teacher Review workflow
   compute/finalize marks independently of them. A distinct feature, not
   a byproduct of either module.
4. **Richer analytics visualizations** — Module 07's Analytics Dashboard
   renders figures as cards/plain-div bars (no charting library available
   in this stack yet); add real charts once a library is chosen.
5. **Per-institution confidence-threshold override** — the 90%/70%
   confidence-review bands (Module 06 ADR-040) and the pass/fail
   computation (Module 07) are fixed constants; make them configurable
   per institution once a concrete need arises.
6. **Multi-node Cloud Deployment / Infrastructure-as-Code** — Module 08
   delivered a single-host production Docker Compose stack plus
   Prometheus/Grafana monitoring; `infrastructure/terraform` and
   `infrastructure/k8s` remain empty placeholders for a genuine multi-node/
   managed-cloud target (managed Postgres/Redis, managed object storage,
   real container orchestration) — see the "Planned cloud path" section of
   [docs/deployment-guide.md](docs/deployment-guide.md).
7. **Import/Export implementation** — the Academic and Assessment
   Domains' `/import` and `/export` endpoints are documented skeletons
   only (Modules 03–04); wiring real CSV/Excel processing to them is
   deferred.
8. **Question option structuring** — `QuestionType.requires_options`
   flags MCQ/Matching/True-False types, but no `QuestionOption` table
   exists yet; question options currently live inside free-text
   `question_text`. Add a structured options table once a concrete UI
   need for it arises (Module 04, deferred — see
   [docs/question-bank-guide.md](docs/question-bank-guide.md)).
9. **Question Bank server-side filtering** — the Question Bank Dashboard
   filters category/type/difficulty/Bloom/approval-status client-side
   over one page of results; add real query-parameter filters (and
   likely a search index) once per-institution question-bank sizes
   outgrow that approach.
10. **Additional OCR providers** — implement one or more of the 5
    registered stub adapters (EasyOCR, PaddleOCR, Azure OCR, Google
    Vision, AWS Textract) once a concrete accuracy/cost/language need
    justifies moving beyond Tesseract — see
    [docs/ocr-pipeline-guide.md](docs/ocr-pipeline-guide.md#adding-a-new-ocr-provider).
11. **Additional AI providers** — implement the OpenAI or Anthropic stub
    adapters (or another provider) once a hosted-LLM evaluation option is
    actually wanted, following the exact same registry/adapter pattern —
    see [docs/ai-evaluation-guide.md](docs/ai-evaluation-guide.md).
12. **Chunked/resumable upload** — `StorageService`'s temp-key/promotion
    helpers exist for this, but no endpoint implements chunked upload
    yet (neither for answer scripts nor official documents); needed once
    file sizes or connection reliability make single-request multipart
    upload impractical.
13. **Question Bank promotion UI** — `ExtractedQuestion`/
    `ExtractedModelAnswer` already have nullable FKs into Module 04's
    bank (`linked_question_id`/`linked_answer_key_id`); a UI action to
    actually perform that promotion (with the required category/type/
    difficulty/Bloom-level curation) doesn't exist yet.
14. **Analytics caching/rollup** — Module 07's `AnalyticsService` computes
    every figure on demand (ADR-044); add a cache or materialized rollup
    once per-institution result volumes grow large enough for that to
    matter.
15. **Student-facing result view** — beyond the notification payload,
    there's no dedicated student-facing result-card screen for a
    published `ExamResult` yet (ADR-048).
16. **Microservice Extraction (conditional)** — only if/when a domain
    module's load or team ownership justifies it. The modular-monolith
    architecture was chosen specifically so this is a later *option*, not
    a day-one requirement — see `docs/architecture.md`.

## Non-goals for the foreseeable future

- Splitting into microservices before there's a concrete operational reason
  to (see `gateway/README.md`).
- Introducing a second database technology without a specific driver for it.
- Any change to `shared/` that turns it into a real npm workspace package
  before something actually needs to import from it (see
  [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)).
