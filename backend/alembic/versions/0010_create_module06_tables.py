"""Create Official Exam Content Ingestion & AI Evaluation tables (Module 06)

Module 06 — Official Exam Content Ingestion & AI Evaluation. Adds every
table for ingesting Exam-Cell-prepared official documents (Question
Paper/Model Answer/Mark Scheme PDFs) and evaluating student answers
against them: the ingestion root (OfficialExamDocument, exam-scoped not
session-scoped — see ADR-035), its pages (OfficialExamDocumentPage), the
three teacher-verifiable extraction tables (ExtractedQuestion,
ExtractedModelAnswer, MarkSchemeRange — see ADR-035/ADR-037), the AI
provider catalog (AIProvider, the second global system-catalog table
after OCRProvider — see ADR-041 — and AIConfiguration), and the live
evaluation-state table (AnswerEvaluation, distinct from Module 04's
unmodified EvaluationHistory — see ADR-038).

Table bodies were generated from the real ORM metadata via Alembic's
autogenerate diffing engine (`produce_migrations`/`render_python_code`
against an in-memory baseline of the pre-Module-06 tables), then annotated
with section comments to match this project's migration style — see
`docs/database-standards.md`. No data is seeded here — the new
`PermissionCode` rows, their default role grants, and the `AIProvider`
catalog rows are seeded by `0011_seed_module06_permissions.py`, the next
migration (same idempotent-seed pattern as `0009_seed_ocr_pipeline_permissions.py`).

Revision ID: 0010_create_module06_tables
Revises: 0009_seed_ocr_pipeline_permissions
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_create_module06_tables"
down_revision: str | None = "0009_seed_ocr_pipeline_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- ai_providers (global system catalog, no institution_id — ADR-041) ---
    op.create_table(
        "ai_providers",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_implemented", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_providers_code"), "ai_providers", ["code"], unique=True)

    # --- ai_configurations ---
    op.create_table(
        "ai_configurations",
        sa.Column("assessment_id", sa.Uuid(), nullable=True),
        sa.Column("ai_provider_id", sa.Uuid(), nullable=False),
        sa.Column("provider_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_configurations_ai_provider_id"),
        "ai_configurations",
        ["ai_provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_configurations_assessment_id"),
        "ai_configurations",
        ["assessment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_configurations_institution_id"),
        "ai_configurations",
        ["institution_id"],
        unique=False,
    )

    # --- official_exam_documents (root: exam-scoped, not session-scoped — ADR-035) ---
    op.create_table(
        "official_exam_documents",
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_status", sa.String(length=30), nullable=False),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("document_metadata", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_official_exam_documents_checksum_sha256"),
        "official_exam_documents",
        ["checksum_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_documents_document_type"),
        "official_exam_documents",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_documents_exam_id"),
        "official_exam_documents",
        ["exam_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_documents_institution_id"),
        "official_exam_documents",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_documents_ocr_status"),
        "official_exam_documents",
        ["ocr_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_documents_uploaded_by"),
        "official_exam_documents",
        ["uploaded_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_documents_verification_status"),
        "official_exam_documents",
        ["verification_status"],
        unique=False,
    )

    # --- official_exam_document_pages ---
    op.create_table(
        "official_exam_document_pages",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("is_blank", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["document_id"], ["official_exam_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_official_exam_document_pages_document_id"),
        "official_exam_document_pages",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_exam_document_pages_institution_id"),
        "official_exam_document_pages",
        ["institution_id"],
        unique=False,
    )

    # --- extracted_questions ---
    op.create_table(
        "extracted_questions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("linked_question_id", sa.Uuid(), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("question_number", sa.String(length=20), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("detected_marks", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("final_marks", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["official_exam_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_question_id"], ["questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "question_number", name="uq_extracted_question_document_number"
        ),
    )
    op.create_index(
        op.f("ix_extracted_questions_document_id"),
        "extracted_questions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_questions_institution_id"),
        "extracted_questions",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_questions_linked_question_id"),
        "extracted_questions",
        ["linked_question_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_questions_verification_status"),
        "extracted_questions",
        ["verification_status"],
        unique=False,
    )

    # --- extracted_model_answers ---
    op.create_table(
        "extracted_model_answers",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("linked_answer_key_id", sa.Uuid(), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("question_number", sa.String(length=20), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["official_exam_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_answer_key_id"], ["answer_keys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "question_number", name="uq_extracted_model_answer_document_number"
        ),
    )
    op.create_index(
        op.f("ix_extracted_model_answers_document_id"),
        "extracted_model_answers",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_model_answers_institution_id"),
        "extracted_model_answers",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_model_answers_linked_answer_key_id"),
        "extracted_model_answers",
        ["linked_answer_key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_model_answers_verification_status"),
        "extracted_model_answers",
        ["verification_status"],
        unique=False,
    )

    # --- mark_scheme_ranges ---
    op.create_table(
        "mark_scheme_ranges",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("question_range_start", sa.String(length=20), nullable=False),
        sa.Column("question_range_end", sa.String(length=20), nullable=False),
        sa.Column("marks_per_question", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["official_exam_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mark_scheme_ranges_document_id"),
        "mark_scheme_ranges",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mark_scheme_ranges_institution_id"),
        "mark_scheme_ranges",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mark_scheme_ranges_verification_status"),
        "mark_scheme_ranges",
        ["verification_status"],
        unique=False,
    )

    # --- answer_evaluations (current evaluation state — distinct from Module 04's unmodified EvaluationHistory, ADR-038) ---
    op.create_table(
        "answer_evaluations",
        sa.Column("exam_session_id", sa.Uuid(), nullable=False),
        sa.Column("answer_script_id", sa.Uuid(), nullable=False),
        sa.Column("extracted_question_id", sa.Uuid(), nullable=False),
        sa.Column("extracted_model_answer_id", sa.Uuid(), nullable=True),
        sa.Column("ai_provider_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("student_answer_text", sa.Text(), nullable=True),
        sa.Column("semantic_similarity_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("keyword_match_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("concept_match_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("reasoning_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("completeness_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("relevance_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("confidence_tier", sa.String(length=10), nullable=True),
        sa.Column("max_marks", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("suggested_marks", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("final_marks", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["answer_script_id"], ["answer_scripts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["exam_session_id"], ["exam_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extracted_model_answer_id"], ["extracted_model_answers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["extracted_question_id"], ["extracted_questions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exam_session_id", "extracted_question_id", name="uq_answer_evaluation_session_question"
        ),
    )
    op.create_index(
        op.f("ix_answer_evaluations_answer_script_id"),
        "answer_evaluations",
        ["answer_script_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answer_evaluations_exam_session_id"),
        "answer_evaluations",
        ["exam_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answer_evaluations_extracted_model_answer_id"),
        "answer_evaluations",
        ["extracted_model_answer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answer_evaluations_extracted_question_id"),
        "answer_evaluations",
        ["extracted_question_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answer_evaluations_institution_id"),
        "answer_evaluations",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answer_evaluations_review_status"),
        "answer_evaluations",
        ["review_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_answer_evaluations_review_status"), table_name="answer_evaluations")
    op.drop_index(op.f("ix_answer_evaluations_institution_id"), table_name="answer_evaluations")
    op.drop_index(
        op.f("ix_answer_evaluations_extracted_question_id"), table_name="answer_evaluations"
    )
    op.drop_index(
        op.f("ix_answer_evaluations_extracted_model_answer_id"), table_name="answer_evaluations"
    )
    op.drop_index(op.f("ix_answer_evaluations_exam_session_id"), table_name="answer_evaluations")
    op.drop_index(op.f("ix_answer_evaluations_answer_script_id"), table_name="answer_evaluations")
    op.drop_table("answer_evaluations")

    op.drop_index(
        op.f("ix_mark_scheme_ranges_verification_status"), table_name="mark_scheme_ranges"
    )
    op.drop_index(op.f("ix_mark_scheme_ranges_institution_id"), table_name="mark_scheme_ranges")
    op.drop_index(op.f("ix_mark_scheme_ranges_document_id"), table_name="mark_scheme_ranges")
    op.drop_table("mark_scheme_ranges")

    op.drop_index(
        op.f("ix_extracted_model_answers_verification_status"), table_name="extracted_model_answers"
    )
    op.drop_index(
        op.f("ix_extracted_model_answers_linked_answer_key_id"),
        table_name="extracted_model_answers",
    )
    op.drop_index(
        op.f("ix_extracted_model_answers_institution_id"), table_name="extracted_model_answers"
    )
    op.drop_index(
        op.f("ix_extracted_model_answers_document_id"), table_name="extracted_model_answers"
    )
    op.drop_table("extracted_model_answers")

    op.drop_index(
        op.f("ix_extracted_questions_verification_status"), table_name="extracted_questions"
    )
    op.drop_index(
        op.f("ix_extracted_questions_linked_question_id"), table_name="extracted_questions"
    )
    op.drop_index(op.f("ix_extracted_questions_institution_id"), table_name="extracted_questions")
    op.drop_index(op.f("ix_extracted_questions_document_id"), table_name="extracted_questions")
    op.drop_table("extracted_questions")

    op.drop_index(
        op.f("ix_official_exam_document_pages_institution_id"),
        table_name="official_exam_document_pages",
    )
    op.drop_index(
        op.f("ix_official_exam_document_pages_document_id"),
        table_name="official_exam_document_pages",
    )
    op.drop_table("official_exam_document_pages")

    op.drop_index(
        op.f("ix_official_exam_documents_verification_status"), table_name="official_exam_documents"
    )
    op.drop_index(
        op.f("ix_official_exam_documents_uploaded_by"), table_name="official_exam_documents"
    )
    op.drop_index(
        op.f("ix_official_exam_documents_ocr_status"), table_name="official_exam_documents"
    )
    op.drop_index(
        op.f("ix_official_exam_documents_institution_id"), table_name="official_exam_documents"
    )
    op.drop_index(op.f("ix_official_exam_documents_exam_id"), table_name="official_exam_documents")
    op.drop_index(
        op.f("ix_official_exam_documents_document_type"), table_name="official_exam_documents"
    )
    op.drop_index(
        op.f("ix_official_exam_documents_checksum_sha256"), table_name="official_exam_documents"
    )
    op.drop_table("official_exam_documents")

    op.drop_index(op.f("ix_ai_configurations_institution_id"), table_name="ai_configurations")
    op.drop_index(op.f("ix_ai_configurations_assessment_id"), table_name="ai_configurations")
    op.drop_index(op.f("ix_ai_configurations_ai_provider_id"), table_name="ai_configurations")
    op.drop_table("ai_configurations")

    op.drop_index(op.f("ix_ai_providers_code"), table_name="ai_providers")
    op.drop_table("ai_providers")
