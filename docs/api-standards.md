# API Standards

## Versioning

All business endpoints are prefixed `/api/v1` (`app.core.config.Settings.API_V1_PREFIX`).
Infrastructure probes (`/health*`) are deliberately unversioned — see
[architecture.md](architecture.md#request-lifecycle-today).

Breaking changes to a business endpoint's contract require a new version
prefix (`/api/v2`) once the API has external consumers.

## Request/response contracts

- Every endpoint declares a Pydantic `response_model`. Never return raw
  ORM objects or untyped dicts.
- Request bodies are validated Pydantic models, not manually-parsed JSON.
- Schemas extend `app.schemas.base.BaseSchema`.

## Error format

All errors — validation, domain, unhandled — return this shape (see
`app/core/exceptions.py`):

```json
{
  "error": {
    "code": "not_found",
    "message": "Human-readable message.",
    "details": {}
  }
}
```

`code` is a stable machine-readable slug (`not_found`, `validation_error`,
`unauthorized`, `forbidden`, `conflict`, `rate_limit_exceeded`,
`internal_error`, ...) — frontend code should branch on `code`, never on
`message` (which may change wording).

## Status codes

| Situation                        | Status |
|------------------------------------|--------|
| Success (read)                       | 200    |
| Success (create)                       | 201    |
| Success (no body)                        | 204    |
| Client sent invalid data                   | 422    |
| Not authenticated                            | 401    |
| Authenticated but not authorized               | 403    |
| Resource doesn't exist                           | 404    |
| Conflicting state (duplicate, version clash)       | 409    |
| Rate limited                                         | 429    |
| Unexpected server error                                | 500    |

## Pagination

**Current standard (Module 03+)**: `app.schemas.pagination.PageParams`
(query params `page`, `page_size` [max 200], `search`, `sort_by`,
`sort_order`) and `Page[T]` (response envelope: `items`, `total`, `page`,
`page_size`, `total_pages`). Every Academic Domain list endpoint follows
this shape — see [academic-domain-guide.md](academic-domain-guide.md).

Module 02's `GET /users` **predates this convention** and still uses bare
`limit`/`offset` query params returning an unwrapped array — it has not
been retrofitted (Module 02 is frozen; changing its contract is out of
scope for later modules unless a prompt explicitly asks for it). New list
endpoints should use `PageParams`/`Page[T]`, not the older shape.

## Authentication

JWT bearer tokens (`Authorization: Bearer <token>`), issued by
`AuthService`/`TokenService` (`app/services/{auth,token}_service.py`).
Refresh tokens travel as an httpOnly, path-scoped
(`/api/v1/auth`) cookie — never in the response body or a header. RBAC is
enforced via `app.core.rbac.require_roles(...)` /
`require_permissions(...)` dependencies on every protected endpoint. Full
design in [authentication-guide.md](authentication-guide.md) and
[rbac.md](rbac.md).

## Module 02 endpoints (`/api/v1`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | — (rate limited 10/min) | Authenticate, issue token pair + session |
| POST | `/auth/logout` | Refresh cookie (optional — no-ops with 200 if absent) | Revoke current session/token family |
| POST | `/auth/refresh` | Refresh cookie | Rotate refresh token, issue new access token |
| POST | `/auth/forgot-password` | — (rate limited 5/min) | Request a password reset token (generic response) |
| POST | `/auth/reset-password` | — | Consume a reset token, set a new password |
| POST | `/auth/change-password` | Bearer | Change password (revokes other sessions) |
| GET | `/users/me` | Bearer | Current user profile (with resolved `roles`/`permissions`) |
| PATCH | `/users/me` | Bearer | Update own profile |
| GET | `/users` | `users:read` | List users (paginated) |
| GET | `/users/{id}` | `users:read` | Get a user by id |
| POST | `/users` | `users:create` | Create a user |
| PATCH | `/users/{id}` | `users:update` | Update a user |
| POST | `/users/{id}/activate` | `users:update` | Reactivate a user |
| POST | `/users/{id}/deactivate` | `users:update` | Deactivate a user |
| DELETE | `/users/{id}` | `users:delete` | Soft-delete a user |
| GET | `/roles` | `roles:read` | List roles |
| GET | `/permissions` | `roles:read` | List permissions |
| GET | `/sessions` | `sessions:read` | List the current user's active sessions |
| DELETE | `/sessions/{id}` | `sessions:revoke` | Revoke a session (and its token family) |

`/users/me` routes are registered **before** `/users/{user_id}` in
`app/api/v1/endpoints/users.py` — FastAPI matches routes in registration
order, so `{user_id}` would otherwise greedily capture the literal path
segment `me`. This is a general rule, not a one-off: every Module 03
entity router registers `/deleted`, `/import`, `/export`, `/bulk` **before**
`/{entity_id}` for the same reason — see
[academic-domain-guide.md](academic-domain-guide.md#known-route-registration-order-pitfall).

## Academic Domain endpoints (Module 03)

Every entity below follows the identical shape: `GET ""` (paginated list),
`GET "/deleted"` (soft-deleted records, for restore), `GET "/{id}"`,
`POST ""`, `PATCH "/{id}"`, `DELETE "/{id}"` (soft-delete), `POST
"/{id}/restore"`, plus `POST "/import"` / `GET "/export"` (documented
skeletons only) and `POST "/bulk"` (real, with per-item error collection).
All require the `X-Institution-Id` header (see
[academic-domain-guide.md](academic-domain-guide.md)) except `institutions`
itself.

| Resource | Base path | Notable extra endpoints |
|---|---|---|
| Institutions | `/institutions` | `GET /mine`, `GET/POST/DELETE /{id}/members` |
| Campuses | `/campuses` | — |
| Departments | `/departments` | — |
| Programs | `/programs` | — |
| Courses | `/courses` | — |
| Academic Years | `/academic-years` | — |
| Semesters | `/semesters` | — |
| Academic Calendar | `/academic-calendar` | — |
| Batches | `/batches` | — |
| Sections | `/sections` | — |
| Subject Categories | `/subject-categories` | — |
| Subjects | `/subjects` | — |
| Rooms | `/rooms` | — |
| Subject Allocations | `/subject-allocations` | — |
| Teacher Assignments | `/teacher-assignments` | — |
| Student Enrollments | `/student-enrollments` | — |
| Academic Statuses | `/academic-statuses` | — |
| Grading Policies | `/grading-policies` | — |
| Attendance Policies | `/attendance-policies` | — |
| Class Schedules | `/class-schedules` | — |

## Assessment Domain endpoints (Module 04)

Same shape as the Academic Domain table above (`GET ""`, `GET "/deleted"`,
`GET "/{id}"`, `POST ""`, `PATCH "/{id}"`, `DELETE "/{id}"`, `POST
"/{id}/restore"`, `POST "/import"` / `GET "/export"` skeletons, `POST
"/bulk"` real with per-item errors), all requiring `X-Institution-Id`.
`Question` and `QuestionPaper` additionally get workflow endpoints; see
[assessment-domain-guide.md](assessment-domain-guide.md#question-workflow-endpoints).

| Resource | Base path | Notable extra endpoints |
|---|---|---|
| Assessment Types/Statuses | `/assessment-types`, `/assessment-statuses` | — |
| Assessments | `/assessments` | — |
| Assessment Configurations | `/assessment-configurations` | — |
| Evaluation Configurations | `/evaluation-configurations` | — |
| Exams | `/exams` | — |
| Exam Instructions | `/exam-instructions` | — |
| Exam Schedules | `/exam-schedules` | — |
| Exam Sessions | `/exam-sessions` | — |
| Question Categories/Types | `/question-categories`, `/question-types` | — |
| Difficulty Levels | `/difficulty-levels` | — |
| Bloom Taxonomy Levels | `/bloom-taxonomy-levels` | — |
| Question Tags | `/question-tags` | — |
| Questions | `/questions` | `POST /{id}/submit-for-review`, `POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/tags`, `DELETE /{id}/tags/{tag_id}`, `POST /{id}/versions` |
| Question Versions | `/question-versions` | Read-only + soft-delete/restore; no `POST ""` (created only via `/questions/{id}/versions`) |
| Question Approvals | `/question-approvals` | Read-only (`GET` only — rows written internally) |
| Question Reviews | `/question-reviews` | — |
| Answer Keys | `/answer-keys` | — |
| Model Answers, Alternative Answers, Reference Notes | `/model-answers`, `/alternative-answers`, `/reference-notes` | — |
| Question Blueprints / Sections | `/question-blueprints`, `/question-blueprint-sections` | — |
| Question Paper Templates | `/question-paper-templates` | — |
| Question Papers | `/question-papers` | `POST /{id}/submit-for-review`, `POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/versions` |
| Question Paper Versions | `/question-paper-versions` | Read-only (same pattern as Question Versions) |
| Question Paper Sections / Question Mappings | `/question-paper-sections`, `/question-paper-question-mappings` | — |
| Randomization Strategies | `/randomization-strategies` | — |
| Rubrics / Rubric Criteria | `/rubrics`, `/rubric-criteria` | — |
| Mark Distributions | `/mark-distributions` | — |
| Expected Keywords / Concepts | `/expected-keywords`, `/expected-concepts` | — |
| Evaluation History | `/evaluation-history` | `GET`/`POST` only — no `PATCH`/`DELETE`/restore (append-only, AI-preparation) |

## OpenAPI

Auto-generated from route/schema definitions, available at `/docs`
(Swagger UI) and `/redoc`, disabled when `ENVIRONMENT=production`. Every
router should set `tags=[...]` for logical grouping in the docs UI.
