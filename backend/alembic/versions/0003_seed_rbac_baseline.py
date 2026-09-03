"""Seed baseline RBAC data: the four canonical roles, permission set, and grants

Data-only migration — no schema changes. Inserts:
  - the four system roles (`app.core.constants.Role`)
  - every permission code (`app.core.constants.PermissionCode`)
  - the default role→permission grants (`app.core.constants.DEFAULT_ROLE_PERMISSIONS`)

Uses lightweight `sa.table()` reflections rather than importing the ORM
models directly, so this migration's behavior stays fixed even if the
`User`/`Role`/`Permission` model classes change shape later — see
`docs/database-standards.md` on migration conventions. The enum *values*
(role names, permission codes) are imported from `app.core.constants`
since they're the actual seed content, not model behavior.

Revision ID: 0003_seed_rbac_baseline
Revises: 0002_create_iam_tables
Create Date: 2026-07-16
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.core.constants import DEFAULT_ROLE_PERMISSIONS, PermissionCode, Role

# revision identifiers, used by Alembic.
revision: str = "0003_seed_rbac_baseline"
down_revision: str | None = "0002_create_iam_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_DESCRIPTIONS: dict[Role, str] = {
    Role.SUPER_ADMIN: "Full platform access across all institutions.",
    Role.INSTITUTION_ADMIN: "Manages users and settings within their institution.",
    Role.TEACHER: "Creates and evaluates answer scripts for their classes.",
    Role.STUDENT: "Submits answer scripts and views their own results.",
}

roles_table = sa.table(
    "roles",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("is_system", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("resource", sa.String()),
    sa.column("action", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("id", sa.Uuid()),
    sa.column("role_id", sa.Uuid()),
    sa.column("permission_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    now = datetime.now(UTC)

    role_ids: dict[Role, uuid.UUID] = {role: uuid.uuid4() for role in Role}
    op.bulk_insert(
        roles_table,
        [
            {
                "id": role_ids[role],
                "name": role.value,
                "description": _ROLE_DESCRIPTIONS[role],
                "is_system": True,
                "created_at": now,
                "updated_at": now,
            }
            for role in Role
        ],
    )

    permission_ids: dict[PermissionCode, uuid.UUID] = {
        perm: uuid.uuid4() for perm in PermissionCode
    }
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": permission_ids[perm],
                "code": perm.value,
                "resource": perm.value.split(":")[0],
                "action": perm.value.split(":")[1],
                "description": None,
                "created_at": now,
                "updated_at": now,
            }
            for perm in PermissionCode
        ],
    )

    grants = [
        {
            "id": uuid.uuid4(),
            "role_id": role_ids[role],
            "permission_id": permission_ids[perm],
            "created_at": now,
            "updated_at": now,
        }
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
        for perm in perms
    ]
    op.bulk_insert(role_permissions_table, grants)


def downgrade() -> None:
    op.execute(role_permissions_table.delete())
    op.execute(permissions_table.delete())
    op.execute(roles_table.delete().where(roles_table.c.is_system.is_(True)))
