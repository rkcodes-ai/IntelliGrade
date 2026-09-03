# Academic Domain Guide (Module 03)

The Academic Domain is IntelliGrade's first multi-tenant business domain,
built on top of the frozen Module 01 (Foundation) and Module 02 (Identity &
Access Management) layers. It introduces `Institution` as the tenant root
and twenty academic entities scoped underneath it, following the exact
layering rules from [architecture.md](architecture.md) (API → Service →
Repository → Model) and reusing Module 02's authentication/RBAC/audit
infrastructure completely unmodified.

## Multi-tenancy model

**Shared-database, shared-schema multi-tenancy**: every academic table
lives in the same database and the same set of tables as every other
tenant, distinguished by an `institution_id` column — there is no
schema-per-tenant or database-per-tenant split (see ADR-016 in
[ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md) for why, and what
a future migration to schema-per-tenant would require).

- `institution_id` is **denormalized onto every academic table directly**,
  not just derivable by walking a parent chain (e.g. `Section` has its own
  `institution_id`, not just a `batch_id` you'd need to join through) — this
  keeps every tenant-isolation filter a single indexed column comparison,
  no matter how deep the entity sits in the hierarchy.
- `Institution` itself has no `institution_id` — it *is* the tenant.
- A user's membership in one or more institutions is tracked by a new
  `user_institutions` join table (`UserInstitution` model), **not** by
  adding a column to Module 02's frozen `users` table. A user can belong to
  multiple institutions (`is_primary` flags their default one).
- Every request to a tenant-scoped endpoint must carry an `X-Institution-Id`
  header identifying which institution it's acting within. This is resolved
  and authorized by `app/core/tenancy.py`'s `get_current_institution_id`
  dependency (`CurrentInstitutionDep`):
  - Missing/malformed header → `422` (client error).
  - `super_admin` may address any institution without an explicit
    membership row (a global role check, consistent with
    [rbac.md](rbac.md)'s existing guidance that per-resource authorization
    is "an additional service-layer check," not a change to
    `CurrentUser`/`require_permissions`).
  - Every other role must hold an active `UserInstitution` membership for
    the requested institution, or the request fails closed with `403`.
  - The resolved `institution_id` is passed explicitly into every service
    call — a client-supplied `institution_id` field inside a request body
    is never trusted for tenant scoping.
- `Institution`'s own CRUD endpoints (`/api/v1/institutions`) are the one
  exception: they don't require `X-Institution-Id` (there's no parent
  tenant to resolve), and are gated purely by permission codes
  (`institutions:create/read/update/delete`).
- `GET /api/v1/institutions/mine` lists the institutions the current user
  may act within (all institutions for `super_admin`, only active
  memberships for everyone else) — this is what powers the frontend's
  institution switcher and requires no special permission (every
  authenticated user needs to know their own memberships to pick a tenant
  in the first place).

## Entity list and hierarchy

```
Institution (tenant root)
├── Campus
│   ├── Department
│   │   └── Program                    ("degree", e.g. B.Tech)
│   │       └── Course                 (specialization, e.g. Computer Science Engineering)
│   │           ├── Batch              (e.g. 2026–2030 intake)
│   │           │   └── Section        (fixed subdivision, e.g. "A")
│   │           └── Subject            (per Subject Category, per semester number)
│   │       ├── AttendancePolicy       (nullable Program scope, or institution-wide)
│   │       └── GradingPolicy          (nullable Program scope, or institution-wide)
│   └── Room                           (building/floor/capacity)
├── AcademicYear
│   ├── Semester
│   └── AcademicCalendarEvent          (holidays, exam windows, etc.)
├── SubjectCategory                    (e.g. Core, Elective, Lab)
├── AcademicStatus                     (e.g. Active, On Probation, Graduated — `is_terminal` flag)
├── SubjectAllocation                  (Subject × Section × Semester × AcademicYear × teacher × Room)
│   ├── ClassSchedule                  (recurring timetable slot: day/time/Room)
│   └── TeacherAssignment              (teacher_user_id × role: primary/assistant/substitute)
└── StudentEnrollment                  (student_user_id × Batch × Section × Course × AcademicYear × Semester × AcademicStatus)
```

