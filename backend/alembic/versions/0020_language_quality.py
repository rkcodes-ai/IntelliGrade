"""Language Quality Intelligence milestone (Step 4.1) — grammar/spelling evidence storage + rubric opt-in

Purely additive:

1. `ocr_results` gains one nullable JSON column, `language_quality_metadata`
   — the same "one JSON blob" convention already used for
   `disagreement_regions`/`DocumentRegion.extra_metadata` — for
   `LanguageEvidence.to_dict()` persistence. Chosen over a new table
   since this is 1:1 with `OCRResult` (one language analysis per page's
   fused text), matching the existing `average_confidence`/
   `disagreement_regions` precedent on this same table.

2. `rubric_criteria` gains one NOT NULL boolean column,
   `is_language_criterion`, defaulting to `false` for every existing row
   — an explicit, auditable opt-in flag (Section 4/35 of the milestone:
   "prefer explicit configuration over guessing based solely on
   criterion text") rather than pattern-matching a criterion's freeform
   `name` string to guess whether it's grammar-related. Defaulting to
   `false` preserves the existing "language never affects marks unless
   explicitly authorized" behavior for every pre-existing rubric.

No existing column altered or dropped; no existing OCR/rubric data
touched.

Revision ID: 0020_language_quality
Revises: 0019_document_intelligence
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_language_quality"
down_revision: str | None = "0019_document_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ocr_results", sa.Column("language_quality_metadata", sa.JSON(), nullable=True)
    )
    op.add_column(
        "rubric_criteria",
        sa.Column(
            "is_language_criterion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("rubric_criteria", "is_language_criterion")
    op.drop_column("ocr_results", "language_quality_metadata")
