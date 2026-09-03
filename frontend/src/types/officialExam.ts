/**
 * Types mirroring the backend's Official Exam Content Ingestion & AI
 * Evaluation (Module 06) Pydantic schemas (`backend/app/schemas/*.py`)
 * field-for-field, including snake_case casing — same convention as
 * `types/ocr.ts` (see its file-level comment). `Decimal`/`Numeric`
 * backend fields are `string` on the Read shape and `number` on
 * Create/Update payloads.
 */

/* ---------------------------------------------------------------------------
 * Official Exam Document (root) / Pages
 * ------------------------------------------------------------------------ */

export type OfficialExamDocumentType = "question_paper" | "model_answer" | "mark_scheme";

export type OfficialExamDocumentOCRStatus =
  | "uploading"
  | "uploaded"
  | "storing"
  | "stored"
  | "preprocessing"
  | "ocr_running"
  | "ocr_complete"
  | "completed"
  | "failed"
  | "cancelled";

export type OfficialExamDocumentVerificationStatus = "not_started" | "in_progress" | "verified";

export interface OfficialExamDocument {
  id: string;
  institution_id: string;
  exam_id: string;
  uploaded_by: string;
  document_type: OfficialExamDocumentType;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  checksum_sha256: string | null;
  storage_key: string | null;
  page_count: number | null;
  raw_ocr_text: string | null;
  ocr_status: OfficialExamDocumentOCRStatus;
  verification_status: OfficialExamDocumentVerificationStatus;
  failure_reason: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** `is_active` is the only client-patchable field — content/status fields are pipeline-managed. */
export interface OfficialExamDocumentUpdate {
  is_active?: boolean;
}

export interface OfficialExamDocumentPage {
  id: string;
  institution_id: string;
  document_id: string;
  page_number: number;
  storage_key: string | null;
  width_px: number | null;
  height_px: number | null;
  is_blank: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

/* ---------------------------------------------------------------------------
 * Teacher-verifiable extraction (Stage: Teacher Verification)
 * ------------------------------------------------------------------------ */

export type VerificationStatus = "pending" | "verified" | "edited" | "rejected";

export interface ExtractedQuestion {
  id: string;
  institution_id: string;
  document_id: string;
  linked_question_id: string | null;
  question_number: string;
  question_text: string;
  raw_ocr_text: string | null;
  detected_marks: string | null;
  final_marks: string | null;
  page_number: number | null;
  display_order: number;
  verification_status: VerificationStatus;
  verified_by: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Only these three are teacher-editable — everything else is system/pipeline-managed. */
export interface ExtractedQuestionUpdate {
  question_text?: string;
  final_marks?: number | null;
  linked_question_id?: string | null;
}

export interface ExtractedModelAnswer {
  id: string;
  institution_id: string;
  document_id: string;
  linked_answer_key_id: string | null;
  question_number: string;
  answer_text: string;
  raw_ocr_text: string | null;
  page_number: number | null;
  display_order: number;
  verification_status: VerificationStatus;
  verified_by: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractedModelAnswerUpdate {
  answer_text?: string;
  linked_answer_key_id?: string | null;
}

export interface MarkSchemeRange {
  id: string;
  institution_id: string;
  document_id: string;
  question_range_start: string;
  question_range_end: string;
  marks_per_question: string;
  display_order: number;
  verification_status: VerificationStatus;
  verified_by: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarkSchemeRangeUpdate {
  question_range_start?: string;
  question_range_end?: string;
  marks_per_question?: number;
  display_order?: number;
}

/** Response shape of `GET /mark-scheme-ranges/expand?document_id=` — the
 * data-driven range -> per-question maximum-marks expansion (never a
 * hardcoded range in application code). */
export interface MarkSchemeExpansionResponse {
  marks_by_question: Record<string, string>;
  warnings: string[];
}

/* ---------------------------------------------------------------------------
 * AI Provider / Configuration
 * ------------------------------------------------------------------------ */

export interface AIProvider {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  is_implemented: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

/** `code`/`name`/`is_implemented` are immutable after seeding — only these two are patchable. */
export interface AIProviderUpdate {
  is_enabled?: boolean;
  is_default?: boolean;
}

export interface AIConfiguration {
  id: string;
  institution_id: string;
  assessment_id: string | null;
  ai_provider_id: string;
  provider_config: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIConfigurationCreate {
  assessment_id?: string | null;
  ai_provider_id: string;
  provider_config?: Record<string, unknown> | null;
  is_active?: boolean;
}

/** Deliberately excludes `ai_provider_id` — fixed at creation, same convention as `OCRConfigurationUpdate`. */
export interface AIConfigurationUpdate {
  assessment_id?: string | null;
  provider_config?: Record<string, unknown> | null;
  is_active?: boolean;
}

/* ---------------------------------------------------------------------------
 * Answer Evaluation (AI evaluation + Teacher Review, ADR-039/ADR-040)
 * ------------------------------------------------------------------------ */

export type ConfidenceTier = "high" | "medium" | "low";

export type AnswerEvaluationReviewStatus =
  | "pending"
  | "auto_suggested"
  | "pending_confirmation"
  | "pending_review"
  | "teacher_confirmed"
  | "teacher_overridden"
  | "teacher_rejected";

export interface AnswerEvaluation {
  id: string;
  institution_id: string;
  exam_session_id: string;
  answer_script_id: string;
  extracted_question_id: string;
  extracted_model_answer_id: string | null;
  ai_provider_id: string;
  student_answer_text: string | null;
  semantic_similarity_score: string | null;
  keyword_match_score: string | null;
  concept_match_score: string | null;
  reasoning_score: string | null;
  completeness_score: string | null;
  relevance_score: string | null;
  confidence_score: string | null;
  confidence_tier: ConfidenceTier | null;
  max_marks: string;
  suggested_marks: string | null;
  final_marks: string | null;
  review_status: AnswerEvaluationReviewStatus;
  evaluated_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** Request body for `POST /answer-evaluations` — triggers evaluation for
 * one (student answer x extracted question) pair. Every other field on
 * `AnswerEvaluation` is AI-computed, never client-supplied. */
export interface AnswerEvaluationTrigger {
  exam_session_id: string;
  extracted_question_id: string;
}

export interface AnswerEvaluationOverride {
  final_marks: number;
  notes?: string | null;
}

/** Request body for `POST /{id}/reject` (Module 07, ADR-043) — `reason`
 * is required. */
export interface AnswerEvaluationReject {
  reason: string;
}
