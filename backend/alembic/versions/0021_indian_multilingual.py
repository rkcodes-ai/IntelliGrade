"""Indian Multilingual Document Intelligence milestone (Step 4.2) — script/language detection evidence + reviewer override

Purely additive:

1. `ocr_results` gains one nullable JSON column,
   `multilingual_metadata` — the same "one JSON blob" convention already
   used for `disagreement_regions`/`language_quality_metadata` on this
   same table — holding script detection, fastText language-
   identification, resolved `LanguageContext`, and OCR-routing
   provenance (`RoutingDecision.to_dict()`). `OCRResult.language`
   (pre-existing column, previously always hardcoded to `"eng"` at the
   call site) is now actually SET from the resolved context — no schema
   change needed for that, a code-side fix only, same precedent as
   `preprocessed_storage_key` in migration 0019's own docstring.

2. `ocr_results` gains three nullable columns for reviewer override
   (Section 38): `language_reviewer_verified_language` (String),
   `language_reviewer_id` (UUID, FK to users, SET NULL on delete so a
   deleted reviewer account never blocks deleting itself), and
   `language_reviewer_verified_at` (DateTime). All nullable — most rows
   will never have a reviewer override, and that's the correct default
   state, not an error.

No existing column altered or dropped; no existing OCR data touched.

Revision ID: 0021_indian_multilingual
Revises: 0020_language_quality
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021_indian_multilingual"
down_revision: str | None = "0020_language_quality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ocr_results", sa.Column("multilingual_metadata", sa.JSON(), nullable=True))
    op.add_column(
        "ocr_results",
        sa.Column("language_reviewer_verified_language", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ocr_results",
        sa.Column("language_reviewer_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ocr_results",
        sa.Column(
            "language_reviewer_verified_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_ocr_results_language_reviewer_id_users",
        "ocr_results",
        "users",
        ["language_reviewer_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ocr_results_language_reviewer_id_users", "ocr_results", type_="foreignkey"
    )
    op.drop_column("ocr_results", "language_reviewer_verified_at")
    op.drop_column("ocr_results", "language_reviewer_id")
    op.drop_column("ocr_results", "language_reviewer_verified_language")
    op.drop_column("ocr_results", "multilingual_metadata")
