# Teacher Review, Result Finalization & Analytics Guide (Module 07)

Module 06 produces a confidence-tiered `AnswerEvaluation` row per
(student answer × extracted question) pair. Module 07 is what happens
next: a teacher works through those suggestions, marks get finalized and
locked into an official result, and everyone downstream — teachers,
institution admins, and (for their own results only) students — gets
dashboards, analytics, reports, search, and notifications built on top.

Nothing here creates an examination or evaluates an answer itself — see
[official-document-guide.md](official-document-guide.md) and
[ai-evaluation-guide.md](ai-evaluation-guide.md) for those. Module 07 is
purely additive: no Module 01–06 table, model, or endpoint is modified.

## Teacher Review actions (Features 2/3, ADR-043)

`AnswerEvaluationService` (Module 06) already had `confirm()`/`override()`.
Module 07 adds two more actions on the same table, no new table:

- **`reject()`** — discards the AI evaluation entirely. Sets
  `review_status = "teacher_rejected"` and clears `final_marks`, but
  **never touches `suggested_marks`** — the original AI suggestion stays
  visible for reference even after rejection, same "never overwrite AI
  values" rule `override()` already followed. Requires a `reason` (stored
  in `notes`).
- **`rerun()`** — force a fresh AI pass even over an already-reviewed row.
  Before recomputing, it writes the *pre-rerun* state to
  `EvaluationHistory` (Module 04, unmodified) so a rerun is never a
  silent, unrecoverable overwrite — a teacher can always see what the row
  looked like immediately before the rerun.

A subtler fix shipped alongside these: previously, calling
`POST /answer-evaluations` again on an already-reviewed row would
silently recompute and overwrite the teacher's confirm/override/reject
decision. `evaluate_question()` now checks `review_status` first — if a
teacher has already acted, a plain re-trigger returns the existing row
unchanged. Only `rerun()` (which snapshots history first) can force past
that.

## Result Finalization & Locking (Features 4/5, ADR-042)

`ExamResultService` owns one validated state machine, one row per
`ExamSession` (`exam_results`, unique on `exam_session_id`, created
lazily by the first finalize call):

```text
draft ──finalize──▶ under_review ──approve──▶ approved ──lock──▶ locked ──publish──▶ published
  ▲                                                                  │
  └──────────────────────────── unlock ─────────────────────────────┘
```

- **`finalize_student(exam_session_id)`** — requires every question in
  that session to already have `final_marks` (i.e. every `AnswerEvaluation`
  has been confirmed/overridden/rejected+overridden — not left
  `pending_*`), sums `max_marks`/`final_marks` into a snapshot
  (`total_max_marks`/`total_marks`), and moves the result to
  `under_review`.
- **`finalize_exam(exam_id)`** / **`finalize_batch(exam_id, batch_id)`** —
  bulk variants of the same call across every `ExamSession` for an exam,
  or every enrolled student in a batch sitting that exam
  (`StudentEnrollment.batch_id`). Failures are collected and reported
  back per-session, never raised — one student's incomplete review
  doesn't block finalizing everyone else.
- **`approve()`/`lock()`/`publish()`** — each requires the exact prior
  status (`under_review`/`approved`/`locked` respectively) or raises a
  409. `publish()` additionally writes a `result_published`
  `NotificationEvent` for the student.
- **`unlock()`** — the one backward transition, from `locked` **or**
  `published` back to `draft`. Gated on its own permission
  (`exam_results:unlock`), deliberately withheld from the default teacher
  grant — an institution_admin/super_admin action, not a routine teacher
  one.
- **`bulk_transition(exam_id, action)`** — Feature 11's bulk
  approve/lock/publish, same "collect failures, don't raise" shape as
  bulk finalize.

Once a session's `ExamResult.status` is `locked` or `published`,
`AnswerEvaluationService._ensure_not_locked()` rejects any further
confirm/override/reject/evaluate_question(force=True) call for that
session with a 409 — enforced once, centrally, not duplicated per action.

## Analytics (Feature 7, ADR-044)

`AnalyticsService` computes every figure on demand — no cache, no
materialized view, no scheduled job — by joining
`ExamResult`/`AnswerEvaluation` through the existing Module 03/04
hierarchy (`Exam → Assessment → Subject → Course → Program →
Department`):

- **Marks stats**: average/highest/lowest, over `ExamResult.total_marks`.
- **Pass/fail %**: per-row, against that row's own `Exam`'s
  `AssessmentConfiguration.passing_marks`/`maximum_marks` (proportionally
  scaled against the row's own `total_max_marks`, since a mark scheme's
  total and an assessment's configured maximum aren't guaranteed equal).
  Rows whose assessment has no `AssessmentConfiguration` are excluded
  from pass/fail (undeterminable) but still counted in marks stats.
