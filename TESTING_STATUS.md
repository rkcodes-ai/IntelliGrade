# Testing Status

Snapshot as of Module 09 completion / **Version 1.0 certification**
(2026-07-23). Module 01–08's original snapshots are preserved below for
history.

## Module 09 — Release Certification (regression + 1 new regression test + live E2E)

**Backend (pytest): 1111 tests, 1111 passing, 0 failing** (1110 carried
forward + 1 new: `test_bulk_approve_lock_publish_via_api`, added as a
regression test for the critical route-ordering bug this module found
and fixed). **Coverage: 97% overall** — unchanged from Module 08.

**Frontend (Vitest): 552 tests, 552 passing, 0 failing. Coverage: 96.41%
statements** — unchanged from Module 08. **`npm run typecheck` and
`npm run build` now both genuinely pass** (previously broken by a stale
Module-04-era test fixture — see `CHANGELOG.md`'s `[1.0.0]` entry — which
also means the frontend production Docker image can now actually build,
confirmed via a real `npm run frontend:build` run).

**Quality gate**: `black`/`isort` clean. `ruff check .` — all checks
passed across the entire backend (the transient Windows Application
Control block noted in Module 08 did not recur this pass). `mypy app` —
26 errors in 8 files, the exact same pre-existing Module 02 baseline, 0
new.

**New this module — a real, live, single-run end-to-end script** (not
part of the durable suite; written, run, and deleted per this project's
established precedent) chained the entire v1.0 workflow in one continuous
story, proving genuine composition across every module boundary rather
than re-testing each module in isolation:

Official Question Paper (real Tesseract OCR) → Official Model Answer
(real Tesseract OCR) → Teacher Verification → Student Answer Script
Upload (real Tesseract OCR) → real AI Evaluation
(`LexicalHeuristicProvider`, genuinely computed — not pre-set marks,
confidence score 100.00) → Teacher Review (confirm) → Result Finalization
→ Approve → Lock (re-verified live: further evaluation edits correctly
blocked once locked) → Publish → real Analytics aggregation
(`result_count >= 1`) → real Report Generation (`reportlab` PDF, verified
`%PDF` magic bytes, 1856 bytes) → **9 real audit-log entries** spanning
the entire chain (`ocr_execution_started`, `ocr_processing_completed`
×3, `academic_entity_created` ×2, `answer_evaluation_generated`,
`answer_evaluation_confirmed`, `exam_result_finalized`, `approved`,
`locked`, `published`, `notification_created`). Passed on the first
complete run after 3 small fixture-format corrections (model-answer text
needed the pipeline's expected `"1) ..."` numbering format; the
`AnalyticsOverview`/`ReportJob` field names needed correcting to match
the real schemas rather than guessed names).

**Backup/Restore** (the last two steps of the requested end-to-end
workflow) were **not** live-run — this sandbox has no real Postgres/MinIO
(same standing constraint as Module 08; a local PostgreSQL 17 Windows
service exists but only ships a `data/` directory with no `bin/`
binaries at the registered install path, and the Windows Service Control
Manager itself refused to start it from this shell). Validated instead
at the level that is possible: `scripts/backup/*.sh` re-confirmed
syntactically valid (`bash -n`) and internally consistent with
`docker-compose.prod.yml`'s service names/volumes.

**Live verification**: `/health`, `/health/live`, `/health/ready`,
`/health/version`, `/metrics` (real Prometheus metrics), and
`/openapi.json` (494 paths, confirmed the 3 previously-broken
`/exam-results/bulk/*` routes are correctly present and — via the new
regression test — correctly *reachable*) all re-confirmed live after
restarting the dev server to pick up the fix.

## Module 08 — Regression validation (no new business-logic tests)

Module 08 is infrastructure/DevOps only — it adds no new business-logic
test suites. What was verified is that the full existing suite still
passes unchanged after the module's backend/infra edits
(`celery_app.py`, `config.py`, `session.py`, `redis.py`, `main.py`,
`health.py`), plus a new load-test script (not part of the durable
pytest/vitest suites — a real, runnable Locust definition).

