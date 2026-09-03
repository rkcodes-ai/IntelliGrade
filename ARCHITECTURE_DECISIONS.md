# Architecture Decision Records

Lightweight ADR log. Each entry: context, decision, consequences. Numbered
sequentially; never renumber or delete a past entry — supersede it instead.

---

## ADR-001: Modular Monolith over Microservices for the initial build

**Context:** The system will eventually need OCR, AI evaluation, analytics,
and notifications as distinct concerns, which *could* be separate services.
**Decision:** Ship as one backend deployable and one frontend deployable,
but enforce strict internal layering (API → Service → Repository → Model)
and domain-oriented folder boundaries, so a future extraction is a folder
move, not a rewrite.
**Consequences:** Faster iteration now (one DB, one deploy). Extraction
later requires discipline today — domains must not reach into each other's
tables directly. See `docs/architecture.md`.

## ADR-002: UUID primary keys generated application-side, not DB-side

**Context:** `app.models.base.UUIDPrimaryKeyMixin` needs a UUID generation
strategy. The baseline migration also enables PostgreSQL's `pgcrypto`
extension, which raised the question of which strategy is authoritative.
**Decision:** Generate primary-key UUIDs in Python via `uuid.uuid4()`
(`default=uuid.uuid4` on the mapped column), not via `gen_random_uuid()`
server-side. `pgcrypto` remains enabled as a general-purpose baseline
extension for whatever future crypto/random needs arise, but it is not
required by the PK strategy.
**Consequences:** IDs are available before `INSERT` (useful for setting
relationships pre-commit), no DB round-trip dependency for ID generation.
Documented explicitly in the migration docstring after this was found
inconsistent during the Module 01 Quality Gate audit (see
[QUALITY_GATE.md](QUALITY_GATE.md)).

## ADR-003: Server state via TanStack Query, client state via Redux Toolkit

**Context:** Need a consistent rule for where frontend state lives, so
answer-script lists, evaluation results, etc. don't end up duplicated
between a manually-synced Redux store and the API cache.
**Decision:** Anything that comes from the API is owned by TanStack Query.
Redux Toolkit is reserved for genuinely client-only, cross-page state
(theme, sidebar collapse, feature flags).
**Consequences:** No manual cache-sync code. Contributors must resist the
urge to mirror query results into Redux "just in case."

## ADR-004: `shared/` is documentation-only until something imports from it

**Context:** A `shared/` directory was scaffolded for cross-cutting
types/constants consumed by both frontend and backend. It was initially
listed as an npm workspace member even though it has no `package.json`.
**Decision:** Removed from `package.json`'s `workspaces` array (it was
being silently dropped by npm anyway — dead configuration). `shared/`
stays as reference files (e.g. `shared/constants/roles.ts`) until a real
consumer needs it, at which point it becomes a proper workspace package.
**Consequences:** No phantom workspace member. Revisit this ADR when
`shared/` gets its first actual import.
**Found during:** Module 01 Quality Gate audit, 2026-07-15.

## ADR-005: Rate limiting is configured but not globally enforced in Module 01

**Context:** `slowapi`'s `Limiter` is wired with `default_limits`, but
enforcing it globally requires registering `SlowAPIMiddleware`. No business
endpoints exist yet to protect, and `slowapi`'s storage-error handling has
a sharp edge — a Redis outage during a limit check gets reported as
`RateLimitExceeded` rather than as an infrastructure error, which would
make `/health*` probes return 429 instead of failing open if they were
wrapped by the middleware.
**Decision:** Leave `SlowAPIMiddleware` unregistered for Module 01.
`in_memory_fallback_enabled=True` is set so the limiter degrades safely
whenever it *is* engaged. The `/health*` probes must be exempted via
`@limiter.exempt` whenever the middleware is eventually added.
**Consequences:** No accidental probe-flakiness risk today. Whoever adds
the first rate-limited endpoint must also register the middleware and
exempt health checks — documented directly in
`app/middleware/rate_limit.py`'s module docstring so this isn't missed.
**Found during:** Module 01 Quality Gate audit, 2026-07-15.

## ADR-006: `bcrypt` used directly, not via `passlib`

**Context:** `passlib[bcrypt]` 1.7.4 (the latest release, unmaintained
since 2020) is incompatible with `bcrypt` >= 4.1 — the version-detection
code it relies on was removed upstream. This made `hash_password()` raise
on every call.
**Decision:** Call the `bcrypt` library directly (`bcrypt.hashpw` /
`bcrypt.checkpw`) instead of going through `passlib`'s abstraction layer.
**Consequences:** One fewer dependency, no abstraction we don't need (we
only ever use one hashing scheme). bcrypt's 72-byte input limit is now
handled explicitly (`ValueError` raised rather than silently truncated —
silent truncation is a security footgun). The future Authentication module
should also enforce this as a `max_length` on the registration schema.
**Found during:** Module 01 Quality Gate audit, 2026-07-15.

## ADR-007: Frontend Docker builds use repo-root context, not `frontend/`

**Context:** This is an npm-workspaces monorepo — the lockfile
(`package-lock.json`) lives at the repository root, not inside `frontend/`.
A Docker build scoped to `./frontend` as its context cannot see files
outside that directory, so `npm ci` had no lockfile to install from and
the frontend image could not build at all.
**Decision:** `frontend/Dockerfile` is built with the repo root as context
(`docker-compose.yml`: `context: ., dockerfile: frontend/Dockerfile`).
COPY paths inside the Dockerfile are root-relative; `npm ci
--workspace=frontend` scopes the install to just the frontend's own
dependencies without needing root devDependencies.
**Consequences:** Anyone building the frontend image manually must run
`docker build` from the repo root with `-f frontend/Dockerfile`, not from
inside `frontend/` — documented at the top of the Dockerfile itself and in
`docs/deployment-guide.md`.
**Found during:** Module 01 Quality Gate audit, 2026-07-15.

## ADR-008: Dialect-agnostic `Uuid`/`JSON` column types instead of `postgresql.UUID`/`JSONB`

**Context:** Module 02's models need portable primary-key and JSON-column
types. Using `sqlalchemy.dialects.postgresql.UUID`/`JSONB` directly would
work in production but breaks the in-memory SQLite test suite (`aiosqlite`
+ `StaticPool`), forcing either a slower Postgres-per-test-run setup or
dialect-specific branching in test fixtures.
**Decision:** Use SQLAlchemy's dialect-agnostic `sqlalchemy.Uuid` and
`sqlalchemy.JSON` types (`app.models.base.UUIDPrimaryKeyMixin` and the
`metadata`/`preferences` columns) instead of the PostgreSQL-specific
variants. Verified the generated DDL is identical between SQLite (tests)
and PostgreSQL (production/CI) for every IAM table.
**Consequences:** Fast, dependency-free unit tests against real SQL
semantics (not mocks) — the primary enabler of the integration-testing
approach that caught the four bugs listed in this module's CHANGELOG
entry. Slight loss of Postgres-native `JSONB` query operators (`@>`, `?`,
GIN indexing) — acceptable for Module 02's usage (a flat preferences/audit
metadata bag, not queried by content). Revisit per-column if a future
module needs to query inside a JSON field.

## ADR-009: `family_id` carried in the access token, not just the refresh cookie

