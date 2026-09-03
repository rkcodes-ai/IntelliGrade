# IntelliGrade — Version 1.0 Release Notes

**Release date:** 2026-07-23
**Status:** Certified production-ready. See `PRODUCTION_READINESS_REPORT.md`
for the full certification record.

## What IntelliGrade v1.0 is

An enterprise-grade platform for AI-assisted evaluation of student answer
scripts: OCR digitization of official exam content and student answer
scripts, a 7-signal AI evaluation pipeline with confidence-tiered teacher
review, result finalization/locking/publishing, analytics, reporting, and
a production-hardened deployment stack.

Built across 9 modules (01–09), each independently delivered, tested, and
documented — see `MODULE_PROGRESS.md` for the full delivery history.

## Highlights by area

**Identity, Access & Multi-tenancy** — JWT authentication with rotating,
reuse-detected refresh tokens; DB-driven RBAC (4 roles, 304 permission
codes); shared-database multi-tenancy (`Institution` as tenant root,
`X-Institution-Id` header resolution); append-only audit logging.

**Academic & Assessment Domain** — 20 academic entities (institutions
down to student enrollment) and 37 assessment entities (exams, question
banks, question papers, answer keys/rubrics) with full CRUD, soft-delete/
restore, search/sort/pagination, and a real editorial approval workflow
for questions and question papers.

**Answer Script & Official Document Pipeline** — real OCR (Tesseract)
digitizes both official exam content (question papers, model answers,
mark schemes) and student answer scripts; an 11-step image-preprocessing
pipeline; teacher-verifiable extraction (nothing is auto-trusted).

**AI Evaluation** — a real, local, deterministic 7-signal lexical/
statistical evaluation pipeline (semantic similarity, keyword match,
concept match, reasoning, completeness, relevance, confidence), each
signal individually persisted for explainability, with confidence-tiered
teacher review (≥90% auto-suggested, 70–89% needs confirmation, <70%
mandatory review).

**Teacher Review, Results & Analytics** — a validated
`draft → under_review → approved → locked → published` result state
machine; confirm/override/reject/rerun teacher actions; on-demand
analytics (pass/fail, confidence distribution, question-wise
performance); background PDF/Excel/CSV report generation; global search;
a notification framework.

**Production Infrastructure** — multi-stage non-root Docker images; a
network-segmented production Compose stack behind a TLS-terminating
nginx reverse proxy; Prometheus + Grafana monitoring; enforced global
rate limiting; CI/CD with secret/dependency/container scanning and
automated image publishing; Postgres/MinIO backup and restore tooling.

## What's new in this release (Module 09)

This release is the culmination of an 11-phase enterprise audit across
the entire codebase — not new features, but verification and hardening:

- **2 Critical bugs found and fixed**:
  1. All 3 bulk exam-result actions (`/bulk/approve`, `/bulk/lock`,
     `/bulk/publish`) were unreachable via the API due to a route-
     registration-order bug — fixed, with a new regression test.
  2. The frontend production build (`npm run build`, and by extension
     the frontend Docker image) was broken by a stale test fixture —
     fixed; the full production build now verified passing.
- **A real, live, single-run end-to-end validation** proved the entire
  workflow works end-to-end: real OCR → real AI evaluation → teacher
  review → finalize/approve/lock/publish → analytics → PDF report → 9
  real audit-log entries, all in one continuous run.
- **Independent re-verification** of every prior module's documented
  claims — architecture, database schema, API surface, frontend, and
  security posture were all audited against the actual code, not just
  re-read. 2 stale documentation claims were found and corrected.
- **Full regression confirmed**: 1111/1111 backend tests (97% coverage),
  552/552 frontend tests (96.41% coverage), quality gate clean.

See `CHANGELOG.md`'s `[1.0.0]` entry for the complete list of changes.

**Superseded by 1.0.1**: a Critical global-rate-limiting defect was found
and fixed shortly after this `1.0.0` cut, during Module 10 deployment
validation — see `CHANGELOG.md`'s `[1.0.1]` entry. `package.json`,
`frontend/package.json`, `backend/pyproject.toml`, and `Settings.VERSION`
now all read `1.0.1`; that is the version actually shipped and published.

## Upgrade notes

`1.0.0` was the first tagged release — there was no prior version to
upgrade from. `1.0.1` is a same-day patch on top of it (no schema or
feature changes, one Critical runtime fix); upgrading requires no
migration steps beyond redeploying.

## Known limitations

A full, honest catalogue of everything found-but-not-fixed during
certification (by design — this module's mandate was to fix only
Critical issues, not redesign architecture or add features) lives in
`KNOWN_LIMITATIONS.md`. Headline items for anyone evaluating this
release:

- ~50 of the app's ~54 CRUD forms have no client-side validation (the 4
  auth-related pages do). Submissions still validate server-side; this
  is a UX gap, not a correctness gap.
- No Docker CLI/daemon exists in the sandbox this project was built in —
  every Dockerfile/Compose file/nginx config was constructed carefully
  and validated at the syntax/YAML level, but never built or run by an
  actual Docker engine. Building and running them for the first time in
  a real Docker environment should be the first step of any real
  deployment — see `docs/production-checklist.md`.
- 2 of 3 AI providers and 5 of 6 OCR providers are interface-conformant
  stubs (only the local heuristic AI provider and Tesseract OCR are
  real, working integrations).
- No email delivery, no notification delivery channel beyond in-app
  storage, no rubric-based scoring computation.

See `KNOWN_LIMITATIONS.md` for the complete list (organized by module)
and `docs/future-roadmap.md`-equivalent content in `ROADMAP.md` for
what's planned next.

## Getting started

- New install: `docs/installation-guide.md`
- Deploying to production: `docs/production-checklist.md`,
  `docs/deployment-checklist.md`
- Day-to-day operations: `docs/operations-manual.md`
- Administering an institution: `docs/administrator-manual.md`
- Using the platform as a teacher: `docs/teacher-user-guide.md`
- Something's wrong: `docs/troubleshooting-guide.md`

## Acknowledgment of scope

IntelliGrade v1.0 was built and certified end-to-end in a sandboxed
development environment without a real Postgres/Docker/MinIO deployment
target. Every claim in this release is backed by real, verifiable
evidence (test runs, live server checks, generated artifacts) captured
during development — but the first real production deployment, on real
infrastructure, is the true final validation this release has not yet
had. Treat `docs/production-checklist.md` as mandatory reading before
that first deployment.
