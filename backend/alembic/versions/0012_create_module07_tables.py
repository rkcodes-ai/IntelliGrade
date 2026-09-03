"""Create Teacher Review, Result Finalization & Analytics tables (Module 07)

Module 07 — Teacher Review, Result Finalization & Analytics. Adds the
three new tables this module needs on top of Module 06's evaluation
pipeline: `ExamResult` (the per-`ExamSession` finalization/locking root —
see ADR-042), `NotificationEvent` (the storage-only notification
framework — ADR-046), and `ReportJob` (background report-generation
tracking — ADR-045). Teacher Review's remaining new actions
(reject/rerun) are new `AnswerEvaluation.review_status` values and two
new endpoints, not new columns/tables — no `answer_evaluations` schema
change is needed here.

Table bodies were generated from the real ORM metadata via Alembic's
autogenerate diffing engine (`produce_migrations`/`render_python_code`
against an in-memory baseline of the pre-Module-07 tables), then
annotated with section comments to match this project's migration style —
see `docs/database-standards.md`. No data is seeded here — the new
`PermissionCode` rows and their default role grants are seeded by
`0013_seed_module07_permissions.py`, the next migration (same idempotent-
seed pattern as `0011_seed_module06_permissions.py`).

Revision ID: 0012_create_module07_tables
Revises: 0011_seed_module06_permissions
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_create_module07_tables"
down_revision: str | None = "0011_seed_module06_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- notification_events (storage-only framework — ADR-046) ---
    op.create_table(
        "notification_events",
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_events_event_type"),
        "notification_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_institution_id"),
        "notification_events",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_is_read"), "notification_events", ["is_read"], unique=False
    )
    op.create_index(
        op.f("ix_notification_events_recipient_user_id"),
        "notification_events",
        ["recipient_user_id"],
        unique=False,
    )

    # --- report_jobs (background report generation — ADR-045) ---
    op.create_table(
        "report_jobs",
        sa.Column("report_type", sa.String(length=30), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_jobs_institution_id"), "report_jobs", ["institution_id"], unique=False
    )
    op.create_index(
        op.f("ix_report_jobs_report_type"), "report_jobs", ["report_type"], unique=False
    )
    op.create_index(op.f("ix_report_jobs_status"), "report_jobs", ["status"], unique=False)

    # --- exam_results (finalization/locking root, one per ExamSession — ADR-042) ---
    op.create_table(
        "exam_results",
        sa.Column("exam_session_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_max_marks", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("total_marks", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("finalized_by", sa.Uuid(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.Uuid(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlocked_by", sa.Uuid(), nullable=True),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["exam_session_id"], ["exam_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finalized_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locked_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unlocked_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_exam_results_exam_session_id"), "exam_results", ["exam_session_id"], unique=True
    )
    op.create_index(
        op.f("ix_exam_results_institution_id"), "exam_results", ["institution_id"], unique=False
    )
    op.create_index(op.f("ix_exam_results_status"), "exam_results", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_exam_results_status"), table_name="exam_results")
    op.drop_index(op.f("ix_exam_results_institution_id"), table_name="exam_results")
    op.drop_index(op.f("ix_exam_results_exam_session_id"), table_name="exam_results")
    op.drop_table("exam_results")

    op.drop_index(op.f("ix_report_jobs_status"), table_name="report_jobs")
    op.drop_index(op.f("ix_report_jobs_report_type"), table_name="report_jobs")
    op.drop_index(op.f("ix_report_jobs_institution_id"), table_name="report_jobs")
    op.drop_table("report_jobs")

    op.drop_index(
        op.f("ix_notification_events_recipient_user_id"), table_name="notification_events"
    )
    op.drop_index(op.f("ix_notification_events_is_read"), table_name="notification_events")
    op.drop_index(op.f("ix_notification_events_institution_id"), table_name="notification_events")
    op.drop_index(op.f("ix_notification_events_event_type"), table_name="notification_events")
    op.drop_table("notification_events")
