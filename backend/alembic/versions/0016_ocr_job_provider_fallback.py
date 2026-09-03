"""Add OCR provider fallback tracking to ocr_jobs

Six-Provider OCR milestone, Phase 12 (provider fallback strategy). Two
purely additive, nullable columns on `ocr_jobs`:

- `requested_ocr_provider_id` -- only populated when the job's actual
  `ocr_provider_id` differs from what was originally resolved (i.e. a
  fallback happened). NULL is the common case ("ran exactly as
  requested"), not a second copy of `ocr_provider_id` duplicated on every
  row.
- `fallback_reason` -- the original provider's real error message, so a
  fallback is always visible/auditable in the job record itself, never
  silent.

See `app/tasks/ocr_tasks.py`'s `_run_pipeline` for where this is set (at
most one fallback attempt per job, to the always-available `tesseract`
provider, never a cascading chain through all six providers).

Revision ID: 0016_ocr_job_provider_fallback
Revises: 0015_create_ai_reference_answer_tables
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_ocr_job_provider_fallback"
down_revision: str | None = "0015_create_ai_reference_answer_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ocr_jobs", sa.Column("requested_ocr_provider_id", sa.Uuid(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_ocr_jobs_requested_ocr_provider_id",
        "ocr_jobs",
        "ocr_providers",
        ["requested_ocr_provider_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocr_jobs_requested_ocr_provider_id",
        "ocr_jobs",
        ["requested_ocr_provider_id"],
    )
    op.add_column("ocr_jobs", sa.Column("fallback_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ocr_jobs", "fallback_reason")
    op.drop_index("ix_ocr_jobs_requested_ocr_provider_id", table_name="ocr_jobs")
    op.drop_constraint("fk_ocr_jobs_requested_ocr_provider_id", "ocr_jobs", type_="foreignkey")
    op.drop_column("ocr_jobs", "requested_ocr_provider_id")