**Backend (pytest): 1110 tests, 1110 passing, 0 failing. Coverage: 97%
overall — identical to the Module 07 baseline**, confirming zero
regressions from the pool-recycling/slow-query-logging/connect-timeout/
rate-limit-middleware/`/metrics` changes.

**Frontend (Vitest): 552 tests, 552 passing, 0 failing across 77 files.
Coverage: 96.41% statements — identical to the Module 07 baseline**
(no frontend file was modified this module).

**Quality gate**: `black --check`/`isort --check-only` clean on the full
backend. `ruff check .` — all checks passed (hit a transient Windows
Application Control block mid-module, same class of issue seen earlier in
this project with `scikit-learn`; cleared by this final pass). `mypy app`
— 26 errors in 8 files, the exact same pre-existing Module 02 baseline
(`auth_service.py`/`user_repository.py`/`role_repository.py`/
`refresh_token_repository.py`/`schemas/base.py`/`middleware/rate_limit.py`/
`main.py`), zero attributable to Module 08. One real new finding was fixed
to get there: the `@limiter.exempt` decorators added to
`app/api/health.py` tripped mypy's strict-mode `disallow_untyped_decorators`
(slowapi ships no type stubs) — resolved with a targeted
`# type: ignore[untyped-decorator]` per line.

