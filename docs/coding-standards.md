# Coding Standards

## General principles

- **SOLID, DRY, KISS, YAGNI.** Don't build abstractions for a second
  implementation that doesn't exist yet. Three similar lines beat a
  premature generic helper.
- **Strong typing everywhere.** Python: full type hints, `mypy --strict`
  target (currently non-blocking in CI until domain modules stabilize the
  patterns — see `lint.yml`). TypeScript: `strict: true`, no `any` without a
  comment explaining why.
- **Errors are handled at the boundary, not swallowed silently.** Backend:
  raise `app.core.exceptions.AppError` subclasses from services; let the
  registered exception handlers translate them to HTTP. Frontend: let
  TanStack Query surface fetch errors (`isError`/`error`) rather than
  catching and discarding them.
- **Comments explain WHY, not WHAT.** Well-named functions/variables explain
  what the code does. A comment earns its place only when it captures a
  non-obvious constraint, a workaround, or a reason a reader would otherwise
  have to dig through git blame to find.

## Python (backend)

- Formatter: **Black** (line length 100). Import order: **isort** (black
  profile). Linter: **Ruff** (`E, F, W, I, B, C4, UP, SIM, N`).
- Layering is enforced by convention, not tooling: API → Service →
  Repository → Model (see [architecture.md](architecture.md)). Don't import
  `app.db.session` inside `app/api/` — go through a service.
- Async all the way down for I/O: routes, services, repositories, and the DB
  session are all `async`. Don't mix sync DB calls into the async engine.
- Prefer `app.core.exceptions.AppError` subclasses over raising
  `HTTPException` directly in services (keeps services HTTP-agnostic).
- New Pydantic schemas extend `app.schemas.base.BaseSchema` (already sets
  `from_attributes=True` for ORM compatibility and `extra="forbid"`).

## TypeScript (frontend)

- Formatter: **Prettier** (100 char width, double quotes, trailing commas).
  Linter: **ESLint** (typescript-eslint recommended + react-hooks +
  react-refresh).
- Server state → **TanStack Query**. Client-only cross-page state →
  **Redux Toolkit**. Don't duplicate server data into Redux.
- UI primitives live in `src/components/ui/` and follow the shadcn/ui
  convention: `forwardRef`, `cn()` for class merging, `cva()` for variants.
  Compose primitives in `pages/`/`components/layout/` rather than adding
  one-off styled elements.
- Path alias `@/*` maps to `src/*` — use it instead of relative `../../..`
  chains.
- Every new environment variable goes through `src/config/env.ts`'s Zod
  schema — no raw `import.meta.env.X` reads elsewhere.

## Naming

- Backend: `snake_case` for files/functions/variables, `PascalCase` for
  classes, `UPPER_CASE` for constants and settings (the latter is an
  intentional Ruff `N802` exception documented in `backend/pyproject.toml`).
- Frontend: `PascalCase` for components and their files, `camelCase` for
  functions/variables/hooks (`useXyz`), `PascalCase` for types/interfaces.

## Testing

- Every bug fix gets a regression test. Every new service/repository method
  gets a unit test. See [api-standards.md](api-standards.md) for endpoint
  test expectations.
- Don't mock what you don't have to — prefer testing against the real
  in-process app (`httpx.AsyncClient` + `ASGITransport` on the backend,
  Testing Library on the frontend) over mocking framework internals.
