"""Seed Surya/docTR/TrOCR-Handwritten OCRProvider catalog rows

Surya/docTR/TrOCR isolated-runtime milestone. Purely additive — same
idempotent seed pattern as `0009_seed_ocr_pipeline_permissions.py`'s
`OCRProvider` seed (checks existing `code` values before inserting), and
the same "code exists != this deployment has it enabled" convention
`0014_extend_ocr_provider_metadata.py` established: all three new rows
are `is_implemented=True` (real, runtime-verified adapters exist — see
`app/services/ocr/providers/{surya,doctr,trocr}_provider.py` and this
milestone's final report for the actual verification evidence) but
`is_enabled=False`/`is_default=False`, since each requires its own
isolated venv (`.venv-surya`/`.venv-doctr`/`.venv-trocr`) to exist on a
given deployment before an administrator should flip it on.

New codes only — `tesseract`/`easyocr`/`paddleocr`/`azure_ocr`/
`google_vision`/`aws_textract` (seeded by 0009) are untouched.

Revision ID: 0018_seed_isolated_local_ocr_providers
Revises: 0017_ocr_ensemble_fusion
Create Date: 2026-07-26
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_seed_isolated_local_ocr_providers"
down_revision: str | None = "0017_ocr_ensemble_fusion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (code, name, is_enabled, is_implemented, is_default) — see ADR-032 and
# this migration's own docstring for why is_implemented=True doesn't imply
# is_enabled=True here.
_NEW_PROVIDER_SEED_DATA: tuple[tuple[str, str, bool, bool, bool], ...] = (
    ("surya", "Surya OCR", False, True, False),
    ("doctr", "docTR", False, True, False),
    ("trocr_handwritten", "Microsoft TrOCR (Handwritten)", False, True, False),
)

ocr_providers_table = sa.table(
    "ocr_providers",
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

    existing_codes = {row.code for row in bind.execute(sa.select(ocr_providers_table.c.code))}
    missing = [
        (code, name, is_enabled, is_implemented, is_default)
        for code, name, is_enabled, is_implemented, is_default in _NEW_PROVIDER_SEED_DATA
        if code not in existing_codes
    ]
    if missing:
        op.bulk_insert(
            ocr_providers_table,
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
                for code, name, is_enabled, is_implemented, is_default in missing
            ],
        )


def downgrade() -> None:
    codes = [code for code, *_ in _NEW_PROVIDER_SEED_DATA]
    op.execute(ocr_providers_table.delete().where(ocr_providers_table.c.code.in_(codes)))
