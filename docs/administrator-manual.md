# Administrator Manual — IntelliGrade v1.0

For Institution Admins and Super Admins setting up and running an
institution in IntelliGrade. For infrastructure/deployment operations,
see `docs/operations-manual.md` instead — this document is about using
the application, not running its servers.

## Roles

IntelliGrade ships 4 seeded roles:

| Role | Scope | Typical use |
|---|---|---|
| `super_admin` | Platform-wide, bypasses institution-membership checks | Platform operator, initial setup |
| `institution_admin` | One (or more) institutions | Runs an institution's academic setup, users, exams |
| `teacher` | One (or more) institutions | Ingests exam content, reviews AI evaluations, finalizes results |
| `student` | Self-scoped only | Views their own published results/notifications |

Permissions are DB-driven (304 codes as of v1.0), not hardcoded — see
`docs/rbac.md` for the full model. Every role's default grants are
additive across modules; nothing is removed by a later module.

## First-time setup order

Academic entities have real dependency chains — set them up in this
order (each references the previous):

1. **Institution** (`super_admin` only creates institutions;
   `institution_admin` manages everything within one they're a member
   of via `UserInstitution`)
2. **Campus** → **Department** → **Program** → **Course**
3. **Academic Year** → **Semester** (and **Academic Calendar** if used)
4. **Section**, **Subject**, **Subject Category**
5. **Batch**, **Room** (referenced by Section/Exam Schedule respectively)
6. **Teacher Assignment** (which teacher teaches which subject/section)
7. **Student Enrollment** (which student is in which batch/section)
8. **Assessment** → **Exam** → **Exam Schedule** (the assessment
   engine — see `docs/assessment-domain-guide.md`)
9. **Question Bank** entities and/or **Official Exam Document** ingestion
   (see `docs/question-bank-guide.md` and
   `docs/official-document-guide.md` for the two paths — v1.0's real
   evaluation workflow uses the Official Document path)

Every entity above has full CRUD, soft-delete/restore, and search/sort/
pagination in the frontend under its own management screen (see the
Sidebar navigation) — 11 of the 20 academic entities and select
Assessment Domain entities got dedicated screens; the remainder (Batch,
Subject Category, Subject Allocation, Room, Academic Status, Grading
Policy, Attendance Policy) are reachable as read-only dropdown selections
on the forms that reference them — see `KNOWN_LIMITATIONS.md` if you need
to manage one of those directly via the API.

## User & role management

- Create users via `POST /users` (or the Users screen); assign roles via
  `POST /users/{id}/roles`.
- A user only has access within an institution once a `UserInstitution`
  membership row exists for them — creating a user does not implicitly
  grant institution access. Add members via the Institution detail
  screen's member list, or `POST /institutions/{id}/members`.
- `super_admin` bypasses membership checks entirely — use sparingly, it's
  a platform-wide role, not an institution-scoped one.
- Account lockout is automatic (configurable via
  `ACCOUNT_LOCKOUT_MAX_ATTEMPTS`/`ACCOUNT_LOCKOUT_DURATION_MINUTES`) — if
  a user reports being locked out, wait for the lockout window or have a
  `super_admin` inspect/clear it directly (no dedicated "unlock" UI
  exists in v1.0 — see `KNOWN_LIMITATIONS.md`).

## Running an exam cycle (the core admin/teacher workflow)

1. Institution Admin (or Teacher, if granted) sets up the Exam + Exam
   Schedule under an Assessment.
2. A Teacher (or Exam Cell staff) uploads the official Question Paper,
   Model Answer, and Mark Scheme documents — real OCR extracts
   structured content automatically (`docs/official-document-guide.md`).
3. A Teacher **verifies** the extracted questions/model answers/mark
   scheme ranges — nothing is auto-trusted; this is a required manual
   step before evaluation can proceed correctly.
4. Students' answer scripts are uploaded (by the student, or bulk-
   uploaded by staff) and OCR'd (`docs/ocr-pipeline-guide.md`).
5. AI evaluation runs per question, producing confidence-tiered
   suggestions (`docs/ai-evaluation-guide.md`).
6. Teachers work the Teacher Review Dashboard queue: confirm, override,
   reject, or rerun each evaluation (`docs/teacher-review-guide.md`).
7. Once every question in a session has a teacher-reviewed evaluation,
   finalize the result (per-student, per-exam, or per-batch), then
   approve → lock → publish. **Locking blocks further evaluation edits**
   — this is deliberate, not a bug, if you need to make a correction
   after locking, `unlock` first (a permission withheld from the default
   teacher grant — `institution_admin`/`super_admin` only, by design).
8. Analytics and Reports are available immediately once results are
   published (or even earlier, for in-progress monitoring).

## Multi-tenancy notes

Every request that touches tenant-scoped data requires an
`X-Institution-Id` header (the frontend's institution switcher sets this
automatically). A `super_admin` can switch between institutions freely;
every other role must have an active `UserInstitution` membership for the
institution they're trying to access, or the request fails closed (403).

## Where administrators should NOT go

- Don't attempt to bypass the Teacher Verification step for official
  documents — evaluation quality depends on it, and the workflow is
  designed to require it.
- Don't unlock a published result casually — it's audit-logged and
  intentionally gated to `institution_admin`/`super_admin` for a reason
  (ADR-042).
- Don't edit `permissions`/`roles` tables directly in the database —
  always go through the API/UI so audit logging and cache invalidation
  (where applicable) stay correct.