**Context:** The Sessions UI needs to mark which session is "this one"
(`is_current`). The natural approach — compare the refresh-token cookie's
family against each session's family — fails because the refresh cookie is
intentionally path-scoped to `/api/v1/auth` (see ADR-010) and is never sent
to `/api/v1/sessions`.
**Decision:** Embed `family_id` as a claim in the short-lived access token
too (`TokenService.create_access_token(..., family_id=...)`), surfaced via
`CurrentUser.session_family_id` after JWT decode. The sessions endpoint
compares this against each `Session.refresh_token_family_id`.
**Consequences:** `is_current` works correctly without loosening the
refresh cookie's path scope (which would have been the alternative fix,
and a strictly worse security trade). Access tokens are slightly larger
and now carry one more piece of session-topology information — acceptable
since access tokens are already short-lived and never persisted.
**Found during:** Module 02 integration testing, 2026-07-16.

## ADR-010: Refresh-token cookie is httpOnly, `SameSite=Lax`, and path-scoped to `/api/v1/auth`

**Context:** Needed a refresh-token storage strategy resistant to XSS
token theft, while keeping the access token itself in memory (Redux) only.
**Decision:** Refresh tokens are set as an httpOnly cookie (unreadable by
JS), `SameSite=Lax` (blocks cross-site `POST` attachment — the CSRF-
relevant case), and `path=/api/v1/auth` (never attached to any other
route, including `/api/v1/sessions`, `/api/v1/users`, etc.).
**Consequences:** No JS-readable long-lived credential exists anywhere
(mitigates XSS token exfiltration for the refresh token specifically —
access tokens remain JS-readable by necessity since Axios must attach
them, but they expire in `ACCESS_TOKEN_EXPIRE_MINUTES`). The path scoping
is what forced ADR-009. Full CSRF analysis in `docs/security.md`.

## ADR-011: Refresh token rotation with family-based reuse detection

**Context:** A refresh token is a long-lived bearer credential; if one
leaks (log capture, XSS before an access token expires, a compromised
device), an attacker with no other constraint could mint access tokens
indefinitely until the token's natural expiry.
**Decision:** Every refresh consumes and revokes the presented token,
issuing a new one linked to the same `family_id`. If a token is presented
that was already revoked (proof of either replay or a stale copy from a
theft), the entire family is revoked immediately, forcing re-authentication
on every device sharing that lineage. This is the OWASP-recommended
mitigation pattern for refresh token theft.
**Consequences:** A stolen-and-reused token burns down the session instead
of granting indefinite access — the legitimate user is forced to re-login
(a UX cost accepted as the correct trade for the security property).
Requires `family_id` bookkeeping across rotations (see ADR-009).

## ADR-012: Explicit commit-before-raise on every state-changing failure path in auth/token services

**Context:** FastAPI's session-per-request pattern rolls back the DB
session automatically when an exception propagates out of a request.
Discovered during integration testing: `auth_service.login()` incremented
`failed_login_count` then raised `InvalidCredentialsError` — the increment
was silently undone by the rollback, meaning account lockout could never
actually trigger no matter how many wrong passwords were submitted.
**Decision:** Every failure path in `auth_service.py`/`token_service.py`
that follows a state-changing write (failed-login counter, lockout
timestamp, audit log entry, token-family revocation on reuse detection)
calls `await self.session.commit()` **before** raising. Documented in a
module docstring in `auth_service.py` as a required pattern for any new
failure path added to that service.
**Consequences:** Security-relevant state changes survive the exception
that reports them to the client — the audit trail and lockout counter are
now trustworthy. The pattern must be manually maintained (no lint rule
enforces it); `test_auth_flow.py`'s lockout tests exist specifically to
catch a regression here.
**Found during:** Module 02 integration testing, 2026-07-16.

## ADR-013: `password_history` and `password_reset_token` added beyond the originally named tables

**Context:** The Module 02 requirements named eight specific tables
(`users`, `roles`, `permissions`, `role_permissions`, `user_roles`,
`refresh_tokens`, `sessions`, `audit_logs`) but also required "prevent
password reuse" and a full "Forgot Password / Reset Password" flow —
neither is implementable without persisted state.
**Decision:** Added `password_history` (last N password hashes per user)
and `password_reset_token` (hashed, single-use, time-boxed reset tokens)
as two additional tables, following the same conventions
(UUID PK, timestamp mixins) as the named eight.
**Consequences:** Full feature coverage of the stated requirements. Sets
the precedent for future modules: a named behavioral requirement that
implies storage gets a table, even when the table itself wasn't explicitly
enumerated — don't skip a required feature because its supporting table
wasn't named.
**Found during:** Module 02 implementation, 2026-07-16.

## ADR-014: `Institution` created as a brand-new tenant root; Module 02 files touched with zero diffs

**Context:** Module 03 requires shared-database multi-tenancy where "every
academic entity must belong to an Institution," but Module 02's `users`
table, `app/core/rbac.py`, and `app/api/deps.py` are explicitly frozen by
this module's instructions ("DO NOT modify authentication/RBAC"). No
`Institution` table existed anywhere in the codebase prior to this module
(confirmed by repository-wide grep — the only prior references were the
string `"institution_admin"`, a role *name*, not a tenant record).
**Decision:** `Institution` is a brand-new root entity with no FK to
anything (every other academic table has a mandatory `institution_id`
FK to it — see ADR-016). Tenant *membership* (which users belong to which
institutions) is modeled as a new, additive `user_institutions` join table
(`app/models/user_institution.py`) rather than adding an `institution_id`
column to `users` — this keeps the `users` table, and every Module 02
migration/model file, byte-for-byte unchanged.
**Consequences:** Module 02's auth/session/token flows are provably
untouched (verified via `git diff` showing zero changes under
`backend/app/core/rbac.py`, `backend/app/api/deps.py`,
`backend/app/models/user.py`). A user can belong to multiple institutions
(useful for a consultant teacher or a super admin auditing several
institutions) without a schema migration on the `users` table later.

## ADR-015: Tenant resolution via a new `app/core/tenancy.py`, not by modifying RBAC

**Context:** `docs/rbac.md` (written in Module 02) already anticipates this
exact situation: its "Future policy-engine compatibility" section states
per-resource/tenant authorization "should be added as an **additional**
service-layer check called from within the endpoint/service — not bolted
onto `CurrentUser`." `CurrentUser` and `require_permissions` are global,
role/permission-only checks by design and must stay that way per this
module's "DO NOT modify RBAC" instruction.
**Decision:** Added `app/core/tenancy.py` (new file) exposing
`CurrentInstitutionDep`, a FastAPI dependency that: (1) depends on the
unmodified `CurrentUserDep`, (2) reads `X-Institution-Id` header, (3)
verifies the user has an active `UserInstitution` membership row for that
institution (super_admin — a global role, checked via the unmodified
`current_user.has_role()` — is exempt from the membership check and may
address any institution). Every Module 03 service method that reads or
writes academic data requires an explicit `institution_id` argument sourced
from this dependency, never from a client-supplied request body field, so
a caller cannot smuggle a different tenant's ID into a payload.
**Consequences:** Zero lines changed in `rbac.py`/`deps.py`. Tenant
isolation is enforced once, centrally, at the dependency layer, then
mechanically reused by every endpoint — no per-endpoint reimplementation.
A missing/invalid `X-Institution-Id` header, or a membership that doesn't
exist, fails closed (403) before any service code runs.

## ADR-016: `institution_id` denormalized onto every academic table, not just derived transitively

