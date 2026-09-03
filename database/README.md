# Database

The single source of truth for the schema is **Alembic**, versioned inside
`backend/alembic/`. This top-level `database/` directory holds operational
concerns that sit alongside — not inside — the application:

- `migrations/` — reference copy / notes on migration strategy (Alembic itself
  lives under `backend/alembic/versions`)
- `seeds/` — future seed data scripts (non-production reference/lookup data only)

No business tables are defined yet — see [docs/database-standards.md](../docs/database-standards.md).
