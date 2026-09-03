"""Create ai_reference_answers table + extend answer_evaluations

AI Reference Answer Builder milestone. Purely additive:

1. Creates `ai_reference_answers` (new table) — see
   `app.models.ai_reference_answer.AIReferenceAnswer` for the full field
   rationale. Anchored to `extracted_questions`/`extracted_model_answers`
   (Module 06's real evaluation-pipeline entities), not Module 04's
   `AnswerKey`-based bank, per the milestone's Phase 0 audit.
2. Adds two nullable columns to `answer_evaluations`:
   `ai_reference_answer_id` (traceability FK) and `used_legacy_reference`
   (Phase 9's explicit, visible fallback marker — backfilled `TRUE` for
   every pre-existing row, since they were all necessarily scored against
   the raw `ExtractedModelAnswer`, this feature not having existed yet).
3. Seeds the 5 new `ai_reference_answers:*` permission codes (idempotent,
   same pattern as `0009`/`0011`/`0013`).
4. Updates `ai_providers` seed data: `openai`/`anthropic` now have real
   adapter code (`OpenAIProvider`/`AnthropicProvider`, both `evaluate()`
   and `generate_reference()`) — flips `is_implemented` to `True` for
   both. `is_enabled`/`is_default` deliberately left `False`: an
   administrator must still configure `OPENAI_API_KEY`/
   `ANTHROPIC_API_KEY` and explicitly enable each one (same
   "implemented != configured" distinction `0014` established for the
   OCR cloud providers).

Revision ID: 0015_create_ai_reference_answer_tables
Revises: 0014_extend_ocr_provider_metadata
Create Date: 2026-07-25
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op
from app.core.constants import DEFAULT_ROLE_PERMISSIONS, PermissionCode, Role

# revision identifiers, used by Alembic.
revision: str = "0015_create_ai_reference_answer_tables"
down_revision: str | None = "0014_extend_ocr_provider_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_PREFIXES = ("ai_reference_answers",)
NEW_PERMISSION_CODES: tuple[PermissionCode, ...] = tuple(
    perm for perm in PermissionCode if perm.value.split(":")[0] in _NEW_PREFIXES
)

_NEWLY_IMPLEMENTED_AI_PROVIDER_CODES = ("openai", "anthropic")

roles_table = sa.table(
    "roles", sa.column("id", sa.Uuid()), sa.column("name", sa.String())
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
    "ai_providers", sa.column("code", sa.String()), sa.column("is_implemented", sa.Boolean())
)


def upgrade() -> None:
    # --- 1. ai_reference_answers ---
    op.create_table(
        "ai_reference_answers",
        sa.Column("extracted_question_id", sa.Uuid(), nullable=False),
        sa.Column("extracted_model_answer_id", sa.Uuid(), nullable=True),
        sa.Column("rubric_id", sa.Uuid(), nullable=True),
        sa.Column("ai_provider_id", sa.Uuid(), nullable=False),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("official_model_answer_text", sa.Text(), nullable=False),
        sa.Column("synthesized_reference_answer", sa.Text(), nullable=True),
        sa.Column("structured_content", sa.JSON(), nullable=True),
        sa.Column("maximum_marks", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("marks_source", sa.String(length=20), nullable=False),
        sa.Column("provider_model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("generation_confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("generation_metadata", sa.JSON(), nullable=True),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.Column("has_conflict_flag", sa.Boolean(), nullable=False),
        sa.Column("conflict_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ai_provider_id"], ["ai_providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["extracted_model_answer_id"], ["extracted_model_answers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["extracted_question_id"], ["extracted_questions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "extracted_question_id", "version", name="uq_ai_reference_answer_question_version"
        ),
    )
    op.create_index(
        op.f("ix_ai_reference_answers_extracted_question_id"),
        "ai_reference_answers",
        ["extracted_question_id"],
    )
    op.create_index(
        op.f("ix_ai_reference_answers_extracted_model_answer_id"),
        "ai_reference_answers",
        ["extracted_model_answer_id"],
    )
    op.create_index(
        op.f("ix_ai_reference_answers_institution_id"), "ai_reference_answers", ["institution_id"]
    )
    op.create_index(
        op.f("ix_ai_reference_answers_is_current"), "ai_reference_answers", ["is_current"]
    )
    op.create_index(op.f("ix_ai_reference_answers_status"), "ai_reference_answers", ["status"])

    # --- 2. answer_evaluations additive columns ---
    op.add_column(
        "answer_evaluations", sa.Column("ai_reference_answer_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "answer_evaluations",
        sa.Column(
            "used_legacy_reference",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index(
        op.f("ix_answer_evaluations_ai_reference_answer_id"),
        "answer_evaluations",
        ["ai_reference_answer_id"],
    )
    op.create_foreign_key(
        "fk_answer_evaluations_ai_reference_answer_id",
        "answer_evaluations",
        "ai_reference_answers",
        ["ai_reference_answer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- 3. RBAC seed (idempotent, same pattern as 0009/0011/0013) ---
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
            if permission_id is None or (role_id, permission_id) in existing_grants:
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

    # --- 4. openai/anthropic now have real adapter code ---
    op.execute(
        ai_providers_table.update()
        .where(ai_providers_table.c.code.in_(_NEWLY_IMPLEMENTED_AI_PROVIDER_CODES))
        .values(is_implemented=True)
    )


def downgrade() -> None:
    op.execute(
        ai_providers_table.update()
        .where(ai_providers_table.c.code.in_(_NEWLY_IMPLEMENTED_AI_PROVIDER_CODES))
        .values(is_implemented=False)
    )

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

    op.drop_constraint(
        "fk_answer_evaluations_ai_reference_answer_id", "answer_evaluations", type_="foreignkey"
    )
    op.drop_index(
        op.f("ix_answer_evaluations_ai_reference_answer_id"), table_name="answer_evaluations"
    )
    op.drop_column("answer_evaluations", "used_legacy_reference")
    op.drop_column("answer_evaluations", "ai_reference_answer_id")

    op.drop_index(op.f("ix_ai_reference_answers_status"), table_name="ai_reference_answers")
    op.drop_index(op.f("ix_ai_reference_answers_is_current"), table_name="ai_reference_answers")
    op.drop_index(
        op.f("ix_ai_reference_answers_institution_id"), table_name="ai_reference_answers"
    )
    op.drop_index(
        op.f("ix_ai_reference_answers_extracted_model_answer_id"),
        table_name="ai_reference_answers",
    )
    op.drop_index(
        op.f("ix_ai_reference_answers_extracted_question_id"), table_name="ai_reference_answers"
    )
    op.drop_table("ai_reference_answers")