**Context:** Some academic entities are transitively scoped to an
institution through a chain (e.g. `Subject → Course → Program →
Department → Campus → Institution`). The prompt explicitly states "every
academic entity must belong to Institution," and tenant-isolation queries
need to be fast and simple.
**Decision:** Every Module 03 table carries its own direct, non-nullable
`institution_id` FK (via a new `InstitutionOwnedMixin` in
`app/models/academic_base.py`), in addition to its natural parent FK. This
is deliberate denormalization, not an oversight — enforced consistent at
INSERT time by services (see ADR-017), not by a DB trigger.
**Consequences:** `TenantScopedRepository` can filter every query with a
single indexed `WHERE institution_id = :tenant` with no joins required for
isolation — the single most important property for both performance and
for making "never expose cross-tenant data" mechanically hard to get
wrong. Trade-off: every child row's `institution_id` must be kept
consistent with its parent's; `TenantScopedService.create()` derives and
sets it from the resolved parent record (never trusts a client-supplied
`institution_id` in the request body), and repository-level
`_assert_parent_institution` helpers reject a request whose supplied
parent (e.g. `campus_id`) doesn't already belong to the caller's resolved
institution.

## ADR-017: Shared `TenantScopedRepository`/`TenantScopedService` base classes, extending Module 02's unmodified bases

**Context:** 20 academic entities need identical cross-cutting behavior:
tenant filtering, soft-delete/restore, search/filter/sort/paginate, and
audit logging on every mutation. Writing this per-entity would violate
"never duplicate code" and make 20x the surface area for a tenant-leak bug.
**Decision:** `app/repositories/tenant_repository.py` defines
`TenantScopedRepository[ModelType](BaseRepository[ModelType])` — it
*subclasses* Module 02's `BaseRepository` unchanged (imported, not copied)
and adds `list_paginated()`, `search()`, `soft_delete()`, `restore()`, all
pre-filtered by `institution_id` and `deleted_at IS NULL` (unless
explicitly including deleted rows for restore flows). Similarly
`app/services/tenant_service.py` defines `TenantScopedService(BaseService)`
subclassing Module 02's `BaseService` unchanged, adding a
`_log_audit()` convenience wrapper around the existing (unmodified)
`AuditService`.
**Consequences:** Every one of the 20 entity repositories/services is a
thin subclass (typically <40 lines) instead of a bespoke reimplementation.
A tenant-isolation fix or a pagination behavior change is made once, in
one base class, and applies everywhere. `BaseRepository`/`BaseService`
themselves have zero diffs from Module 02.

## ADR-018: Hand-rolled `PageParams`/`Page[T]` pagination instead of a third-party library

