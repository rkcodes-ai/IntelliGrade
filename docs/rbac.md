# RBAC (Role-Based Access Control)

## Model

Four independent, DB-driven entities — not hardcoded enums baked into
application logic:

```
User ──< UserRole >── Role ──< RolePermission >── Permission
```

- **`roles`**: `id, name, description, is_system` (`is_system` roles —
  the four seeded ones — cannot be deleted via the API, only
  application-created custom roles can).
- **`permissions`**: `id, code, description` — `code` is a stable slug like
  `users:read`, `sessions:revoke` (see `app.core.constants.PermissionCode`
  for the 15 seeded codes).
- **`role_permissions`**: join table, unique on `(role_id, permission_id)`.
- **`user_roles`**: join table, unique on `(user_id, role_id)` — a user can
  hold more than one role.

`app.core.constants.Role` (a `StrEnum`) exists **only** as a typed reference
for seeding and tests — it is not consulted at authorization time. The
actual source of truth at runtime is always the database via
`UserRepository`'s eager-loaded `user_roles → role → role_permissions →
permission` chain. This is deliberate: adding a fifth role or a new
permission is a data change (an Alembic seed migration or an admin API
call), never a code change or a redeploy.

## Seeded baseline (migration `0003_seed_rbac_baseline.py`)

| Role | Purpose |
|---|---|
| `super_admin` | Full system access, all 15 permissions |
| `institution_admin` | Manages users/roles within their institution |
| `teacher` | Manages own sessions/profile, future grading permissions |
| `student` | Manages own sessions/profile only |

34 `role_permission` grants total. Exact grant matrix lives in
`app.core.constants.DEFAULT_ROLE_PERMISSIONS` — read that dict rather than
this doc if you need the current authoritative mapping, since it's the
value the seed migration actually inserts.

## `CurrentUser`

`app.core.rbac.CurrentUser` is the object every protected endpoint receives
via the `CurrentUserDep` dependency. It pre-computes two frozensets at
construction time (not on every check) from the eager-loaded relationship
chain:

```python
self.role_names: frozenset[str] = frozenset(ur.role.name for ur in user.user_roles)
self.permissions: frozenset[str] = frozenset(
    role_permission.permission.code
    for user_role in user.user_roles
    for role_permission in user_role.role.role_permissions
)
```

This requires `UserRepository`'s `_with_roles()` to eager-load **four
levels deep** (`user_roles` → `role` → `role_permissions` → `permission`)
via `selectinload`. Shortcutting this chain reintroduces a
`MissingGreenlet` error — SQLAlchemy's async ORM cannot lazy-load a
relationship outside the request's async context, and `CurrentUser`'s
`__init__` runs after the dependency's `await` has already returned.

## Enforcing authorization on an endpoint

Two FastAPI dependency factories, both in `app.core.rbac`:

```python
@router.get("/admin-only", dependencies=[Depends(require_roles(Role.SUPER_ADMIN))])
async def admin_only(): ...

@router.delete(
    "/sessions/{session_id}",
    dependencies=[Depends(require_permissions(PermissionCode.SESSIONS_REVOKE))],
)
async def revoke_session(session_id: uuid.UUID, current_user: CurrentUserDep): ...
```

- `require_roles(*role_names)` — passes if the user holds **any** of the
  named roles.
- `require_permissions(*permission_codes)` — passes if the user holds
  **all** of the named permission codes (AND semantics — a caller needing
  either/or should call it twice as separate `Depends` in an `or` pattern,
  or add a dedicated any-of variant when that need actually arises).

**Every** non-public endpoint in Module 02 uses one of these two
dependencies — there is no endpoint that hand-rolls its own role/permission
check. This is enforced by convention and by test coverage
(`test_rbac.py`), not by a lint rule; keep it that way when adding
endpoints.

Prefer `require_permissions` over `require_roles` for anything that isn't
inherently role-shaped (e.g. "can view any user's profile") — permissions
compose across future roles without editing the endpoint, roles don't.

## Future policy-engine compatibility

`CurrentUser.has_role()` / `has_permission()` are the only two query methods
exposed. If a future module needs attribute-based or resource-scoped
authorization (e.g. "a teacher can only grade answer scripts belonging to
their own institution"), that logic should be added as an **additional**
service-layer check called from within the endpoint/service — not bolted
onto `CurrentUser`, which represents the user's *global* grant, not a
per-resource decision. Keeping these separate is what lets a real policy
engine (OPA, Casbin, or similar) be introduced later as a service-layer
concern without touching the `require_roles`/`require_permissions`
dependency surface every endpoint already depends on.

## Frontend authorization

`routes/guards/RoleGuard.tsx` and `PermissionGuard.tsx` mirror the backend
semantics using `user.roles` / `user.permissions` from the `/users/me`
response (both arrays are already resolved server-side via
`RBACService.role_names` / `effective_permissions` — the frontend never
computes effective permissions itself, it only checks membership). Neither
guard is currently nested under any route, since every `/dashboard/*` route
in Module 02 is self-service (a user managing their own profile/sessions);
they exist and are tested so the first admin-only page in a future module
can nest under them with no new guard code.
