"""Initial baseline (no business tables)

Establishes the migration chain and enables the `pgcrypto` extension for
future crypto/random needs (e.g. `gen_random_uuid()` if a model ever wants
server-side UUID generation). Note: `app.models.base.UUIDPrimaryKeyMixin`
generates primary-key UUIDs application-side via Python's `uuid.uuid4()`,
not `gen_random_uuid()` — pgcrypto is not required for that mixin specifically,
it's provisioned here as a generally-useful baseline extension. Intentionally
creates no application tables — Module 01 is foundation-only.

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')


def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