**Context:** No pagination/filtering/sorting convention existed anywhere in
the codebase before this module (confirmed by repo-wide grep — Module 02's
`list_users` used bare `limit`/`offset` int params with no envelope,
metadata, filtering, or sorting). `fastapi-pagination` was evaluated.
**Decision:** Added `app/schemas/pagination.py` with a plain
`PageParams` (query-param dependency: `page`, `page_size`, `search`,
`sort_by`, `sort_order`) and a generic `Page[T]` response envelope
(`items`, `total`, `page`, `page_size`, `total_pages`), applied uniformly
by `TenantScopedRepository.list_paginated()`. No new runtime dependency
added.
**Consequences:** Zero new third-party dependency surface for something
this codebase can implement in ~40 lines; consistent envelope shape across
all 20 list endpoints, unlike Module 02's un-enveloped `list[UserRead]`
(which is left as-is — out of this module's scope to touch IAM endpoints).
Future modules should adopt `Page[T]` for any new list endpoint, including
eventually Module 02's, as a follow-up.

## ADR-019: "Course" modeled as a specialization/branch under "Program"; "Class" modeled as a timetable slot

**Context:** The prompt lists both `Program` and `Course`, and both
`Section` and `Class`, as distinct entities without defining their
relationship — these terms are used inconsistently across real-world
academic ERPs (some treat "Course" as a synonym for "Subject"; some treat
"Class" as a synonym for "Section").
**Decision:** `Program` = the degree awarded (e.g. "Bachelor of
Technology"); `Course` = the specialization/branch offered under a Program
(e.g. "Computer Science Engineering") — `Program 1—* Course`. `Section` =
a fixed batch subdivision (e.g. "CSE 2024 – Section A"), while `Class`
(modeled as `ClassSchedule`) = a recurring timetable slot binding a
`SubjectAllocation` to a `Room`, day-of-week, and time range — genuinely
distinct from `Section`, not a duplicate of it. Documented in
`docs/academic-domain-guide.md` with the full entity-relationship
rationale so this interpretation is traceable if it needs revisiting.
**Consequences:** All 20 named entities map to exactly one modeled table
with no redundant overlap; every relationship is justified rather than
guessed. If a future module's real-world usage reveals a different
intended meaning, only this ADR and the guide need updating — the schema
itself already supports either subject-level or branch-level "Course"
semantics without a breaking migration, since `Course` sits as its own
normalized table rather than being folded into `Program`.

## ADR-020: Assessment Domain (Module 04) reuses Module 03's tenancy/repository/service base classes unchanged

**Context:** Module 04's ~37 entities are exactly as tenant-scoped as
Module 03's 20 — every one belongs to an `Institution` and needs the same
search/sort/paginate/soft-delete/restore behavior.
**Decision:** No new tenancy or base-repository/service machinery was
written. Every Assessment Domain model composes `InstitutionOwnedMixin`
(imported from `app.models.academic_base` — not copied; the mixin is
domain-agnostic despite its module name) alongside the Module 02 mixins;
every repository subclasses `TenantScopedRepository`; every service
subclasses `TenantScopedService`; every endpoint depends on the unmodified
`CurrentInstitutionDep`. Zero diffs to `app/core/tenancy.py`,
`app/repositories/tenant_repository.py`, or `app/services/tenant_service.py`.
**Consequences:** Module 04 is purely additive to the tenancy layer, per
the prompt's explicit "DO NOT change tenancy" instruction. The only new
shared file is `app/models/assessment_base.py`, adding one genuinely new
cross-cutting concern (see ADR-022).

## ADR-021: Consolidating scalar "entities" into columns, not tables

**Context:** The prompt names several concepts as top-level items
("Maximum Marks," "Passing Marks," "Negative Marks," "Grace Marks," "Time
Limit," "Attempt Rules," "Question Metadata," "Question Ordering") that,
on inspection, are scalar attributes of a parent entity's configuration or
relationship, not independent entities with their own identity, lifecycle,
or one-to-many fan-out.
**Decision:** Maximum/Passing/Negative/Grace Marks, Time Limit, and Attempt
Rules became columns on `AssessmentConfiguration` (one row per
`Assessment`) rather than six separate tables. Question Metadata became a
`metadata: JSON` column on `Question` (matching Module 02's
`User.preferences` JSON-column precedent — arbitrary key/value data that
doesn't need relational structure or its own query patterns). Question
Ordering became an `order_index` integer column on
`QuestionPaperQuestionMapping` (the "Question Mapping" table) rather than
a parallel ordering table.
**Consequences:** ~9 named concepts fold into 3 existing tables instead of
9 new ones, without dropping any required capability — every value is
still stored, queryable, and independently updatable via its parent
entity's PATCH endpoint. If any of these ever needs independent versioning
or a one-to-many relationship (e.g. multiple attempt-rule presets per
institution), promoting a column to its own table is a additive migration,
not a redesign.

## ADR-022: `ApprovalWorkflowMixin` — a new, genuinely shared cross-cutting concern

**Context:** Unlike Module 03 (where every entity was either simple CRUD
or had bespoke validation), Module 04 has a real recurring pattern: several
entities (`Question`, `QuestionPaper`) move through an identical
draft → pending_review → approved/rejected → archived lifecycle with an
identical set of tracking columns.
**Decision:** A new mixin, `ApprovalWorkflowMixin`
(`app/models/assessment_base.py`), adds `approval_status` (plain `String`,
`Literal`-typed at the schema level — same idiom as Module 03's
`AcademicYear.status`, no DB `CHECK` constraint), `approved_by`,
`approved_at`, and `rejection_reason`. This is the one new piece of shared
model infrastructure Module 04 introduces.
**Consequences:** Approval-gated entities get consistent columns and a
single service-layer helper (`TenantScopedService` subclasses add
`approve()`/`reject()` methods per entity, since the *rules* for who may
approve what differ, but the *shape* of the state transition doesn't).
Non-workflow entities (lookups, junctions, history tables) don't compose
this mixin at all.

## ADR-023: Versioning is a separate history table per entity, not a temporal/mixin pattern

**Context:** The prompt requires "Version Support" and "History Support"
on Question and Question Paper specifically (`QuestionVersion`,
`QuestionPaperVersion`), plus a generic "Version" column requirement across
all entities in the "DATABASE" section.
**Decision:** Every entity gets a lightweight `current_version` integer
column (starts at 1, incremented on each content-changing update) to
satisfy the blanket "Version support" requirement cheaply. `Question` and
`QuestionPaper` additionally get a full append-only history table
(`QuestionVersion`, `QuestionPaperVersion`) capturing a point-in-time
snapshot on every content edit, because those two are the entities where
"what did this look like before" is a real, named product requirement
(reviewers/approvers need to diff versions), not just a counter.
**Consequences:** No generic "temporal table" or SQLAlchemy versioning
library was introduced — each history table is a plain, explicit model
following the exact same repository/service pattern as everything else,
kept consistent with this codebase's stated preference for explicit code
over framework magic (see ADR-018's pagination rationale for the same
philosophy).

## ADR-024: AI-preparation columns are typed placeholders, not a vector store

**Context:** The prompt requires the schema to "prepare... for Module 05
and Module 06" (OCR, AI evaluation, embeddings, semantic similarity, vector
search, confidence scores, evaluation history) while explicitly forbidding
implementing AI in this module.
**Decision:** `EvaluationConfiguration` gets `confidence_threshold`
(nullable `Numeric`) and `ai_config` (nullable `JSON`) columns. A new
`EvaluationHistory` table records each evaluation attempt (human or future
AI) against an `ExamSession` + `AnswerKey` pair, with `evaluator_type`
(`"human"` / `"ai"`), `score`, `confidence_score` (nullable), and
`embedding_vector` stored as nullable `JSON` (a plain float-array
placeholder, not `pgvector`) — no vector-similarity extension or index is
installed, since no code queries it yet. `ExpectedKeyword`/
`ExpectedConcept` exist as plain relational tables now (keyword strings,
concept names) so a future embedding step has structured input to embed
*against*, without needing to redesign the answer-key schema.
**Consequences:** Module 05/06 can add a `pgvector` column and similarity
index to `EvaluationHistory` (or a new table) as a pure *addition* later —
nothing in Module 04 needs to change shape for that. Zero AI/ML code,
libraries, or external calls exist in this module.

## ADR-025: Students get no default read access to Question/AnswerKey/Rubric/QuestionPaper content

**Context:** Module 03's default RBAC philosophy grants `teacher`/`student`
read-only access across every academic entity as a documented "starting
point." Applying that same blanket rule to Module 04 would give students
default read access to answer keys and rubrics — a real content-leak, not
a hypothetical one.
**Decision:** Default grants for `student` in Module 04 are deliberately
narrow: read-only on `Assessment`, `Exam`, `ExamSchedule`, `ExamInstructions`
only (what a student needs to know an exam exists and when). No default
grants on `Question`, `QuestionBank`-adjacent tables, `AnswerKey`, `Rubric`,
or `QuestionPaper` — those default to zero access for `student` and must be
explicitly granted (e.g. after grading, for a review screen) by an
institution admin, once that workflow exists. `teacher` gets full CRUD on
content-authoring entities (Question, QuestionVersion, tags, rubrics,
answer keys) plus read on Assessment/Exam, but not blanket approve/reject
rights (`institution_admin`/`super_admin` only, matching a real editorial
workflow).
**Consequences:** This is a deliberate divergence from Module 03's "every
role gets read-only by default" pattern, made explicit here so it isn't
mistaken for an oversight. `docs/assessment-domain-guide.md` documents the
full grant table.

## ADR-026: Module 05 builds the storage and background-job layers as new, real infrastructure — not a modification of anything

**Context:** Module 05 (Answer Script OCR Processing Pipeline) needs
object storage and asynchronous background processing. Repo analysis
confirmed neither exists as working code today: `MINIO_*` settings exist
in `app/core/config.py` and MinIO/Redis are provisioned in
`docker-compose.yml`, but no module imports the `minio` SDK anywhere, and
`app/tasks/celery_app.py` is a genuine skeleton (`include=[]`, zero
`@celery_app.task` definitions, no worker service in Compose). File
upload is *entirely new territory* — no `UploadFile`/multipart endpoint
exists anywhere in the codebase to extend or duplicate.
**Decision:** Module 05 is the first module to write real code against
this pre-provisioned infra: a new `app/services/storage_service.py`
(`StorageBackend` protocol + a `MinioStorageBackend` implementation) and
a new `app/tasks/ocr_tasks.py` (registered in `celery_app.py`'s
`include=[...]`). A `celery-worker` service is added to
`docker-compose.yml` for production readiness, even though it can't be
exercised in this sandbox (no Docker daemon here — same constraint
already documented for Postgres in `KNOWN_LIMITATIONS.md`).
**Consequences:** Nothing from Modules 01–04 is touched to make this
work — this is purely additive. The `StorageBackend` protocol means a
future non-MinIO backend (e.g. a different S3-compatible provider) is a
new class, not a rewrite, mirroring the OCR provider abstraction (see
ADR-032).

## ADR-027: Consolidating DocumentMetadata and ProcessingStatus into columns, not tables

**Context:** The prompt lists `DocumentMetadata` and `ProcessingStatus`
as entities to design. `DocumentMetadata` (filename, mime type, page
count, size, checksum) is inherently 1:1 with `AnswerScript` — a separate
table would only add a mandatory join for data that's always fetched
together. `ProcessingStatus` describes a fixed, code-defined pipeline
state machine (uploading → validating → storing → preprocessing →
ocr_queued → ocr_running → ocr_complete → structuring → completed /
failed / cancelled), not tenant-customizable data like Module 03's
`AcademicStatus` or Module 04's `AssessmentStatus`.
**Decision:** `DocumentMetadata`'s fields become plain columns on
`AnswerScript` (`original_filename`, `mime_type`, `page_count`,
`file_size_bytes`, `checksum_sha256`). `ProcessingStatus` becomes a
`status: str` column on `AnswerScript` (and a narrower one on `OCRJob`),
`Literal`-typed at the Pydantic layer — exactly the same pattern already
used for `ExamSession.status` and `ApprovalWorkflowMixin.approval_status`
in Module 04.
**Consequences:** Same "consolidate scalar entities into columns"
philosophy as Module 04's ADR-021 — 11 real tables instead of 13,
with zero loss of the capability the prompt asked for.

## ADR-028: OCRProvider is a global system catalog; OCRConfiguration is the tenant-scoped choice

**Context:** The prompt wants provider adapters for six OCR engines with
"only implement one default provider... others remain plug-in ready,"
plus a tenant-configurable `OCRConfiguration`. OCR engines are a
technical/system concept (which adapters this deployment has code for),
not institution-authored content.
**Decision:** `OCRProvider` is a **global** lookup table (no
`institution_id` — the only Module 05 table without
`InstitutionOwnedMixin`, alongside a code-level `OCRProviderAdapter`
protocol/registry in `app/services/ocr/providers/`). It is seeded with
all six named engines; only `tesseract` has `is_implemented=True` and a
real adapter class — the other five have `is_implemented=False` and a
stub adapter that raises `OCRProviderNotImplementedError` with a clear
message, so the catalog is honest about what actually runs today.
`OCRConfiguration` is tenant-scoped (`InstitutionOwnedMixin`), with a
nullable `assessment_id` (null = institution-wide default, set =
per-assessment override — the same reusable-template pattern Module 04's
`Rubric.question_id` already established), and a required FK to
`OCRProvider`.
**Consequences:** Enabling a *new* engine still requires writing its
adapter class (this ADR doesn't claim otherwise) — but enabling/disabling
*already-coded* engines, and picking a default, is admin-configurable
data, not a code change. Institution admins can toggle
`OCRProvider.is_enabled` (global, `super_admin`-gated) and per-tenant
default via `OCRConfiguration` (institution-admin-gated).

## ADR-029: OCRBlock consolidates "Blocks" and "Paragraphs" into one hierarchy level

**Context:** The prompt lists "Blocks, Paragraphs, Lines, Words" as
things OCR output must capture — a literal four-level hierarchy under
`OCRResult`.
**Decision:** `OCRBlock` represents both concepts (a block *is* a
paragraph-equivalent layout unit — bounding box, block-level confidence,
reading-order index). The hierarchy is `OCRResult → OCRBlock → OCRLine →
OCRWord`, three levels, not four.
**Consequences:** Matches how every real OCR engine's own output actually
works (Tesseract's `image_to_data` has exactly block/line/word levels;
Google Vision has block/paragraph/word but paragraph and block are
adjacent, not meaningfully separable for this pipeline's purposes). No
capability is lost — a "paragraph" is simply a block whose text spans
multiple lines, queryable the same way either name would be.

## ADR-030: ProcessingHistory is a new pipeline-stage log, distinct from the generic AuditLog

**Context:** The prompt wants both "Audit: Upload, Delete, Retry, OCR
execution, Processing completion, Failure, Cancellation" and a
`ProcessingHistory` entity. Module 02's `AuditLog`/`AuditService` already
logs generic "who did what" actions and is reused unmodified by every
module since.
**Decision:** Two distinct logs, not one stretched to cover both jobs:
`AuditLog` (via 7 new `AuditAction` entries) keeps recording
human-initiated actions — upload, delete, retry, cancel — exactly like
every other module's create/update/delete audit trail. A new
`ProcessingHistory` table records the pipeline's own stage-by-stage
state machine transitions against one `AnswerScript` (including fully
automatic Celery-driven transitions no human triggered), with
`from_status`/`to_status`, `stage`, `duration_ms`, and nullable
`error_detail` — richer, stage-specific data the generic audit log isn't
shaped for.
**Consequences:** A support engineer debugging a stuck pipeline reads
`ProcessingHistory` for the technical timeline; a compliance/security
review reads `AuditLog` for who-did-what. Neither is redundant with the
other.

## ADR-031: Document structure output is JSON, not a relational Section/Heading/Table/Image entity set

**Context:** Stage 6 (Document Structure Extraction) and Stage 8
(Structured Output Generation) need to capture "Pages, Questions,
Detected sections, Detected headings, Paragraphs, Images, Tables,
Coordinates, Confidence, Metadata." Modeling each of those as its own
relational table would add ~6 more tables for data that is read as one
nested tree per script, never queried/filtered at the individual
heading/table row level.
**Decision:** A `structured_content: JSON` column on `AnswerScript`
holds the assembled document-structure tree (built from the already-real
`OCRBlock`/`OCRLine`/`OCRWord` rows, which remain relational since those
*are* individually useful — e.g. rendering a bounding-box overlay). It
includes a best-effort, regex/heuristic **detected question-boundary
list** (`detected_questions: [{marker, page, block_id}, ...]`) — this is
explicitly boundary *detection*, matching a "Q1"/"Question 2:"-style
marker in normalized text, never answer scoring or evaluation, which
stays entirely out of scope for this module per the prompt's own
constraint.
**Consequences:** Same "JSON extension point over table explosion"
philosophy as Module 04's `question_metadata` (ADR-021). Module 06 reads
`structured_content` as its primary input; its exact shape is documented
in `docs/ocr-pipeline-guide.md` and versioned informally (a `schema_version`
key) so it can evolve without a migration.

## ADR-032: Only Tesseract is a real OCR provider adapter; five others are documented, interface-conformant stubs

**Context:** "Do NOT hardcode one engine... prepare adapters for:
Tesseract, EasyOCR, PaddleOCR, Azure OCR, Google Vision, AWS Textract.
Only implement one default provider."
**Decision:** `app/services/ocr/providers/base.py` defines an
`OCRProviderAdapter` abstract base (one method:
`extract(image_path) -> OCRPageResult`, returning the full block/line/word
tree + raw text + confidence). `tesseract_provider.py` is a real,
production-correct implementation wrapping `pytesseract` (Tesseract
binary itself is a system dependency, installed in this sandbox via
`winget` for live validation — see `docs/ocr-pipeline-guide.md`; a
production Docker image installs the `tesseract-ocr` apt package).
`easyocr_provider.py`, `paddleocr_provider.py`, `azure_provider.py`,
`google_vision_provider.py`, `aws_textract_provider.py` all conform to
the same interface but raise `OCRProviderNotImplementedError` from
`extract()` — present so `OCRProvider.code` values resolve to a real
class via the registry, absent any actual engine call, cloud credential,
or network dependency.
**Consequences:** Swapping the default engine, or adding a real
implementation to one of the five stubs later, touches exactly one file
each and a registry entry — never the pipeline/service code that calls
`OCRProviderAdapter.extract()`.

## ADR-033: Image preprocessing is a pipeline of swappable, single-responsibility steps

**Context:** The prompt lists twelve preprocessing operations (deskew,
denoise, contrast, brightness, rotation detection, cropping, margin
trim, resolution normalization, orientation detection, page splitting,
blank-page detection, noise removal) and requires them to be "modular"
and support "swapping implementations."
**Decision:** `app/services/image_processing/` holds one function per
operation (`deskew.py`, `denoise.py`, `contrast.py`, ...), each a plain
`(image: np.ndarray, **params) -> np.ndarray` transform (OpenCV/Pillow
under the hood), composed by a `PreprocessingPipeline` class that runs a
configurable ordered list of steps — the same "small composable units,
config-driven pipeline" shape as the OCR provider registry, not a
monolithic `preprocess_everything()` function.
**Consequences:** A step can be disabled, reordered, or replaced by
changing `OCRConfiguration`'s pipeline step list — no code change for
the common case of "skip denoise for already-clean scans."

## ADR-034: Students get no default access to AnswerScript/OCR data

**Context:** Uploaded answer scripts contain a student's actual exam
answers pre-grading — the same sensitivity class as Module 04's answer
keys and rubrics (ADR-025).
**Decision:** Default `student` grants for every Module 05 permission
prefix are **zero**. `teacher` gets create/read/retry on `AnswerScript`
plus read on jobs/results/configuration; `institution_admin` gets full
CRUD plus cancel/delete plus `OCRConfiguration` management;
`OCRProvider.update` (enable/disable an engine) is `super_admin`-only,
since it's a platform-level technical toggle, not per-institution
content.
**Consequences:** Consistent with ADR-025's precedent — this is the
second module in a row where the "every role gets read-only by default"
Module-03-era rule is deliberately not applied, for the same underlying
reason (leaking ungraded student work / exam-adjacent material).

## ADR-035: `OfficialExamDocument` is the root entity for official exam content ingestion, exam-scoped not session-scoped

**Context:** Module 06's brief redefines IntelliGrade's starting point:
the Question Paper, Model Answer, and Mark Scheme already exist as
official PDFs prepared by the Exam Cell/Faculty — the system ingests
them, it does not author them. `AnswerScript` (Module 05) cannot
represent this: its `exam_session_id` FK is `NOT NULL` and
`ExamSession` is per-student (`UniqueConstraint(exam_id,
student_user_id)`), but a Question Paper/Model Answer/Mark Scheme
belongs to the `Exam` as a whole, not to any one student's sitting of it.
No existing table in Modules 01–05 has an exam-level (not session-level)
document/file column.
**Decision:** A new `OfficialExamDocument` table, FK'd to `exams.id`
(not `exam_sessions.id`), is the root entity for all three document
types, distinguished by a `document_type` column
(`question_paper`/`model_answer`/`mark_scheme`) rather than three
near-identical tables — the same consolidation precedent as ADR-027's
`DocumentMetadata`/`ProcessingStatus` collapse. It carries: `storage_key`
(the original uploaded PDF — **immutable**, never overwritten by any
later step), a `raw_ocr_text` column (the whole-document OCR dump,
written once by the pipeline and likewise immutable — the document-level
"OCR Output"), `ocr_status` (pipeline state machine, mirrors
`AnswerScript.status`'s shape but is its own enum), and
`verification_status` (`not_started`/`in_progress`/`verified` — an
aggregate rollup of its children's verification state). The
question/answer/mark-range-level "Verified Output" is normalized into
three child tables (`ExtractedQuestion`, `ExtractedModelAnswer`,
`MarkSchemeRange` — see ADR-037/ADR-039's sibling entries) rather than a
second giant JSON blob on the parent, because — unlike `AnswerScript`'s
`structured_content` (ADR-031, where the shape was still evolving) —
the target shape here (a list of numbered questions, each with text and
marks) is well understood upfront, so relational modeling is the
better-fitted tool, not premature.
**Consequences:** Teacher verification (Stage: "Teacher Verification" in
the brief) always operates on the *child* rows' mutable fields
(`question_text`, `answer_text`, `marks_per_question`) — the parent
document's `storage_key` and `raw_ocr_text` are write-once and never
touched by any verification action, satisfying "the original document
must never be modified" literally, not just in spirit.

## ADR-036: Official document OCR is a new orchestration layer over Module 05's unmodified engine — no OCR logic is duplicated

**Context:** Module 05's OCR *engine* code (`app/services/image_processing/`,
`app/services/ocr/base.py` + registry + all 6 providers, `StorageService`,
PDF page extraction, text normalization) is document-type-agnostic by
construction — none of it imports `AnswerScript` or any Module 05 model.
Only the *orchestration* (`app/tasks/ocr_tasks.py::_run_pipeline`) is
hardwired, via `session.get(AnswerScript, ...)` and
`AnswerScriptPageService`/`OCRJobService`/`OCRResultService` calls, to
the per-student answer-script chain.
**Decision:** A new Celery task (`app/tasks/official_document_tasks.py`)
orchestrates official-document processing, calling the exact same
engine-layer functions Module 05 built
(`PreprocessingPipeline.run()`, `get_provider_adapter(code).extract()`,
`extract_pages_as_images()`, `normalize_text()`, `StorageService`) —
zero new OCR/preprocessing code is written. Only the persistence glue
(reading/writing `OfficialExamDocument`/`OfficialExamDocumentPage` instead
of `AnswerScript`/`AnswerScriptPage`) is new. `app/tasks/ocr_tasks.py`
itself is not imported from, not modified, not extended — the two task
modules are siblings, not a base/subclass relationship, since Celery task
functions don't compose that way cleanly and forcing it would risk the
frozen module.
**Consequences:** A future engine change (a new preprocessing step, a
newly-implemented OCR provider) benefits both pipelines automatically,
since both call into the same `app/services/ocr/`/`app/services/image_processing/`
code. A future *orchestration* change (e.g. a new pipeline stage specific
to official documents) touches only `official_document_tasks.py`.

## ADR-037: Extracted questions/model-answers are never promoted into the Module 04 Question Bank; evaluation reads verified extraction data directly

**Context:** Module 04's `Question` table is a curated, reusable academic
repository — it requires `question_category_id`/`question_type_id`/
`difficulty_level_id`/`bloom_level_id` and carries a full
draft→pending_review→approved editorial workflow
(`ApprovalWorkflowMixin`). An officially-uploaded exam's questions are a
**temporary evaluation asset** for one exam sitting, not bank content,
and forcing every verified question through full bank curation before
evaluation can run would block evaluation on work the brief never asked
for.
**Decision:** `ExtractedQuestion`/`ExtractedModelAnswer` carry **nullable**
`linked_question_id`/`linked_answer_key_id` FKs into `questions.id`/
`answer_keys.id`, populated only if an institution deliberately chooses
to promote a verified question into the reusable bank — a separate,
optional, explicitly-triggered action, never a precondition. The AI
evaluation service (ADR-039) reads `ExtractedQuestion.question_text`/
`ExtractedModelAnswer.answer_text` and the mark-scheme-derived maximum
directly; it never requires `linked_question_id`/`linked_answer_key_id`
to be populated.
**Consequences:** An institution can run a full exam's evaluation without
a single row ever touching `questions`/`answer_keys`. Bank promotion,
if/when built, is additive UI on top of already-working evaluation, not
a dependency of it.

## ADR-038: `AnswerEvaluation` is the new live evaluation-state entity; `EvaluationHistory` (Module 04) is retained, unmodified, as the historical action/audit log

**Context:** Module 04's `EvaluationHistory` was built as an
AI-preparation placeholder (ADR-024) but is session-grained (one FK to
`exam_session_id`, no `question_id`) and shaped around a single
`score`/`confidence_score`/`embedding_vector` per row — it cannot
represent Module 06's per-question, multi-signal (7 individual component
scores, ADR-039), mutable "current state" (suggested marks pending
review → confirmed/overridden) without either widening its columns
(touching a frozen Module 04 table) or misusing an append-only table as
if it were mutable state.
**Decision:** `EvaluationHistory` is used exactly as Module 04 defined
it and is not altered: **every** teacher-facing review action — the
initial AI evaluation being generated, a teacher confirming
suggested marks, a teacher overriding them — writes one new
`EvaluationHistory` row (`evaluator_type="ai"` for the first,
`evaluator_type="human"` for the latter two), giving it real, working
use for the first time since Module 04 shipped it unused. A new table,
`AnswerEvaluation`, holds the **current** evaluation state for one
(student answer × extracted question) pair — the 7 individual component
scores, `confidence_tier`, `suggested_marks`, `final_marks`, and
`review_status` — updated in place as it moves through the review
lifecycle, which is exactly the kind of mutable "latest state" row an
append-only history table is the wrong shape for.
**Consequences:** `AnswerEvaluation` is what the Evaluation Review
Dashboard queries (current state, one row per question); `EvaluationHistory`
is what an audit trail / "who changed this mark and when" view queries
(every state transition, many rows per `AnswerEvaluation` over time) —
the same read-model split already established between `AnswerScript.status`
(current) and `ProcessingHistory` (Module 05's append-only transition
log, ADR-030) for exactly the same reason.

## ADR-039: AI evaluation is a fixed 7-signal pipeline per question, every component score persisted individually

**Context:** The brief is explicit that evaluation "MUST NOT rely only on
semantic similarity" and must combine multiple signals, each of which
needs to be independently inspectable by a teacher deciding whether to
trust a suggested mark.
**Decision:** `AnswerEvaluationService` runs, per (student answer ×
extracted question) pair: semantic similarity → keyword match → concept
match → reasoning analysis → completeness analysis → answer relevance →
an overall confidence estimate → suggested marks (bounded by the
mark-scheme-derived maximum for that question, ADR-035's children). Each
of the six component scores plus the overall confidence score is its own
column on `AnswerEvaluation` (`semantic_similarity_score`,
`keyword_match_score`, `concept_match_score`, `reasoning_score`,
`completeness_score`, `relevance_score`, `confidence_score`) — never
collapsed into one opaque number. The uploaded official model answer
(`ExtractedModelAnswer.answer_text`) is always the primary reference
input to every signal, not just the similarity signal, per the brief's
explicit "the uploaded official model answer must always be treated as
the primary reference" requirement.
**Consequences:** A teacher reviewing a low-confidence suggestion can see
*which* signal disagreed (e.g. high keyword match but low reasoning
score) rather than a single unexplained number — this is the
explainability the brief asks for, and it's a data-shape decision, not a
UI-only one: collapsing to one score at write time would make it
unrecoverable later.

## ADR-040: Confidence-tiered teacher review — ≥90% auto-suggest, 70–89% requires confirmation, <70% mandatory review

**Context:** The brief specifies three confidence bands with different
teacher-review obligations, to avoid both "AI silently finalizes every
mark" and "a teacher must manually re-check every single answer"
extremes.
**Decision:** `AnswerEvaluation.confidence_tier` is derived from
`confidence_score` via fixed thresholds — `>= 90` → `"high"` (marks
suggested, `review_status="auto_suggested"`, no teacher action required
to stand, though still overridable); `70–89` → `"medium"`
(`review_status="pending_confirmation"` — a one-click accept surfaces in
the UI); `< 70` → `"low"` (`review_status="pending_review"` — cannot
reach `final_marks` without an explicit teacher action). These thresholds
are named constants in the evaluation service (not hardcoded inline at
each call site, and not a per-institution `AIConfiguration` override in
this first pass — see ADR-041 for what *is* configurable).
**Consequences:** `final_marks` is only ever set by a teacher action
(confirm or override) for medium/low tiers; for high-tier rows,
`final_marks` may be auto-populated from `suggested_marks` but
`review_status` still allows a teacher to override it later — "no
teacher action required" is not "no teacher action possible."

## ADR-041: AI providers sit behind the same provider-abstraction shape as Module 05's OCR providers — one real implementation, others stub-conformant

**Context:** No LLM/embedding/AI-provider code exists anywhere in
Modules 01–05 (`ai/` is a documentation-only placeholder) — this is
genuinely new infrastructure, and the brief requires it not be
hardcoded to one vendor.
**Decision:** `app/services/ai/base.py` defines an `AIProviderAdapter`
abstract interface (methods covering the 7-signal evaluation surface from
ADR-039) and `app/services/ai/registry.py` maps provider codes to adapter
classes — deliberately mirroring `app/services/ocr/base.py`/`registry.py`'s
shape exactly, down to a global `AIProvider` catalog table (using the
same `GlobalRepository`/`GlobalService` base classes Module 05 introduced
for `OCRProvider`) and a tenant-scoped `AIConfiguration` table (mirroring
`OCRConfiguration`). Exactly one provider is a real, working
implementation; any additional providers are interface-conformant stubs
raising a dedicated not-implemented error, following ADR-032's precedent
exactly rather than inventing a new pattern.
**Consequences:** Swapping or adding an evaluation backend later touches
one new provider file and a registry entry, never
`AnswerEvaluationService` or any endpoint — identical blast-radius
property to Module 05's OCR provider swap story.

## ADR-042: `ExamResult` is a new, per-`ExamSession` root entity for finalization and locking — not a status column on `AnswerEvaluation`

**Context:** Module 07's Result Finalization/Locking features (Draft →
Under Review → Approved → Locked → Published) operate at the level of
"one student's overall result for one exam," while `AnswerEvaluation`
rows are per-question. Bolting a lock status onto each per-question row
would mean N status columns to keep in sync per student instead of one.
**Decision:** A new table, `exam_results` (one row per `ExamSession`,
`institution_id`-scoped, unique on `exam_session_id`), holds
`total_max_marks`/`total_marks` (both computed by summing the session's
`AnswerEvaluation.max_marks`/`final_marks` at finalization time — a
snapshot, not a live view, matching `AnswerEvaluation.max_marks`'s own
snapshot precedent from ADR-039) and the lifecycle `status` column
(`draft` / `under_review` / `approved` / `locked` / `published`), plus
`finalized_by`/`finalized_at`, `locked_by`/`locked_at`,
`published_by`/`published_at`, `unlocked_by`/`unlocked_at`. Rows are
created lazily by the first finalization action, not eagerly for every
`ExamSession` — an exam session with no finalized result simply has no
`ExamResult` row yet (same "lazily created on first real action"
precedent as `AnswerEvaluation` itself, ADR-038).
**Consequences:** `ExamResultService` owns one validated state machine
(`draft→under_review→approved→locked→published`, plus an explicit
`unlock` transition back to `draft` gated on a dedicated permission —
Feature 5's "transitions must be validated"). Once a session's
`ExamResult.status` is `locked` or `published`,
`AnswerEvaluationService.confirm/override/reject/evaluate_question` all
reject further writes for that session's evaluations with a 409 unless
the caller holds the unlock permission and unlocks first — enforced once,
centrally, in `AnswerEvaluationService`, not duplicated per action.

## ADR-043: Teacher "Reject" is a new `review_status` value, not a new table; "Re-run AI Evaluation" reuses `evaluate_question()` under an explicit `force` flag

**Context:** Feature 2 asks for a third teacher action beyond
accept/modify (confirm/override, both already shipped in Module 06):
"Reject Evaluation," plus a future-ready "Re-run AI Evaluation" endpoint.
Both are actions on an existing `AnswerEvaluation` row, not a new kind of
entity.
**Decision:** `review_status` gains one new value, `"teacher_rejected"` —
set by a new `AnswerEvaluationService.reject()` method, which clears
`final_marks` (a rejected AI evaluation must not silently keep
contributing a final mark) and requires a `reason` (reusing the
`notes` column), same shape as `override()`. `evaluate_question()`
gains a `force: bool = False` parameter: called normally it stays the
existing idempotent upsert (Module 06 behavior, unchanged); called with
`force=True` (the new `POST /{id}/rerun` endpoint) it re-runs the
configured AI provider against the same inputs and overwrites the AI-
computed columns — always after writing the *pre-rerun* state to
`EvaluationHistory` first, so a rerun is never a silent, unrecoverable
overwrite. No new AI provider logic is needed for this to work today;
"future-ready" means the endpoint and history trail already exist for
whenever a second real provider makes re-running against a different
engine meaningful.
**Consequences:** Every teacher action (confirm/override/reject/rerun)
now funnels through the same `_record_review_history()` helper Module 06
already introduced — reject and rerun are two more call sites, not a new
logging mechanism.

## ADR-044: Analytics and question-wise reports are computed on demand from existing tables — no new cache/materialized-view table this pass

**Context:** Feature 7 asks for a wide set of statistics (average/
highest/lowest marks, pass/fail %, question-wise performance, confidence
distribution, override %, AI-vs-teacher difference, most-difficult
questions, department/subject/course/institution rollups). All of the
inputs already exist: `AnswerEvaluation` (per-question scores/marks),
`ExamResult` (per-student totals, ADR-042), and the Module 03/04
hierarchy (`Exam → Assessment → Subject → Course → Program → Department`,
`Exam → Section → Batch`).
**Decision:** `AnalyticsService` computes every figure via SQL
aggregation (`func.avg`/`func.count`/`func.max`/`func.min`, grouped and
joined through the existing FK chain) at request time — no new
persisted rollup table, no scheduled recomputation job. This mirrors
Module 03's precedent of shipping working functionality first and
deferring a cache/index layer until a real per-institution data-volume
need is demonstrated (see `KNOWN_LIMITATIONS.md`'s Question Bank
server-side-filtering entry for the same "defer until it hurts"
reasoning).
**Consequences:** Every analytics endpoint is correct-by-construction
(no cache-invalidation bugs, since there's no cache) but re-scans the
relevant rows on every call; acceptable at this module's scale, flagged
in `KNOWN_LIMITATIONS.md` as the first thing to revisit once
per-institution result volumes grow large enough for this to matter.

## ADR-045: Reports are generated asynchronously via a new Celery task and tracked by a new `ReportJob` row; files are stored through Module 05's existing `StorageService`

**Context:** Feature 8 requires PDF/Excel/CSV export of several report
types, and Feature 11 explicitly calls for "background report
generation." Generating a multi-page PDF or large Excel workbook inline
in a request handler would block the request and doesn't fit this
project's existing synchronous-request-handler convention.
**Decision:** `POST /reports` creates a `ReportJob` row
(`institution_id`-scoped: `report_type`, `format`, `parameters` JSON,
`requested_by`, `status` — `pending`/`processing`/`completed`/`failed` —
`storage_key`, `failure_reason`) and dispatches a new Celery task,
`app/tasks/report_tasks.py`, which reuses `StorageService` (Module 05,
unmodified) to write the generated file to the same object-storage
bucket official documents and answer scripts already use, under a new
`reports/` key prefix. PDF generation uses `reportlab`, Excel uses
`openpyxl`, CSV uses the standard library `csv` module — no new
provider-abstraction is introduced here (unlike OCR/AI) because there is
exactly one real way to write a PDF/XLSX/CSV file; that dimension isn't
pluggable the way an OCR or AI *engine* is.
**Consequences:** `ReportJob` is this module's version of the
"orchestration root + Celery task" shape Modules 05/06 already
established (`AnswerScript`/`OfficialExamDocument` + their tasks) —
consistent async-job UX (submit → poll status → download) across all
three modules. Same sandbox constraint as Modules 05/06 applies: this
task is verified by direct invocation against the real (SQLite) session
and real report-generation libraries, not through a live Celery broker
round-trip — see `KNOWN_LIMITATIONS.md`.

## ADR-046: `NotificationEvent` is a storage-only framework — no delivery channel, per the brief's explicit scope limit

**Context:** Feature 10 explicitly says "Prepare notification framework.
No email or SMS integration yet. Store notification events only."
**Decision:** A new table, `notification_events` (`institution_id`-scoped:
`event_type`, `recipient_user_id`, `payload` JSON, `is_read`,
`read_at`), is written by the services that already perform the
triggering action (e.g. `ExamResultService.publish()` writes one
`result_published` event per affected student) — no email/SMS/push
provider, no queue consumer, no delivery-status tracking, because there
is nothing to deliver to yet. `NotificationService` only supports
create/list/mark-read.
**Consequences:** When a real delivery channel is built (Roadmap item
"Notifications"), it becomes a consumer of this existing table (a
poller or a trigger-based dispatcher) rather than a schema change —
same "lay the groundwork, defer the integration" precedent as Module
02's password-reset token issuance shipping before any SMTP provider was
wired in.

## ADR-047: The audit trail reuses Module 02's `AuditService`/`AuditAction` and Module 04's `EvaluationHistory` exactly — no new audit table

**Context:** Feature 6 requires every teacher-review and result-lifecycle
action to be logged, and explicitly "nothing should be deleted." Module
02 already has a working, append-only `audit_logs` table and service;
Module 06 already established `EvaluationHistory` as the
per-evaluation domain history log (ADR-038).
**Decision:** Module 07 adds new `AuditAction` members
(`teacher_review_rejected`, `answer_evaluation_rerun`,
`exam_result_finalized`, `exam_result_approved`, `exam_result_locked`,
`exam_result_unlocked`, `exam_result_published`, `report_generated`,
`notification_created`) logged through the existing `AuditService`, and
continues writing to `EvaluationHistory` for every per-question review
action (reject/rerun join confirm/override there). No new logging
table, no new logging service.
**Consequences:** Every Module 07 action shows up in the same
`GET /audit-logs` a security reviewer already knows how to query;
per-evaluation history stays queryable per-question via the existing
`EvaluationHistory` endpoints Module 04 shipped.

## ADR-048: Students get almost no new default permissions in Module 07 — the one exception is self-scoped notification read/mark-read

**Context:** Feature 12 lists explicit restrictions (no model answers,
no mark modification, no confidence scores, no teacher comments) but
does not ask for any new student-facing capability; the brief's own
Security section only describes what students must continue to be
denied.
**Decision:** `DEFAULT_ROLE_PERMISSIONS[Role.STUDENT]` gains no new
entries for Teacher Review/Result Finalization/Analytics/Reports/Search
— identical to Modules 05/06's precedent of a deliberately restrictive
student default for sensitive evaluation content. The one addition is
`notifications:read`/`notifications:update`: every notification
endpoint is self-scoped to `current_user.id` as recipient (a student can
only ever list/mark-read their *own* events — see
`app/api/v1/endpoints/notifications.py`), and a `NotificationEvent`'s
payload carries only what the triggering action chose to put there
(e.g. `publish()` writes total/max marks, never confidence scores or
teacher notes) — so granting this doesn't reopen the restriction the
other withheld grants protect. Without it, the "your result was
published" notification framework Feature 10 asks for would have no
student-reachable read path at all. A student viewing their own
finalized/published *result* in full (a richer result-card view beyond
the notification payload) remains a documented, explicitly deferred item
in `KNOWN_LIMITATIONS.md`.
**Consequences:** Every other new Module 07 permission code is granted
to `teacher`/`institution_admin`/`super_admin` only, following the exact
`_AI_*`/`_OCR_*` grant-tuple pattern Modules 05/06 established.
