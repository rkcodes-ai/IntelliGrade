# Rollback Guide (Module 08)

## When to roll back

Immediately after a deploy, if: elevated 5xx rate, `/health/ready` won't
return to `ready`, a smoke test fails, or Grafana shows a clear latency/
error regression correlated with the deploy time. Don't spend more than a
few minutes debugging forward before rolling back — a known-good previous
image is one command away; a prolonged outage while root-causing under
pressure is worse than a rollback followed by calm root-causing after.

## Application rollback (no migration involved)

If the release didn't include a database migration, or the migration was
purely additive (new nullable column/table — safe for the old code to
ignore):

```bash
# Roll the images back to the previous commit SHA tag (from GHCR)
docker compose -f docker-compose.prod.yml pull backend@sha256:<previous-digest> \
  worker@sha256:<previous-digest> frontend@sha256:<previous-digest>
# Or, simpler, if IMAGE_TAG in .env.production is pinned to a commit SHA:
#   set IMAGE_TAG=<previous-sha> in .env.production, then:
docker compose -f docker-compose.prod.yml up -d --no-deps backend worker frontend
```

`.github/workflows/deploy.yml` tags every image by full commit SHA (not
just a mutable `latest`), specifically so a previous release is always
addressable by tag for exactly this scenario.

## Rollback involving a migration

This is why `docs/upgrade-guide.md` insists migrations be
backward-compatible with the previous release — if that principle was
followed, rolling the application back is safe without touching the
schema at all (the old code simply doesn't use the new column/table).

If a migration was **not** backward-compatible (should not happen if the
upgrade guide's principle is followed, but if it did):

1. Do not run `alembic downgrade` against a live database without first
   confirming the downgrade migration doesn't destroy data the new release
   already wrote — it usually does (e.g. dropping a column silently
   discards whatever the new release wrote into it).
2. Prefer rolling the application back first and leaving the schema as-is
   if the old code can tolerate an unused extra column/table (it usually
   can, since Postgres/SQLAlchemy models the old code loads only reference
   columns they know about).
3. Only run `alembic downgrade -1` if the schema change is actually
   incompatible with the old code continuing to run — and take a fresh
   backup immediately before doing so (see `docs/backup-guide.md`).

## Verifying a rollback succeeded

Same checks as a forward deploy (`docs/upgrade-guide.md` step 7–8):
`/health/ready` reports `ready`, `/health/version` shows the expected
(previous) version string, smoke test passes, Grafana error rate returns
to baseline.

## Post-rollback

Treat the rolled-back release as blocked from re-deploying until the root
cause is understood and fixed — don't re-attempt the same deploy hoping
it works the second time. Follow `docs/incident-response-guide.md`'s
post-incident process for anything that triggered a rollback.
