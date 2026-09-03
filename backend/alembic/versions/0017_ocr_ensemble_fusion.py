"""Add OCR Ensemble Mode + Fusion tables/columns

Six-Provider OCR milestone — "OCR Ensemble & Fusion" phase. Purely
additive:

1. New table `ocr_provider_candidates` — one row per (OCRResult, provider)
   pair, preserving each contributing provider's raw output before fusion
   (never discarded). See the model's own docstring for the full
   rationale.
2. `ocr_results` gains three nullable/defaulted columns:
   `is_ensemble_result` (default `False`), `contributing_provider_codes`,
   `disagreement_regions` — every pre-existing row is valid as-is
   (`is_ensemble_result=False`, the other two `NULL`).
3. `ocr_configurations` gains `is_ensemble_enabled` (default `False`) and
   `ensemble_provider_codes` (nullable) — every existing institution's
   OCR behavior is completely unchanged unless an admin explicitly opts
   in.

No existing table is dropped, renamed, or recreated; no existing column
changes type or nullability.

Revision ID: 0017_ocr_ensemble_fusion
Revises: 0016_ocr_job_provider_fallback
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_ocr_ensemble_fusion"
down_revision: str | None = "0016_ocr_job_provider_fallback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_provider_candidates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("institution_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ocr_result_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("structured_content", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ocr_result_id"], ["ocr_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "ocr_result_id", "provider_code", name="uq_ocr_provider_candidate_result_provider"
        ),
    )
    op.create_index(
        "ix_ocr_provider_candidates_institution_id",
        "ocr_provider_candidates",
        ["institution_id"],
    )
    op.create_index(
        "ix_ocr_provider_candidates_ocr_result_id",
        "ocr_provider_candidates",
        ["ocr_result_id"],
    )
    op.create_index(
        "ix_ocr_provider_candidates_provider_code",
        "ocr_provider_candidates",
        ["provider_code"],
    )

    op.add_column(
        "ocr_results",
        sa.Column(
            "is_ensemble_result", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "ocr_results", sa.Column("contributing_provider_codes", sa.JSON(), nullable=True)
    )
    op.add_column("ocr_results", sa.Column("disagreement_regions", sa.JSON(), nullable=True))

    op.add_column(
        "ocr_configurations",
        sa.Column(
            "is_ensemble_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "ocr_configurations", sa.Column("ensemble_provider_codes", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ocr_configurations", "ensemble_provider_codes")
    op.drop_column("ocr_configurations", "is_ensemble_enabled")

    op.drop_column("ocr_results", "disagreement_regions")
    op.drop_column("ocr_results", "contributing_provider_codes")
    op.drop_column("ocr_results", "is_ensemble_result")

    op.drop_index("ix_ocr_provider_candidates_provider_code", table_name="ocr_provider_candidates")
    op.drop_index("ix_ocr_provider_candidates_ocr_result_id", table_name="ocr_provider_candidates")
    op.drop_index(
        "ix_ocr_provider_candidates_institution_id", table_name="ocr_provider_candidates"
    )
    op.drop_table("ocr_provider_candidates")
