"""Seed assessment-domain RBAC data: new permission codes and role grants

Module 04 — Assessment Domain. Adds the permission rows and role grants for
the 148 new assessment `PermissionCode` members (36 entity resource
prefixes x create/read/update/delete, plus `evaluation_history`'s
create/read-only pair and 6 workflow-specific approve/reject/archive
actions on `questions`/`question_papers`) introduced in
`app.core.constants`, along with their entries in
`DEFAULT_ROLE_PERMISSIONS`.

Written to be idempotent with `0003_seed_rbac_baseline` for the exact same
reason `0005_seed_academic_permissions.py` is: `0003` seeds `for perm in
PermissionCode` using the *live* enum, so on a brand new database it will
already have inserted these same codes (since `PermissionCode` already
contains the Module 04 members by the time anyone runs migrations against
a fresh DB). This migration checks what already exists before inserting,
so it is a correct no-op on a fresh DB and a real backfill on any database
whose `0003` ran before the Module 04 permission codes existed — see
`docs/database-standards.md` on migration conventions.

Revision ID: 0007_seed_assessment_permissions
Revises: 0006_create_assessment_domain_tables
Create Date: 2026-07-17
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op
from app.core.constants import DEFAULT_ROLE_PERMISSIONS, PermissionCode, Role

# revision identifiers, used by Alembic.
revision: str = "0007_seed_assessment_permissions"
down_revision: str | None = "0006_create_assessment_domain_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Resource prefixes introduced by Module 04 — mirrors
# `app.core.constants._ASSESSMENT_LOOKUP_PREFIXES` +
# `_ASSESSMENT_CONTENT_PREFIXES` + `_ASSESSMENT_ADMIN_ONLY_PREFIXES` (kept
# as a literal tuple here, rather than importing the private constants, so
# this migration's seed set stays fixed even if that module changes shape).
_ASSESSMENT_PREFIXES = (
    "assessment_types",
    "assessment_statuses",
    "question_categories",
    "question_types",
    "difficulty_levels",
    "bloom_taxonomy_levels",
    "question_tags",
    "questions",
    "question_versions",
    "question_reviews",
    "question_blueprints",
    "question_blueprint_sections",
    "question_paper_templates",
    "question_papers",
    "question_paper_versions",
    "question_paper_sections",
    "question_paper_question_mappings",
    "randomization_strategies",
    "answer_keys",
    "model_answers",
    "alternative_answers",
    "rubrics",
    "rubric_criteria",
    "mark_distributions",
    "expected_keywords",
    "expected_concepts",
    "reference_notes",
    "assessments",
    "assessment_configurations",
    "evaluation_configurations",
    "exams",
    "exam_schedules",
    "exam_sessions",
    "exam_instructions",
    "question_approvals",
    "evaluation_history",
)

NEW_PERMISSION_CODES: tuple[PermissionCode, ...] = tuple(
    perm for perm in PermissionCode if perm.value.split(":")[0] in _ASSESSMENT_PREFIXES
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


def downgrade() -> None:
    bind = op.get_bind()
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