- **Confidence distribution**, **teacher override %**, **average AI vs.
  teacher difference**: over `AnswerEvaluation` rows in the same scope.
- **Question-wise performance** / **most difficult questions**: grouped
  by `extracted_question_id`, ranked ascending by `average_marks /
  max_marks`. There's no separate "most incorrectly answered" signal in
  this dataset, so both surface the same ascending-ratio ranking — see
  ADR-044.

Every endpoint accepts the same optional filter set (`exam_id`,
`subject_id`, `course_id`, `department_id`) so the same figures can be
scoped from a single exam up to an entire institution.

## Reports (Feature 8, ADR-045)

`POST /reports` persists a `ReportJob` row (`pending`) and best-effort
dispatches `app/tasks/report_tasks.py`'s Celery task — same
fire-and-forget dispatch helper pattern as Module 05/06's OCR/ingestion
tasks (broker-connectivity failures are logged, not turned into a 500;
the job just stays `pending` for a manual retry once the broker is
reachable).

The task resolves whichever `report_type` was requested
(`student`/`question_wise`/`teacher_review`/`ai_performance`/
`institution_summary`/`department_summary`/`course_summary`) into a
generic list of flat row-dicts (reusing `AnalyticsService`/
`TeacherReviewDashboardService`/direct queries), then renders those same
rows with one of three format-specific renderers — `reportlab` (PDF),
`openpyxl` (Excel), the stdlib `csv` module (CSV) — and stores the result
through Module 05's unmodified `StorageService` under a `reports/`
key prefix. `GET /reports/{id}/download` returns a short-lived presigned
URL, same convention as Module 06's document downloads.

## Global Search (Feature 9)

`SearchService` runs `ILIKE` queries across five categories in one call —
students (name/username/email + `StudentEnrollment.roll_number`, this
codebase's closest existing field to the brief's "Register Number"/"Hall
Ticket"), teachers, subjects, questions, and evaluations (by the
evaluated student's name/roll number) — all scoped to the current
institution. No search index, no new table; see ADR-044's "compute on
demand, defer caching" reasoning, which applies equally here.

## Notifications (Feature 10, ADR-046)

`NotificationEvent` is intentionally storage-only: no email/SMS/push
provider is wired in. A service that performs a notification-worthy
action (currently just `ExamResultService.publish()`) writes one row per
recipient; `GET /notifications`/`POST /{id}/read` let a user read and
acknowledge their own events. When a real delivery channel is eventually
built (see the root [ROADMAP.md](../ROADMAP.md)), it becomes a consumer
of this existing table, not a schema change.

## RBAC

15 new `PermissionCode` members (see `app/core/constants.py`):
`answer_evaluations:reject`/`:rerun`,
`teacher_review_dashboard:read`, `exam_results:read/finalize/approve/
lock/unlock/publish`, `analytics:read`, `reports:read/generate`,
`search:read`, `notifications:read/update`. `teacher`/`institution_admin`
get every one of these except `exam_results:unlock`, which only
`institution_admin`/`super_admin` hold (ADR-042). Students get zero new
grants **except** `notifications:read`/`:update` — every notification
endpoint self-scopes to `current_user.id` as recipient, so a student can
only ever see their own events, never another student's or any
evaluation content (ADR-048).

## Testing

Backend: `tests/module07_helpers.py` provides shared fixture builders
(full exam hierarchy incl. `AssessmentConfiguration`/`StudentEnrollment`,
directly-constructed `AnswerEvaluation` rows with `final_marks` already
set — the AI computation itself is already covered by Module 06's tests,
so these bypass the real provider call to focus on Module 07's own
state-machine/aggregation logic). Report generation is tested against the
real `reportlab`/`openpyxl`/csv libraries and the fake in-memory storage
bucket (same convention as Module 05/06's real-Tesseract/real-pipeline
tests) — every one of the 7 report types × PDF/Excel/CSV is exercised at
least once.

## Related documents

- [official-document-guide.md](official-document-guide.md) — Module 06's
  ingestion/verification pipeline this module's results are built on.
- [ai-evaluation-guide.md](ai-evaluation-guide.md) — Module 06's 7-signal
  evaluation pipeline and confidence tiers.
- [database-standards.md](database-standards.md) — the 3 new tables.
- [rbac.md](rbac.md) — the full permission model.
