# Shared

Cross-cutting types, constants, and utilities intended to be consumed by *both*
`backend/` and `frontend/` (or by future extracted microservices) without duplication.

- `types/` — language-agnostic contract definitions (kept in sync with OpenAPI-generated
  frontend types; not a runtime dependency of either app yet)
- `constants/` — shared enums/constants (roles, status codes, error codes)
- `utils/` — pure, dependency-free helper specs/documentation

This directory intentionally holds no business logic in Module 01.
