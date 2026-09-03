"""Document Intelligence milestone — page quality/enhancement metadata + unified region detection

Purely additive:

1. `answer_script_pages` gains 5 nullable columns: `quality_score`,
   `quality_classification`, `quality_metrics` (JSON), `enhancement_metadata`
   (JSON), `processing_substage`. `preprocessed_storage_key` already
   existed (added in an earlier Module 05 migration) but was never
   actually populated by `_run_pipeline` until this milestone's fix —
   no schema change needed for that field, just a code-side fix.

2. `official_exam_document_pages` gains the same 5 columns PLUS
   `preprocessed_storage_key` (which `answer_script_pages` already had
   but this parallel Module 06 table never did) — so Question Paper/Model
   Answer pages can carry the same original-vs-enhanced provenance
   `AnswerScriptPage` already could.

3. New `document_regions` table — one row per detected layout region
   (Section 14's unified `PageRegion` concept), belonging to EITHER an
   `AnswerScriptPage` OR an `OfficialExamDocumentPage` (exactly one FK
   set, enforced by a CHECK constraint) — see
   `app.models.document_region.DocumentRegion`'s docstring for why this
   is a genuinely new table rather than a retrofit of `OCRBlock`.

No existing column altered or dropped; no existing OCR/answer-script data
touched.

Revision ID: 0019_document_intelligence
Revises: 0018_seed_isolated_local_ocr_providers
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_document_intelligence"
down_revision: str | None = "0018_seed_isolated_local_ocr_providers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- answer_script_pages: quality/enhancement metadata ---
    op.add_column(
        "answer_script_pages", sa.Column("quality_score", sa.Numeric(5, 2), nullable=True)
    )
    op.add_column(
        "answer_script_pages",
        sa.Column("quality_classification", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "answer_script_pages", sa.Column("quality_metrics", sa.JSON(), nullable=True)
    )
    op.add_column(
        "answer_script_pages", sa.Column("enhancement_metadata", sa.JSON(), nullable=True)
    )
    op.add_column(
        "answer_script_pages", sa.Column("processing_substage", sa.String(length=30), nullable=True)
    )

    # --- official_exam_document_pages: same fields + the storage-key
    # column answer_script_pages already had ---
    op.add_column(
        "official_exam_document_pages",
        sa.Column("preprocessed_storage_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "official_exam_document_pages", sa.Column("quality_score", sa.Numeric(5, 2), nullable=True)
    )
    op.add_column(
        "official_exam_document_pages",
        sa.Column("quality_classification", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "official_exam_document_pages", sa.Column("quality_metrics", sa.JSON(), nullable=True)
    )
    op.add_column(
        "official_exam_document_pages", sa.Column("enhancement_metadata", sa.JSON(), nullable=True)
    )
    op.add_column(
        "official_exam_document_pages",
        sa.Column("processing_substage", sa.String(length=30), nullable=True),
    )

    # --- document_regions (new table) ---
    op.create_table(
        "document_regions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("institution_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("answer_script_page_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("official_exam_document_page_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("parent_region_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("region_type", sa.String(length=30), nullable=False),
        sa.Column("source_label", sa.String(length=50), nullable=False),
        sa.Column("source_detector", sa.String(length=30), nullable=False),
        sa.Column("reading_order", sa.Integer(), nullable=False),
        sa.Column("bbox_left", sa.Integer(), nullable=False),
        sa.Column("bbox_top", sa.Integer(), nullable=False),
        sa.Column("bbox_width", sa.Integer(), nullable=False),
        sa.Column("bbox_height", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("classification_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("crop_storage_key", sa.String(length=500), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
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
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["answer_script_page_id"], ["answer_script_pages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["official_exam_document_page_id"],
            ["official_exam_document_pages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["parent_region_id"], ["document_regions.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "(answer_script_page_id IS NOT NULL) != (official_exam_document_page_id IS NOT NULL)",
            name="ck_document_region_exactly_one_parent",
        ),
    )
    op.create_index(
        op.f("ix_document_regions_institution_id"), "document_regions", ["institution_id"]
    )
    op.create_index(
        op.f("ix_document_regions_answer_script_page_id"),
        "document_regions",
        ["answer_script_page_id"],
    )
    op.create_index(
        op.f("ix_document_regions_official_exam_document_page_id"),
        "document_regions",
        ["official_exam_document_page_id"],
    )
    op.create_index(op.f("ix_document_regions_region_type"), "document_regions", ["region_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_document_regions_region_type"), table_name="document_regions")
    op.drop_index(
        op.f("ix_document_regions_official_exam_document_page_id"), table_name="document_regions"
    )
    op.drop_index(
        op.f("ix_document_regions_answer_script_page_id"), table_name="document_regions"
    )
    op.drop_index(op.f("ix_document_regions_institution_id"), table_name="document_regions")
    op.drop_table("document_regions")

    op.drop_column("official_exam_document_pages", "processing_substage")
    op.drop_column("official_exam_document_pages", "enhancement_metadata")
    op.drop_column("official_exam_document_pages", "quality_metrics")
    op.drop_column("official_exam_document_pages", "quality_classification")
    op.drop_column("official_exam_document_pages", "quality_score")
    op.drop_column("official_exam_document_pages", "preprocessed_storage_key")

    op.drop_column("answer_script_pages", "processing_substage")
    op.drop_column("answer_script_pages", "enhancement_metadata")
    op.drop_column("answer_script_pages", "quality_metrics")
    op.drop_column("answer_script_pages", "quality_classification")
    op.drop_column("answer_script_pages", "quality_score")