Two semantic decisions worth calling out explicitly (see ADR-019):

- **Program vs. Course**: `Program` is the *degree awarded* (e.g. "Bachelor
  of Technology"); `Course` is a *specialization/branch offered under a
  Program* (e.g. "Computer Science Engineering"). A Program has many
  Courses.
- **Section vs. Class**: `Section` is a fixed batch subdivision (a
  classroom cohort, e.g. "Batch 2026 → Section A"). `Class` is modeled as
  `ClassSchedule` — a recurring timetable slot (day-of-week, start/end
  time) binding a `SubjectAllocation` to a `Room`. These are deliberately
  distinct concepts, not aliases of each other.

`Room`, `Batch`, `SubjectCategory`, `SubjectAllocation`, `AcademicStatus`,
`GradingPolicy`, and `AttendancePolicy` all have full backend CRUD but
**no dedicated frontend management screen** in this module — only the 11
entities explicitly listed in the Module 03 UI scope (Institution, Campus,
Department, Program, Course, Semester, Academic Year, Section, Subject,
Teacher Assignment, Student Enrollment) got a screen. The remaining
entities are reachable as read-only dropdown selections on the forms that
reference them (e.g. picking an existing Batch when creating a Section) —
see [Frontend](#frontend) below.

## Backend architecture

Every entity follows the same four-layer shape:

```
app/api/v1/endpoints/{entity}.py       — HTTP routing, permission gating, Page[T] envelope
    → app/services/{entity}_service.py  — business rules, uniqueness/overlap checks, audit logging
        → app/repositories/{entity}_repository.py — tenant-scoped queries, search/sort/paginate
            → app/models/{entity}.py         — SQLAlchemy model
```

Two new shared base classes (in `app/repositories/tenant_repository.py` and
`app/services/tenant_service.py`) extend Module 02's unmodified
`BaseRepository`/`BaseService` with tenant-aware defaults:

- `TenantScopedRepository[ModelType]`: `get_by_id_for_institution`,
  `list_paginated`, `list_deleted`, `code_exists` (scoped uniqueness),
  `soft_delete`, `restore` — every query institution-filtered and
  soft-delete-aware by default.
- `TenantScopedService[ModelType]`: `get_by_id`, `list_paginated`,
  `list_deleted`, `soft_delete`, `restore`, `_log_audit` — `create()` and
  `update()` are deliberately left to each concrete service, since business
  rules (parent-FK validation, uniqueness, date-overlap checks) differ per
  entity.

`Institution` itself does **not** extend these tenant-scoped base classes
(it has no `institution_id` of its own) — its repository/service are
structured the same way Module 02's `UserService` was, as a standalone
non-tenant-scoped implementation.

### Pagination

`app/schemas/pagination.py` defines the contract every Module 03 list
endpoint uses — hand-rolled (no third-party pagination library existed in
the codebase, see ADR-018):

- `PageParams` (FastAPI dependency): `page`, `page_size` (max 200),
  `search`, `sort_by`, `sort_order`.
- `Page[T]` (generic Pydantic response envelope, PEP 695 syntax):
  `items`, `total`, `page`, `page_size`, `total_pages`.

This is a different, newer shape than Module 02's `GET /users` (which
predates this convention and uses bare `limit`/`offset` with no envelope —
see [api-standards.md](api-standards.md)).

### Validation rules implemented

| Rule | Where |
|---|---|
| Duplicate institution name/code | `InstitutionService.create/update` |
| Duplicate campus/department/program/course code (scoped to parent) | each entity's service, via `code_exists` |
| Duplicate subject code (scoped to institution) | `SubjectService` |
| Academic year date-range overlap | `AcademicYearService._assert_no_overlap` |
| Semester within parent academic year's date range, sibling-semester overlap, `semester_number` uniqueness per year | `SemesterService` |
| Teacher-assignment conflicts (same allocation + teacher) | unique constraint `uq_teacher_assignment_allocation_teacher` + service check |
| Student-enrollment conflicts (same student/year/semester; roll number unique per section) | unique constraints `uq_enrollment_student_year_semester`, `uq_enrollment_section_roll_number` |
| Room double-booking (same room/day/overlapping time range) | `ClassScheduleService._assert_no_overlap` |
| Invalid/nonexistent parent relationships | every `create`/`update` validates parent FK existence before writing, raising `404` |

### Audit logging

Every create/update/delete/restore/assignment/enrollment/status-change
action logs through the same `AuditService` used by Module 02, using seven
new generic `AuditAction` entries added to `app/core/constants.py`:
`ACADEMIC_ENTITY_CREATED/UPDATED/DELETED/RESTORED`,
`ACADEMIC_ASSIGNMENT_CREATED`, `ACADEMIC_ENROLLMENT_CREATED`,
`ACADEMIC_STATUS_CHANGED` — resource-agnostic since `AuditLog.resource_type`
already distinguishes which entity was affected.

### RBAC

80 new `PermissionCode` members were added (20 entities × create/read/
update/delete), purely additively — no existing Module 02 permission code
was changed. Default grants:

- `super_admin`: every permission (automatic, via `tuple(PermissionCode)`).
- `institution_admin`: full CRUD on all 19 non-Institution entities, plus
  `institutions:read` only (creating/deleting an institution is a
  platform-level, super-admin-only action).
- `teacher` / `student`: read-only across all 20 entities — an explicit
  "starting point" default, extendable per-role later via the (future)
  admin RBAC UI without a code change.

## Database

21 new tables (20 academic entities + `user_institutions`), created by
`0004_create_academic_domain_tables.py`; permission/grant seed data added
by `0005_seed_academic_permissions.py` (written to be idempotent against
`0003_seed_rbac_baseline.py` — see that migration's docstring for why an
enum-seeded migration needs that care). See
[database-standards.md](database-standards.md) for the full table list and
conventions.

### ER diagram (textual summary)

```
Institution 1───* UserInstitution *───1 User (Module 02, unmodified)
Institution 1───* Campus 1───* Department 1───* Program 1───* Course
Course 1───* Batch 1───* Section
Course 1───* Subject *───1 SubjectCategory
Institution 1───* AcademicYear 1───* Semester
AcademicYear 1───* AcademicCalendarEvent
Subject *───1 Section, Semester, AcademicYear, teacher (User) ──→ SubjectAllocation
SubjectAllocation 1───* ClassSchedule *───1 Room
SubjectAllocation 1───* TeacherAssignment *───1 teacher (User)
Batch, Section, Course, AcademicYear, Semester, AcademicStatus *───1 StudentEnrollment *───1 student (User)
Program 0..1───* AttendancePolicy, GradingPolicy (nullable — may be institution-wide instead)
Campus 1───* Room
```

All foreign keys are indexed. `ondelete` is `CASCADE` for strict
parent-owns-child relationships (e.g. deleting a `Campus` cascades to its
`Department`s), `RESTRICT` where an entity must not be silently orphaned
by deleting something it references (e.g. a `Subject`'s
`subject_category_id`, a `TeacherAssignment`'s `teacher_user_id`), and
`SET NULL` for genuinely optional references (e.g. `SubjectAllocation.room_id`).

## Frontend

New shared infrastructure (`frontend/src/`):

- `types/pagination.ts`, `types/academic.ts` — mirror the backend's
  `Page[T]`/`PageParams` contract and every entity's Pydantic schemas.
- `shared/constants/permissions.ts` — TypeScript mirror of the backend's
  `PermissionCode` enum (generated from it directly), alongside the
  existing `shared/constants/roles.ts`. A `@shared/*` path alias was
  wired up (`tsconfig.app.json`, `vite.config.ts`, `vitest.config.ts`) so
  the frontend could import it — **correction (Module 09 audit,
  2026-07-23): no frontend file actually imports from `@shared`/
  `shared/constants` anywhere.** `routes/index.tsx` passes hardcoded
  permission-code string literals to `PermissionGuard` instead, meaning
  the file/alias remain unconsumed and `shared/` is still not a real
  runtime dependency of either app. See `KNOWN_LIMITATIONS.md`.
- `store/slices/institutionSlice.ts` — the selected "current institution"
  id, persisted to `localStorage` — client/session state, same category as
  `uiSlice`'s theme/sidebar (the list of institutions a user can choose
  from is server state and stays in TanStack Query, matching the
  `authSlice` precedent).
- `api/client.ts` — the shared Axios instance now also injects
  `X-Institution-Id` from the Redux institution slice on every request
  (harmless no-op for Institution's own endpoints, which ignore it).
- `api/createCrudApi.ts` — a generic factory for the uniform REST shape
  (list/listDeleted/get/create/update/remove/restore), used by all eleven
  entity API modules instead of hand-writing near-identical CRUD wrappers
  eleven times.
- `hooks/usePaginatedList.ts`, `hooks/useSelectOptions.ts`,
  `hooks/useCrudMutations.ts`, `hooks/useMyInstitutions.ts` — generic,
  reusable data-fetching/mutation hooks shared by every management page.
- `components/common/{DataTable,PaginationControls,SearchInput,
  ConfirmDialog,FormDialog,FormField,PageHeader}.tsx` — the shared table/
  form/dialog shell every page is built from.
- `components/ui/{dialog,table,select,textarea}.tsx` — new primitives
  (Dialog wraps `@radix-ui/react-dialog`, the first Radix primitive beyond
  `react-slot` in this codebase, chosen for its accessible focus-trap/
  dismissable-layer behavior rather than hand-rolling one).
- `components/layout/InstitutionSwitcher.tsx` — topbar tenant switcher,
  wired into `Topbar.tsx`.

11 management screens (`pages/academic/*Page.tsx`): Institutions, Campuses,
Departments, Programs, Courses, Academic Years, Semesters, Sections,
Subjects, Teacher Assignments, Student Enrollments. Each has: a searchable,
server-paginated `DataTable`; a create/edit `FormDialog`; a delete
`ConfirmDialog` (soft-delete); permission-gated action buttons
(`institutions:create` etc., read from `state.auth.user.permissions`);
parent-entity `<select>` pickers populated via `useSelectOptions` against
the relevant list endpoint (including for Batch/SubjectCategory/
SubjectAllocation/AcademicStatus, which have no dedicated screen but are
still selectable). Routes are gated with `PermissionGuard` (nested under
`ProtectedRoute` in `routes/index.tsx`), and the sidebar (`Sidebar.tsx`)
filters its Academic Domain nav entries by the current user's permissions.

Import/Export and Bulk-create endpoints exist on the backend as documented
skeletons only (`POST /{entity}/import` returns 202 without processing
anything yet, `GET /{entity}/export` is a stub, `POST /{entity}/bulk`
does real per-item create with per-item error collection) — there is no
frontend UI wired to the import/export skeletons yet, matching the
prompt's "framework/skeleton only" requirement for that piece.

## Known route-registration-order pitfall

FastAPI/Starlette match routes in registration order. Every entity router
registers literal-path routes (`/deleted`, `/import`, `/export`, `/bulk`)
**before** the parametrized `/{entity_id}` route — registering them after
would cause e.g. `GET /subjects/export` to be captured by the
`GET /{entity_id}` handler and fail UUID parsing with a spurious `422`.
This bit the initial Module 03 implementation (19 of 20 routers had it
backwards) and was fixed with a mechanical route-reordering pass — see
`docs/api-standards.md`'s existing note about `/users/me` vs.
`/users/{user_id}` for the same underlying rule from Module 02.

## Testing

Backend: 314 tests, 96%+ coverage, every service's business rules and every
endpoint's tenant-isolation/RBAC/validation behavior exercised through real
request/response cycles against SQLite (not mocks) — same convention as
Module 02. Frontend: 159 tests (36 files), ~96% coverage, covering every
new hook, every shared component, the institution slice/switcher, and
either a full CRUD-dialog flow or a list+create smoke test for all 11
pages. See [TESTING_STATUS.md](../TESTING_STATUS.md) for the itemized
breakdown.