**Frontend quality gate — 2 pre-existing findings discovered, neither
introduced by Module 08 (no frontend file was touched):**
`npm run typecheck` fails on one Module-04-era test fixture
(`AssessmentDashboardPage.test.tsx:75` assigns a `description` field the
real `Subject` type doesn't have); `npm run format:check` reports 110
files with pre-existing Prettier drift. Neither affects the actual test
suite (Vitest transforms via esbuild, doesn't type-check) — both are
documented, not fixed, per this module's "don't modify any previous
module" constraint. See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

**Real load test** (`backend/loadtests/locustfile.py`, run headlessly
against the live backend, 20 users/45s): 612 requests, 15.05 req/s
aggregate. Result highlights: health/liveness/version/docs endpoints all
healthy with single-digit-ms median latency; `/health/ready` correctly
returned 503 (no real DB/Redis in this sandbox) at ~4.1s per call
pre-fix, ~3.1s post-fix (bounded connect timeouts); `/openapi.json`
genuinely returned 429 under load, confirming `SlowAPIMiddleware`'s
global rate limiting is enforced end-to-end, not just configured.

**Live verification**: `/health`, `/health/live`, `/health/ready`,
`/health/version` all responded correctly; `/metrics` confirmed exposing
real Prometheus metrics (`http_requests_total`, `http_request_duration_seconds_*`,
etc.); `/openapi.json` confirmed live with 494 paths and `/metrics`
correctly excluded from the schema.

**Not run**: `docker compose ... config` (no Docker CLI/daemon exists in
this sandbox — YAML-syntax-validated instead via `yaml.safe_load()`);
`nginx -t` (no nginx binary — brace-balance-checked instead). See
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Module 07 — Backend (pytest)

**1110 tests, 1110 passing, 0 failing.** Coverage: 97%+ overall (target ≥97%).

`tests/module07_helpers.py` provides shared fixture builders on top of
`test_official_exam_documents_api._create_exam` (full exam hierarchy
including `AssessmentConfiguration` for pass/fail thresholds and
`StudentEnrollment` for batch-scoped finalization and roll-number
search) plus a helper that directly constructs `AnswerEvaluation` rows
with `final_marks` already set — the AI computation itself is already
covered by Module 06's real-provider tests, so these bypass the real
provider call to focus purely on Module 07's own new state-machine/
aggregation logic.

- `tests/test_exam_result_service.py` (11 tests) — the full
  `draft → under_review → approved → locked → published` state machine:
  successful finalize with correct totals, rejection when questions are
  unresolved or an exam session has no evaluations at all, every
  out-of-order transition rejected with a 409, `unlock()` returning a
  result to `draft` and re-enabling edits, bulk finalize-exam/
  finalize-batch (batch-scoped to actually-enrolled students only), and
  `bulk_transition` correctly reporting un-finalized sessions as failures
  rather than raising.
- `tests/test_exam_results_api.py` (5 tests) — the same lifecycle
  through the real HTTP/RBAC layer, plus the deliberate `exam_results:unlock`
  permission withholding from the default teacher grant (ADR-042).
- `tests/test_answer_evaluations_api.py` (extended, +8 tests this
  module) — reject (clears `final_marks`, keeps `suggested_marks`,
  requires a `reason`), rerun (recomputes over an already-reviewed row,
  snapshotting pre-rerun state to `EvaluationHistory` first), a plain
  re-trigger no longer silently overwriting a teacher's prior decision,
  and a locked `ExamResult` blocking further confirm/override/reject/
  evaluate calls with a 409.
- `tests/test_teacher_review_dashboard_service.py` (3 tests),
  `tests/test_analytics_service.py` (4 tests) — the 5 independent
  dashboard bucket counts, filtering by exam id, and analytics
  correctness verified against hand-computed expected values (pass/fail
  %, confidence distribution, teacher-override %, average AI-vs-teacher
  difference, most-difficult-question ranking).
- `tests/test_search_service.py` (4 tests) — student (by name and
  `StudentEnrollment.roll_number`), subject, and question search, plus
  institution-scoped isolation.
- `tests/test_report_tasks.py` (10 tests) — real PDF (`reportlab`,
  verified via `%PDF` magic bytes)/Excel (`openpyxl`, verified via the
  `PK` zip magic bytes)/CSV generation, run directly against
  `_run_report_generation` (bypassing Celery itself, same convention as
  `test_official_document_tasks.py`) — includes all 7 report types
  resolving successfully, not just one.
- `tests/test_reports_api.py`,
  `tests/test_notifications_api.py`,
  `tests/test_teacher_review_analytics_search_api.py` — HTTP-level
  smoke tests confirming the real endpoint/RBAC wiring on top of the
  service-level correctness tests above, including `ExamResultService.
  publish()` genuinely writing a `NotificationEvent` a student can list,
  see the unread count for, and mark read.

### Run it

```bash
cd backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=97
```

## Module 07 — Frontend (Vitest)

**552 tests, 552 passing, 0 failing** across 77 files, 96.41% coverage.

New coverage added this module: `teacherReviewApiModules.test.ts` (28
tests — every Module 07 `api/*.ts` module's URL wiring, plus the two new
`answerEvaluations.ts` functions, `rejectAnswerEvaluation`/
`rerunAnswerEvaluation`), 6 new `pages/ocr/*.tsx` screens (Teacher
Review Dashboard, Result Finalization & Locking, Analytics Dashboard,
Reports, Global Search, Notifications — built by 3 parallel background
agents, 2 screens each), and `AnswerEvaluationDetailPage`'s reject/rerun
extension (built directly, alongside its existing confirm/override
actions). The Result Finalization screen's tests explicitly assert that
Approve/Lock/Publish/Unlock actions only render for the correct
`(status, permission)` combination — the same conditional-action-gating
contract Module 06 established for Teacher Review actions.

### Run it

```bash
cd frontend
npm run test:coverage
```

## Module 07 — Code quality gates

| Tool | Backend | Frontend |
|---|---|---|
| Formatter (`black` / `prettier`) | ✅ Clean | n/a (not run separately this pass) |
| Import order (`isort`) | ✅ Clean | n/a |
| Linter (`ruff` / `eslint`) | ✅ Clean | ✅ Clean |
| Type checker (`mypy app` / `tsc`) | ✅ Clean (only pre-existing, out-of-scope Module 02 errors — same 26 as Modules 05/06, none in any Module 07 file) | ✅ Clean |

---

## Module 06 — Backend (pytest)

**1060 tests, 1060 passing, 0 failing.** Coverage: 97.12% overall (target ≥97%).

Every one of the 8 new entities has its own `test_*_api.py` file following
the same convention as Modules 03–05 (create/get/update/soft-delete/
restore where applicable, requires-institution-header, non-privileged-role
rejection, paginated list envelope). `test_official_exam_documents_api.py`
(14 tests) covers multipart upload with `document_type`, duplicate-checksum
rejection, and the retry/cancel state-machine guards, mirroring
`test_answer_scripts_api.py`'s conventions but stopping the parent chain
at `Exam` (exam-level, not per-student — ADR-035).

Real, non-mocked tests exercise both new capability classes end-to-end:

- `tests/test_official_document_tasks.py` (6 tests) — the full ingestion
  pipeline orchestration (`_run_pipeline`), run directly against the real
  Tesseract binary for all three document types (question paper, model
  answer, mark scheme), asserting the exact extracted question text/marks
  and mark-scheme ranges from synthetically rendered images.
- `tests/test_ai_providers.py` (11 tests) — the real
  `LexicalHeuristicProvider`, calibration-asserting that a verbatim match
  scores near-100% confidence and full marks, a good paraphrase scores
  moderately, a poor/off-topic answer scores low confidence (forcing
  mandatory review per ADR-040 even when one signal is fooled), and a
  blank answer is handled as a confident zero rather than a low-confidence
  guess.
- `tests/test_answer_evaluations_api.py` (9 tests) — full API-level
  evaluation runs including an idempotent-upsert check, a rejection when
  a question has no maximum marks yet, confirm/override (including
  rejecting an override above `max_marks`), and a genuinely low-confidence
  case verified to produce `review_status="pending_review"`.
- `tests/test_mark_scheme_service.py` (8 tests),
  `tests/test_official_document_extraction_service.py` (9 tests),
  `tests/test_answer_extraction_service.py` (4 tests) — the pure
  extraction/expansion logic, including the exact brief example ("Q1-12 =
  1 mark, Q13-17 = 2 marks, Q18-25 = 14 marks").

Two real bugs were found and fixed via this testing, both documented in
the new guides: a Module 05 `orientation` preprocessing false-positive
(worked around via configuration, no frozen file touched) and two AI
provider calibration errors (bigram-matching mismatch; a reasoning-score
scale that made a verbatim match read as low confidence) — both caught
before any test asserted against the provider's final output.

### Run it

```bash
cd backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=97
```

## Module 06 — Frontend (Vitest)

**490 tests, 490 passing, 0 failing** across 70 files, 96.42% coverage.

New coverage added this module: `officialExamApiModules.test.ts` (35
tests — every Module 06 `api/*.ts` module's URL wiring, including the
multipart-upload/verify-action/expand-endpoint edge cases), and all 9 new
`pages/ocr/*.tsx` screens (built by 3 parallel background agents plus one
page — the document detail/routing hub — written directly). The Mark
Scheme Verification screen's test explicitly asserts the "Preview
Expansion" panel renders from a real (mocked) call to the live
`GET /mark-scheme-ranges/expand` endpoint, never a client-computed value.
The Answer Evaluation Detail screen's test explicitly asserts all 7 AI
signal labels and values render individually from a mocked response — the
explainability requirement (ADR-039) is a testable UI contract, not just
a backend one.

### Run it

```bash
cd frontend
npm run test:coverage
```

## Module 06 — Code quality gates

| Tool | Backend | Frontend |
|---|---|---|
| Formatter (`black` / `prettier`) | ✅ Clean | n/a (not run separately this pass) |
| Import order (`isort`) | ✅ Clean | n/a |
| Linter (`ruff` / `eslint`) | ✅ Clean | ✅ Clean |
| Type checker (`mypy app` / `tsc`) | ✅ Clean (only pre-existing, out-of-scope Module 02 errors — same 26 as Module 05, none in any Module 06 file) | ✅ Clean |

---

## Module 05 — Backend (pytest)

**944 tests, 944 passing, 0 failing.** Coverage: 97.54% overall (target ≥97%).

Every one of the 11 OCR pipeline entities has its own `test_*_api.py` file
following the same convention as Modules 03/04 (create/get/update/
soft-delete/restore, requires-institution-header, non-privileged-role
rejection, paginated list envelope). `test_answer_scripts_api.py` (17
tests) additionally covers multipart upload, duplicate-checksum rejection
(409, with an `allow_duplicate` override), bulk upload with per-item error
collection, and the retry/cancel state-machine guards. `test_ocr_results_api.py`
covers the nested `GET /ocr-results/{id}/blocks` tree endpoint.

Five test files exist specifically to close coverage gaps left by the
directly-written (not agent-generated) cross-cutting infrastructure:

- `tests/test_image_processing.py` (33 tests) — every function in all 14
  `app/services/image_processing/` modules, against small synthetic numpy
  arrays (no real scanned images needed).
- `tests/test_ocr_providers.py` (10 tests) — the **real** Tesseract
  adapter, run against real Tesseract 5.5.0 (installed via `winget` in
  this sandbox specifically to enable this), plus all 5 stub providers'
  `OCRProviderNotImplementedError` behavior and the registry.
- `tests/test_ocr_tasks.py` (6 tests) — the full Celery pipeline
  orchestration function (`_run_pipeline`), run directly (not through a
  real Celery worker/broker round-trip — see
  [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) for why live dispatch
  isn't possible in this sandbox) against the real Tesseract binary,
  covering the happy path, an institution-level
  `OCRConfiguration` override, a missing-provider failure, a
  missing/cancelled-script early-return, and blank-page handling.
- `tests/test_storage_service.py` (16 tests) — the real `StorageService`
  implementation against a `MagicMock` Minio client, required discovering
  that a module-level `pytest.fixture(autouse=True)` of the same name
  shadows `conftest.py`'s global autouse fixture (which otherwise
  monkeypatches storage for every other test in the suite).
- `tests/test_text_normalization_service.py` (9 tests) — every pure
  normalization function plus the full `normalize_text()` pipeline.

Every service is exercised through real request/response cycles against
an in-memory SQLite database (not mocks) — same convention as Modules
02–04. Object storage uses a real (Minio-SDK-shaped) mock in
`test_storage_service.py` and an in-memory dict fake everywhere else (see
[storage-guide.md](docs/storage-guide.md#testing)); OCR uses the real
installed Tesseract binary throughout, not a mocked adapter.

### Run it

```bash
cd backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=97
```

## Module 05 — Frontend (Vitest)

**407 tests, 407 passing, 0 failing** across 60 files, 96.42% coverage.

New coverage added this module: `ocrApiModules.test.ts` (32 tests —
every Module 05 `api/*.ts` module's URL wiring, including the 7
hand-written non-`createCrudApi` modules and their multipart-upload/
nested-tree/no-filter-support edge cases), and all 10 OCR Pipeline pages
(built by 5 parallel background agents across two waves, each independently
verified tsc/eslint/vitest-clean before being accepted).

A real gap was found via the full-suite coverage run (not caught by any
individual agent's own scoped test run): all 8 Module 05 `api/*.ts`
modules had 0% coverage — each screen's own tests only exercised the
module indirectly through mocked hooks, never the module's actual Axios
URL wiring directly. Closed by `ocrApiModules.test.ts`, mirroring
`assessmentApiModules.test.ts`'s established per-module URL-assertion
pattern from Module 04.

### Run it

```bash
cd frontend
npm run test:coverage
```

## Module 05 — Code quality gates

| Tool | Backend | Frontend |
|---|---|---|
| Formatter (`black` / `prettier`) | ✅ Clean | n/a (not run separately this pass) |
| Import order (`isort`) | ✅ Clean | n/a |
| Linter (`ruff` / `eslint`) | ✅ Clean | ✅ Clean |
| Type checker (`mypy app` / `tsc`) | ✅ Clean (only pre-existing, out-of-scope Module 02 errors in `user_repository.py`/`role_repository.py`/`refresh_token_repository.py`/`schemas/base.py`/`core/logging.py`/`middleware/rate_limit.py`/`services/auth_service.py`/`main.py` — none in any Module 05 file) | ✅ Clean |

---

## Module 04 — Backend (pytest)

**794 tests, 794 passing, 0 failing.** Coverage: 98.08% overall.

Every one of the 37 assessment entities has its own `test_*_api.py` file
covering: create (as super_admin and as a permission-scoped role),
requires-institution-header (422), duplicate-code/name rejection where
applicable (409), nonexistent-parent rejection (404), non-privileged-role
rejection (403), get/update/soft-delete/restore round-trip, get-nonexistent
(404), paginated list envelope shape, and — new this module — real bulk-create
success/partial-error coverage (`POST /{prefix}/bulk`) and the
`GET /{prefix}/export` / `POST /{prefix}/import` skeleton responses for
every entity. `Question`/`QuestionPaper` additionally get workflow tests
(submit-for-review/approve/reject state-transition guards, version
snapshots, tag management). `test_exam_schedules_api.py` covers
room/time-overlap rejection (mirroring Module 03's
`test_class_schedules_api.py`).

Two coverage classes worth noting explicitly:

- Every FK-revalidation branch in every `update()` service method (both
  the "new FK exists" success path and the "new FK missing → 404" path)
  is exercised — these were the last gaps closed to cross the 96%
  threshold, since no prior test PATCHed a foreign-key field on an
  existing row.
- `EvaluationHistory`'s router intentionally has no
  `PATCH`/`DELETE`/restore — only `GET ""`, `GET "/{id}"`, `POST ""` are
  tested, matching its append-only design.

Every service is exercised through real request/response cycles against
an in-memory SQLite database (not mocks) — same convention as Modules
02–03.

### Run it

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

## Module 04 — Frontend (Vitest)

**331 tests, 331 passing, 0 failing** across 49 files, 96.42% coverage.

New coverage added this module: `assessmentApiModules.test.ts` (every
Module 04 `api/*.ts` module's URL wiring, including the 5 hand-written
non-`createCrudApi` modules — `questions.ts`, `questionPapers.ts`,
`evaluationHistory.ts`, `questionVersions.ts`, `questionApprovals.ts` —
and their extra workflow functions), and all 12 Assessment Domain pages —
full create/edit/delete flows for every page, workflow-action tests
(submit-for-review/approve/reject/version-snapshot) for the two
approval-workflow entities, and multi-level drill-down tests for the
three nested-CRUD screens (Question Paper Builder and Rubric Builder both
go three levels deep: parent → section/criterion → mapping/mark-band;
Blueprint Builder and Exam Management go one level; Answer Key Builder
has one level with five sibling child sub-panels).

A real, previously-latent bug was found and fixed via this pass:
`ToastProvider`'s auto-dismiss `setTimeout` was never cleared on unmount,
so a toast firing after a test's component tree had torn down triggered a
spurious "state update after unmount" error, non-deterministically
attributed to whichever test happened to be running when the stale timer
fired — this caused `npm run test:coverage` to exit 1 (build failure)
even when every test passed. Fixed by tracking pending timeout ids and
clearing them in a `useEffect` cleanup.

### Run it

```bash
cd frontend
npm run test:coverage
```

## Module 03 — Backend (pytest)

**314 tests, 314 passing, 0 failing.** Coverage: 96.55% overall.

Every one of the 20 academic entities has its own `test_*_api.py` file
covering: create (as super_admin and as a permission-scoped role),
requires-institution-header (422), duplicate-code/name rejection (409),
nonexistent-parent rejection (404), non-privileged-role rejection (403),
get/update/soft-delete/restore round-trip (including the
`MissingGreenlet` regression check on `updated_at`), get-nonexistent
(404), and paginated list envelope shape. Entity-specific business rules
get additional tests: `test_academic_years_api.py`/
`test_semesters_api.py` (date-overlap rejection),
`test_class_schedules_api.py` (room-double-booking rejection),
`test_teacher_assignments_api.py`/`test_student_enrollments_api.py`
(conflict/uniqueness rejection). `test_institutions_api.py` additionally
covers membership assign/revoke and the `/mine` endpoint (super_admin sees
all institutions, a regular member sees only their own).

Every service is exercised through real request/response cycles against
an in-memory SQLite database (not mocks) — same convention as Module 02.

### Run it

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

## Module 03 — Frontend (Vitest)

**159 tests, 159 passing, 0 failing** across 36 files, ~96.2% coverage.

New coverage added this module: `institutionSlice`, `createCrudApi` (+
every entity API module's URL wiring), `usePaginatedList`/
`useCrudMutations`/`useSelectOptions` (via `renderHook`),
`InstitutionSwitcher`, every shared component (`DataTable`,
`PaginationControls`, `SearchInput`, `ConfirmDialog`, `FormDialog`,
`FormField`, `PageHeader`), and all 11 Academic Domain pages — a full
create/edit/delete-dialog flow for `InstitutionsPage`/`CampusesPage`, a
parent-select-dropdown flow for `DepartmentsPage`, and a list+create smoke
test for the remaining 8 pages (including the 7-FK-select
`StudentEnrollmentsPage`). Existing `Sidebar`/`Topbar`/`DashboardLayout`
tests were updated for the new `institution` Redux slice and
`QueryClientProvider` requirement (both components now depend on
TanStack Query via the institution switcher).

A jsdom + Radix compatibility fix was required: `hasPointerCapture`/
`setPointerCapture`/`releasePointerCapture`/`scrollIntoView` polyfills
were added to `src/tests/setup.ts` (jsdom implements neither the Pointer
Events API nor `scrollIntoView`, and the new `Dialog` component — built on
`@radix-ui/react-dialog` — hangs indefinitely under `userEvent` without
them).

### Run it

```bash
cd frontend
npm run test:coverage
```

## Module 03 — Code quality gates

| Tool | Backend | Frontend |
|---|---|---|
| Formatter (`black` / `prettier`) | ✅ Clean | n/a (not run separately this pass) |
| Import order (`isort`) | ✅ Clean | n/a |
| Linter (`ruff` / `eslint`) | ✅ Clean | ✅ Clean (1 pre-existing accepted warning) |
| Type checker (`mypy --strict` / `tsc`) | ✅ Clean (only pre-existing, out-of-scope Module 02 errors in `user_repository.py`/`schemas/base.py`/`core/logging.py`) | ✅ Clean |

---

## Module 02 — Backend (pytest)

**87 tests, 87 passing, 0 failing.** Coverage: 95% overall.

| File | Covers |
|---|---|
| `test_auth_flow.py` | Login, logout, refresh rotation, remember-me, lockout after N failed attempts, failed-login counter survives the exception path |
| `test_rbac.py` | Role/permission resolution, `require_roles`/`require_permissions` dependency enforcement across all four seeded roles |
| `test_users_api.py` | `/users/me`, admin CRUD, activate/deactivate/soft-delete, permission gating |
| `test_sessions_api.py` | List sessions, `is_current` detection, revoke (single + family) |
| `test_password_policy.py` | Length/character-class enforcement, weak-password rejection |
| `test_password_reset_flow.py` | Forgot/reset password, generic-response anti-enumeration, reuse-prevention against `password_history` |
| `test_security_hardening.py` | JWT tampering rejection, rate-limit enforcement, token reuse triggers family revocation |

Every security-critical service (`auth_service.py`, `token_service.py`,
`rbac.py`, `password_policy.py`) is exercised through real request/response
cycles against an in-memory SQLite database (not mocks) — see ADR-008.

### Run it

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

## Module 02 — Frontend (Vitest)

**79 tests, 79 passing, 0 failing** across 20 files, ~97% coverage.

Covers: `authSlice`, all three route guards, every new page (Login,
ForgotPassword, ResetPassword, Profile, Sessions, Unauthorized, Landing,
NotFound, DashboardHome), `Topbar` sign-out flow, `AuthProvider` session
bootstrap, the Axios client's request/response interceptors (token
injection, 401-triggered silent refresh with in-flight de-duplication,
logout-on-refresh-failure), every `api/*.ts` module, `ErrorBoundary`,
layouts, `Footer`, `ThemeProvider`, `useHealthCheck`, and the route table
structure. `App.tsx` is excluded from coverage (composition-root wiring
only, renders the real `createBrowserRouter` which hits a known jsdom
`AbortSignal` incompatibility — same class of issue documented for
`createMemoryRouter` in the guard tests).

### Run it

```bash
cd frontend
npm run test:coverage
```

## Module 02 — Code quality gates

| Tool | Backend | Frontend |
|---|---|---|
| Formatter (`black` / `prettier`) | ✅ Clean | ✅ Clean |
| Import order (`isort`) | ✅ Clean | n/a |
| Linter (`ruff` / `eslint`) | ✅ Clean | ✅ Clean (1 pre-existing accepted warning) |
| Type checker (`mypy` / `tsc`) | ⚠️ Not runnable in this sandbox (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)) | ✅ Clean |

---

## Module 01 snapshot (2026-07-15, historical)

### Backend (pytest)

**26 tests, 26 passing, 0 failing.** Coverage: 76% overall (up from 67%
before this audit pass), with every security-critical module at 100%.

| File | Tests | What it covers |
|---|---|---|
| `test_health.py` | 4 | `/health`, `/health/live`, `/health/ready`, `/health/version` smoke tests |
| `test_security.py` | 6 | Password hashing round-trip, wrong-password rejection, 72-byte limit, JWT create/decode for both token types — **added this pass**; this module previously had zero test coverage and a critical bug (see [CHANGELOG.md](CHANGELOG.md)) |
| `test_config.py` | 8 | Production `SECRET_KEY` safety validator (placeholder rejection, minimum length, valid-key acceptance), CORS parsing, DB/Celery URL construction — **added this pass** |
| `test_exceptions.py` | 2 | Validation-error handling survives a custom validator raising `ValueError` (previously would crash — see [CHANGELOG.md](CHANGELOG.md)) — **added this pass** |
| `test_logging.py` | 2 | JSON renderer fallback for non-serializable log values, `configure_logging()` idempotency — **added this pass** |
| `test_middleware.py` | 4 | Request ID header propagation (generated + client-supplied), request ID reaching structured logs via contextvars, security headers present — **added this pass** |

### Run it

```bash
cd backend
pytest                    # full suite + coverage report
pytest tests/test_security.py -v   # one file
```

### Frontend (Vitest)

**8 tests, 8 passing, 0 failing** across 3 files.

| File | Tests | What it covers |
|---|---|---|
| `Button.test.tsx` | 3 | Renders children, fires `onClick`, respects `disabled` |
| `uiSlice.test.ts` | 3 | Theme toggle, explicit theme set, sidebar collapse toggle |
| `Sidebar.test.tsx` | 2 | Accessible name present for nav links both expanded and collapsed — **added this pass** as a regression test for a real WCAG failure found and fixed during this audit |

### Run it

```bash
cd frontend
npm run test               # Vitest, single run
npm run test:coverage      # with coverage report
```

### Frontend (Playwright e2e)

2 specs exist in `frontend/src/tests/e2e/landing.spec.ts` (landing page
renders, unknown route shows 404). **Not re-executed in this audit pass**
— see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for why, and what was
used instead (a direct headless-browser smoke check covering the same
routes plus a live backend call, with zero console errors observed).

### Run it

```bash
cd frontend
npm run test:e2e
```

### What was verified live (not just unit-tested)

- Backend booted via `uvicorn`, every health endpoint curled directly,
  including confirming `/health/ready` returns a real `503` when
  dependencies are unreachable.
- Frontend dev server booted via `vite`, driven through a real headless
  Chromium session (landing page, `/dashboard`, and an unknown route all
  rendered correctly; the live backend health check succeeded end-to-end
  with zero browser console errors).
- Both critical Docker build-context bugs fixed this pass were verified by
  reproducing each Dockerfile stage's exact commands in an isolated
  directory (no Docker daemon available — see
  [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)).

### Code quality gates

| Tool | Status |
|---|---|
| `black` | ✅ Clean |
| `isort` | ✅ Clean |
| `ruff` | ✅ Clean (0 errors) |
| `mypy` | ⚠️ Could not run in this environment (Windows Application Control policy blocks its DLL — see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)); already non-blocking in CI |
| `eslint` | ✅ Clean (1 pre-existing, accepted warning — `react-refresh/only-export-components` on a context+hook file, a common accepted pattern) |
| `prettier` | ✅ Clean |
| `tsc` | ✅ Clean |
