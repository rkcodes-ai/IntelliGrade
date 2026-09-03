"""Seed Module 06 RBAC data and the AIProvider system catalog

Module 06 — Official Exam Content Ingestion & AI Evaluation. Adds the
permission rows and role grants for the 26 new `PermissionCode` members
introduced in `app.core.constants` (`official_exam_documents`,
`official_exam_document_pages`, `extracted_questions`,
`extracted_model_answers`, `mark_scheme_ranges`, `ai_providers`,
`ai_configurations`, `answer_evaluations`), along with their entries in
`DEFAULT_ROLE_PERMISSIONS`. Also seeds the three `AIProvider` catalog rows
(`lexical_heuristic`, `openai`, `anthropic`) — only `lexical_heuristic` is
`is_implemented=True`/`is_enabled=True`/`is_default=True`; the other two
exist as honest "registered but not implemented" catalog entries (see
ADR-041).

Written to be idempotent with `0003_seed_rbac_baseline` for the exact same
reason `0005`/`0007`/`0009_seed_ocr_pipeline_permissions.py` are: `0003`
seeds `for perm in PermissionCode` using the *live* enum, so on a brand
new database it will already have inserted these same codes. This
migration checks what already exists before inserting, so it is a correct
no-op on a fresh DB and a real backfill on any database whose `0003` ran
before the Module 06 permission codes existed. The `AIProvider` seed is
similarly idempotent (checks existing `code` values before inserting).

Revision ID: 0011_seed_module06_permissions
Revises: 0010_create_module06_tables
Create Date: 2026-07-19
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op
from app.core.constants import DEFAULT_ROLE_PERMISSIONS, PermissionCode, Role

# revision identifiers, used by Alembic.
revision: str = "0011_seed_module06_permissions"
down_revision: str | None = "0010_create_module06_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Resource prefixes introduced by Module 06 — mirrors the union of
# `app.core.constants._AI_READ_ONLY_GRANTS`/`_AI_VERIFICATION_AND_REVIEW_GRANTS`/
# `_AI_ADMIN_FULL_CRUD`'s resource segments (kept as a literal tuple here,
# rather than importing the private constants, so this migration's seed
# set stays fixed even if that module changes shape).
_MODULE06_PREFIXES = (
    "official_exam_documents",
    "official_exam_document_pages",
    "extracted_questions",
    "extracted_model_answers",
    "mark_scheme_ranges",
    "ai_providers",
    "ai_configurations",
    "answer_evaluations",
)

NEW_PERMISSION_CODES: tuple[PermissionCode, ...] = tuple(
    perm for perm in PermissionCode if perm.value.split(":")[0] in _MODULE06_PREFIXES
)

# (code, name, is_enabled, is_implemented, is_default) — see ADR-041.
_AI_PROVIDER_SEED_DATA: tuple[tuple[str, str, bool, bool, bool], ...] = (
    ("lexical_heuristic", "Lexical Heuristic", True, True, True),
    ("openai", "OpenAI", False, False, False),
    ("anthropic", "Anthropic", False, False, False),
)

roles_table = sa.table(
    "roles",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.String()),
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

ai_providers_table = sa.table(
    "ai_providers",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("is_enabled", sa.Boolean()),
    sa.column("is_implemented", sa.Boolean()),
    sa.column("is_default", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    permission_ids: dict[PermissionCode, uuid.UUID] = {
        PermissionCode(row.code): row.id
        for row in bind.execute(sa.select(permissions_table.c.id, permissions_table.c.code))
    }

    missing_codes = [perm for perm in NEW_PERMISSION_CODES if perm not in permission_ids]
    if missing_codes:
        new_ids = {perm: uuid.uuid4() for perm in missing_codes}
        op.bulk_insert(
            permissions_table,
            [
                {
                    "id": new_ids[perm],
                    "code": perm.value,
                    "resource": perm.value.split(":")[0],
                    "action": perm.value.split(":")[1],
                    "description": None,
                    "created_at": now,
                    "updated_at": now,
                }
                for perm in missing_codes
            ],
        )
        permission_ids.update(new_ids)

    role_ids: dict[Role, uuid.UUID] = {
        Role(row.name): row.id
        for row in bind.execute(sa.select(roles_table.c.id, roles_table.c.name))
    }

    existing_grants = {
        (row.role_id, row.permission_id)
        for row in bind.execute(
            sa.select(role_permissions_table.c.role_id, role_permissions_table.c.permission_id)
        )
    }

    grants = []
    for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
        role_id = role_ids.get(role)
        if role_id is None:
            continue
        for perm in perms:
            if perm not in NEW_PERMISSION_CODES:
                continue
            permission_id = permission_ids.get(perm)
            if permission_id is None:
                continue
            if (role_id, permission_id) in existing_grants:
                continue
            grants.append(
                {
                    "id": uuid.uuid4(),
                    "role_id": role_id,
                    "permission_id": permission_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    if grants:
        op.bulk_insert(role_permissions_table, grants)

    existing_provider_codes = {
        row.code for row in bind.execute(sa.select(ai_providers_table.c.code))
    }
    missing_providers = [
        (code, name, is_enabled, is_implemented, is_default)
        for code, name, is_enabled, is_implemented, is_default in _AI_PROVIDER_SEED_DATA
        if code not in existing_provider_codes
    ]
    if missing_providers:
        op.bulk_insert(
            ai_providers_table,
            [
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "name": name,
                    "description": None,
                    "is_enabled": is_enabled,
                    "is_implemented": is_implemented,
                    "is_default": is_default,
                    "created_at": now,
                    "updated_at": now,
                }
                for code, name, is_enabled, is_implemented, is_default in missing_providers
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()

    provider_codes = [code for code, *_ in _AI_PROVIDER_SEED_DATA]
    op.execute(ai_providers_table.delete().where(ai_providers_table.c.code.in_(provider_codes)))

    codes = [perm.value for perm in NEW_PERMISSION_CODES]
    permission_ids = [
        row.id
        for row in bind.execute(
            sa.select(permissions_table.c.id).where(permissions_table.c.code.in_(codes))
        )
    ]
    if permission_ids:
        op.execute(
            role_permissions_table.delete().where(
                role_permissions_table.c.permission_id.in_(permission_ids)
            )
        )
        op.execute(permissions_table.delete().where(permissions_table.c.id.in_(permission_ids)))
