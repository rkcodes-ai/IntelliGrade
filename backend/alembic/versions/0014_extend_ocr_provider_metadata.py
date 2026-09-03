"""Extend OCRResult with provider metadata + mark all six OCR providers implemented

Module 12 — Enterprise Multi-OCR Platform. Two purely additive changes, no
existing entity is redesigned (see `ARCHITECTURE_DECISIONS.md` ADR-028/
ADR-032 and this module's own report):

1. Adds four nullable columns to `ocr_results` -- `provider_version`,
   `processing_time_ms`, `image_resolution`, `raw_response_reference` --
   so every OCR run can record which provider version produced it, how
   long it took, the processed image's resolution, and (optionally) a
   pointer to the provider's raw native response. All nullable: every
   pre-Module-12 row, and any provider/call site that doesn't populate a
   given field, stays valid.

2. Updates the `ocr_providers` seed data: EasyOCR, PaddleOCR, Azure OCR,
   Google Vision, and AWS Textract now have real adapter code (previously
   `is_implemented=False` "registered but not implemented" stubs, per
   ADR-032) -- this flips `is_implemented` to `True` for those five rows.
   `is_enabled`/`is_default` are deliberately left as-is (still `False`):
   `is_implemented=True` means "code exists", not "this deployment has
   configured credentials for it" -- an administrator must still enable
   each provider explicitly once it's configured (see
   `OCRProviderService.update`'s `is_enabled` requires `is_implemented`
   rule, unaffected by this migration). Tesseract's row is untouched.

Revision ID: 0014_extend_ocr_provider_metadata
Revises: 0013_seed_module07_permissions
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_extend_ocr_provider_metadata"
down_revision: str | None = "0013_seed_module07_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEWLY_IMPLEMENTED_CODES = ("easyocr", "paddleocr", "azure_ocr", "google_vision", "aws_textract")

ocr_providers_table = sa.table(
    "ocr_providers",
    sa.column("code", sa.String()),
    sa.column("is_implemented", sa.Boolean()),
)


def upgrade() -> None:
    op.add_column("ocr_results", sa.Column("provider_version", sa.String(length=50), nullable=True))
    op.add_column("ocr_results", sa.Column("processing_time_ms", sa.Integer(), nullable=True))
    op.add_column("ocr_results", sa.Column("image_resolution", sa.String(length=20), nullable=True))
    op.add_column(
        "ocr_results", sa.Column("raw_response_reference", sa.String(length=500), nullable=True)
    )

    op.execute(
        ocr_providers_table.update()
        .where(ocr_providers_table.c.code.in_(_NEWLY_IMPLEMENTED_CODES))
        .values(is_implemented=True)
    )


def downgrade() -> None:
    op.execute(
        ocr_providers_table.update()
        .where(ocr_providers_table.c.code.in_(_NEWLY_IMPLEMENTED_CODES))
        .values(is_implemented=False)
    )

    op.drop_column("ocr_results", "raw_response_reference")
    op.drop_column("ocr_results", "image_resolution")
    op.drop_column("ocr_results", "processing_time_ms")
    op.drop_column("ocr_results", "provider_version")
